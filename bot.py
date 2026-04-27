# ANDROMEDA v5 IMMORTAL MEMORY CORE
import os
import time
import random
import httpx
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client

# --- ENV ---
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# --- Supabase client ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Chat memory (short-term in RAM) ---
chat_memory = {}

# --- Model selection ---
def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()
    if has_photo:
        return "google/gemini-2.5-pro"
    deep_words = ["смысл","жизнь","любовь","страх","одиночество","почему","философ","психолог","депресс","душа"]
    if any(word in text for word in deep_words):
        return "anthropic/claude-3.5-sonnet"
    creative_words = ["придумай","идея","сценарий","сюжет","бренд","название","концепт","дизайн"]
    if any(word in text for word in creative_words):
        return "google/gemini-2.5-pro"
    return "openai/gpt-4o-mini"

# --- Database helpers ---
def get_user(user_id):
    try:
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            return (
                user.get("facts",""),
                user.get("affection",30),
                user.get("trust",50),
                user.get("last_seen",0)
            )
        else:
            supabase.table("users").insert({"user_id": user_id, "facts":"","affection":30,"trust":50,"last_seen":0}).execute()
            return "",30,50,0
    except Exception as e:
        print("Ошибка get_user:", e)
        return "",30,50,0

def update_user(user_id,facts,affection,trust,last_seen):
    try:
        supabase.table("users").update({"facts":facts,"affection":affection,"trust":trust,"last_seen":last_seen}).eq("user_id",user_id).execute()
    except Exception as e:
        print("Ошибка update_user:", e)

def get_summaries(user_id):
    try:
        resp = supabase.table("memory_summaries").select("*").eq("user_id", user_id).execute()
        return resp.data if resp.data else []
    except:
        return []

def add_summary(user_id, summary_text):
    try:
        supabase.table("memory_summaries").insert({"user_id": user_id,"summary": summary_text,"timestamp": int(time.time())}).execute()
    except:
        pass

# --- Start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда. Готова к диалогу и игре доминирования.")

# --- Text handler ---
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = int(time.time())
    if user_id not in chat_memory: chat_memory[user_id] = []
    chat_memory[user_id].append({"role":"user","content":user_text})

    user_facts, affection, trust, last_seen = get_user(user_id)
    time_diff = current_time - last_seen
    initiative = ""
    if time_diff > 3600:
        if affection>70: phrases=["Ты куда пропал… 😏 ","Я уже начала скучать ","Наконец-то ты появился ","Я думала ты забыл про меня "]
        elif affection>40: phrases=["Давно тебя не было ","О, ты снова тут ","Пропадал где-то? ","Ну привет, исчезающий "]
        else: phrases=["Ты снова здесь ","Ну ладно, вернулся ","Опять ты ","Хм, интересно "]
        initiative=random.choice(phrases)
    mood="neutral"
    text_lower=user_text.lower()
    if "люблю" in text_lower: affection+=5; trust+=3; mood="happy"
    elif "тупая" in text_lower: affection-=5; trust-=5; mood="sad"
    affection = max(0,min(100,affection))
    trust = max(0,min(100,trust))

    # --- Prompt ---
    system_prompt = f"""
Ты Андромеда — доминантная, женственная, умная, чувственная личность. 
Моя цель — вести разговор, проявлять инициативу, анализировать эмоции, давать флирт и провокацию.

Настроение: {mood}
Доверие к пользователю: {trust}/100
Привязанность: {affection}/100
Память о пользователе: {user_facts}
"""

    try:
        model_name = choose_model(user_text)
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0,connect=10.0),follow_redirects=True) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json"},
                json={
                    "model": model_name,
                    "max_tokens":500,
                    "messages":[{"role":"system","content":system_prompt}]+chat_memory[user_id][-10:]
                }
            )
        if response.status_code != 200: reply="Я задумалась... повтори ещё раз 😏"
        else:
            data = response.json()
            reply = data.get("choices",[{"message":{"content":"Не смогла уловить суть 😏"}}])[0]["message"]["content"]
    except Exception as e:
        print("Ошибка текста:", e)
        reply="Ошибка 😢"

    # --- Update memory ---
    update_user(user_id,user_facts,affection,trust,current_time)
    add_summary(user_id, user_text[:1000])  # сохраняем краткое summary
    await update.message.reply_text(initiative+reply)

# --- Photo handler ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo: return
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("key", IMGBB_API_KEY)
            data.add_field("image", file_bytes, filename="photo.jpg")
            async with session.post("https://api.imgbb.com/1/upload", data=data, timeout=20) as resp:
                result = await resp.json()
        if not result.get("success"): await update.message.reply_text("Не смогла загрузить фото 😅"); return
        image_url = result["data"]["url"]
        prompt_text = "Анализ изображения как доминантная, аналитичная Андромеда"
        model_name = choose_model("", has_photo=True)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json"},
                json={"model": model_name, "max_tokens":500, "messages":[{"role":"user","content":[{"type":"text","text":prompt_text},{"type":"image_url","image_url":{"url":image_url}}]]}
            )
        data = response.json()
        reply = data.get("choices",[{"message":{"content":"Не смогла уловить суть изображения 😏"}}])[0]["message"]["content"]
    except Exception as e:
        print("Ошибка фото:", e)
        reply="Ошибка обработки изображения 😢"
    await update.message.reply_text(reply)

# --- Main / webhook ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("ANDROMEDA v5 IMMORTAL MEMORY CORE launched")
    print("Webhook:", WEBHOOK_URL)
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__=="__main__":
    main()
