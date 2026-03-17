import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import MAIN_BOT_TOKEN, USE_WEBHOOK
from database import init_db, get_all_bots, get_all_bots_count
from bot_manager import bot_manager
from handlers.main_handlers import router as main_router
import uvicorn

async def startup_check():
    # Load all bots that were running before the server restarted
    bots = await get_all_bots()
    count = await get_all_bots_count()
    logging.info(f"Loaded {count} bots from database.")
    for bot in bots:
        db_id, token, bot_id, bot_username, status, user_id, created_at = bot
        if status == 'Running':
            logging.info(f"Auto-starting bot {db_id} - @{bot_username}")
            await bot_manager.start_bot(db_id, token)

async def polling_main():
    logging.info("Starting in POLLING mode...")
    
    # Startup check to restart 'Running' bots
    await startup_check()

    # Configure and start Main Bot manager
    main_bot = Bot(token=MAIN_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(main_router)
    
    await main_bot.delete_webhook(drop_pending_updates=True)
    logging.info("Main Bot Manager is listening via POLLING.")
    try:
        await dp.start_polling(main_bot)
    finally:
        await main_bot.session.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    if not MAIN_BOT_TOKEN:
        logging.error("MAIN_BOT_TOKEN is not provided. Program will now exit.")
        exit(1)

    # Initialize DB (which connects to Supabase synchronously, though wrapper is async)
    asyncio.run(init_db())
    
    if USE_WEBHOOK:
        logging.info("Starting in WEBHOOK mode via Uvicorn...")
        # startup_check will be handled within main_app if needed, or bots will wake on webhook hit in Vercel.
        uvicorn.run("main_app:app", host="0.0.0.0", port=8000, reload=True)
    else:
        try:
            asyncio.run(polling_main())
        except (KeyboardInterrupt, SystemExit):
            logging.info("Systems shut down gracefully.")
