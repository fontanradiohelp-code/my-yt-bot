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

# Проверка токена
if not API_TOKEN:
    print("Ошибка: Переменная BOT_TOKEN не найдена в Environment Variables!")
    sys.exit(1)

# Создание папки для временных файлов
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_links = {}

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы не засыпал) ---
async def handle(request):
    return web.Response(text="Bot is Alive!")

app = web.Application()
app.router.add_get('/', handle)

# --- ЛОГИКА ОБХОДА БЛОКИРОВКИ YOUTUBE ---
def get_ydl_opts(media_type, file_id):
    common_opts = {
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        # 'cookiefile': 'cookies.txt', # Раскомментируй эту строку, если добавишь файл cookies.txt
        
        # Обманка YouTube: используем имитацию мобильных устройств
        'extractor_args': {
            'youtube': {
                'player_client': ['android_vr', 'ios'],
                'skip': ['dash', 'hls']
            }
        },
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
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
    await message.answer("🚀 **Бот готов к работе!**\n\nПришли ссылку на YouTube (Shorts тоже работают).")

@dp.message(F.text.regexp(r'(https?://)?(www\.)?(youtube\.com|youtu\.be|youtube\.com/shorts)/.+'))
async def process_link(message: types.Message):
    url = message.text.strip()
    user_links[message.from_user.id] = url
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📹 Видео (MP4)", callback_data="dl_mp4"),
        types.InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data="dl_mp3")
    )
    await message.answer("Выберите формат:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def start_download(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_links:
        return await callback.answer("Ошибка: ссылка потеряна. Отправь заново.")
    
    media_type = callback.data.split("_")[1]
    url = user_links[user_id]
    file_id = f"file_{user_id}_{int(asyncio.get_event_loop().time())}"
    
    status_msg = await callback.message.edit_text(f"⏳ **Загрузка {media_type.upper()}...**")
    
    try:
        opts = get_ydl_opts(media_type, file_id)
        loop = asyncio.get_event_loop()
        # Запуск скачивания
        await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([url]))
        
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
                await bot.send_video(callback.message.chat.id, video=input_file)
            else:
                await bot.send_audio(callback.message.chat.id, audio=input_file)
            
            os.remove(final_file)
        else:
            raise Exception("YouTube заблокировал запрос. Нужны Cookies.")
            
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
    # Запуск веб-заглушки для Render
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    asyncio.create_task(site.start())
    
    print("✅ Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
