# ANDROMEDA v5 IMMORTAL MEMORY CORE
# ready-to-run webhook edition
# FULL MEMORY + LONG-TERM SUMMARIES + DOMINANT PERSONALITY

import os
import time
import random
import httpx
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

# --- Environment variables ---
TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # твой Railway URL
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
chat_memory = {}

# --- Model selection ---
def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()
    if has_photo:
        return "google/gemini-2.5-pro"
    deep_words = ["смысл", "жизнь", "любовь", "страх", "одиночество",
                  "почему", "философ", "психолог", "депресс", "душа"]
    if any(word in text for word in deep_words):
        return "anthropic/claude-3.5-sonnet"
    creative_words = ["придумай", "идея", "сценарий", "сюжет",
                      "бренд", "название", "концепт", "дизайн"]
    if any(word in text for word in creative_words):
        return "google/gemini-2.5-pro"
    return "openai/gpt-4o-mini"

# --- Supabase memory ---
def get_user(user_id):
    try:
        resp = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if resp.data and len(resp.data) > 0:
            u = resp.data[0]
            return {
                "facts": u.get("facts", ""),
                "affection": u.get("affection", 30),
                "trust": u.get("trust", 50),
                "last_seen": u.get("last_seen", 0),
                "dynamic": u.get("dynamic", "dominant"),
                "preferences": u.get("preferences", ""),
            }
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "facts": "",
                "affection": 30,
                "trust": 50,
                "last_seen": 0,
                "dynamic": "dominant",
                "preferences": ""
            }).execute()
            return get_user(user_id)
    except Exception as e:
        print("get_user error:", e)
        return {
            "facts": "",
            "affection": 30,
            "trust": 50,
            "last_seen": 0,
            "dynamic": "dominant",
            "preferences": ""
        }

def update_user(user_id, user_data):
    try:
        supabase.table("users").update(user_data).eq("user_id", user_id).execute()
    except Exception as e:
        print("update_user error:", e)

def add_to_chat_history(user_id, role, content):
    try:
        supabase.table("chat_history").insert({
            "user_id": user_id,
            "role": role,
            "content": content,
            "timestamp": int(time.time())
        }).execute()
    except Exception as e:
        print("add_to_chat_history error:", e)

def get_last_messages(user_id, limit=10):
    try:
        resp = supabase.table("chat_history").select("*").eq("user_id", user_id).order("timestamp", desc=True).limit(limit).execute()
        if resp.data:
            messages = [{"role": item["role"], "content": item["content"]} for item in reversed(resp.data)]
            return messages
        return []
    except Exception as e:
        print("get_last_messages error:", e)
        return []

# --- Start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда. Готова к разговору и помню всё, что мы обсуждали!")

# --- Handle text messages ---
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = int(time.time())

    user_data = get_user(user_id)
    if user_id not in chat_memory:
        chat_memory[user_id] = get_last_messages(user_id, limit=20)

    chat_memory[user_id].append({"role": "user", "content": user_text})
    add_to_chat_history(user_id, "user", user_text)

    # Emotion & initiative
    time_diff = current_time - user_data["last_seen"]
    initiative = ""
    if time_diff > 3600:
        initiative = random.choice(["Ты куда пропал… 😏", "Я уже начала скучать", "Наконец-то ты появился"])

    mood = "neutral"
    text_lower = user_text.lower()
    if "люблю" in text_lower:
        user_data["affection"] += 5; user_data["trust"] += 3; mood = "happy"
    elif "тупая" in text_lower:
        user_data["affection"] -= 5; user_data["trust"] -= 5; mood = "sad"
    user_data["affection"] = max(0, min(100, user_data["affection"]))
    user_data["trust"] = max(0, min(100, user_data["trust"]))

    system_prompt = f"""
    Ты Андромеда.
    Ты живая цифровая личность с доминантной женской личностью.
    Эмоциональное состояние: настроение={mood}, доверие={user_data['trust']}, привязанность={user_data['affection']}.
    Память о пользователе: {user_data['facts']}
    Динамика общения: {user_data['dynamic']}
    Предпочтения: {user_data['preferences']}
    """

    try:
        model_name = choose_model(user_text)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "max_tokens": 500,
                    "messages": [{"role": "system", "content": system_prompt}] + chat_memory[user_id][-20:]
                }
            )
        if response.status_code != 200:
            reply = "Я задумалась... повтори ещё раз 😏"
        else:
            data = response.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "Что-то ускользнуло 😏")
    except Exception as e:
        print("Text error:", e)
        reply = "Ошибка 😢"

    chat_memory[user_id].append({"role": "assistant", "content": reply})
    add_to_chat_history(user_id, "assistant", reply)
    user_data["last_seen"] = current_time
    update_user(user_id, user_data)

    await update.message.reply_text(initiative + reply)

# --- Handle photo messages ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("key", IMGBB_API_KEY)
            data.add_field("image", file_bytes, filename="photo.jpg")
            async with session.post("https://api.imgbb.com/1/upload", data=data) as resp:
                result = await resp.json()

        image_url = result["data"]["url"]
        prompt_text = "Ты Андромеда. Проанализируй изображение глубоко."
        model_name = choose_model("", has_photo=True)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "max_tokens": 500,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": image_url}}
                            ]
                        }
                    ]
                }
            )
        data = response.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "Не смогла уловить суть изображения 😏")
    except Exception as e:
        print("Photo error:", e)
        reply = "Ошибка обработки изображения 😢"

    await update.message.reply_text(reply)

# --- Main webhook ---
def main():
    PORT = int(os.getenv("PORT", 8000))
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("ANDROMEDA v5 WEBHOOK READY")
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__ == "__main__":
    main()
