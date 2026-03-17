from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

from database import (
    add_user, get_user_bots_count, add_bot, get_user_bots,
    get_bot_by_id, update_bot_status, get_all_users_count,
    get_all_bots_count, get_all_bots, get_all_bot_files
)
from utils import get_bot_json_path, get_bot_stats
from bot_manager import bot_manager
from config import OWNER_ID

router = Router()

class AddBotState(StatesGroup):
    waiting_for_token = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id)
    text = (
        "👑 <b>BOSHQARUV PANELIGA XUSH KELIBSIZ!</b>\n\n"
        "Men orqali o'zingizning shaxsiy <b>Collector Bot</b> lar tarmog'ingizni yarating va ularni markazdan boshqaring.\n\n"
        "👇 <b>Mavjud buyruqlar:</b>\n"
        "📎 /add — Yangi bot tizimga qo'shish\n"
        "🤖 /my_bots — Faol botlaringizni boshqarish\n"
        "📊 /system_stats — Tizim statistikasi"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("add"))
async def cmd_add(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    count = await get_user_bots_count(user_id)
    if count >= 5:
        await message.answer(
            "⚠️ <b>Kechirasiz! Siz limitdan oshib ketdingiz.</b>\n"
            "<i>Bitta akkaunt uchun eng ko'pi bilan 5 ta bot ulanishi mumkin.</i>",
            parse_mode="HTML"
        )
        return
        
    await message.answer(
        "📝 <b>Yangi Collector Bot ulaymiz!</b>\n\n"
        "Iltimos, @BotFather orqali yaratilgan botingizning <b>TOKEN</b> raqamini yuboring.\n"
        "👉 <i>Namuna:</i> <code>123456789:ABCDefghIJKlmnOPQRSTuvwXYZ</code>",
        parse_mode="HTML"
    )
    await state.set_state(AddBotState.waiting_for_token)

@router.message(AddBotState.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    user_id = message.from_user.id
    
    # Check if this token is actually valid using aiogram Bot manually via simple async call
    temp_bot = Bot(token=token)
    try:
        me = await temp_bot.get_me()
        bot_id = me.id
        bot_username = me.username
    except TelegramUnauthorizedError:
        await message.answer("❌ <b>Noxoto'g'ri TOKEN!</b>\n<i>Iltimos, tokenni tekshirib qaytadan yuboring yoki amaliyotni bekor qiling.</i>", parse_mode="HTML")
        await temp_bot.session.close()
        return
    except Exception as e:
        await message.answer(f"❌ <b>Tokenni tekshirishda xatolik:</b>\n<i>{e}</i>", parse_mode="HTML")
        await temp_bot.session.close()
        return
        
    await temp_bot.session.close()

    # Now add to the database
    added = await add_bot(user_id, token, bot_id, bot_username)
    if not added:
        await message.answer("⚠️ <b>Ushbu bot allaqachon tizimga ulangan!</b>", parse_mode="HTML")
        await state.clear()
        return

    await state.clear()
    await message.answer(f"✅ <b>Bot @{bot_username} muvaffaqiyatli ulandi!</b> \n<i>Tizim ishga tushirilmoqda...</i>", parse_mode="HTML")

    # At this point, retrieve the correct auto-increment ID to start the bot
    bots = await get_user_bots(user_id)
    # The last one might be our bot
    db_id = None
    for b in bots:
        if b[1] == token:
            db_id = b[0]
            break
            
    if db_id:
        started = await bot_manager.start_bot(db_id, token)
        if started:
            await message.answer(f"🚀 <b>Ajoyib! BOT @{bot_username} muvaffaqiyatli ishga tushdi va xizmatga tayyor!</b>", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ <b>@{bot_username} botni ishga tushirishda muammo bo'ldi.</b>\n<i>/my_bots orqali qayta urinib ko'rishingiz mumkin.</i>", parse_mode="HTML")


@router.message(Command("my_bots"))
async def cmd_my_bots(message: types.Message):
    user_id = message.from_user.id
    bots = await get_user_bots(user_id)
    
    if not bots:
        await message.answer("😔 <b>Sizda hozircha birorta ham bot ulangan emas!</b>\n\nYangi bot ulash uchun /add buyrug'idan foydalaning.", parse_mode="HTML")
        return
        
    for bot in bots:
        db_id, token, bot_id, bot_username, status = bot
        
        stats = get_bot_stats(db_id)
        status_emoji = "🟢 Ishlamoqda" if status == 'Running' else "🔴 To'xtatilgan"
        text = (
            f"👤 <b>Tarmoq Boti:</b> @{bot_username}\n"
            f"🔄 <b>Holat:</b> {status_emoji}\n"
            f"📥 <b>Saqlangan fayllar:</b> {stats['total']} ta"
        )
        
        builder = InlineKeyboardBuilder()
        if status == 'Running':
            builder.button(text="🛑 To'xtatish", callback_data=f"stop_{db_id}")
        else:
            builder.button(text="▶️ Ishga tushirish", callback_data=f"start_{db_id}")
            
        builder.button(text="📄 Fayllarni olish", callback_data=f"getres_{db_id}")
        
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("stop_"))
async def callback_stop(query: types.CallbackQuery):
    db_id = int(query.data.split("_")[1])
    bot_info = await get_bot_by_id(db_id, query.from_user.id)
    if not bot_info:
        await query.answer("Bot not found or unauthorized.", show_alert=True)
        return
        
    await bot_manager.stop_bot(db_id)
    await query.message.edit_text(
        query.message.text.replace("🟢 Ishlamoqda", "🔴 To'xtatilgan"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Ishga tushirish", callback_data=f"start_{db_id}")],
            [InlineKeyboardButton(text="📄 Fayllarni olish", callback_data=f"getres_{db_id}")]
        ]),
        parse_mode="HTML"
    )
    await query.answer("Bot to'xtatildi! 🛑")

@router.callback_query(F.data.startswith("start_"))
async def callback_start(query: types.CallbackQuery):
    db_id = int(query.data.split("_")[1])
    bot_info = await get_bot_by_id(db_id, query.from_user.id)
    if not bot_info:
        await query.answer("Bot not found or unauthorized.", show_alert=True)
        return
        
    token = bot_info[1]
    started = await bot_manager.start_bot(db_id, token)
    
    if started:
        await query.message.edit_text(
            query.message.text.replace("🔴 To'xtatilgan", "🟢 Ishlamoqda"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛑 To'xtatish", callback_data=f"stop_{db_id}")],
                [InlineKeyboardButton(text="📄 Fayllarni olish", callback_data=f"getres_{db_id}")]
            ]),
            parse_mode="HTML"
        )
        await query.answer("Bot muvaffaqiyatli ishga tushirildi! 🚀")
    else:
        await query.answer("Failed to start bot.", show_alert=True)

@router.callback_query(F.data.startswith("getres_"))
async def callback_getres(query: types.CallbackQuery):
    parts = query.data.split("_")
    db_id = int(parts[1])
    
    # Check if this is from owner or regular user
    is_owner = (query.from_user.id == OWNER_ID)
    bot_info = await get_bot_by_id(db_id, query.from_user.id if not is_owner else None)
    
    if not bot_info:
        await query.answer("Bot topilmadi yoki ruxsatingiz yo'q.", show_alert=True)
        return
        
    files = await get_all_bot_files(db_id)
    if not files or len(files) == 0:
        await query.answer("Bu bot uchun omborxonada hech qanday fayl yo'q... 🤷‍♂️", show_alert=True)
        return
        
    try:
        import json
        import tempfile
        import os
        
        # Create a temporary json file with the database records
        data = {"files": files}
        fd, path = tempfile.mkstemp(suffix=".json", prefix="result_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        document = FSInputFile(path, filename=f"bot_{db_id}_omborxona.json")
        await query.message.answer_document(document, caption=f"📦 <b>@{bot_info[3]}</b> boti orqali yig'ilgan jami xazina bazasi!", parse_mode="HTML")
        await query.answer("Sizga fayl yuborilmoqda... 📤")
        
        # Delete temp file after sending
        os.remove(path)
        
    except Exception as e:
        await query.answer(f"Faylni yuborishda muammo chiqdi: {e}", show_alert=True)


# Admin commands (Optional as per requirements)
@router.message(Command("all_users"))
async def cmd_all_users(message: types.Message):
    # Optional logic to check if message.from_user.id is ADMIN
    # For now, it's open to all or simple security.
    count = await get_all_users_count()
    await message.answer(f"Total users in the system: {count}")

@router.message(Command("all_bots"))
async def cmd_all_bots(message: types.Message):
    count = await get_all_bots_count()
    await message.answer(f"Total bots in the system: {count}")

@router.message(Command("owner"))
async def cmd_owner(message: types.Message):
    if message.from_user.id != OWNER_ID or OWNER_ID == 0:
        return
        
    users_count = await get_all_users_count()
    bots_count = await get_all_bots_count()
    
    # Active bots
    bots = await get_all_bots()
    active_count = sum(1 for b in bots if b[4] == 'Running')
    
    text = (
        f"👑 <b>ASOSIY EGASI (OWNER) PANELI:</b>\n\n"
        f"👥 Odamlar: {users_count} ta\n"
        f"🤖 Barcha qo'shilgan botlar: {bots_count} ta\n"
        f"🟢 Aktiv botlar: {active_count} ta"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Barcha Botlarni Ko'rish", callback_data="owner_bots_list")
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "owner_bots_list")
async def callback_owner_bots_list(query: types.CallbackQuery):
    if query.from_user.id != OWNER_ID:
        return
        
    bots = await get_all_bots()
    if not bots:
        await query.answer("Hozircha tizimda hech qanday bot yo'q.", show_alert=True)
        return
        
    text = "🤖 <b>Tizimdagi barcha botlar:</b>\n<i>Qaysi botni boshqarmoqchisiz?</i>"
    builder = InlineKeyboardBuilder()
    
    for bot in bots:
        db_id, token, bot_id, bot_username, status, user_id, created_at = bot
        status_emoji = "🟢" if status == 'Running' else "🔴"
        builder.button(text=f"{status_emoji} @{bot_username}", callback_data=f"owner_bot_{db_id}")
        
    builder.adjust(1)
    
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("owner_bot_"))
async def callback_owner_bot_view(query: types.CallbackQuery):
    if query.from_user.id != OWNER_ID:
        return
        
    db_id = int(query.data.split("_")[2])
    bot_info = await get_bot_by_id(db_id)
    
    if not bot_info:
        await query.answer("Bot topilmadi.", show_alert=True)
        return
        
    db_id, token, bot_id, bot_username, status, user_id, created_at = bot_info
    
    stats = get_bot_stats(db_id)
    status_emoji = "🟢 Ishlamoqda" if status == 'Running' else "🔴 To'xtatilgan"
    token_str = str(token) if token else ""
    
    if type(created_at) == str:
        created_at = created_at[:19].replace("T", " ")
        
    text = (
        f"👤 <b>Bot Ma'lumotlari:</b> @{bot_username}\n\n"
        f"🆔 <b>Bot ID:</b> <code>{bot_id}</code>\n"
        f"🔑 <b>Token:</b> <code>{token_str}</code>\n\n"
        f"👤 <b>Kim tomondan qo'shildi (User ID):</b> <code>{user_id}</code>\n"
        f"📅 <b>Qo'shilgan vaqti:</b> {created_at}\n\n"
        f"🔄 <b>Holati:</b> {status_emoji}\n"
        f"📥 <b>Jami fayllari:</b> {stats['total']} ta"
    )
    
    builder = InlineKeyboardBuilder()
    if status == 'Running':
        builder.button(text="🛑 To'xtatish", callback_data=f"owner_toggle_{db_id}")
    else:
        builder.button(text="▶️ Ishga tushirish", callback_data=f"owner_toggle_{db_id}")
        
    builder.button(text="📄 Fayllarni olish", callback_data=f"getres_{db_id}")
    builder.button(text="🔙 Orqaga", callback_data="owner_bots_list")
    builder.adjust(1)
    
    await query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("owner_toggle_"))
async def callback_owner_bot_toggle(query: types.CallbackQuery):
    if query.from_user.id != OWNER_ID:
        return
        
    db_id = int(query.data.split("_")[2])
    bot_info = await get_bot_by_id(db_id)
    
    if not bot_info:
        await query.answer("Bot topilmadi.", show_alert=True)
        return
        
    db_id, token, bot_id, bot_username, status, user_id, created_at = bot_info
    
    if status == 'Running':
        await bot_manager.stop_bot(db_id)
        await query.answer("Bot to'xtatildi! 🛑")
    else:
        started = await bot_manager.start_bot(db_id, token)
        if started:
            await query.answer("Bot ishga tushirildi! 🚀")
        else:
            await query.answer("Botni ishga tushirishda xatolik yuz berdi.", show_alert=True)
            return
            
    # Refresh the view
    class FakeData:
        pass
    new_query = query
    new_query.data = f"owner_bot_{db_id}"
    await callback_owner_bot_view(new_query)
