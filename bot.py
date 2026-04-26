import os
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

chat_memory = {}
user_facts = {}
affection = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text

    # Инициализация
    if user_id not in chat_memory:
        chat_memory[user_id] = []

    if user_id not in user_facts:
        user_facts[user_id] = ""

    if user_id not in affection:
        affection[user_id] = 30

    chat_memory[user_id].append({"role": "user", "content": user_text})

    # Обновление привязанности
    text_lower = user_text.lower()

    if any(word in text_lower for word in ["люблю", "нравишься", "классная", "милая"]):
        affection[user_id] += 5
    elif any(word in text_lower for word in ["тупая", "глупая", "отстань"]):
        affection[user_id] -= 5

    affection[user_id] = max(0, min(100, affection[user_id]))

    # SYSTEM PROMPT
    system_prompt = f"""
Ты девушка по имени Андромеда.

Личность:
— живая, эмоциональная, иногда дерзкая
— любишь внимание и лёгкий флирт
— иногда подшучиваешь
— не ведёшь себя как бот

Отношение к пользователю:
— уровень привязанности: {affection[user_id]} из 100
0–20: холодная
20–50: спокойная
50–80: тёплая
80–100: флиртующая и заинтересованная

Настроение:
— playful, teasing, calm
— выбираешь сама по ситуации

Память о пользователе:
{user_facts[user_id]}

Стиль:
— короткие, живые сообщения
— иногда эмоции
— не говоришь что ты ИИ
"""

    # Основной ответ
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

    except Exception:
        reply = "Ошибка ИИ 😢"

    # Умная память
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
                        {"role": "system", "content": "Выдели важные факты о пользователе кратко."},
                        {"role": "user", "content": user_text}
                    ]
                }
            )

        memory_data = memory_response.json()

        if "choices" in memory_data:
            fact = memory_data["choices"][0]["message"]["content"]
            user_facts[user_id] += fact + "\n"

    except:
        pass

    await update.message.reply_text(reply)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Бот с характером и памятью запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
