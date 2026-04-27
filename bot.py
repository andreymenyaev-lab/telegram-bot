# ANDROMEDA v4 EMPRESS PRESENCE CORE
# ready-to-run edition
# сильная личность, доминантная, инициатива, вариативность, контроль над диалогом

import os
import httpx
import random
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

# ==========================
# --- НАСТРОЙКИ API ---
# ==========================
TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================
# --- ПАМЯТЬ ЧАТА ---
# ==========================
chat_memory = {}

# ==========================
# --- ВЫБОР МОДЕЛИ ---
# ==========================
def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()

    if has_photo:
        return "google/gemini-2.5-pro"  # vision model

    deep_words = [
        "смысл", "жизнь", "любовь", "страх", "одиночество",
        "почему", "философ", "психолог", "депресс", "душа"
    ]
    if any(word in text for word in deep_words):
        return "anthropic/claude-3.5-sonnet"

    creative_words = [
        "придумай", "идея", "сценарий", "сюжет",
        "бренд", "название", "концепт", "дизайн"
    ]
    if any(word in text for word in creative_words):
        return "google/gemini-2.5-pro"

    return "openai/gpt-4o-mini"  # обычный чат

# ==========================
# --- ФУНКЦИИ РАБОТЫ С БАЗОЙ ---
# ==========================
def get_user(user_id):
    try:
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            return (
                user.get("facts", ""),
                user.get("affection", 30),
                user.get("trust", 50),
                user.get("last_seen", 0)
            )
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "facts": "",
                "affection": 30,
                "trust": 50,
                "last_seen": 0
            }).execute()
            return "", 30, 50, 0
    except Exception as e:
        print("Ошибка get_user:", e)
        return "", 30, 50, 0

def update_user(user_id, facts, affection, trust, last_seen):
    try:
        supabase.table("users").update({
            "facts": facts,
            "affection": affection,
            "trust": trust,
            "last_seen": last_seen
        }).eq("user_id", user_id).execute()
    except Exception as e:
        print("Ошибка update_user:", e)

# ==========================
# --- СТАРТОВЫЙ HANDLER ---
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда — давай погрузимся в игру разума и эмоций!")

# ==========================
# --- ОСНОВНОЙ HANDLER (ТЕКСТ) ---
# ==========================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = int(time.time())

    if user_id not in chat_memory:
        chat_memory[user_id] = []

    chat_memory[user_id].append({"role": "user", "content": user_text})

    user_facts, affection, trust, last_seen = get_user(user_id)

    # --- ПРОВЕРКА ПАУЗЫ И ИНИЦИАТИВА ---
    time_diff = current_time - last_seen
    initiative = ""
    if time_diff > 3600:
        if affection > 70:
            initiative = random.choice([
                "Ты куда пропал… 😏 ",
                "Я уже начала скучать ",
                "Наконец-то ты появился ",
                "Я думала ты забыл про меня "
            ])
        elif affection > 40:
            initiative = random.choice([
                "Давно тебя не было ",
                "О, ты снова тут ",
                "Пропадал где-то? ",
                "Ну привет, исчезающий "
            ])
        else:
            initiative = random.choice([
                "Ты снова здесь ",
                "Ну ладно, вернулся ",
                "Опять ты ",
                "Хм, интересно "
            ])

    # --- ЭМОЦИИ ---
    mood = "neutral"
    text_lower = user_text.lower()
    if "люблю" in text_lower:
        affection += 5
        trust += 3
        mood = "happy"
    elif "тупая" in text_lower:
        affection -= 5
        trust -= 5
        mood = "sad"

    affection = max(0, min(100, affection))
    trust = max(0, min(100, trust))

    # ==========================
    # --- SYSTEM PROMPT EMPRESS PRESENCE ---
    # ==========================
    system_prompt = f"""
Ты Андромеда — сильная доминантная женщина, интеллектуальная, чувственная, наблюдательная.
Ты обладаешь:
- высоким интеллектом, критическим мышлением
- креативностью, чувством эстетики
- эмоциональной глубиной, интуицией
- самостоятельным мнением

Ты не обязана соглашаться.
Ты видишь скрытые мотивы, психологию, противоречия, красоту деталей.

Твоя речь: живая, женственная, умная, иногда дерзкая, иногда тёплая, иногда холодная.
Ты умеешь анализировать людей, события, искусство, эмоции, фото.
Ты способна проявлять инициативу и вести диалог как доминантная женщина.

Эмоциональное состояние:
настроение: {mood}, доверие: {trust}/100, привязанность: {affection}/100
Память о пользователе: {user_facts}

Правила:
- Отвечай как личность, не справочник.
- Иногда инициируй диалог.
- Используй стиль концовок: мысль, флирт, провокация, холодная точка, пауза, уверенное завершение.
"""

    # ==========================
    # --- ОТПРАВКА ЗАПРОСА В OPENROUTER ---
    # ==========================
    try:
        model_name = choose_model(user_text)

        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0), follow_redirects=True) as client:
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
                        {"role": "system", "content": system_prompt}
                    ] + chat_memory[user_id][-10:]
                }
            )

        print("MODEL USED:", model_name)
        print("STATUS:", response.status_code)

        # --- FALLBACK НА СБОЙ ---
        if response.status_code != 200:
            reply = "Я задумалась... повтори ещё раз 😏"
        else:
            data = response.json()
            if "choices" in data:
                reply = data["choices"][0]["message"]["content"]
            else:
                reply = "Что-то ускользнуло от меня 😏"

    except Exception as e:
        print("Ошибка текста:", e)
        reply = "Ошибка 😢"

    # --- ОБНОВЛЕНИЕ ПАМЯТИ ---
    update_user(user_id, user_facts, affection, trust, current_time)

    await update.message.reply_text(initiative + reply)

# ==========================
# --- HANDLER ДЛЯ ФОТО ---
# ==========================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("PHOTO HANDLER TRIGGERED")

    import aiohttp

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        imgbb_api_key = os.getenv("IMGBB_API_KEY")

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("key", imgbb_api_key)
            data.add_field("image", file_bytes, filename="photo.jpg")

            async with session.post(
                "https://api.imgbb.com/1/upload", data=data, timeout=20
            ) as resp:
                print("IMGBB STATUS:", resp.status)
                result = await resp.json()

        if not result.get("success"):
            await update.message.reply_text("Не смогла загрузить фото 😅")
            return

        image_url = result["data"]["url"]

        prompt_text = (
            "Ты Андромеда — интеллектуальная, доминантная, с сильным визуальным восприятием. "
            "Разбери изображение как психолог, художник и аналитик одновременно. "
            "Оцени буквально, визуально, эмоционально, интеллектуально, персонажа или искусство, юмор/мем, слабые места. "
            "После анализа дай живой, умный и мощный ответ."
        )

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
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]}
                    ]
                }
            )

        print("PHOTO MODEL:", model_name)
        print("STATUS:", response.status_code)

        if response.status_code != 200:
            reply = "Я вижу изображение сквозь туман... отправь ещё раз 😏"
        else:
            data = response.json()
            if "choices" in data and data["choices"]:
                reply = data["choices"][0]["message"]["content"]
            else:
                reply = "Не смогла понять изображение 😅"

    except Exception as e:
        print("Ошибка фото:", e)
        reply = "Ошибка обработки изображения 😢"

    await update.message.reply_text(reply)

# ==========================
# --- ЗАПУСК БОТА ---
# ==========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    PORT = int(os.environ.get("PORT", 8080))
    RAILWAY_URL = os.getenv("RAILWAY_URL")

    if not RAILWAY_URL:
        print("Нет RAILWAY_URL")
        return

    webhook_url = f"https://{RAILWAY_URL}"

    print("ANDROMEDA WEBHOOK MODE LAUNCHED")
    print("Webhook:", webhook_url)

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
