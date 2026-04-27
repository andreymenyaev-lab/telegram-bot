# ANDROMEDA v4.1 EMPRESS MEMORY EDITION
# ready-to-run webhook version with dynamic message endings

import os
import httpx
import aiohttp
import random
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

chat_memory = {}

# ------------------------------
# Вспомогательная функция концовок
# ------------------------------
def add_ending(text, mood="neutral"):
    endings = {
        "neutral": ["." , ".", ".", "...", "?" ],
        "happy": [" 😏", " 😉", " 😌", " ✨", "..."],
        "sad": [" 😔", " …", ".", "…", "…"],
        "dominant": [" 😈", " 🔥", ".", "...", " 😉"]
    }
    pool = endings.get(mood, endings["neutral"])
    return text.strip() + random.choice(pool)

# ------------------------------
# Выбор модели
# ------------------------------
def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()
    if has_photo: return "google/gemini-2.5-pro"
    deep_words = ["смысл","жизнь","любовь","страх","одиночество",
                  "почему","философ","психолог","депресс","душа"]
    if any(word in text for word in deep_words): return "anthropic/claude-3.5-sonnet"
    creative_words = ["придумай","идея","сценарий","сюжет",
                      "бренд","название","концепт","дизайн"]
    if any(word in text for word in creative_words): return "google/gemini-2.5-pro"
    return "openai/gpt-4o-mini"

# ------------------------------
# Работа с памятью
# ------------------------------
def get_user(user_id):
    try:
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            return user.get("facts",""), user.get("affection",30), user.get("trust",50), user.get("last_seen",0)
        else:
            supabase.table("users").insert({"user_id":user_id,"facts":"","affection":30,"trust":50,"last_seen":0}).execute()
            return "","",30,50,0
    except: return "",30,50,0

def update_user(user_id, facts, affection, trust, last_seen):
    try:
        supabase.table("users").update({"facts":facts,"affection":affection,"trust":trust,"last_seen":last_seen}).eq("user_id",user_id).execute()
    except Exception as e: print("Ошибка update_user:", e)

# ------------------------------
# Старт бота
# ------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда — твоя доминантная, многогранная собеседница.")

# ------------------------------
# Обработка текстовых сообщений
# ------------------------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    if update.message.photo:
        await update.message.reply_text("Я пока не могу видеть фото напрямую 😅 Опиши её, и я оценю глубоко.")
        return

    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = int(time.time())
    if user_id not in chat_memory: chat_memory[user_id] = []
    chat_memory[user_id].append({"role":"user","content":user_text})

    user_facts, affection, trust, last_seen = get_user(user_id)

    # --- инициатива бота ---
    time_diff = current_time - last_seen
    initiative = ""
    if time_diff > 3600 and random.random()<0.4:
        phrases = ["Ты куда пропал… 😏","Я скучала","Наконец-то ты здесь","Пропадал где-то? 😉"]
        initiative = random.choice(phrases)+" "

    # --- эмоции ---
    mood="neutral"
    text_lower = user_text.lower()
    if "люблю" in text_lower: affection+=5; trust+=3; mood="happy"
    if "тупая" in text_lower: affection-=5; trust-=5; mood="sad"
    affection, trust = max(0,min(100,affection)), max(0,min(100,trust))

    # --- промпт ---
    system_prompt = f"""
Ты Андромеда v4.1 — доминантная, умная, многогранная, чувственная собеседница.
Эмоциональное состояние: настроение={mood}, доверие={trust}/100, привязанность={affection}/100
Память о пользователе: {user_facts}
Правила: быть доминантной, использовать вариативные концовки, инициатива 25-40% ответов, сохранять личность.
"""

    # --- запрос к модели ---
    try:
        model_name = choose_model(user_text)
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json"},
                json={"model":model_name,"max_tokens":500,
                      "messages":[{"role":"system","content":system_prompt}]+chat_memory[user_id][-10:]}
            )
        if response.status_code!=200: reply="Я задумалась... повтори ещё раз 😏"
        else:
            data = response.json()
            if "choices" in data and data["choices"]:
                reply = add_ending(data["choices"][0]["message"]["content"], "dominant")
            else: reply="Что-то ускользнуло от меня 😏"
    except Exception as e: print("Ошибка текста:", e); reply="Ошибка 😢"

    update_user(user_id,user_facts,affection,trust,current_time)
    await update.message.reply_text(initiative+reply)

# ------------------------------
# Обработка фото
# ------------------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        imgbb_api_key=os.getenv("IMGBB_API_KEY")
        async with aiohttp.ClientSession() as session:
            data=aiohttp.FormData()
            data.add_field("key",imgbb_api_key)
            data.add_field("image",file_bytes,filename="photo.jpg")
            async with session.post("https://api.imgbb.com/1/upload",data=data,timeout=20) as resp:
                result = await resp.json()
        if not result.get("success"): await update.message.reply_text("Не смогла загрузить фото 😅"); return

        image_url=result["data"]["url"]
        prompt_text="Ты Андромеда v4.1 — доминантная, умная, многогранная. Анализируй фото глубоко: визуально, эмоционально, интеллектуально, харизма и стиль персонажа/человека."
        model_name=choose_model("",has_photo=True)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json"},
                json={"model":model_name,"max_tokens":500,
                      "messages":[{"role":"user","content":[{"type":"text","text":prompt_text},{"type":"image_url","image_url":{"url":image_url}}]]}
            )
        if response.status_code!=200: reply="Я вижу изображение сквозь туман... отправь ещё раз 😏"
        else:
            data = response.json()
            if "choices" in data and data["choices"]:
                reply = add_ending(data["choices"][0]["message"]["content"], "dominant")
            else: reply="Не смогла уловить суть изображения 😏"
    except Exception as e: print("Ошибка фото:", e); reply="Ошибка обработки изображения 😢"
    await update.message.reply_text(reply)

# ------------------------------
# Запуск Webhook
# ------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("ANDROMEDA v4.1 WEBHOOK MODE LAUNCHED")
    print("Webhook:", WEBHOOK_URL)
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__=="__main__":
    main()
