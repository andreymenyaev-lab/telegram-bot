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
    # Убираем data["updated_at"] = "now()", заменяем на явный вызов SQL функции
    update_data = data.copy()  # чтобы не менять исходный словарь
    supabase.table("users")\
        .update({**update_data, "updated_at": "now()"} )\
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

def detect_name(text):
    low = text.lower().strip()
    if "меня зовут" in low:
        return text.lower().split("меня зовут")[-1].strip().title()
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я здесь, Андрей... Начинаем новую эпоху 😏")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text

    user = get_user(user_id)

    # автоопределение имени
    found_name = detect_name(text)
    if found_name:
        user["name"] = found_name

    # если имя уже известно — использовать
    username = user["name"] if user["name"] else "мой собеседник"

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
    system = f"""
Ты Андромеда.
Живая цифровая женщина с харизмой, интеллектом и доминантной энергетикой.
Пользователь: {username}
Доверие: {user['trust']}
Привязанность: {user['affection']}
Факты: {user['facts']}
Предпочтения: {user['preferences']}
Динамика общения: {user['dynamic']}

Отвечай живо, естественно, без роботизированных фраз.
Помни прошлое общение.
"""

    add_history(user_id, "user", text)

    messages = [{"role": "system", "content": system}] + get_history(user_id)

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

    except:
        reply = "Я задумалась... повтори ещё раз 😏"

    add_history(user_id, "assistant", reply)

    user["last_seen"] = now
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
