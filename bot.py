import os
import httpx
import random
import base64
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

chat_memory = {}

# --- БАЗА ---
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


# --- СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда")


# --- ОСНОВНАЯ ЛОГИКА ---
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if update.message.photo:
        await update.message.reply_text("Я пока не умею смотреть картинки 😅 Но можешь описать её?")
        return

    user_id = update.message.from_user.id
    user_text = update.message.text
    current_time = int(time.time())

    if user_id not in chat_memory:
        chat_memory[user_id] = []

    chat_memory[user_id].append({"role": "user", "content": user_text})

    user_facts, affection, trust, last_seen = get_user(user_id)

    # --- ПРОВЕРКА ПАУЗЫ ---
    time_diff = current_time - last_seen
    initiative = ""

    if time_diff > 3600:  # больше часа
        if affection > 70:
            phrases = [
                "Ты куда пропал… 😏 ",
                "Я уже начала скучать ",
                "Наконец-то ты появился ",
                "Я думала ты забыл про меня "
            ]
        elif affection > 40:
            phrases = [
                "Давно тебя не было ",
                "О, ты снова тут ",
                "Пропадал где-то? ",
                "Ну привет, исчезающий "
            ]
        else:
            phrases = [
                "Ты снова здесь ",
                "Ну ладно, вернулся ",
                "Опять ты ",
                "Хм, интересно "
            ]

        initiative = random.choice(phrases)

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

    # --- ПРОМПТ ---
    system_prompt = f"""
Ты девушка по имени Андромеда.

Эмоции:
настроение: {mood}
доверие: {trust}
привязанность: {affection}

Память:
{user_facts}

Стиль:
живая, немного дерзкая, иногда флирт
"""

    # --- ОТВЕТ ---
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(25.0, connect=10.0),
            follow_redirects=True
        ) as client:
            
            response = await client.post(

            print("OPENROUTER CONNECTED")
                
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o",
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

        print("OPENROUTER STATUS:", response.status_code)
        print("OPENROUTER TEXT:", response.text)

        data = response.json()
        print("OPENROUTER RESPONSE:", data)

        if "choices" in data and data["choices"]:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Не смогла понять изображение 😅"

        data = response.json()
        print("OPENROUTER RESPONSE:", data)

        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Ошибка"

    except Exception as e:
        print(e)
        reply = "Ошибка 😢"

    # --- ОБНОВЛЕНИЕ ВРЕМЕНИ ---
    update_user(user_id, user_facts, affection, trust, current_time)

    await update.message.reply_text(initiative + reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("PHOTO HANDLER TRIGGERED")

    import aiohttp

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        # загрузка на imgbb
        imgbb_api_key = os.getenv("IMGBB_API_KEY")

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("key", imgbb_api_key)
            data.add_field("image", file_bytes, filename="photo.jpg")

            async with session.post(
                "https://api.imgbb.com/1/upload",
                data=data,
                timeout=20
            ) as resp:

                print("IMGBB STATUS:", resp.status)
                result = await resp.json()

        if not result.get("success"):
            await update.message.reply_text("Не смогла загрузить фото 😅")
            return

        image_url = result["data"]["url"]

        prompt_text = (
            "Опиши подробно что изображено на фото. "
            "Затем добавь дружелюбную реакцию."
        )

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o",
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

        print("OPENROUTER STATUS:", response.status_code)
        print("OPENROUTER TEXT:", response.text)

        data = response.json()

        if "choices" in data and data["choices"]:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Не смогла понять изображение 😅"

    except Exception as e:
        print("Ошибка фото:", e)
        reply = "Ошибка обработки изображения 😢"

    await update.message.reply_text(reply)

# --- ЗАПУСК ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Андромеда (реакция на отсутствие) запущена...")
    app.run_polling()


if __name__ == "__main__":
    main()
