import os
import time
import asyncio
import logging
from aiohttp import web
from dotenv import load_dotenv
import json
from typing import Dict, Any

from aiogram import Bot, Dispatcher, types, F # type: ignore
from aiogram.exceptions import TelegramBadRequest
import google.generativeai as genai

# .env faylidan o'zgaruvchilarni yuklash (lokal muhit uchun)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or ""
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""

genai.configure(api_key=GEMINI_API_KEY)  # type: ignore
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction="Sen foydali yordamchisan. Barcha savollarga aniq va faqat O'zbek tilida javob ber."
)  # type: ignore

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

USERS_FILE = "user.json"

def get_all_users() -> Dict[str, Any]:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}

def save_user(user_id, full_name, username):
    users = get_all_users()
    str_id = str(user_id)
    if str_id not in users:
        users[str_id] = {
            "name": full_name,
            "username": username,
            "joined": time.time()
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
        return True
    return False

@dp.message(F.text == "/stat")
async def bot_stats(message: types.Message):
    users = get_all_users()
    count = len(users)
    text = f"📊 <b>Bot Statistikasi</b>\n\nJami foydalanuvchilar: <b>{count} ta</b>\n"
    
    if count > 0:
        text += "\nOxirgi qo'shilganlar:\n"
        sorted_users = sorted(users.items(), key=lambda x: x[1].get('joined', 0), reverse=True)
        count_display = 0
        for uid, udata in sorted_users:
            if count_display >= 10:
                break
            count_display += 1
            uname = udata.get('username')
            uname_text = f"(@{uname})" if uname else ""
            text += f"👤 {udata.get('name')} {uname_text} - ID: <code>{uid}</code>\n"
            
    await message.reply(text, parse_mode="HTML")
    return

@dp.message(F.text)
async def chat_with_ai(message: types.Message):
    user = message.from_user
    if user is None or message.text is None:
        return
    
    # Yangi foydalanuvchilarni saqlash
    is_new = save_user(user.id, user.full_name, user.username)
    if is_new:
        logging.info(f"✨ YANGI FOYDALANUVCHI: {user.full_name} (@{user.username}) | ID: {user.id}")
        
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
        logging.error(f"❌ Gemini ishlamadi: {e}. GROQ fallbackga o'tilmoqda...")
        try:
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                raise ValueError("GROQ_API_KEY topilmadi.")
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": "Sen aqlli, yordamchi sun'iy intellektsan. Barcha savollarga aniq va faqat O'zbek tilida javob ber."},
                        {"role": "user", "content": message.text}
                    ]
                }
                async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        groq_text = data["choices"][0]["message"]["content"]
                        
                        if groq_text.strip():
                            try:
                                await sent_message.edit_text(groq_text, parse_mode="Markdown")
                            except TelegramBadRequest:
                                await sent_message.edit_text(groq_text)
                        else:
                            await sent_message.edit_text("Kechirasiz, men javob topolmadim.", parse_mode="HTML")
                    else:
                        logging.error(f"❌ Groq xatosi: {await resp.text()}")
                        await sent_message.edit_text("⚠️ Barcha sun'iy intellekt tarmoqlarida limit tugadi. Keyinroq urinib ko'ring.")
        except Exception as groq_e:
            logging.error(f"❌ Groq ham ishlamadi: {groq_e}")
            await sent_message.edit_text("⚠️ Xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")

# Render portini so'kishiga javob (Health check) server
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly 24/7!")

async def web_server():
    try:
        app = web.Application()
        app.router.add_get('/', handle_ping)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", "8080"))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logging.info(f"🌐 Web server {port} portida ishga tushdi")
    except Exception as e:
        logging.error(f"❌ Web serverni ishga tushirishda xatolik (masalan, port allaqachon band): {e}")

async def main():
    try:
        # Bir vaqtning o'zida ham botni, ham web serverni ishga tushirish (Render uchun)
        asyncio.create_task(web_server())
        logging.info("🚀 Bot ishga tushishni boshladi (start_polling)...")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Bot ishlashida jiddiy xatolik yuz berdi: {e}")

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.warning("🛑 Bot foydalanuvchi orqali to'xtatildi (KeyboardInterrupt)")
