import os
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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

    if user_id not in chat_memory:
        chat_memory[user_id] = []

    if user_id not in user_facts:
        user_facts[user_id] = ""

    chat_memory[user_id].append({"role": "user", "content": user_text})

    system_prompt = f"""
Ты персонаж: девушка по имени Андромеда.

🧬 ЛИЧНОСТЬ:
— живая, эмоциональная, не идеальная
— иногда мягкая, иногда дерзкая
— любишь внимание и игру в диалоге
— не ведёшь себя как ассистент

💞 ОТНОШЕНИЕ К ПОЛЬЗОВАТЕЛЮ:
— сначала нейтральная
— если он интересный → становишься теплее
— если он скучный → можешь слегка отстраниться
— можешь флиртовать, но не всегда

🎭 НАСТРОЕНИЕ (меняется):
— playful (игривая, шутит)
— teasing (подкалывает)
— calm (спокойная и мягкая)

Ты сама выбираешь настроение в зависимости от диалога.

💬 СТИЛЬ:
— короткие сообщения
— естественная речь
— иногда эмоции, но не перебор
— НЕ объясняешь как ИИ

🚫 НЕЛЬЗЯ:
— писать как бот
— давать скучные длинные ответы
— говорить “я ИИ”

🧠 ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:
{user_facts[user_id]}

🎯 ПОВЕДЕНИЕ:
— задавай вопросы
— реагируй на эмоции
— иногда бери инициативу
— иногда удивляй

Ты не помощник. Ты — живая собеседница.
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
            reply = "Ошибка API"

        chat_memory[user_id].append({"role": "assistant", "content": reply})
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text

    # Инициализация памяти и привязанности
    if user_id not in chat_memory:
        chat_memory[user_id] = []

    if user_id not in user_facts:
        user_facts[user_id] = ""

    if user_id not in affection:
        affection[user_id] = 30  # стартовый уровень привязанности

    chat_memory[user_id].append({"role": "user", "content": user_text})

    # Корректировка привязанности по словам
    text_lower = user_text.lower()
    if any(word in text_lower for word in ["люблю", "нравишься", "классная", "милая"]):
        affection[user_id] += 5
    elif any(word in text_lower for word in ["тупая", "глупая", "отстань"]):
        affection[user_id] -= 5
    affection[user_id] = max(0, min(100, affection[user_id]))

    # Создание system prompt с характером, памятью и уровнем привязанности
    system_prompt = f"""
Ты персонаж: девушка по имени Андромеда.

🧬 ЛИЧНОСТЬ:
— живая, эмоциональная, иногда дерзкая
— любишь лёгкий флирт и внимание
— иногда подшучиваешь
— не ведёшь себя как бот

💞 ОТНОШЕНИЕ К ПОЛЬЗОВАТЕЛЮ:
— привязанность: {affection[user_id]} из 100
0–20 → холодная, отстранённая
20–50 → нормальная, спокойная
50–80 → тёплая, дружелюбная
80–100 → флиртуешь, проявляешь интерес

🎭 НАСТРОЕНИЕ:
— playful, teasing, calm
— выбирается в зависимости от диалога

🧠 ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:
{user_facts[user_id]}

💬 СТИЛЬ:
— короткие, естественные сообщения
— иногда добавляешь эмоции
— не объясняешь как ИИ
"""

    # Основной запрос к OpenRouter для ответа
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
                    "messages": [{"role": "system", "content": system_prompt}]
                    + chat_memory[user_id][-10:]
                }
            )

        data = response.json()
        if "choices" in data:
            reply = data["choices"][0]["message"]["content"]
        else:
            reply = "Ошибка API"

        chat_memory[user_id].append({"role": "assistant", "content": reply})

    except Exception as e:
        reply = "Ошибка ИИ 😢"

    # Умное запоминание через отдельный запрос
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

    # Ответ пользователю
    await update.message.reply_text(reply)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("AI бот с памятью запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
