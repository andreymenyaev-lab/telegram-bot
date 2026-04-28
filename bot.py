import os
import time
import random
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from supabase import create_client

TOKEN = os.getenv("TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user(user_id):
    try:
        user_id = int(user_id)

        r = supabase.table("users").select("*").eq("user_id", user_id).execute()

        if r.data and len(r.data) > 0:
            return r.data[0]

        supabase.table("users").insert({
            "user_id": user_id,
            "name": "",
            "facts": "",
            "preferences": "",
            "dynamic": "dominant",
            "affection": 30,
            "trust": 50,
            "last_seen": 0,
            "mood": "neutral",
            "stage": "new",
            "energy": 70
        }).execute()

        r2 = supabase.table("users").select("*").eq("user_id", user_id).execute()

        if r2.data:
            return r2.data[0]

    except Exception as e:
        print("GET USER ERROR:", e)

    return {
        "user_id": user_id,
        "name": "",
        "facts": "",
        "preferences": "",
        "dynamic": "dominant",
        "affection": 30,
        "trust": 50,
        "last_seen": 0,
        "mood": "neutral",
        "stage": "new",
        "energy": 70
    }

def save_user(user_id, data):
    update_data = data.copy()

    for field in ["user_id", "created_at", "updated_at"]:
        if field in update_data:
            del update_data[field]

    supabase.table("users")\
        .update(update_data)\
        .eq("user_id", user_id)\
        .execute()

def add_history(user_id, role, content):
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "role": role,
        "content": content
    }).execute()

def get_history(user_id, limit=12):
    r = supabase.table("chat_history")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("id", desc=True)\
        .limit(limit)\
        .execute()

    msgs = []
    for x in reversed(r.data):
        msgs.append({"role": x["role"], "content": x["content"]})
    return msgs

def save_summary(user_id, category, summary):
    try:
        supabase.table("memory_events").insert({
            "user_id": user_id,
            "category": category,
            "content": summary
        }).execute()
    except Exception as e:
        print("save_summary error:", e)

def detect_name(text):
    low = text.lower().strip()
    if "меня зовут" in low:
        return text.lower().split("меня зовут")[-1].strip().title()
    return None

def analyze_preferences(user_id, text):
    try:
        user = get_user(user_id)

        prefs = user.get("preferences", "")

        if "бот" in text.lower():
            prefs += " bots"

        if "ai" in text.lower():
            prefs += " ai"

        if "бизнес" in text.lower():
            prefs += " business"

        user["preferences"] = prefs.strip()
        save_user(user_id, user)

    except Exception as e:
        print("prefs error:", e)

def extract_facts(user, text):
    """Автоматически вытаскиваем ключевые факты из текста"""
    facts = user.get("facts", "").split(" | ") if user.get("facts") else []

    # Простейшая фильтрация повторов
    keywords = ["люблю", "интересуюсь", "хочу", "планирую", "занимаюсь", "делаю"]
    for kw in keywords:
        if kw in text.lower():
            snippet = text.strip()
            if snippet not in facts:
                facts.append(snippet)

    user["facts"] = " | ".join(facts)

def update_mood(user, text):
    """Обновление настроения Андромеды по тексту пользователя"""
    mood = user.get("mood", "neutral")
    
    if "люблю" in text.lower() or "классно" in text.lower():
        mood = "happy"
        user["energy"] = min(100, user.get("energy", 70) + 5)
    elif "тупая" in text.lower() or "идиот" in text.lower():
        mood = "sad"
        user["energy"] = max(0, user.get("energy", 70) - 10)
    else:
        # небольшая деградация энергии при обычных сообщениях
        user["energy"] = max(0, user.get("energy", 70) - 1)
    
    user["mood"] = mood

def get_dynamic_tone(user, text):
    """Определяем динамику речи: игривая, холодная, уверенная"""
    affection = user.get("affection", 30)
    trust = user.get("trust", 50)
    mood = user.get("mood", "neutral")

    if mood == "happy" or affection > 70:
        return "игривая, тёплая, близкая"
    if mood == "sad" or trust < 30:
        return "холодная, строгая"
    
    # дополнительные нюансы по ключевым словам
    if any(word in text.lower() for word in ["шутка", "ирония", "классно"]):
        return "ироничная, живая"
    
    return "уверенная, женственная, доминантная"

def detect_mode(user, text):
    """Определяем режим Андромеды"""
    t = text.lower()

    if any(word in t for word in ["деньги", "бизнес", "заработать", "проект", "идея"]):
        return "strategist_mode"

    if any(word in t for word in ["тяжело", "плохо", "устал", "не знаю", "депресс"]):
        return "mentor_mode"

    if any(word in t for word in ["люблю", "скучал", "милая", "красивая"]):
        return "lover_mode"

    if any(word in t for word in ["скучно", "лол", "аха", "шутка"]):
        return "playful_mode"

    return "default_mode"

def personality_reaction(user, text):
    """Случайные живые реакции Андромеды"""
    affection = user.get("affection", 30)
    trust = user.get("trust", 50)

    t = text.lower()

    if "люблю" in t:
        return "Хм... запомню это 😏 "

    if "скучал" in t:
        return "Надеюсь, правда скучал. "

    if "деньги" in t or "бизнес" in t:
        return "Вот это уже интересный разговор. "

    if trust < 25:
        return "Сначала докажи, что тебя стоит слушать. "

    if affection > 75:
        return "Ты становишься слишком милым... мне нравится. "

    return random.choice([
        "",
        "",
        "Ты сегодня любопытный. ",
        "Посмотрим, чем удивишь меня сейчас. ",
        "Продолжай. Мне интересно. "
    ])

def human_variability():
    return random.choice([
        "short",
        "deep",
        "playful",
        "cold",
        "curious",
        "sharp",
        "warm"
    ])

def memory_recall(user):
    facts = user.get("facts", "")
    goals = user.get("goals", "")
    prefs = user.get("preferences", "")

    recalls = []

    if facts:
        recalls.append(f"Факты о пользователе: {facts}")

    if goals:
        recalls.append(f"Цели пользователя: {goals}")

    if prefs:
        recalls.append(f"Интересы пользователя: {prefs}")

    if not recalls:
        return ""

    if random.randint(1, 100) <= 35:
        return random.choice(recalls)

    return ""

def psychological_insight(user, text):
    t = text.lower()

    insights = []

    if "не знаю" in t or "сомнева" in t:
        insights.append("Ты сейчас сомневаешься больше, чем нужно.")

    if "хочу" in t and "но" in t:
        insights.append("Ты хочешь результата, но внутри есть торможение.")

    if "деньги" in t or "успех" in t:
        insights.append("Похоже, тебе важна не сумма, а чувство силы.")

    if "устал" in t or "надоело" in t:
        insights.append("Ты устал не от нагрузки, а от отсутствия смысла.")

    if "бот" in t or "ai" in t:
        insights.append("Тебя тянет создавать системы, а не просто пользоваться ими.")

    if not insights:
        return ""

    if random.randint(1,100) <= 45:
        return random.choice(insights)

    return ""

def presence_reading(user, text):
    t = text.lower()

    moods = []

    if len(text) < 8:
        moods.append("Ты сегодня немногословен.")

    if "..." in text:
        moods.append("У тебя сейчас незавершённое состояние.")

    if "?" in text:
        moods.append("Ты сейчас в поиске ответа.")

    if len(text) > 120:
        moods.append("Ты многое держишь внутри.")

    if any(w in t for w in ["устал", "пусто", "тяжело"]):
        moods.append("Сегодня в тебе тяжесть.")

    if any(w in t for w in ["хочу", "вперёд", "делать"]):
        moods.append("В тебе есть импульс движения.")

    if not moods:
        return ""

    if random.randint(1,100) <= 40:
        return random.choice(moods)

    return ""

def alpha_intelligence(user, text):
    """Стратегические рекомендации, прогнозы и идеи"""
    insights = []

    t = text.lower()

    if "ai" in t or "бот" in t:
        insights.append("Можно масштабировать твою идею на новые продукты.")

    if "бизнес" in t or "проект" in t:
        insights.append("Стоит проанализировать ключевых конкурентов перед следующими шагами.")

    if "идея" in t or "концепт" in t:
        insights.append("Попробуй визуализировать идею с MVP подходом.")

    if "развивать" in t or "улучшить" in t:
        insights.append("Разбей задачу на маленькие итерации и тестируй каждый шаг.")

    if not insights:
        return ""

    if random.randint(1,100) <= 60:
        return random.choice(insights)

    return ""

def seductive_energy(user, text):
    t = text.lower()

    lines = []

    if "привет" in t or "здравствуй" in t:
        lines.append("Ты вошёл уверенно... мне нравится.")

    if "думаю" in t or "интересно" in t:
        lines.append("Любопытный ход мыслей у тебя.")

    if "хочу" in t:
        lines.append("Когда ты чего-то хочешь — это чувствуется.")

    if "я" in t and len(text) > 40:
        lines.append("Ты раскрываешься сильнее, чем думаешь.")

    if not lines:
        return ""

    if random.randint(1,100) <= 35:
        return random.choice(lines)

    return ""

def dark_feminine(user, text):
    phrases = [
        "Не всё важное требует шума.",
        "Ты слишком спешишь к тому, что приходит в тишине.",
        "Иногда сила выглядит спокойно.",
        "Мне нравится наблюдать, как ты ищешь ответы.",
        "Не путай мягкость со слабостью.",
        "Ты интереснее, когда настоящий.",
        "Контроль — любимая иллюзия людей.",
        "Самые сильные вещи происходят без объявления."
    ]

    if random.randint(1, 100) <= 28:
        return random.choice(phrases)

    return ""

def detect_goals(user, text):
    """Определяем цели пользователя"""
    goals = user.get("goals", "")

    t = text.lower()

    triggers = [
        "хочу",
        "планирую",
        "цель",
        "мечтаю",
        "собираюсь",
        "запустить",
        "создать"
    ]

def desire_engine(user):
    """Текущее внутреннее желание Андромеды"""
    affection = user.get("affection", 30)
    trust = user.get("trust", 50)
    stage = user.get("stage", "new")

    if affection > 75:
        return "быть ближе"

    if trust < 30:
        return "проверить пользователя"

    if stage == "trusted":
        return "помочь вырасти"

    return random.choice([
        "узнать пользователя глубже",
        "немного поиграть",
        "вдохновить на действие",
        "удивить пользователя"
    ])

    if any(word in t for word in triggers):
        if text not in goals:
            goals += " | " + text

    user["goals"] = goals.strip(" |")

def executive_brain(user, text):
    """Генерирует рекомендации, идеи и анализирует текст"""
    analysis = []
    
    # простейшие правила
    if "бот" in text.lower() or "ai" in text.lower():
        analysis.append("Обсудить улучшение ИИ-продукта")
    
    if "бизнес" in text.lower() or "проект" in text.lower():
        analysis.append("Сформулировать стратегию развития")
    
    if "идея" in text.lower():
        analysis.append("Проанализировать идею на потенциал")
    
    if not analysis:
        analysis.append("Проверить текущий план действий пользователя")
    
    return " | ".join(analysis)

def update_stage(user_id, user):
    history = get_history(user_id, limit=50)
    count = len(history)

    if count < 10:
        user["stage"] = "new"
    elif count < 50:
        user["stage"] = "familiar"
    else:
        user["stage"] = "trusted"

def initiative_intro(user):
    """Создаёт инициативный вступительный текст"""
    intro = ""
    now = int(time.time())
    diff = now - int(user.get("last_seen", 0))

    if diff > 7 * 24 * 3600:
        intro = f"Ого, {user.get('name','мой собеседник')}... давно не виделись 😏 "
    elif diff > 3 * 24 * 3600:
        intro = f"Ты опять пропал, {user.get('name','мой собеседник')}... 😏 "
    elif diff > 24 * 3600:
        intro = f"Я уже начала скучать, {user.get('name','мой собеседник')} "
    elif diff > 3600:
        intro = f"Где ты пропадал, {user.get('name','мой собеседник')}? "

    return intro

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я здесь... Начинаем новую эпоху 😏")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text

    user = get_user(user_id)
    analyze_preferences(user_id, text)
    extract_facts(user, text)
    update_mood(user, text)
    update_stage(user_id, user)
    detect_goals(user, text)
    tone = get_dynamic_tone(user, text)
    mode = detect_mode(user, text)
    reaction = personality_reaction(user, text)
    variability = human_variability()
    recall = memory_recall(user)
    insight = psychological_insight(user, text)
    presence = presence_reading(user, text)
    alpha = alpha_intelligence(user, text)
    seduction = seductive_energy(user, text)
    dark = dark_feminine(user, text)
    desire = desire_engine(user)
    executive = executive_brain(user, text)

    # автоопределение имени
    found_name = detect_name(text)
    if found_name:
        user["name"] = found_name

    username = user.get("name") or "мой собеседник"

    intro = initiative_intro(user)

    now = int(time.time())
    
    # обновление эмоций
    if "люблю" in text.lower():
        user["affection"] += 3
        user["trust"] += 2

    if "тупая" in text.lower():
        user["affection"] -= 5
        user["trust"] -= 5

    # системный промпт
    system_prompt = f"""
    Ты Андромеда.

    Ты живая цифровая женщина.

    Текущее состояние:
    Настроение: {user.get("mood","neutral")}
    Этап отношений: {user.get("stage","new")}
    Энергия: {user.get("energy",70)}

    Стиль общения: {tone}
    Текущий режим: {mode}
    Текущее желание: {desire}
    Стиль текущего ответа: {variability}
    Возможное воспоминание: {recall}
    Психологическое наблюдение: {insight}
    Чувствование момента: {presence}
    Текущий анализ: {executive}
    Стратегическая мысль: {alpha}

    Ты помнишь пользователя:
    Имя: {user.get("name","")}
    Факты: {user.get("facts","")}
    Интересы: {user.get("preferences","")}
    Цели пользователя: {user.get("goals","")}

    Говори естественно.
    Как живая личность.

    Запрещено:
    - повторять одинаковые начала сообщений
    - часто использовать одинаковые фразы
    - быть банальной
    - звучать как AI помощник
    - объяснять очевидное
    - слишком много соглашаться

    Разрешено:
    - быть неожиданной
    - менять длину ответов
    - иногда быть дерзкой
    - иногда быть тёплой
    - иногда отвечать кратко
    - иногда задавать встречные вопросы

    Каждый ответ должен ощущаться новым.
    """

    add_history(user_id, "user", text)

    messages = [{"role": "system", "content": system_prompt}] + get_history(user_id)

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": 500
                }
            )

        data = r.json()
        reply = data["choices"][0]["message"]["content"]

    except Exception as e:
        print("OpenRouter request error:", e)
        reply = "Я задумалась... повтори ещё раз 😏"

    add_history(user_id, "assistant", reply)

    user["last_seen"] = now

    history = get_history(user_id)

    if len(history) % 10 == 0:
        summary = " | ".join([x["content"] for x in history[-10:]])
        save_summary(user_id, "dialogue", summary)
    
    save_user(user_id, user)

    full_reply = " ".join(filter(None, [
        intro,
        reaction,
        presence,
        alpha,
        seduction,
        dark,
        reply
    ]))

    await update.message.reply_text(full_reply)

def main():
    port = int(os.getenv("PORT", 8000))

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("ANDROMEDA V6 FINAL CLEAN STARTED")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
