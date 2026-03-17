import asyncio
import logging
from aiogram import Bot, Dispatcher
from database import update_bot_status, get_bot_by_id
from handlers.collector_handlers import setup_collector_handlers
from config import USE_WEBHOOK, WEBHOOK_URL

class BotManager:
    def __init__(self):
        self.running_bots = {}  # db_id -> {"bot": Bot, "task": asyncio.Task, "dp": Dispatcher}

    async def get_or_create_bot(self, db_id: int):
        '''Called by Webhook handler to get instances in a serverless environment'''
        if db_id in self.running_bots:
            return self.running_bots[db_id]
            
        bot_info = await get_bot_by_id(db_id)
        if not bot_info: return None
        
        _, token, _, _, status, _, _ = bot_info
        if status != "Running": return None
        
        bot = Bot(token=token)
        dp = Dispatcher()
        setup_collector_handlers(dp, db_id)
        
        self.running_bots[db_id] = {
            "bot": bot,
            "dp": dp,
            "task": None
        }
        return self.running_bots[db_id]

    async def start_bot(self, db_id: int, token: str):
        if db_id in self.running_bots:
            logging.warning(f"Bot {db_id} is already running.")
            if not USE_WEBHOOK:
                return True

        try:
            bot = Bot(token=token)
            # Check if bot token is valid
            await bot.get_me()
            
            dp = Dispatcher()
            setup_collector_handlers(dp, db_id)

            if USE_WEBHOOK:
                webhook_url = f"{WEBHOOK_URL}/api/webhook/bot/{db_id}"
                await bot.set_webhook(webhook_url)
                task = None
                logging.info(f"Bot {db_id} webhook set to {webhook_url}")
            else:
                await bot.delete_webhook(drop_pending_updates=True)
                task = asyncio.create_task(dp.start_polling(bot))
                logging.info(f"Bot {db_id} polling started.")

            self.running_bots[db_id] = {
                "bot": bot,
                "dp": dp,
                "task": task
            }
            
            await update_bot_status(db_id, "Running")
            logging.info(f"Bot {db_id} started successfully.")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start bot {db_id}: {e}")
            await update_bot_status(db_id, "Stopped")
            return False

    async def stop_bot(self, db_id: int):
        bot_data = self.running_bots.pop(db_id, None)
        
        if USE_WEBHOOK:
            if not bot_data:
                bot_info = await get_bot_by_id(db_id)
                if bot_info:
                    bot_data = {"bot": Bot(token=bot_info[1]), "task": None, "dp": None}
            
            if bot_data and "bot" in bot_data:
                try:
                    await bot_data["bot"].delete_webhook()
                except Exception as e:
                    logging.error(f"Failed to delete webhook for bot {db_id}: {e}")
        else:
            if bot_data and bot_data.get("task"):
                try:
                    await bot_data["dp"].stop_polling()
                    try:
                        await asyncio.wait_for(bot_data["task"], timeout=3.0)
                    except asyncio.TimeoutError:
                        logging.warning(f"Timeout waiting for bot {db_id} to stop polling.")
                        bot_data["task"].cancel()
                except Exception as e:
                    logging.error(f"Error stopping polling for bot {db_id}: {e}")
                    
        # Always close session
        if bot_data and "bot" in bot_data:
            try:
                await bot_data["bot"].session.close()
            except Exception as e:
                logging.error(f"Error closing bot session: {e}")
                
        # Always mark as stopped in the database
        await update_bot_status(db_id, "Stopped")
        logging.info(f"Bot {db_id} stopped.")

bot_manager = BotManager()
