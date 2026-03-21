import os
import time
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
import google.generativeai as genai

# .env faylidan o'zgaruvchilarni yuklash (lokal muhit uchun)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(F.text)
async def chat_with_ai(message: types.Message):
    user = message.from_user
    logging.info(f"👤 Kim ishlatyapti: {user.full_name} (@{user.username}) | ID: {user.id} | Xabar: {message.text}")
    
    sent_message = await message.reply("⏳ <i>O'ylayapman...</i>", parse_mode="HTML")
    try:
        response = await model.generate_content_async(message.text, stream=True)
        full_text = ""
        last_edit_time = time.time()

        async for chunk in response:
            full_text += chunk.text
            if time.time() - last_edit_time > 1.5:
                if full_text.strip():
                    try:
                        await sent_message.edit_text(full_text + " ✍️", parse_mode="Markdown")
                        last_edit_time = time.time()
                    except TelegramBadRequest:
                        pass

        if full_text.strip():
            try:
                await sent_message.edit_text(full_text, parse_mode="Markdown")
            except TelegramBadRequest:
                pass
        else:
            await sent_message.edit_text("Kechirasiz, men javob topolmadim.", parse_mode="HTML")
            
    except Exception as e:
        await sent_message.edit_text("⚠️ Xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")

# Render portini so'kishiga javob (Health check) server
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly 24/7!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server is running on port {port}")

async def main():
    # Bir vaqtning o'zida ham botni, ham web serverni ishga tushirish (Render uchun)
    asyncio.create_task(web_server())
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")
