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
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from gtts import gTTS
import google.generativeai as genai

# .env faylidan o'zgaruvchilarni yuklash (lokal muhit uchun)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or ""
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""
ADMIN_ID = os.getenv("ADMIN_ID")

genai.configure(api_key=GEMINI_API_KEY)  # type: ignore
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction="Sen foydali yordamchisan. Barcha savollarga aniq va faqat O'zbek tilida javob ber."
)  # type: ignore

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

class BotStates(StatesGroup):
    waiting_for_audio_text = State()

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🧠 AI Repetitor"))
    builder.add(KeyboardButton(text="🕒 Namoz vaqtlari"))
    builder.add(KeyboardButton(text="📝 Text-to-Audio"))
    builder.add(KeyboardButton(text="📈 Valyuta kursi"))
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

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

async def notify_admin(user: types.User):
    if not ADMIN_ID or not ADMIN_ID.isdigit():
        return
    try:
        uname = f"@{user.username}" if user.username else "yo'q"
        text = f"🔔 <b>YANGI ODAM QO'SHILDI!</b>\n\n👤 <b>Ism:</b> {user.full_name}\n🔗 <b>User:</b> {uname}\n🆔 <b>ID:</b> <code>{user.id}</code>\n🕰 <b>Vaqt:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"
        await bot.send_message(chat_id=int(ADMIN_ID), text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xatolik: {e}")

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

@dp.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    if not user:
        return
        
    is_new = save_user(user.id, user.full_name, user.username)
    if is_new:
        logging.info(f"✨ YANGI: {user.full_name}")
        await notify_admin(user)
    await message.reply(f"Assalomu alaykum, {user.first_name}! \nO'zingizga kerakli bo'limni tanlang 👇", reply_markup=get_main_menu())

@dp.message(F.text == "🧠 AI Repetitor")
async def ai_repetitor_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("🧠 <b>AI Repetitor</b> rejimi faol!\n\nMenga istalgan savolingizni bering (Masalan: 'Nyuton qonunlarini tushuntirib ber'), men sizga qisqa va aniq tushuntirib beraman!", parse_mode="HTML")

@dp.message(F.text == "🕒 Namoz vaqtlari")
async def namoz_times(message: types.Message, state: FSMContext):
    await state.clear()
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("https://islomapi.uz/api/present/day?region=Toshkent") as resp:
            if resp.status == 200:
                data = await resp.json()
                times = data.get("times", {})
                text = (f"🕌 <b>Toshkent shahri uchun namoz vaqtlari:</b>\n\n"
                        f"📅 Sana: {data.get('date')}\n"
                        f"🌅 Bomdod: {times.get('tong_saharlik')}\n"
                        f"☀️ Quyosh: {times.get('quyosh')}\n"
                        f"🌞 Peshin: {times.get('peshin')}\n"
                        f"🌤 Asr: {times.get('asr')}\n"
                        f"🌇 Shom: {times.get('shom_iftor')}\n"
                        f"🌃 Xufton: {times.get('hufton')}\n")
                await message.reply(text, parse_mode="HTML")
            else:
                await message.reply("Kechirasiz, namoz vaqtlarini olishda xatolik yuz berdi.")

@dp.message(F.text == "📈 Valyuta kursi")
async def valyuta_rates(message: types.Message, state: FSMContext):
    await state.clear()
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("https://cbu.uz/uz/arkhiv-kursov-valyut/json/") as resp:
            if resp.status == 200:
                data = await resp.json()
                text = "📈 <b>Markaziy Bank kunlik kurslari:</b>\n\n"
                for item in data:
                    if item["Ccy"] == "USD":
                        text += f"🇺🇸 1 {item['Ccy']} = {item['Rate']} UZS\n"
                    elif item["Ccy"] == "EUR":
                        text += f"🇪🇺 1 {item['Ccy']} = {item['Rate']} UZS\n"
                    elif item["Ccy"] == "RUB":
                        text += f"🇷🇺 1 {item['Ccy']} = {item['Rate']} UZS\n"
                text += f"\n📅 Sana: {data[0].get('Date', 'Nomalum')}"
                await message.reply(text, parse_mode="HTML")
            else:
                await message.reply("Xatolik! Valyuta kurslarini olib bo'lmadi.")

@dp.message(F.text == "📝 Text-to-Audio")
async def start_audio(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_audio_text)
    await message.reply("🎤 <b>Matnni yuboring!</b>\nIltimos, audioga aylantirmoqchi bo'lgan ma'lumotni yozib yuboring (O'qishga vaqtingiz yo'q matnlar bo'lsa ajoyib!):", parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())

@dp.message(BotStates.waiting_for_audio_text)
async def process_audio(message: types.Message, state: FSMContext):
    text = message.text
    user = message.from_user
    if not text or not user:
        return
    sent_message = await message.reply("⏳ <i>Ovoz yozilmoqda... Iltimos kuting</i>", parse_mode="HTML")
    file_name = f"audio_{user.id}_{int(time.time())}.mp3"
    try:
        def generate_audio():
            tts = gTTS(text=text, lang="uz")
            tts.save(file_name)
        
        await asyncio.to_thread(generate_audio)
        voice = FSInputFile(file_name)
        await message.reply_voice(voice=voice)
        os.remove(file_name)
        await state.clear()
        try:
            await sent_message.delete()
        except TelegramBadRequest:
            pass
        await message.answer("✅ Tayyor! Bosh menyuga qaytdik.", reply_markup=get_main_menu())
    except Exception as e:
        logging.error(f"TTS Error: {e}")
        await sent_message.edit_text("Ovoz yaratishda xatolik yuz berdi. Matnni qisqaroq yoki maxsus belgilarsiz yuborib ko'ring.")
        await state.clear()
        await message.answer("Bosh menyu", reply_markup=get_main_menu())

@dp.message(F.text)
async def chat_with_ai(message: types.Message, state: FSMContext):
    user = message.from_user
    if user is None or message.text is None:
        return
    
    # Yangi foydalanuvchilarni saqlash
    is_new = save_user(user.id, user.full_name, user.username)
    if is_new:
        logging.info(f"✨ YANGI FOYDALANUVCHI: {user.full_name} (@{user.username}) | ID: {user.id}")
        await notify_admin(user)
        
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
