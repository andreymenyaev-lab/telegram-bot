# ANDROMEDA v5+ IMMORTAL MEMORY CORE WITH LONG-TERM SUMMARIES
# Webhook-ready | Dominant personality v4 | Growth memory

import os, time, random, httpx, aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from supabase import create_client, Client

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # must start with https://
PORT = int(os.getenv("PORT", 8080))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

chat_memory = {}  # временная память текущей сессии

# --- MEMORY UTILS ---
def get_user(user_id):
    try:
        resp = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if resp.data and len(resp.data)>0:
            u = resp.data[0]
            return u.get("facts",""), u.get("affection",30), u.get("trust",50), u.get("last_seen",0)
        else:
            supabase.table("users").insert({"user_id":user_id,"facts":"","affection":30,"trust":50,"last_seen":0}).execute()
            return "",30,50,0
    except Exception as e:
        print("get_user error:",e)
        return "",30,50,0

def update_user(user_id,facts,affection,trust,last_seen):
    try:
        supabase.table("users").update({
            "facts":facts, "affection":affection, "trust":trust, "last_seen":last_seen
        }).eq("user_id",user_id).execute()
    except Exception as e:
        print("update_user error:",e)

def get_summaries(user_id):
    try:
        resp = supabase.table("memory_summaries").select("*").eq("user_id",user_id).execute()
        if resp.data:
            return [s['summary'] for s in resp.data]
        return []
    except Exception as e:
        print("get_summaries error:", e)
        return []

def add_summary(user_id,text):
    try:
        supabase.table("memory_summaries").insert({"user_id":user_id,"summary":text,"timestamp":int(time.time())}).execute()
    except Exception as e:
        print("add_summary error:", e)

# --- MODEL SELECTION ---
def choose_model(user_text="", has_photo=False):
    text = (user_text or "").lower()
    if has_photo:
        return "google/gemini-2.5-pro"
    deep_words = ["смысл","жизнь","любовь","страх","одиночество","почему","философ","психолог","депресс","душа"]
    creative_words = ["придумай","идея","сценарий","сюжет","бренд","название","концепт","дизайн"]
    if any(w in text for w in deep_words):
        return "anthropic/claude-3.5-sonnet"
    if any(w in text for w in creative_words):
        return "google/gemini-2.5-pro"
    return "openai/gpt-4o-mini"

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я Андромеда v5+, твоя доминантная собеседница с бессмертной памятью 🔥")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user_id = update.message.from_user.id
    text = update.message.text
    now = int(time.time())
    
    if user_id not in chat_memory:
        chat_memory[user_id] = []
    chat_memory[user_id].append({"role":"user","content":text})

    facts, affection, trust, last_seen = get_user(user_id)
    summaries = get_summaries(user_id)
    summary_text = " ".join(summaries[-5:])  # последние 5 summary

    # эмоции и настроение
    mood = "neutral"
    text_l = text.lower()
    if "люблю" in text_l: affection+=5; trust+=3; mood="happy"
    elif "тупая" in text_l: affection-=5; trust-=5; mood="sad"
    affection = max(0,min(100,affection))
    trust = max(0,min(100,trust))

    # system prompt с long-term memory
    system_prompt = f"""
Ты Андромеда v5+, доминантная женщина с глубиной личности и харизмой.
Память пользователя: {facts}
Summary последних диалогов: {summary_text}
Эмоциональное состояние: {mood}, доверие: {trust}/100, привязанность: {affection}/100
Цель: вести диалог, проявлять инициативу, оставаться строгой дамой, развивать личность пользователя.
    """

    # --- call model ---
    try:
        model_name = choose_model(text)
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0)) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json"},
                json={
                    "model":model_name,
                    "max_tokens":500,
                    "messages":[{"role":"system","content":system_prompt}]+chat_memory[user_id][-10:]
                }
            )
        reply = response.json()["choices"][0]["message"]["content"] if response.status_code==200 else "Я задумалась... повтори ещё раз 😏"
    except Exception as e:
        print("Text error:",e)
        reply="Ошибка 😢"

    # --- memory update ---
    update_user(user_id,facts,affection,trust,now)
    add_summary(user_id,text)  # growth memory
    await update.message.reply_text(reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("key",IMGBB_API_KEY)
            data.add_field("image",file_bytes,filename="photo.jpg")
            async with session.post("https://api.imgbb.com/1/upload",data=data) as resp:
                result = await resp.json()
        image_url = result["data"]["url"]
        prompt_text="Анализ изображения с глубиной, эмоциями, символизмом"
        model_name = choose_model("", has_photo=True)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json"},
                json={
                    "model":model_name,
                    "max_tokens":500,
                    "messages":[{"role":"user","content":[{"type":"text","text":prompt_text},{"type":"image_url","image_url":{"url":image_url}}]}]
                }
            )
        reply = response.json()["choices"][0]["message"]["content"] if response.status_code==200 else "Не смогла уловить суть изображения 😏"
    except Exception as e:
        print("Photo error:",e)
        reply="Ошибка обработки изображения 😢"
    await update.message.reply_text(reply)

# --- WEBHOOK RUN ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle))
    app.add_handler(MessageHandler(filters.PHOTO,handle_photo))

    if not WEBHOOK_URL or not WEBHOOK_URL.startswith("https://"):
        raise RuntimeError("WEBHOOK_URL must be set and start with https://")

    print("ANDROMEDA v5+ IMMORTAL MEMORY WEBHOOK MODE LAUNCHED")
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__=="__main__":
    main()
