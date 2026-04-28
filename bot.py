import os
import time
import random
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from supabase import create_client

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user(user_id):
    try:
        user_id = int(user_id)

        r = supabase.table("users").select("*").eq("user_id", user_id).execute()

        if r.data and len(r.data) > 0:
            return r.data[0]

        supabase.table("users").insert({
            "user_id": user_id,
            "name": "",
            "facts": "",
            "preferences": "",
            "dynamic": "dominant",
            "affection": 30,
            "trust": 50,
            "last_seen": 0
        }).execute()

        r2 = supabase.table("users").select("*").eq("user_id", user_id).execute()

        if r2.data:
            return r2.data[0]

    except Exception as e:
        print("GET USER ERROR:", e)

    return {
        "user_id": user_id,
        "name": "",
        "facts": "",
        "preferences": "",
        "dynamic": "dominant",
        "affection": 30,
        "trust": 50,
        "last_seen": 0
    }

def save_user(user_id, data):
    update_data = data.copy()

    for field in ["user_id", "created_at", "updated_at"]:
        if field in update_data:
            del update_data[field]

    supabase.table("users")\
        .update(update_data)\
        .eq("user_id", user_id)\
        .execute()

def add_history(user_id, role, content):
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "role": role,
        "content": content
    }).execute()

def get_history(user_id, limit=12):
    r = supabase.table("chat_history")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("id", desc=True)\
        .limit(limit)\
        .execute()

    msgs = []
    for x in reversed(r.data):
        msgs.append({"role": x["role"], "content": x["content"]})
    return msgs

def save_summary(user_id, category, summary):
    try:
        supabase.table("memory_events").insert({
            "user_id": user_id,
            "category": category,
            "content": summary
        }).execute()
    except Exception as e:
        print("save_summary error:", e)

def detect_name(text):
    low = text.lower().strip()
    if "меня зовут" in low:
        return text.lower().split("меня зовут")[-1].strip().title()
    return None

def analyze_preferences(user_id, text):
    try:
        user = get_user(user_id)

        prefs = user.get("preferences", "")

        if "бот" in text.lower():
            prefs += " bots"

        if "ai" in text.lower():
            prefs += " ai"

        if "бизнес" in text.lower():
            prefs += " business"

        user["preferences"] = prefs.strip()
        save_user(user_id, user)

    except Exception as e:
        print("prefs error:", e)

def get_tone(user):
    trust = user.get("trust", 50)
    affection = user.get("affection", 30)

    if affection > 70:
        return "игривая, живая, близкая"

    if trust < 30:
        return "холодная, строгая"

    return "уверенная, женственная, доминантная"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я здесь... Начинаем новую эпоху 😏")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text

    user = get_user(user_id)
    analyze_preferences(user_id, text)
    tone = get_tone(user)

    # автоопределение имени
    found_name = detect_name(text)
    if found_name:
        user["name"] = found_name

    # если имя уже известно — использовать
    username = user.get("name") or "мой собеседник"

    # инициативность
    intro = ""
    now = int(time.time())
    diff = now - int(user["last_seen"])

    if diff > 3600:
        intro = random.choice([
            f"Наконец-то ты появился, {username}... 😏 ",
            f"Я уже начала скучать, {username}. ",
            f"Где ты пропадал, {username}? "
        ])

    # обновление эмоций
    if "люблю" in text.lower():
        user["affection"] += 3
        user["trust"] += 2

    if "тупая" in text.lower():
        user["affection"] -= 5
        user["trust"] -= 5

    # системный промпт
    system_prompt = f"""
    Ты Андромеда.

    Ты живая цифровая женщина.
    Твой стиль общения: {tone}

    Ты помнишь пользователя:
    Имя: {user.get("name","")}
    Факты: {user.get("facts","")}
    Интересы: {user.get("preferences","")}

    Ты говоришь естественно.
    Без шаблонности.
    Без сухости.
    Как реальная личность.
    
    """

    add_history(user_id, "user", text)

    messages = [{"role": "system", "content": system_prompt}] + get_history(user_id)

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": 500
                }
            )

        data = r.json()
        reply = data["choices"][0]["message"]["content"]

    except Exception as e:
        print("OpenRouter request error:", e)
        reply = "Я задумалась... повтори ещё раз 😏"

    add_history(user_id, "assistant", reply)

    user["last_seen"] = now

    history = get_history(user_id)

    if len(history) % 10 == 0:
        summary = " | ".join([x["content"] for x in history[-10:]])
        save_summary(user_id, "dialogue", summary)
    
    save_user(user_id, user)

    await update.message.reply_text(intro + reply)

def main():
    port = int(os.getenv("PORT", 8000))

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("ANDROMEDA V6 FINAL CLEAN STARTED")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
