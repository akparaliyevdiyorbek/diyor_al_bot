# 🚀 Telegram Multi-Bot Manager (Serverless Ready)

A powerful, multi-threaded telegram bot management system. It allows a single owner to host, manage, and fetch statistics from unlimited "Collector Bots" dynamically.

## 🌟 Key Features
- **Dynamic Bot Management:** Add or shut down collector bots seamlessly from the Main Bot.
- **Supabase Integration:** 100% Cloud-based database (PostgreSQL via Supabase). No risk of losing data on server restarts!
- **Serverless Ready:** Supports FastAPI Webhook mode natively (configured exactly for `Vercel` / `Heroku`).
- **Owner Super Panel:** Features a beautifully formatted HTML panel for the Admin (`/owner`) to view tokens, status, and stats of all sub-bots.
- **Robust Security:** Aiogram 3's modern dispatcher features and graceful session closures ensure Telegram doesn't block you.

## ⚙️ Setup Instructions

### 1. Requirements
- Python 3.10+
- A Supabase Project (Database)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### 2. Installation
Clone the repo and install dependencies:
```bash
git clone https://github.com/hayolnoma/get_json_bot.git
cd get_json_bot
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory and add the following:
```env
MAIN_BOT_TOKEN="your_main_bot_token"
SUPABASE_URL="your_supabase_url"
SUPABASE_KEY="your_supabase_service_role_key"
OWNER_ID=1234567890
# WEBHOOK_URL="https://your-vercel-app.vercel.app" # Only add this line if you are deploying to Vercel/Webhook!
```

> **Note:** Do NOT share your `SUPABASE_KEY` or `MAIN_BOT_TOKEN` with anyone. That's why `.env` is strongly hidden by `.gitignore`.

### 4. Running Locally (Polling Mode)
To run the bot on your own computer or VPS without webhooks:
```bash
python run.py
```

### 5. Deploying to Vercel (Webhook Mode)
1. Fork or push this repository to your GitHub account.
2. Go to [Vercel](https://vercel.com/) -> Add New Project -> Import from GitHub.
3. Once imported, go to **Environment Variables** in Vercel settings and add all your `.env` keys.
4. After deployment, Vercel will give you a domain (e.g., `https://my-bot-app.vercel.app`).
5. Copy that domain, add a new environment variable `WEBHOOK_URL` in Vercel with that domain link.
6. Trigger a re-deploy on Vercel. Done! Your Bot Manager is now fully Serverless!

## 📦 Database Tables (Supabase)
Ensure your Supabase project contains the following tables:
- `users`: Tracks who used the bot `(user_id)`.
- `bots`: Tracks dynamic sub-bots `(id, user_id, bot_token, bot_id, bot_username, status, created_at)`.
- `files`: Tracks files received by the collector bots `(id, file_id, file_unique_id, bot_db_id, type, size, ...)`.

---
*Created by the amazing power of Python and Aiogram 3!* 💎
# get_json_bot
