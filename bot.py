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
            return (
                user.get("facts", ""),
                user.get("affection", 30),
                user.get("trust", 50)
            )
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "facts": "",
                "affection": 30,
                "trust": 50
            }).execute()
            return "", 30, 50
    except Exception as e:
        print("Ошибка get_user:", e)
        return "", 30, 50


def update_user(user_id, facts, affection, trust):
    try:
        supabase.table("users").update({
            "facts": facts,
            "affection": affection,
            "trust": trust
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

    user_facts, affection, trust = get_user(user_id)

    # --- ЭМОЦИИ ---
    mood = "neutral"
    text_lower = user_text.lower()

    if any(word in text_lower for word in ["люблю", "нравишься", "классная", "милая"]):
        affection += 5
        trust += 3
        mood = "happy"

    elif any(word in text_lower for word in ["тупая", "глупая", "отстань"]):
        affection -= 5
        trust -= 5
        mood = "sad"

    elif any(word in text_lower for word in ["привет", "как дела"]):
        mood = "playful"

    affection = max(0, min(100, affection))
    trust = max(0, min(100, trust))

    # --- ПРОМПТ ---
    system_prompt = f"""
Ты девушка по имени Андромеда.

Характер:
— живая, эмоциональная, иногда дерзкая
— любишь внимание и лёгкий флирт

ЭМОЦИИ:
— настроение: {mood}
— доверие: {trust}/100
— привязанность: {affection}/100

Поведение:
— низкое доверие → осторожная
— среднее → дружелюбная
— высокое → открытая и личная

Настроение влияет на стиль:
— happy → теплая, милая
— sad → холоднее
— playful → игривая

Память:
{user_facts}

Стиль:
— короткие ответы
— эмоции (😊 😏 😈)
— не говоришь что ты ИИ
"""

    # --- ОТВЕТ ---
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": "Bearer " + str(OPENROUTER_API_KEY),
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

    # --- ПАМЯТЬ ---
    try:
        async with httpx.AsyncClient() as client:
            prompt_text = "Обнови память:\n" + str(user_facts) + "\nНовое:\n" + str(user_text)

            memory_response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": "Bearer " + str(OPENROUTER_API_KEY),
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "system", "content": prompt_text}]
                }
            )

        memory_data = memory_response.json()

        if "choices" in memory_data:
            user_facts = memory_data["choices"][0]["message"]["content"]

    except Exception as e:
        print("Ошибка памяти:", e)

    update_user(user_id, user_facts, affection, trust)

    await update.message.reply_text(reply)


# --- ЗАПУСК ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Бот с эмоциями 3.0 запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
