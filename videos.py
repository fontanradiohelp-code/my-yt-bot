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
    print("Ошибка: Токен BOT_TOKEN не задан!")
    sys.exit(1)

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_links = {}

# --- ВЕБ-СЕРВЕР (Живучесть на Render) ---
async def handle(request):
    return web.Response(text="Бот активен и готов к работе!")

app = web.Application()
app.router.add_get('/', handle)

# --- УЛЬТИМАТИВНЫЕ НАСТРОЙКИ ДЛЯ ОБХОДА БЛОКИРОВОК ---
def get_ydl_opts(media_type, file_id):
    common_opts = {
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'cookiefile': 'cookies.txt',  # Файл должен быть в репозитории!
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        
        # Маскировка под обычный браузер
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Sec-Fetch-Mode': 'navigate',
        },
        
        # Обход новых алгоритмов YouTube (2026)
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android', 'ios'],
                'player_skip': ['webpage', 'configs']
            }
        }
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

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎬 **YouTube Downloader**\n\n"
        "Пришлите мне ссылку на видео или Shorts!"
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
    await message.answer("Файл найден! Выберите формат:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def start_download(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_links:
        return await callback.answer("Ошибка: ссылка не найдена. Отправьте её еще раз.")
    
    media_type = callback.data.split("_")[1]
    url = user_links[user_id]
    file_id = f"file_{user_id}_{int(asyncio.get_event_loop().time())}"
    
    status_msg = await callback.message.edit_text(f"⏳ **Начинаю загрузку {media_type.upper()}...**")
    
    try:
        opts = get_ydl_opts(media_type, file_id)
        loop = asyncio.get_event_loop()
        
        # Скачивание
        await loop.run_in_executor(None, lambda: YoutubeDL(opts).download([url]))
        
        # Поиск файла
        ext = "mp4" if media_type == "mp4" else "mp3"
        final_file = None
        for f in os.listdir(DOWNLOAD_PATH):
            if f.startswith(file_id) and f.endswith(ext):
                final_file = os.path.join(DOWNLOAD_PATH, f)
                break

        if final_file and os.path.exists(final_file):
            await status_msg.edit_text("🚀 **Почти готово! Отправляю файл...**")
            input_file = types.FSInputFile(final_file)
            
            if media_type == "mp4":
                await bot.send_video(callback.message.chat.id, video=input_file, caption="Ваше видео готово!")
            else:
                await bot.send_audio(callback.message.chat.id, audio=input_file, caption="Ваше аудио готово!")
            
            os.remove(final_file) # Удаляем файл после отправки
        else:
            raise Exception("YouTube применил усиленную защиту. Попробуйте обновить cookies.txt.")
            
    except Exception as e:
        await callback.message.answer(f"❌ **Ошибка загрузки:**\n{str(e)}")
    finally:
        try:
            await status_msg.delete()
        except:
            pass
        user_links.pop(user_id, None)

# --- ЗАПУСК ---
async def main():
    # Запуск сервера-заглушки
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    asyncio.create_task(site.start())
    
    print("✅ Бот запущен и подключен к системе обхода блокировок!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
