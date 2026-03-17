from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
import logging
from hurry.filesize import size, alternative

from database import add_file, clear_bot_files, get_bot_files_stats, get_all_bot_files
import os

def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def setup_collector_handlers(dp: Dispatcher, db_id: int):

    @dp.message(Command("start"))
    async def start_cmd(message: types.Message):
        await message.answer(
            "👋 <b>Assalomu alaykum! Men fayl yig'uvchi (Collector) botman.</b>\n\n"
            "Menga turli xil fayllarni (Video, Rasm, Hujjat, Audio, Ovoz va Animatsiya) yuboring, men ularni ID raqamlari bilan birga xavfsiz omborga joylayman.\n\n"
            "👇 <b>Mavjud buyruqlar:</b>\n"
            "📊 /status — Yig'ilgan fayllar statistikasi\n"
            "📥 /get — Natijalarni (JSON formatda) tortib olish\n"
            "🗑 /reset — Omborxonani tozalash",
            parse_mode="HTML"
        )

    @dp.message(Command("reset"))
    async def reset_cmd(message: types.Message):
        await clear_bot_files(db_id)
        await message.answer("♻️ <b>Omborxona muvaffaqiyatli tozalandi!</b>\n<i>Endi bazada hech qanday fayl yo'q.</i>", parse_mode="HTML")

    @dp.message(Command("status"))
    async def status_cmd(message: types.Message):
        stats = await get_bot_files_stats(db_id)
        text = (
            f"📈 <b>BOT BAZASI KUZATUVI</b>\n\n"
            f"📁 <b>Umumiy fayllar:</b> {stats['total']} ta\n\n"
            f"🎬 Videolar: {stats['video']} ta\n"
            f"🖼️ Rasmlar: {stats['photo']} ta\n"
            f"📄 Hujjatlar: {stats['document']} ta\n"
            f"🎵 Audiolar: {stats['audio']} ta\n"
            f"🎤 Ovozli xabar: {stats['voice']} ta\n"
            f"🏃 Animatsiyalar: {stats['animation']} ta"
        )
        await message.answer(text, parse_mode="HTML")

    @dp.message(Command("get"))
    async def get_cmd(message: types.Message):
        files = await get_all_bot_files(db_id)
        if not files or len(files) == 0:
            await message.answer("⚠️ <b>Hozircha hech qanday fayl saqlanmagan.</b>\n<i>Omborxona bo'sh...</i>", parse_mode="HTML")
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
                
            document = FSInputFile(path, filename="result.json")
            await message.answer_document(document, caption="📦 <b>Sizning bazangiz tayyor!</b>\n<i>Barcha fayllar shu JSON ichida jamlangan.</i>", parse_mode="HTML")
            
            # Delete temp file after sending
            os.remove(path)
            
        except Exception as e:
            logging.error(f"Error sending file to user: {e}")
            await message.answer("❌ <b>Xatolik yuz berdi.</b>\nMa'lumotlarni yuklab bo'lmadi.", parse_mode="HTML")

    @dp.message(F.content_type.in_({'video', 'photo', 'document', 'audio', 'voice', 'animation'}))
    async def process_file(message: types.Message):
        ct = message.content_type
        
        file_obj = None
        file_name = "Unknown"
        file_size = 0
        duration = 0
        
        if ct == 'photo':
            file_obj = message.photo[-1]
            file_name = "photo.jpg"
            file_size = file_obj.file_size
        elif ct == 'video':
            file_obj = message.video
            file_name = file_obj.file_name or "video.mp4"
            file_size = file_obj.file_size
            duration = file_obj.duration
        elif ct == 'document':
            file_obj = message.document
            file_name = file_obj.file_name or "document.file"
            file_size = file_obj.file_size
        elif ct == 'audio':
            file_obj = message.audio
            file_name = file_obj.file_name or "audio.mp3"
            file_size = file_obj.file_size
            duration = file_obj.duration
        elif ct == 'voice':
            file_obj = message.voice
            file_name = "voice.ogg"
            file_size = file_obj.file_size
            duration = file_obj.duration
        elif ct == 'animation':
            file_obj = message.animation
            file_name = file_obj.file_name or "animation.gif"
            file_size = file_obj.file_size
            duration = file_obj.duration
            
        file_id = file_obj.file_id
        file_unique_id = file_obj.file_unique_id
        
        try:
            bot_username = (await message.bot.me()).username
            formatted_size = size(file_size, system=alternative) if file_size else "Unknown"
            formatted_duration = format_duration(duration) if duration else "Unknown"
            caption = message.caption or "No description"
            
            file_data = {
                "type": ct,
                "title": file_name,
                "description": caption,
                "duration": formatted_duration,
                "size": formatted_size,
                "name": file_name,
                "bot_username": f"@{bot_username}",
                "file_id": file_id,
                "file_unique_id": file_unique_id
            }

            added = await add_file(db_id, file_data)
            if added:
                # Format output message
                emoji_map = {
                    'video': '🎥 Video',
                    'photo': '🖼️ Rasm',
                    'document': '📄 Hujjat',
                    'audio': '🎵 Audio',
                    'voice': '🎤 Ovoz',
                    'animation': '🏃 Animatsiya'
                }
                type_name = emoji_map.get(ct, '📁 Fayl')
                
                # Format description conditionally
                desc_html = f"\n<blockquote><b>Ta'rif:</b>\n<i>{caption}</i></blockquote>\n" if caption != "No description" else "\n"
                
                # Format output message (Premium Clean Design)
                response_text = (
                    f"✨ <b>YANGI FILE QABUL QILINDI</b>\n\n"
                    f"🔹 <b>Sarlavha:</b> {file_name}\n"
                    f"🔹 <b>Turi:</b> {type_name}\n"
                    f"🔹 <b>Hajmi:</b> {formatted_size}\n"
                    f"🔹 <b>Davomiylik:</b> {formatted_duration}"
                    f"{desc_html}"
                    f"👇 <b>[ FILE ID NUMBASI ]</b> (Nusxalash uchun bosing)\n"
                    f"<code>{file_id}</code>\n\n"
                    f"💎 <i>{bot_username} orqali saqlandi</i>"
                )
                
                await message.reply(response_text, parse_mode="HTML", disable_notification=True)
            else:
                await message.reply("⚠️ <b>Ushbu file allaqachon bazada mavjud!</b>", parse_mode="HTML", disable_notification=True)
        except Exception as e:
            logging.error(f"Error saving file in collector bot {db_id}: {e}")
            await message.reply("❌ There was an error saving the file.", disable_notification=True)
