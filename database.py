import os
import logging
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logging.error(f"Failed to initialize Supabase client: {e}")

async def init_db():
    if not supabase:
        logging.warning("Supabase client not configured. Database will not work properly.")
        return
        
    logging.info("Connected to Supabase. Assuming tables 'users' and 'bots' exist.")
    # In Supabase, table creation is usually done via the dashboard or migrations.
    # We will assume:
    # `users` table:
    #   - user_id (int8, primary key)
    #
    # `bots` table:
    #   - id (int8, primary key, identity)
    #   - user_id (int8, foreign key to users.user_id)
    #   - bot_token (text, unique)
    #   - bot_id (int8)
    #   - bot_username (text)
    #   - status (text)
    
async def add_user(user_id: int):
    if not supabase: return
    try:
        # Supabase Python client is synchronous for standard operations, so we run them directly.
        # Check if user exists first to avoid unnecessary errors
        response = supabase.table('users').select('user_id').eq('user_id', user_id).execute()
        if not response.data:
            supabase.table('users').insert({"user_id": user_id}).execute()
    except Exception as e:
        # Ignore unique constraint violations (if they happen concurrently)
        logging.error(f"Error adding user {user_id}: {e}")

async def get_user_bots_count(user_id: int) -> int:
    if not supabase: return 0
    try:
        response = supabase.table('bots').select('*', count='exact').eq('user_id', user_id).execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logging.error(f"Error getting bots count for user {user_id}: {e}")
        return 0

async def add_bot(user_id: int, bot_token: str, bot_id: int, bot_username: str) -> bool:
    if not supabase: return False
    try:
        data = {
            "user_id": user_id,
            "bot_token": bot_token,
            "bot_id": bot_id,
            "bot_username": bot_username,
            "status": "Running"
        }
        supabase.table('bots').insert(data).execute()
        return True
    except Exception as e:
        # Likely a unique constraint violation on bot_token
        logging.error(f"Error adding bot: {e}")
        return False

async def get_user_bots(user_id: int):
    # Returns list of tuples: (id, bot_token, bot_id, bot_username, status)
    if not supabase: return []
    try:
        response = supabase.table('bots').select('*').eq('user_id', user_id).execute()
        return [(
            item.get('id'),
            item.get('bot_token'),
            item.get('bot_id'),
            item.get('bot_username'),
            item.get('status')
        ) for item in response.data]
    except Exception as e:
        logging.error(f"Error fetching bots for user {user_id}: {e}")
        return []

async def get_bot_by_id(db_id: int, user_id: int = None):
    # Returns tuple: (id, bot_token, bot_id, bot_username, status, user_id)
    if not supabase: return None
    try:
        query = supabase.table('bots').select('*').eq('id', db_id)
        if user_id:
            query = query.eq('user_id', user_id)
            
        response = query.execute()
        
        if response.data and len(response.data) > 0:
            item = response.data[0]
            return (
                item.get('id'),
                item.get('bot_token'),
                item.get('bot_id'),
                item.get('bot_username'),
                item.get('status'),
                item.get('user_id'),
                item.get('created_at', 'Unknown')
            )
        return None
    except Exception as e:
        logging.error(f"Error fetching bot by id {db_id}: {e}")
        return None

async def update_bot_status(db_id: int, status: str):
    if not supabase: return
    try:
        supabase.table('bots').update({'status': status}).eq('id', db_id).execute()
    except Exception as e:
        logging.error(f"Error updating bot status {db_id}: {e}")

async def get_all_bots():
    # Returns list of tuples: (id, bot_token, bot_id, bot_username, status, user_id)
    if not supabase: return []
    try:
        response = supabase.table('bots').select('*').execute()
        return [(
            item.get('id'),
            item.get('bot_token'),
            item.get('bot_id'),
            item.get('bot_username'),
            item.get('status'),
            item.get('user_id'),
            item.get('created_at', 'Unknown')
        ) for item in response.data]
    except Exception as e:
        logging.error(f"Error getting all bots: {e}")
        return []

async def get_all_users_count() -> int:
    if not supabase: return 0
    try:
        response = supabase.table('users').select('*', count='exact').execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logging.error(f"Error counting users: {e}")
        return 0

async def get_all_bots_count() -> int:
    if not supabase: return 0
    try:
        response = supabase.table('bots').select('*', count='exact').execute()
        return response.count if response.count is not None else 0
    except Exception as e:
        logging.error(f"Error counting bots: {e}")
        return 0

async def add_file(db_id: int, file_data: dict) -> bool:
    if not supabase: return False
    try:
        # Prevent unique constraint errors by first checking if it exists
        response = supabase.table('files').select('file_unique_id').eq('file_unique_id', file_data.get('file_unique_id')).execute()
        if len(response.data) > 0:
            return False # Duplicate
            
        # Write to files table
        data_to_insert = file_data.copy()
        data_to_insert['bot_db_id'] = db_id
        
        supabase.table('files').insert(data_to_insert).execute()
        return True
    except Exception as e:
        logging.error(f"Error saving file to supabase: {e}")
        return False

async def get_bot_files_stats(db_id: int) -> dict:
    if not supabase: return {"total": 0, "video": 0, "photo": 0, "document": 0, "audio": 0, "voice": 0, "animation": 0}
    try:
        response = supabase.table('files').select('type').eq('bot_db_id', db_id).execute()
        files = response.data
        
        stats = {
            "total": len(files),
            "video": sum(1 for f in files if f.get("type") == "video"),
            "photo": sum(1 for f in files if f.get("type") == "photo"),
            "document": sum(1 for f in files if f.get("type") == "document"),
            "audio": sum(1 for f in files if f.get("type") == "audio"),
            "voice": sum(1 for f in files if f.get("type") == "voice"),
            "animation": sum(1 for f in files if f.get("type") == "animation"),
        }
        return stats
    except Exception as e:
        logging.error(f"Error fetching stats for bot {db_id}: {e}")
        return {"total": 0, "video": 0, "photo": 0, "document": 0, "audio": 0, "voice": 0, "animation": 0}

async def get_all_bot_files(db_id: int) -> list:
    if not supabase: return []
    try:
        response = supabase.table('files').select('*').eq('bot_db_id', db_id).execute()
        return response.data
    except Exception as e:
        logging.error(f"Error fetching all files for bot {db_id}: {e}")
        return []

async def clear_bot_files(db_id: int):
    if not supabase: return
    try:
        supabase.table('files').delete().eq('bot_db_id', db_id).execute()
    except Exception as e:
        logging.error(f"Error clearing files for bot {db_id}: {e}")
