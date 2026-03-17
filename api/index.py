import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update
import sys
import os

# Add parent directory to path to allow importing modules correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import WEBHOOK_URL, MAIN_BOT_TOKEN
from bot_manager import bot_manager
from handlers.main_handlers import router as main_router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# Initialize Main Bot
main_bot = Bot(token=MAIN_BOT_TOKEN)
main_dp = Dispatcher()
main_dp.include_router(main_router)

@app.on_event("startup")
async def on_startup():
    logging.info(f"Starting webhook server. Webhook URL: {WEBHOOK_URL}")
    if WEBHOOK_URL:
        # Set webhook for main bot
        await main_bot.set_webhook(f"{WEBHOOK_URL}/api/webhook/main")
        logging.info("Main bot webhook set.")

@app.on_event("shutdown")
async def on_shutdown():
    logging.info("Shutting down webhook server.")
    if WEBHOOK_URL:
        await main_bot.delete_webhook()
    await main_bot.session.close()
    
    # Close all running bots
    for db_id in list(bot_manager.running_bots.keys()):
        await bot_manager.stop_bot(db_id)

@app.post("/api/webhook/main")
async def main_bot_webhook(request: Request):
    try:
        update_dict = await request.json()
        update = Update(**update_dict)
        await main_dp.feed_update(main_bot, update)
    except Exception as e:
        logging.error(f"Error processing main bot webhook: {e}")
    return {"ok": True}

@app.post("/api/webhook/bot/{db_id}")
async def collector_bot_webhook(db_id: int, request: Request):
    bot_data = await bot_manager.get_or_create_bot(db_id)
    if not bot_data:
        logging.warning(f"Webhook received for unknown or stopped bot (db_id: {db_id})")
        return {"error": "Bot is not running or unconfigured"}
    
    try:
        target_bot = bot_data["bot"]
        target_dp = bot_data["dp"]
        
        update_dict = await request.json()
        update = Update(**update_dict)
        await target_dp.feed_update(target_bot, update)
    except Exception as e:
        logging.error(f"Error processing collector bot webhook for {db_id}: {e}")
        
    return {"ok": True}

@app.get("/")
async def root_view():
    return {"status": "ok", "service": "Telegram Multi-Bot Manager is running!"}
