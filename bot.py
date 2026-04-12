import telebot
import google.generativeai as genai
import subprocess
import os
import time
import imageio_ffmpeg
import re
from yt_dlp import YoutubeDL

import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# FFmpeg manzilini olish (Server yoki Lokal muhit uchun)
try:
    import shutil
    FFMPEG_PATH = shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# --- SETUP ---
# Serverda xavfsizlik uchun TOKEN va API kalitlar muhit o'zgaruvchilaridan (Env) olinadi
TOKEN = os.getenv("BOT_TOKEN", "8587491091:AAE1ym5zMBoLqjyHumIL5LisPTw-_bzP3Ww")
GEMINI_API_KEY = os.getenv("GEMINI_KEY", "AIzaSyCpvsN_hSejI3Tg7H9Ul8dOBH3T0JcHx24")

bot = telebot.TeleBot(TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Bot tavsifini sozlash
try:
    bot.set_my_description("videoni sifatini Full HD gacha ko'tarib beradigan bot")
    bot.set_my_short_description("Video sifatini Full HD gacha ko'taruvchi bot")
except Exception as e:
    print(f"Tavsifni o'rnatib bo'lmadi: {e}")

print("Bot ishga tushdi...")

# --- UTILS ---

def process_video_file(input_path, message, status_msg):
    output_path = f"output_hd_{int(time.time())}.mp4"
    
    try:
        bot.edit_message_text("⚙️ Videoni 9:16 (GPU 🚀) formatga o'tkazyapman...", message.chat.id, status_msg.message_id)
        
        # 1-urilish: Intel QSV (GPU) orqali o'ta tezkor renders
        command_gpu = [
            FFMPEG_PATH, '-hwaccel', 'qsv', '-i', input_path,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease:flags=bilinear,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'h264_qsv', '-global_quality', '25', '-preset', 'veryfast',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
            '-c:a', 'copy', output_path
        ]
        
        try:
            subprocess.run(command_gpu, check=True, capture_output=True)
        except Exception as e:
            print(f"GPU xatosi: {e}. CPU ga qaytilyapti...")
            bot.edit_message_text("⚙️ GPU band yoki topilmadi, CPU orqali davom etyapman...", message.chat.id, status_msg.message_id)
            # 2-urilish: Standart CPU orqali (Fallback)
            command_cpu = [
                FFMPEG_PATH, '-i', input_path,
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease:flags=bilinear,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                '-threads', '0', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                '-c:a', 'copy', output_path
            ]
            subprocess.run(command_cpu, check=True)
        
        # Tayyor videoni yuborish
        bot.edit_message_text("📤 Video tayyor! Yuboryapman...", message.chat.id, status_msg.message_id)
        with open(output_path, 'rb') as video:
            bot.send_video(message.chat.id, video, caption="✅ Video 9:16 (Raketa 🚀) sifatda tayyor bo'ldi!", timeout=120)
            
    except Exception as e:
        print(f"Xatolik: {e}")
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {str(e)}")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
        try: bot.delete_message(message.chat.id, status_msg.message_id)
        except: pass

def download_with_ytdlp(url):
    name = f"dl_{int(time.time())}.mp4"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': name,
        'quiet': True,
        'no_warnings': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return name

# --- HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! Menga video yuboring, men uni siz uchun Full HD (1080p) formatga o'tkazib beraman."
    )

@bot.message_handler(content_types=['video', 'document'])
def handle_video(message):
    video_file = None
    if message.content_type == 'video':
        video_file = message.video
    elif message.content_type == 'document' and message.document.mime_type.startswith('video/'):
        video_file = message.document

    if not video_file: return

    status_msg = bot.reply_to(message, "⏳ Videoni yuklab olyapman...")
    
    try:
        file_info = bot.get_file(video_file.file_id)
        downloaded_data = bot.download_file(file_info.file_path)
        input_path = f"input_{int(time.time())}.mp4"
        with open(input_path, 'wb') as f:
            f.write(downloaded_data)
        
        # Parallel ravishda videoni qayta ishlashni boshlash
        threading.Thread(target=process_video_file, args=(input_path, message, status_msg), daemon=True).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Faylni yuklab olishda xatolik: {e}")

@bot.message_handler(func=lambda message: True)
def handle_all_text(message):
    # Havolani aniqlash (YouTube, Instagram)
    url_pattern = r'https?://(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com)[\w\d\?&=\./-]+'
    match = re.search(url_pattern, message.text)
    
    if match:
        url = match.group(0)
        status_msg = bot.reply_to(message, "🔗 Havola aniqlandi. Video yuklab olinyapti...")
        try:
            input_path = download_with_ytdlp(url)
            # Parallel ravishda videoni qayta ishlashni boshlash
            threading.Thread(target=process_video_file, args=(input_path, message, status_msg), daemon=True).start()
        except Exception as e:
            bot.edit_message_text(f"❌ Havoladan yuklab bo'lmadi: {e}", message.chat.id, status_msg.message_id)
    else:
        # Agar havola bo'lmasa, Gemini bilan gaplashadi
        try:
            javob = model.generate_content(message.text)
            bot.reply_to(message, javob.text)
        except Exception as e:
            bot.reply_to(message, "❌ Savolingizga javob topishda xatolik bo‘ldi!")

# Flask serverni alohida tarmoqda ishga tushirish
threading.Thread(target=run_flask, daemon=True).start()

bot.infinity_polling(timeout=90, long_polling_timeout=60)

