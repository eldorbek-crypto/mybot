FROM python:3.11-slim

# FFmpeg va tizim kutubxonalarini o'rnatish
RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 && rm -rf /var/lib/apt/lists/*

# Hugging Face uchun UID 1000 ga ega foydalanuvchi yaratish (Xavfsizlik uchun)
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Fayllarni nusxalash va egalikni o'zgartirish
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# Hugging Face portini ochish (7860 default)
EXPOSE 7860
ENV PORT=7860

# Foydalanuvchiga o'tish
USER user

# Botni ishga tushirish
CMD ["python", "bot.py"]
