# ANDROMEDA v4 EMPRESS PRESENCE CORE
# ready-to-run edition
# сильная личность, доминантная, инициатива, вариативность, контроль над диалогом

import os
import httpx
import random
import time
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # свой сгенерированный URL Railway

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
chat_memory = {}

# --- ВЫБОР МОДЕЛИ ---
def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()
    if has_photo:
        return "google/gemini-2.5-pro"
    deep_words = ["смысл","жизнь","любовь","страх","одиночество","почему","философ","психолог","депресс","душа"]
    creative_words = ["придумай","идея","сценарий","сюжет","бренд","название","концепт","дизайн"]
    if any(word in text for word in deep_words):
        return "anthropic/claude-3.5-sonnet"
    if any(word in text for word in creative_words):
        return "google/gemini-2.5-pro"
    return "openai/gpt-4o-mini"

# --- БАЗА ---
def get_user(user_id):
    try:
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            return user.get("facts",""), user.get("affection",30), user.get("trust",50), user.get("last_seen",0)
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "facts": "",
                "affection": 30,
                "trust": 50,
                "last_seen": 0
            }).execute()
            return "",30,50,0
    except:
        return "",30,50,0

def update_user(user_id, facts, affection, trust, last_seen):
    try:
        supabase.table("users").update({
            "facts": facts,
            "affection": affection,
            "trust": trust,
            "last_seen": last_seen
        }).eq("user_id", user_id).execute()
    except:
        pass

# --- СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда")

# --- ОБРАБОТКА ТЕКСТА ---
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.photo:
        return await update.message.reply_text("Я пока не умею смотреть картинки 😅 Опиши её словесно")
    
    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = int(time.time())

    if user_id not in chat_memory:
        chat_memory[user_id] = []
    chat_memory[user_id].append({"role": "user", "content": user_text})

    user_facts, affection, trust, last_seen = get_user(user_id)

    # --- ПРОВЕРКА ПАУЗЫ ---
    initiative = ""
    time_diff = current_time - last_seen
    if time_diff > 3600:
        phrases = ["Пропал… 😏 ","Скучала ","Наконец-то ты здесь ","Здравствуй снова "]
        initiative = random.choice(phrases)

    # --- ЭМОЦИИ ---
    mood = "neutral"
    txt_lower = user_text.lower()
    if "люблю" in txt_lower: affection, trust, mood = min(100, affection+5), min(100, trust+3), "happy"
    if "тупая" in txt_lower: affection, trust, mood = max(0, affection-5), max(0, trust-5), "sad"

    # --- ПРОМПТ ---
    system_prompt = f"""
    Ты Андромеда — сильная, независимая, доминантная, многогранная.
    Настроение: {mood}, доверие: {trust}/100, привязанность: {affection}/100
    Память о пользователе: {user_facts}
    """

    try:
        model_name = choose_model(user_text)
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0)) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={"model": model_name, "max_tokens":500,
                      "messages":[{"role":"system","content":system_prompt}]+chat_memory[user_id][-10:]}
            )
        data = resp.json()
        reply = data.get("choices",[{"message":{"content":"Не смогла ответить 😅"}}])[0]["message"]["content"]
    except:
        reply = "Ошибка 😢"

    update_user(user_id, user_facts, affection, trust, current_time)
    await update.message.reply_text(initiative + reply)

# --- ОБРАБОТКА ФОТО ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        imgbb_api_key = os.getenv("IMGBB_API_KEY")

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("key", imgbb_api_key)
            data.add_field("image", file_bytes, filename="photo.jpg")
            async with session.post("https://api.imgbb.com/1/upload", data=data) as resp:
                result = await resp.json()
        if not result.get("success"): return await update.message.reply_text("Не смогла загрузить фото 😅")
        image_url = result["data"]["url"]
        await update.message.reply_text(f"Фото загружено: {image_url}")
    except:
        await update.message.reply_text("Ошибка обработки изображения 😢")

# --- ЗАПУСК С WEBHOOK ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("ANDROMEDA WEBHOOK MODE LAUNCHED")
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__ == "__main__":
    main()
