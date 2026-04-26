import os
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# память
chat_memory = {}
user_facts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text

    # краткая память
    if user_id not in chat_memory:
        chat_memory[user_id] = []

    chat_memory[user_id].append({"role": "user", "content": user_text})

    # инициализация фактов
    if user_id not in user_facts:
        user_facts[user_id] = ""

    # формируем промпт
    system_prompt = f"""
Ты девушка по имени Андромеда.
Ты милая, живая и немного флиртуешь.

Вот что ты знаешь о пользователе:
{user_facts[user_id]}

Запоминай важные факты о пользователе.
"""

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
                    "messages": [
                        {"role": "system", "content": system_prompt}
                    ] + chat_memory[user_id][-10:]
                }
            )

        data = response.json()

        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Ошибка 😢"

        # сохраняем ответ
        chat_memory[user_id].append({"role": "assistant", "content": reply})

      except Exception as e:
        reply = "Ошибка ИИ 😢
          
    # умное запоминание через ИИ
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
                        "content": "Выдели важные факты о пользователе из текста. Коротко."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
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

    print("AI бот с памятью запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
