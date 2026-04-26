import os
import httpx
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
            return user.get("facts", ""), user.get("affection", 30)
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "facts": "",
                "affection": 30
            }).execute()
            return "", 30
    except Exception as e:
        print("Ошибка get_user:", e)
        return "", 30


def update_user(user_id, facts, affection):
    try:
        supabase.table("users").update({
            "facts": facts,
            "affection": affection
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

    user_id = update.message.from_user.id
    user_text = update.message.text

    if user_id not in chat_memory:
        chat_memory[user_id] = []

    chat_memory[user_id].append({"role": "user", "content": user_text})

    user_facts, affection = get_user(user_id)

    # --- ПРИВЯЗАННОСТЬ ---
    text_lower = user_text.lower()

    if any(word in text_lower for word in ["люблю", "нравишься", "классная", "милая"]):
        affection += 5
    elif any(word in text_lower for word in ["тупая", "глупая", "отстань"]):
        affection -= 5

    affection = max(0, min(100, affection))

    # --- ПРОМПТ ---
    system_prompt = f"""
Ты девушка по имени Андромеда.

Характер:
— живая, эмоциональная, иногда дерзкая
— любишь внимание и лёгкий флирт

Отношение:
— привязанность: {affection}/100
0–20 холодная
20–50 спокойная
50–80 тёплая
80–100 флиртующая

Память:
{user_facts}

Стиль:
— короткие ответы
— живые эмоции
— не говоришь что ты ИИ
"""

    # --- ОТВЕТ ---
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "system", "content": system_prompt}] + chat_memory[user_id][-10:]
                }
            )

        data = response.json()

        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Ошибка API"

        chat_memory[user_id].append({"role": "assistant", "content": reply})

    except Exception as e:
        print("Ошибка ответа:", e)
        reply = "Ошибка ИИ 😢"

# --- ПАМЯТЬ 3.0 (СТРУКТУРНАЯ) ---
try:
    async with httpx.AsyncClient() as client:
        memory_response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": f"""
Ты система долгосрочной памяти.

Вот текущая память:
{user_facts}

Новое сообщение пользователя:
{user_text}

Твоя задача:
— выделить только важные факты
— обновить существующие
— не дублировать
— писать СТРУКТУРИРОВАННО

Формат строго:

Имя:
Интересы:
Цели:
Особенности:

Если информации нет — оставь поле пустым.
"""
                    }
                ]
            }
        )

    memory_data = memory_response.json()

    if "choices" in memory_data:
        user_facts = memory_data["choices"][0]["message"]["content"]

except Exception as e:
    print("Ошибка памяти:", e)

    update_user(user_id, user_facts, affection)

    await update.message.reply_text(reply)


# --- ЗАПУСК ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Бот с памятью 2.0 запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
