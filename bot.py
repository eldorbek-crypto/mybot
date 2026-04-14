import telebot
import google.generativeai as genai
import subprocess
import os
import time
import re
import threading
import shutil
from flask import Flask

try:
    import imageio_ffmpeg
    FFMPEG_PATH = shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = shutil.which('ffmpeg') or 'ffmpeg'

# --- Flask health check ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- SETUP ---
TOKEN = os.getenv("BOT_TOKEN", "8587491091:AAE1ym5zMBoLqjyHumIL5LisPTw-_bzP3Ww")
GEMINI_API_KEY = os.getenv("GEMINI_KEY", "AIzaSyCpvsN_hSejI3Tg7H9Ul8dOBH3T0JcHx24")

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

try:
    bot.set_my_description("Videoni Full HD sifatida va rang jihatdan yaxshilab beradigan bot 🎬")
    bot.set_my_short_description("Video sifatini Full HD + rang yaxshilovchi bot")
except Exception as e:
    print(f"Tavsifni o'rnatib bo'lmadi: {e}")

print("Bot ishga tushdi...")

# --- VIDEO PROCESSING ---

def process_video_file(input_path, message, status_msg):
    output_path = f"output_hd_{int(time.time())}.mp4"

    try:
        bot.edit_message_text(
            "⚙️ Video qayta ishlanmoqda: Full HD + rang yaxshilanmoqda...",
            message.chat.id, status_msg.message_id
        )

        # FFmpeg: 9:16 crop, Full HD, rang saturatsiyasi +2 (brightness=0.02, saturation=3)
        command = [
            FFMPEG_PATH,
            '-y',
            '-i', input_path,
            '-vf', (
                'scale=720:1280:force_original_aspect_ratio=increase,'
                'crop=720:1280,'
                'eq=saturation=3.0:brightness=0.02:contrast=1.05'
            ),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '26',
            '-threads', '0',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ]

        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("FFmpeg chiqish fayl yaratilmadi yoki bo'sh")

        bot.edit_message_text(
            "📤 Video tayyor! Yuboryapman...",
            message.chat.id, status_msg.message_id
        )

        with open(output_path, 'rb') as video:
            bot.send_video(
                message.chat.id,
                video,
                caption="✅ Video Full HD + rang yaxshilandi! 🎬✨",
                timeout=180
            )

        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass

    except subprocess.CalledProcessError as e:
        err = e.stderr[-500:] if e.stderr else str(e)
        print(f"FFmpeg xatosi: {err}")
        try:
            bot.edit_message_text(
                f"❌ Video qayta ishlashda xatolik:\n`{err}`",
                message.chat.id, status_msg.message_id,
                parse_mode='Markdown'
            )
        except Exception:
            bot.reply_to(message, f"❌ FFmpeg xatolik: {err}")

    except Exception as e:
        print(f"Umumiy xatolik: {e}")
        try:
            bot.edit_message_text(
                f"❌ Xatolik: {str(e)}",
                message.chat.id, status_msg.message_id
            )
        except Exception:
            bot.reply_to(message, f"❌ Xatolik: {str(e)}")

    finally:
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except Exception:
                pass
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass


def download_with_ytdlp(url, status_msg, message):
    """yt-dlp orqali video yuklash"""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        raise Exception("yt-dlp o'rnatilmagan! 'pip install yt-dlp' ishlatib o'rnating.")

    name = f"dl_{int(time.time())}.mp4"

    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'outtmpl': name,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'socket_timeout': 30,
        'retries': 3,
    }

    try:
        bot.edit_message_text(
            "⬇️ Video yuklab olinmoqda... iltimos kuting",
            message.chat.id, status_msg.message_id
        )
        from yt_dlp import YoutubeDL
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise Exception(f"Yuklab bo'lmadi: {str(e)}")

    # Fayl topilmasa tekshiruv
    if not os.path.exists(name):
        # yt-dlp ba'zan format qo'shadi, tekshiramiz
        for ext in ['.mp4', '.mkv', '.webm']:
            candidate = name.replace('.mp4', ext)
            if os.path.exists(candidate):
                return candidate
        raise Exception("Yuklangan fayl topilmadi.")

    if os.path.getsize(name) == 0:
        os.remove(name)
        raise Exception("Fayl bo'sh yuklandi.")

    return name


# --- HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "👋 Assalomu alaykum!\n\n"
        "🎬 Men video sifatini *Full HD* va ranglarni yaxshilab beradigan botman!\n\n"
        "📌 *Nima yuborishingiz mumkin:*\n"
        "• 📹 Video fayl to'g'ridan-to'g'ri\n"
        "• 🔗 YouTube / Instagram / TikTok havolasi\n\n"
        "💡 Video 9:16 formatda, rang saturatsiyasi +2 oshirilgan holda qaytariladi!",
        parse_mode='Markdown'
    )


@bot.message_handler(content_types=['video', 'document'])
def handle_video(message):
    video_file = None

    if message.content_type == 'video':
        video_file = message.video
    elif message.content_type == 'document':
        doc = message.document
        if doc and doc.mime_type and doc.mime_type.startswith('video/'):
            video_file = doc

    if not video_file:
        bot.reply_to(message, "⚠️ Bu video fayl emas. Iltimos video yuboring.")
        return

    # Fayl hajmi tekshiruvi (Telegram bot API: max 20MB download)
    file_size = getattr(video_file, 'file_size', 0) or 0
    if file_size > 20 * 1024 * 1024:
        bot.reply_to(
            message,
            "⚠️ Fayl 20MB dan katta! Bot API bu hajmni yuklay olmaydi.\n"
            "Iltimos, YouTube/Instagram havolasini yuboring yoki kichikroq video yuboring."
        )
        return

    status_msg = bot.reply_to(message, "⏳ Video yuklab olinmoqda...")

    try:
        file_info = bot.get_file(video_file.file_id)
        downloaded_data = bot.download_file(file_info.file_path)

        if not downloaded_data or len(downloaded_data) == 0:
            raise Exception("Fayl ma'lumotlari bo'sh qaytdi.")

        input_path = f"input_{int(time.time())}.mp4"
        with open(input_path, 'wb') as f:
            f.write(downloaded_data)

        if os.path.getsize(input_path) == 0:
            raise Exception("Saqlangan fayl bo'sh.")

        threading.Thread(
            target=process_video_file,
            args=(input_path, message, status_msg),
            daemon=True
        ).start()

    except Exception as e:
        print(f"Video yuklab olish xatosi: {e}")
        try:
            bot.edit_message_text(
                f"❌ Faylni yuklab olishda xatolik:\n{str(e)}",
                message.chat.id, status_msg.message_id
            )
        except Exception:
            bot.reply_to(message, f"❌ Xatolik: {str(e)}")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_text(message):
    if not message.text:
        return

    # Keng URL pattern (YouTube, Instagram, TikTok, Twitter/X, va boshqalar)
    url_pattern = (
        r'https?://'
        r'(?:www\.)?'
        r'(?:youtube\.com|youtu\.be|instagram\.com|tiktok\.com|'
        r'twitter\.com|x\.com|fb\.com|facebook\.com|vimeo\.com|'
        r't\.me|dailymotion\.com)'
        r'[\w\d\?\&\=\.\-\/\%\#\_\+\~\:\@\!]*'
    )

    match = re.search(url_pattern, message.text)

    if match:
        url = match.group(0).rstrip('.,!?)')
        status_msg = bot.reply_to(message, "🔗 Havola aniqlandi. Video yuklanmoqda...")

        def download_and_process():
            try:
                input_path = download_with_ytdlp(url, status_msg, message)
                process_video_file(input_path, message, status_msg)
            except Exception as e:
                print(f"Link error: {e}")
                try:
                    bot.edit_message_text(
                        f"❌ Havoladan yuklab bo'lmadi:\n{str(e)}\n\n"
                        f"💡 Havola ochiq va to'g'ri ekanligini tekshiring.",
                        message.chat.id, status_msg.message_id
                    )
                except Exception:
                    bot.reply_to(message, f"❌ Xatolik: {str(e)}")

        threading.Thread(target=download_and_process, daemon=True).start()

    else:
        # Gemini AI javob
        try:
            javob = model.generate_content(message.text)
            bot.reply_to(message, javob.text)
        except Exception as e:
            print(f"Gemini xato: {e}")
            bot.reply_to(message, "❌ Savolingizga javob topishda xatolik bo'ldi! Qayta urinib ko'ring.")


# --- START ---
threading.Thread(target=run_flask, daemon=True).start()
bot.infinity_polling(timeout=90, long_polling_timeout=60)
