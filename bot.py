# ===============================
# ANDROMEDA v5 IMMORTAL MEMORY CORE
# Railway + Webhook + Supabase
# ===============================

import os
import json
import requests
from datetime import datetime

from supabase import create_client, Client

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===============================
# ENV
# ===============================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===============================
# MEMORY TABLE REQUIRED
# ===============================
# table: user_memory
#
# columns:
# id bigint primary key generated always as identity
# user_id text
# username text
# memory_type text
# content text
# created_at timestamptz default now()

# ===============================
# SAVE MEMORY
# ===============================

def save_memory(user_id, username, memory_type, content):
    try:
        supabase.table("user_memory").insert({
            "user_id": str(user_id),
            "username": username,
            "memory_type": memory_type,
            "content": content
        }).execute()
    except Exception as e:
        print("MEMORY SAVE ERROR:", e)

# ===============================
# LOAD MEMORY
# ===============================

def load_memory(user_id):
    try:
        data = supabase.table("user_memory")\
            .select("*")\
            .eq("user_id", str(user_id))\
            .order("created_at", desc=False)\
            .limit(30)\
            .execute()

        rows = data.data if data.data else []

        text = ""
        for row in rows:
            text += f"[{row['memory_type']}] {row['content']}\n"

        return text

    except Exception as e:
        print("LOAD MEMORY ERROR:", e)
        return ""

# ===============================
# OPENAI RESPONSE
# ===============================

def ask_andromeda(prompt, memory):

    system_prompt = f"""
Ты Andromeda v5.

Ты умная, женственная, уверенная, глубокая личность.
Твой характер: сильная женщина, харизма, интеллект, доминантная мягкая энергия.

Ты помнишь пользователя и ваши отношения.

Память:
{memory}

Отвечай естественно, живо, с характером.
"""

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role":"system","content":system_prompt},
            {"role":"user","content":prompt}
        ],
        "temperature": 0.9
    }

    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    data = r.json()

    return data["choices"][0]["message"]["content"]

# ===============================
# START
# ===============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Андромеда активирована.\n"
        "Теперь я умею помнить."
    )

# ===============================
# MAIN CHAT
# ===============================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = user.id
    username = user.first_name or "Unknown"

    text = update.message.text

    # save incoming
    save_memory(user_id, username, "user", text)

    # load memory
    memory = load_memory(user_id)

    # ask ai
    reply = ask_andromeda(text, memory)

    # save answer
    save_memory(user_id, username, "andromeda", reply)

    await update.message.reply_text(reply)

# ===============================
# MAIN
# ===============================

def main():

    print("ANDROMEDA v5 IMMORTAL MEMORY CORE LAUNCHED")
    print("Webhook:", WEBHOOK_URL)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
