import os
import httpx
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    try:
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()

        print("GET RESPONSE:", response)

        if response.data and len(response.data) > 0:
            user = response.data[0]
            return user.get("facts", ""), user.get("affection", 30)
        else:
            insert = supabase.table("users").insert({
                "user_id": user_id,
                "facts": "",
                "affection": 30
            }).execute()

            print("INSERT RESPONSE:", insert)

            return "", 30

    except Exception as e:
        print("Ошибка get_user:", e)
        return "", 30

def update_user(user_id, facts, affection):
    try:
        response = supabase.table("users").update({
            "facts": facts,
            "affection": affection
        }).eq("user_id", user_id).execute()

        print("UPDATE RESPONSE:", response)

    except Exception as e:
        print("Ошибка update_user:", e)

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

    # --- УМНАЯ ПАМЯТЬ 2.0 ---
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
Ты система памяти.

У тебя есть старая память:
{user_facts}

Новый текст пользователя:
{user_text}

Твоя задача:
— сохранить только важные факты о человеке
— убрать мусор
— объединить с предыдущей памятью
— не дублировать
— писать кратко

Формат:
короткие факты списком или текстом
"""
                    }
                ]
            }
        )

    memory_data = memory_response.json()

    if "choices" in memory_data:
        new_memory = memory_data["choices"][0]["message"]["content"]
        user_facts = new_memory

except Exception as e:
    print("Ошибка памяти:", e)

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
