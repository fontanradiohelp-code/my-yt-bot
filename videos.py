import asyncio
import os
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from yt_dlp import YoutubeDL
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = '8357041848:AAFdjLp--MFMe40-axA6rwerdpHTNqVH1gw'
DOWNLOAD_PATH = "downloads"

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_links = {}

# --- ВЕБ-СЕРВЕР ДЛЯ ХОСТИНГА (ЧТОБЫ НЕ ЗАСЫПАЛ) ---
async def handle(request):
    return web.Response(text="Бот работает!")

app = web.Application()
app.router.add_get('/', handle)

# --- ЛОГИКА СКАЧИВАНИЯ ---
def get_ydl_opts(media_type, file_id):
    # Определяем путь к папке, где лежит этот скрипт
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Общие настройки для всех форматов
    common_opts = {
        'ffmpeg_location': current_dir,  # Указываем боту искать ffmpeg в нашей папке
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
    }

    if media_type == "mp4":
        return {
            **common_opts,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{DOWNLOAD_PATH}/{file_id}.%(ext)s',
            'merge_output_format': 'mp4',
        }
    else:
        return {
            **common_opts,
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_PATH}/{file_id}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Привет! Я обновленный загрузчик 2026.**\n\n"
        "Я использую локальный ffmpeg для обхода защиты.\n"
        "**Просто пришли мне ссылку на YouTube!**"
    )

@dp.message(F.text.regexp(r'(https?://)?(www\.)?(youtube\.com|youtu\.be|youtube\.com/shorts)/.+'))
async def process_link(message: types.Message):
    url = message.text.strip()
    user_links[message.from_user.id] = url
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📹 Видео (MP4)", callback_data="dl_mp4"),
        types.InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data="dl_mp3")
    )
    
    await message.answer("Файл обнаружен. Выберите формат:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def start_download(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_links:
        return await callback.answer("Ошибка: ссылка устарела.")
    
    media_type = callback.data.split("_")[1]
    url = user_links[user_id]
    file_id = f"file_{user_id}_{int(asyncio.get_event_loop().time())}"
    
    status_msg = await callback.message.edit_text(f"⏳ **Загрузка {media_type.upper()}...**\nИспользую локальный движок ffmpeg.")
    
    try:
        opts = get_ydl_opts(media_type, file_id)
        
        # Скачивание в фоновом режиме
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([url]))
        
        # Поиск итогового файла
        ext = "mp4" if media_type == "mp4" else "mp3"
        final_file = None
        for f in os.listdir(DOWNLOAD_PATH):
            if f.startswith(file_id) and f.endswith(ext):
                final_file = os.path.join(DOWNLOAD_PATH, f)
                break

        if final_file and os.path.exists(final_file):
            await status_msg.edit_text("🚀 **Отправка в Telegram...**")
            
            input_file = types.FSInputFile(final_file)
            if media_type == "mp4":
                await bot.send_video(callback.message.chat.id, video=input_file, caption="Ваше видео готово!")
            else:
                await bot.send_audio(callback.message.chat.id, audio=input_file, caption="Ваше аудио готово!")
            
            os.remove(final_file)
        else:
            raise Exception("Файл не найден после скачивания.")
            
    except Exception as e:
        await callback.message.answer(f"❌ **Ошибка:**\n{str(e)}")
    finally:
        try:
            await status_msg.delete()
        except:
            pass
        if user_id in user_links:
            del user_links[user_id]

# --- ЗАПУСК ---
async def main():
    # Запуск веб-сервера (для Render.com)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    asyncio.create_task(site.start())
    
    print("✅ Бот запущен! Локальный ffmpeg подключен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass