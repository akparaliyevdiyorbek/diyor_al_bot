import os
import json
import shutil

RESULTS_DIR = 'results'

if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

def get_bot_json_path(db_id: int) -> str:
    return os.path.join(RESULTS_DIR, f'bot_{db_id}_result.json')

def get_bot_backup_path(db_id: int) -> str:
    return os.path.join(RESULTS_DIR, f'bot_{db_id}_result_backup.json')

def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"files": []}
    return {"files": []}

def save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_file_to_json(db_id: int, file_data: dict) -> bool:
    """Adds a file to the JSON if it doesn't exist. Returns True if added, False if duplicate."""
    path = get_bot_json_path(db_id)
    data = load_json(path)
    
    file_unique_id = file_data.get("file_unique_id")
    
    # Check duplicate
    for f in data.get("files", []):
        if f.get("file_unique_id") == file_unique_id:
            return False
            
    # Add payload
    data["files"].append(file_data)
    
    save_json(path, data)
    
    # Backup after every 50 files
    if len(data["files"]) > 0 and len(data["files"]) % 50 == 0:
        backup_path = get_bot_backup_path(db_id)
        shutil.copy2(path, backup_path)
        
    return True

def reset_bot_json(db_id: int):
    path = get_bot_json_path(db_id)
    save_json(path, {"files": []})

def get_bot_stats(db_id: int) -> dict:
    path = get_bot_json_path(db_id)
    data = load_json(path)
    files = data.get("files", [])
    
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
