import asyncio
import os
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from yt_dlp import YoutubeDL
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('BOT_TOKEN')
DOWNLOAD_PATH = "downloads"

if not API_TOKEN:
    print("Ошибка: Токен BOT_TOKEN не найден в настройках Environment!")
    sys.exit(1)

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_links = {}

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Бот онлайн!")

app = web.Application()
app.router.add_get('/', handle)

# --- ГИБКИЕ НАСТРОЙКИ ЗАГРУЗКИ ---
def get_ydl_opts(media_type, file_id):
    # Общие настройки для обхода блокировок
    common_opts = {
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'cookiefile': 'cookies.txt',  # Обязательно загрузи этот файл на GitHub!
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        },
    }

    if media_type == "mp4":
        return {
            **common_opts,
            # 'best' — самый универсальный вариант, если связка video+audio недоступна
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

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 **Бот готов!**\n\nПришли ссылку на YouTube видео или Shorts, и я помогу его скачать.")

@dp.message(F.text.regexp(r'(https?://)?(www\.)?(youtube\.com|youtu\.be|youtube\.com/shorts)/.+'))
async def process_link(message: types.Message):
    url = message.text.strip()
    user_links[message.from_user.id] = url
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📹 Видео (MP4)", callback_data="dl_mp4"),
        types.InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data="dl_mp3")
    )
    await message.answer("🎬 Видео найдено! Выберите формат:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def start_download(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_links:
        return await callback.answer("Ошибка: ссылка потеряна. Отправьте её еще раз.")
    
    media_type = callback.data.split("_")[1]
    url = user_links[user_id]
    file_id = f"file_{user_id}_{int(asyncio.get_event_loop().time())}"
    
    status_msg = await callback.message.edit_text(f"⏳ **Загрузка {media_type.upper()}...**\nПожалуйста, подождите.")
    
    try:
        opts = get_ydl_opts(media_type, file_id)
        # Запускаем тяжелую загрузку в отдельном потоке, чтобы бот не «завис»
        await asyncio.to_thread(lambda: YoutubeDL(opts).download([url]))
        
        # Находим и отправляем файл
        ext = "mp4" if media_type == "mp4" else "mp3"
        final_file = None
        for f in os.listdir(DOWNLOAD_PATH):
            if f.startswith(file_id) and f.endswith(ext):
                final_file = os.path.join(DOWNLOAD_PATH, f)
                break

        if final_file and os.path.exists(final_file):
            await status_msg.edit_text("🚀 **Отправляю файл в Telegram...**")
            input_file = types.FSInputFile(final_file)
            
            if media_type == "mp4":
                await bot.send_video(callback.message.chat.id, video=input_file)
            else:
                await bot.send_audio(callback.message.chat.id, audio=input_file)
            
            os.remove(final_file)
        else:
            raise Exception("Файл не был создан. Проверьте формат видео.")
            
    except Exception as e:
        await callback.message.answer(f"❌ **Ошибка:**\n{str(e)}")
    finally:
        try:
            await status_msg.delete()
        except:
            pass
        user_links.pop(user_id, None)

# --- ЗАПУСК ---
async def main():
    # Запуск веб-сервера (нужен для Render)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    asyncio.create_task(site.start())
    
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
