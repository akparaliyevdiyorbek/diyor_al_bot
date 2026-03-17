import os
from dotenv import load_dotenv

load_dotenv()

MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # e.g. https://your-vercel-app.vercel.app
USE_WEBHOOK = bool(WEBHOOK_URL)

if not MAIN_BOT_TOKEN:
    print("Warning: MAIN_BOT_TOKEN is not set in environment or .env file.")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: SUPABASE credentials are not set in environment or .env file.")
