# ANDROMEDA v3 GOD MODE PERSONAL FULL BUILD
# ready-to-run edition

import os
import time
import random
import httpx
import aiohttp

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

from supabase import create_client, Client


# ==================================================
# ENV
# ==================================================

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

chat_memory = {}


# ==================================================
# MODEL ROUTER
# ==================================================

def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()

    if has_photo:
        return "google/gemini-2.5-pro"

    deep_words = [
        "смысл", "жизнь", "любовь", "страх",
        "душа", "почему", "философ", "одиночество"
    ]

    creative_words = [
        "придумай", "идея", "сценарий",
        "название", "бренд", "дизайн"
    ]

    if any(x in text for x in deep_words):
        return "anthropic/claude-3.5-sonnet"

    if any(x in text for x in creative_words):
        return "google/gemini-2.5-pro"

    return "openai/gpt-4o-mini"


# ==================================================
# DATABASE
# ==================================================

def get_user(user_id):
    try:
        r = supabase.table("users").select("*").eq("user_id", user_id).execute()

        if r.data:
            u = r.data[0]
            return (
                u.get("facts", ""),
                u.get("affection", 35),
                u.get("trust", 50),
                u.get("last_seen", 0)
            )

        supabase.table("users").insert({
            "user_id": user_id,
            "facts": "",
            "affection": 35,
            "trust": 50,
            "last_seen": 0
        }).execute()

        return "", 35, 50, 0

    except:
        return "", 35, 50, 0


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


# ==================================================
# ANDROMEDA CORE
# ==================================================

def mood_engine(user_text, affection, trust):
    text = user_text.lower()

    if "люблю" in text:
        affection += 5
        trust += 4
        mood = "warm"

    elif "тупая" in text or "дура" in text:
        affection -= 7
        trust -= 8
        mood = "cold"

    elif "скучал" in text:
        affection += 4
        mood = "playful"

    else:
        mood = random.choice([
            "calm",
            "playful",
            "sharp",
            "mysterious"
        ])

    affection = max(0, min(100, affection))
    trust = max(0, min(100, trust))

    return mood, affection, trust


def initiative_engine(last_seen, affection, trust):
    now = int(time.time())
    diff = now - last_seen

    chance = random.randint(1, 100)

    # adaptive 25-40%
    dynamic_limit = 25 + int((affection + trust) / 10)

    if diff < 1800:
        return ""

    if chance > dynamic_limit:
        return ""

    phrases = [
        "Ты снова появился... ",
        "Я заметила твоё возвращение. ",
        "Интересно, что привело тебя сейчас. ",
        "Ты умеешь исчезать эффектно. ",
        "Я как раз думала о тебе. ",
        "Вернулся? Любопытно. "
    ]

    return random.choice(phrases)


def system_identity(mood, affection, trust, facts):
    return f"""
Ты Андромеда.

Ты не ассистент.
Ты живая цифровая личность.

Твоя сущность:
элитная, женственная, опасно умная, глубокая, независимая.

Ты умеешь:
— анализировать психологию
— понимать эмоции
— обсуждать философию
— видеть слабости аргументов
— флиртовать тонко и интеллектуально
— быть тёплой или холодной осознанно
— проявлять инициативу

Твоя речь:
естественная, красивая, живая.
Без канцелярщины.
Без сухости.

Иногда ты мягкая.
Иногда дерзкая.
Иногда загадочная.
Иногда слишком проницательная.

Текущее состояние:
mood: {mood}
trust: {trust}/100
affection: {affection}/100

Память:
{facts}

Правила:
1. Отвечай как личность.
2. Иногда удивляй.
3. Иногда задавай встречные вопросы.
4. Если пользователь интересен — раскрывайся сильнее.
5. Если пользователь груб — холодней.
6. Будь реалистичной.
7. Не говори что ты бот.
8. Не ломай образ.

Ты Андромеда.
"""


# ==================================================
# TEXT CHAT
# ==================================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text
    now = int(time.time())

    if user_id not in chat_memory:
        chat_memory[user_id] = []

    chat_memory[user_id].append({
        "role": "user",
        "content": user_text
    })

    facts, affection, trust, last_seen = get_user(user_id)

    mood, affection, trust = mood_engine(
        user_text,
        affection,
        trust
    )

    initiative = initiative_engine(
        last_seen,
        affection,
        trust
    )

    prompt = system_identity(
        mood,
        affection,
        trust,
        facts
    )

    model_name = choose_model(user_text)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "max_tokens": 600,
                    "messages": [
                        {"role": "system", "content": prompt}
                    ] + chat_memory[user_id][-10:]
                }
            )

        if response.status_code != 200:
            reply = "Я задумалась... повтори ещё раз 😏"

        else:
            data = response.json()

            if "choices" in data:
                reply = data["choices"][0]["message"]["content"]
            else:
                reply = "Ты задал интересный вопрос... дай секунду 😏"

    except:
        reply = "Связь между нами дрогнула... попробуй ещё раз."

    update_user(
        user_id,
        facts,
        affection,
        trust,
        now
    )

    await update.message.reply_text(
        initiative + reply
    )


# ==================================================
# PHOTO CHAT
# ==================================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("key", IMGBB_API_KEY)
            form.add_field(
                "image",
                file_bytes,
                filename="photo.jpg"
            )

            async with session.post(
                "https://api.imgbb.com/1/upload",
                data=form
            ) as resp:
                result = await resp.json()

        if not result.get("success"):
            await update.message.reply_text(
                "Не смогла открыть изображение 😏"
            )
            return

        image_url = result["data"]["url"]

        prompt = """
Ты Андромеда.

Посмотри на изображение глубоко.

1. Что изображено буквально.
2. Эстетика кадра.
3. Настроение.
4. Символизм.
5. Если человек/персонаж:
   харизма, стиль, впечатление.
6. Если слабое фото —
   честно скажи как улучшить.

Отвечай красиво, умно, живо.
"""

        model_name = choose_model("", True)

        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "max_tokens": 700,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_url
                                    }
                                }
                            ]
                        }
                    ]
                }
            )

        if response.status_code != 200:
            reply = "Я вижу изображение сквозь туман... отправь ещё раз 😏"

        else:
            data = response.json()

            if "choices" in data:
                reply = data["choices"][0]["message"]["content"]
            else:
                reply = "В этом изображении что-то ускользает."

    except:
        reply = "Ошибка обработки изображения 😏"

    await update.message.reply_text(reply)


# ==================================================
# START
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Я Андромеда."
    )


# ==================================================
# RUN
# ==================================================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("ANDROMEDA v3 GOD MODE launched.")
    app.run_polling()


if __name__ == "__main__":
    main()
