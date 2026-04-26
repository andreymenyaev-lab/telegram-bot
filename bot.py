import os
import httpx
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

chat_memory = {}

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    facts TEXT,
    affection INTEGER
)
""")
conn.commit()

def get_user(user_id):
    cursor.execute("SELECT facts, affection FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row:
        return row[0] or "", row[1] or 30
    else:
        cursor.execute("INSERT INTO users (user_id, facts, affection) VALUES (?, ?, ?)",
                       (user_id, "", 30))
        conn.commit()
        return "", 30

def update_user(user_id, facts, affection):
    cursor.execute("UPDATE users SET facts=?, affection=? WHERE user_id=?",
                   (facts, affection, user_id))
    conn.commit()

# --- КОМАНДА СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Привет 😊 Я Андромеда")

# --- ОСНОВНАЯ ЛОГИКА ---
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text

    # краткая память
    if user_id not in chat_memory:
        chat_memory[user_id] = []

    chat_memory[user_id].append({"role": "user", "content": user_text})

    # загрузка из БД
    user_facts, affection = get_user(user_id)

    # изменение привязанности
    text_lower = user_text.lower()

    if any(word in text_lower for word in ["люблю", "нравишься", "классная", "милая"]):
        affection += 5
    elif any(word in text_lower for word in ["тупая", "глупая", "отстань"]):
        affection -= 5

    affection = max(0, min(100, affection))

    # SYSTEM PROMPT
    system_prompt = f"""
Ты девушка по имени Андромеда.

Личность:
— живая, эмоциональная, иногда дерзкая
— любишь внимание и лёгкий флирт
— иногда подшучиваешь

Отношение:
— уровень привязанности: {affection}/100
0–20: холодная
20–50: спокойная
50–80: тёплая
80–100: флиртующая

Память:
{user_facts}

Стиль:
— короткие, живые ответы
— не говоришь что ты ИИ
"""

    # ответ
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

    # умная память
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
            user_facts += fact + "\n"

    except:
        pass

    # сохраняем в БД
    update_user(user_id, user_facts, affection)

    await update.message.reply_text(reply)

# --- ЗАПУСК ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("Бот с БД запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
