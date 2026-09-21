import os
import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------
# SETUP & CONFIGURATION
# ---------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ALLOWED_CHAT_ID = None  # Group ID එක මෙතනට දමන්න (e.g., -1002145678912)

# ---------------------------------------------------------
# DATABASE HELPER FUNCTIONS (MongoDB / PyMongo)
# ---------------------------------------------------------
client = MongoClient(DATABASE_URL)
db = client["casino_bot_db"]
users_col = db["users"]
inventory_col = db["inventory"]

def get_user(user_id, name="Player"):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user_doc = {
            "user_id": user_id,
            "name": name,
            "pocket": 100.0,
            "bank": 0.0,
            "energy": 100,
            "xp": 0,
            "job": None,
            "last_daily": None
        }
        users_col.insert_one(user_doc)
        return user_doc
    else:
        users_col.update_one({"user_id": user_id}, {"$set": {"name": name}})
        user["name"] = name
        return user

def update_user(user_id, **kwargs):
    users_col.update_one({"user_id": user_id}, {"$set": kwargs})

def get_inventory(user_id):
    items = inventory_col.find({"user_id": user_id, "quantity": {"$gt": 0}})
    return {item["item_name"]: item["quantity"] for item in items}

def add_inventory(user_id, item_name, qty=1):
    inventory_col.update_one(
        {"user_id": user_id, "item_name": item_name},
        {"$inc": {"quantity": qty}},
        upsert=True
    )

def remove_inventory(user_id, item_name, qty=1):
    item = inventory_col.find_one({"user_id": user_id, "item_name": item_name})
    if item and item.get("quantity", 0) >= qty:
        inventory_col.update_one(
            {"user_id": user_id, "item_name": item_name},
            {"$inc": {"quantity": -qty}}
        )
        return True
    return False

# Group Access Guard
async def is_allowed_chat(update: Update) -> bool:
    if ALLOWED_CHAT_ID is None:
        return True
    chat_id = update.effective_chat.id
    if chat_id != ALLOWED_CHAT_ID:
        if update.message:
            await update.message.reply_text("❌ කණගාටුයි! මෙම බොට් සක්‍රීය කර ඇත්තේ නියමිත Telegram Group එක තුළ පමණි.")
        elif update.callback_query:
            await update.callback_query.answer("❌ මෙම බොට් සක්‍රීය කර ඇත්තේ නියමිත Group එක තුළ පමණි.", show_alert=True)
        return False
    return True

math_challenges = {}

# ---------------------------------------------------------
# COMMAND HANDLERS
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed_chat(update):
        return
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    get_user(user_id, user_name)

    welcome_text = (
        f"🎰 **Jackpot Nexus Casino වෙත සාදරයෙන් පිළිගනිමු!** 🎲\n\n"
        f"ආයුබෝවන් {user_name}! ඔබේ කැසිනෝ සහ මුදල් ගනුදෙනු සියල්ල මෙතැනින් සිදු කළ හැක.\n"
        f"මෙනුව ලබා ගැනීමට `/menu` විධානය භාවිත කරන්න."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed_chat(update):
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Economy", callback_data="economy"), InlineKeyboardButton("🎰 Casino", callback_data="casino")],
        [InlineKeyboardButton("📅 Daily Coin", callback_data="daily"), InlineKeyboardButton("⚡ Energy", callback_data="energy")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"), InlineKeyboardButton("💼 Job", callback_data="menu_job")],
        [InlineKeyboardButton("🛠 Work (/work)", callback_data="menu_work"), InlineKeyboardButton("🛒 Shop", callback_data="shop")],
        [InlineKeyboardButton("🎒 Inventory", callback_data="inventory"), InlineKeyboardButton("⭐ XP", callback_data="xp_val")]
    ]
    await update.message.reply_text("🎰 **Jackpot Nexus Menu**\n\nපහත බොත්තම් මගින් ඔබට අවශ්‍ය විධානය තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def job_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed_chat(update):
        return
    
    keyboard = [
        [InlineKeyboardButton("🏹 Hunter (100 Coins)", callback_data="buy_job_hunter"), InlineKeyboardButton("🌾 Farmer (100 Coins)", callback_data="buy_job_farmer")],
        [InlineKeyboardButton("🎣 Fisherman (100 Coins)", callback_data="buy_job_fishmen"), InlineKeyboardButton("⛏️ Miner (100 Coins)", callback_data="buy_job_miner")],
        [InlineKeyboardButton("🎒 Inventory", callback_data="inventory")]
    ]
    await update.message.reply_text(
        "💼 **Jobs Menu**\n\nරකියාවක් මිලදී ගැනීමට පහතින් තෝරන්න (මිල: 100 Coins).\n\n⚠️ *සටහන:* /job මගින් කළ හැක්කේ Job එකක් Buy කිරීම පමණි. වැඩ කිරීමට `/work` භාවිත කරන්න.",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def work_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed_chat(update):
        return
    
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    
    if not user.get("job"):
        await update.message.reply_text("❌ ඔබට තවම Job එකක් නැත! `/job` භාවිත කර Job එකක් මිලදී ගන්න.")
        return

    if user.get("energy", 0) < 23:
        await update.message.reply_text("⚡ ඔබේ Energy ප්‍රමාණය මදි (අවම 23% ක් තිබිය යුතුය). Shop එකෙන් කෑමක් කා Energy වැඩි කරගන්න!")
        return

    new_energy = max(0, user["energy"] - 23)
    new_xp = user.get("xp", 0) + 10
    update_user(user["user_id"], energy=new_energy, xp=new_xp)

    msg = f"🔨 **වැඩ නිම කරන ලදී!**\n\n⚡ Energy: -23% (ඉතිරි: {new_energy}%)\n⭐ XP: +10 (මුළු XP: {new_xp})\n"

    if random.random() <= 0.36:
        drops = {
            "hunter": [("Wool", "Wool 🧶"), ("Leather", "Leather 📜")],
            "farmer": [("Golden Carrot", "Golden Carrot 🥕"), ("Cherry", "Cherry 🍒")],
            "fishmen": [("Sea Pickle", "Sea Pickle 🥒"), ("Star Fish", "Star Fish 🌟")],
            "miner": [("Iron", "Iron ⛓️"), ("Platinum", "Platinum 🪙")]
        }
        job_drops = drops.get(user["job"], [])
        if job_drops:
            item_code, item_disp = random.choice(job_drops)
            add_inventory(user["user_id"], item_code, 1)
            msg += f"\n🎉 **දුර්ලභ අයිතමයක් ලැබුණා!**: {item_disp} x1 (36% Chance)"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------------------------------------------------------
# CALLBACK QUERY HANDLER
# ---------------------------------------------------------
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed_chat(update):
        return

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id, query.from_user.first_name)

    if query.data == "economy":
        text = f"💰 **ඔබගේ ගිණුම් විස්තර**\n\n💵 ඔබගේ pocket money balance එක: **{user['pocket']:.2f} Coins**\n🏦 ඔබගේ bank balance එක: **{user['bank']:.2f} Coins**"
        await query.edit_message_text(text, parse_mode="Markdown")

    elif query.data == "casino":
        keyboard = [
            [InlineKeyboardButton("🎲 Roll Dice", callback_data="play_dice"), InlineKeyboardButton("🪙 Coin Toss", callback_data="play_cointoss")],
            [InlineKeyboardButton("🎴 Humanga Game", callback_data="play_humanga")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_menu")]
        ]
        await query.edit_message_text("🎰 **Jackpot Nexus Casino Games**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "play_dice":
        u_score, b_score = random.randint(1, 6), random.randint(1, 6)
        res = f"🎲 **Dice Roll**\n\nඔබ: {u_score} | Bot: {b_score}\n\n"
        if u_score > b_score:
            update_user(user_id, pocket=user['pocket'] + 20)
            res += "🎉 ඔබ දිනුවා! (+20 Coins)"
        elif u_score < b_score:
            update_user(user_id, pocket=max(0, user['pocket'] - 20))
            res += "❌ ඔබ පරාජය වුණා! (-20 Coins)"
        else:
            res += "🤝 ජය පරාජයෙන් තොරයි!"
        kb = [[InlineKeyboardButton("🔄 නැවත සෙල්ලම් කරන්න", callback_data="play_dice")]]
        await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif query.data == "play_cointoss":
        outcome = random.choice(["Heads", "Tails"])
        update_user(user_id, pocket=user['pocket'] + 10)
        res = f"🪙 **Coin Toss Results**\n\nකාසිය වැටුණේ: **{outcome}**!\n🎉 ඔබට +10 Coins ලැබුණා!"
        kb = [[InlineKeyboardButton("🔄 නැවත Toss කරන්න", callback_data="play_cointoss")]]
        await query.edit_message_text(res, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif query.data == "play_humanga":
        res = f"🎴 **Humanga Special Game**\n\nජැක්පොට් අගය පරීක්ෂා කෙරේ...\n🎉 සුබ පැතුම්! ඔබට Bonus +30 Coins හිමිවිය!"
        update_user(user_id, pocket=user['pocket'] + 30)
        await query.edit_message_text(res, parse_mode="Markdown")

    elif query.data == "daily":
        now = datetime.now()
        can_claim = True
        if user.get("last_daily"):
            last_date = datetime.fromisoformat(user["last_daily"])
            if now - last_date < timedelta(hours=24):
                can_claim = False
                rem = timedelta(hours=24) - (now - last_date)
                h, r = divmod(rem.seconds, 3600)
                m, _ = divmod(r, 60)
                await query.edit_message_text(f"⏳ තව පැය {h} යි මිනිත්තු {m} ක් රැඳී සිටින්න.")

        if can_claim:
            update_user(user_id, pocket=user['pocket'] + 5, last_daily=now.isoformat())
            await query.edit_message_text("📅 **Daily Coin**\n\n🎉 අද දිනය සඳහා සාර්ථකව **5 Coins** ලැබුණා!")

    elif query.data == "energy":
        await query.edit_message_text(f"⚡ **Energy තත්ත්වය**: **{user['energy']}% / 100%**", parse_mode="Markdown")

    elif query.data == "leaderboard":
        pipeline = [
            {"$project": {"name": 1, "total": {"$add": ["$pocket", "$bank"]}}},
            {"$sort": {"total": -1}},
            {"$limit": 10}
        ]
        top_users = list(users_col.aggregate(pipeline))

        lb_text = "🏆 **Top 10 ක්‍රීඩකයෝ**\n\n"
        for idx, u in enumerate(top_users, 1):
            lb_text += f"{idx}. **{u['name']}** - {u['total']:.2f} Coins\n"
        await query.edit_message_text(lb_text, parse_mode="Markdown")

    elif query.data == "menu_job":
        await job_command(update, context)

    elif query.data.startswith("buy_job_"):
        selected_job = query.data.replace("buy_job_", "")
        if user["pocket"] < 100:
            await query.edit_message_text("❌ Job එකක් මිලදී ගැනීමට ඔබ ළඟ Coins 100 ක් තිබිය යුතුය!")
            return

        num1, num2 = random.randint(10, 50), random.randint(5, 45)
        op = random.choice(["+", "-"])
        ans = num1 + num2 if op == "+" else num1 - num2
        
        math_challenges[user_id] = {"ans": ans, "job": selected_job}
        await query.edit_message_text(
            f"🧮 **Job Verification Quiz**\n\n👉 **{num1} {op} {num2} = ?**\n\nපිළිතුර ලබාදීමට bot ට Reply එකක් ලෙස අගය ගහන්න (Type in Chat).",
            parse_mode="Markdown"
        )

    elif query.data == "menu_work":
        await query.edit_message_text("🛠 වැඩ කිරීමට Telegram Chat එකේ `/work` ලෙස Type කර Send කරන්න.")

    elif query.data == "shop":
        kb = [
            [InlineKeyboardButton("🥃 Whisky ($5.79)", callback_data="buy_whisky"), InlineKeyboardButton("🍎 Apple ($2.5)", callback_data="buy_apple")],
            [InlineKeyboardButton("🍪 Biscuit ($1.28)", callback_data="buy_biscuit")],
            [InlineKeyboardButton("🏷️ Sell Rare Items", callback_data="sell_items")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_menu")]
        ]
        await query.edit_message_text("🛒 **Jackpot Nexus Shop**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif query.data in ["buy_whisky", "buy_apple", "buy_biscuit"]:
        prices = {"buy_whisky": (5.79, "Whisky"), "buy_apple": (2.5, "Apple"), "buy_biscuit": (1.28, "Biscuit")}
        cost, item = prices[query.data]

        if user["pocket"] < cost:
            await query.edit_message_text("❌ මෙය මිලදී ගැනීමට Coins මදි!")
            return

        update_user(user_id, pocket=user["pocket"] - cost)
        add_inventory(user_id, item, 1)
        await query.edit_message_text(f"✅ සාර්ථකව **{item}** මිලදී ගත්තා! (ගාස්තුව: {cost} Coins)", parse_mode="Markdown")

    elif query.data == "sell_items":
        inv = get_inventory(user_id)
        prices = {"Wool": 3.0, "Leather": 6.0, "Sea Pickle": 3.0, "Star Fish": 6.0, "Golden Carrot": 6.0, "Cherry": 3.0, "Iron": 3.0, "Platinum": 6.0}
        total_earned = sum(prices[item] * qty for item, qty in inv.items() if item in prices)
        
        if total_earned > 0:
            for item in list(inv.keys()):
                if item in prices:
                    remove_inventory(user_id, item, inv[item])
            update_user(user_id, pocket=user["pocket"] + total_earned)
            await query.edit_message_text(f"💰 දුර්ලභ අයිතම විකුණා ඔබට **+{total_earned:.2f} Coins** ලැබුණා!", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ විකිණීමට තරම් දුර්ලභ අයිතම ඔබගේ Inventory එකේ නැත.")

    elif query.data == "inventory":
        inv = get_inventory(user_id)
        text = "🎒 **Inventory හිස්ය.**" if not inv else "🎒 **Inventory:**\n\n" + "\n".join(f"• **{i}**: {q}" for i, q in inv.items())
        kb = [[InlineKeyboardButton("🍔 Eat / Drink Food", callback_data="use_food")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif query.data == "use_food":
        inv = get_inventory(user_id)
        for food in ["Whisky", "Apple", "Biscuit"]:
            if inv.get(food, 0) > 0:
                remove_inventory(user_id, food, 1)
                new_energy = min(100, user["energy"] + 50)
                update_user(user_id, energy=new_energy)
                await query.edit_message_text(f"🍔 ඔබ **{food}** අනුභව කළා! වත්මන් Energy: {new_energy}%.")
                return
        await query.edit_message_text("❌ අනුභව කිරීමට කෑම/බීම නැත!")

    elif query.data == "xp_val":
        await query.edit_message_text(f"⭐ **ඔබගේ XP ප්‍රමාණය**: **{user.get('xp', 0)} XP**", parse_mode="Markdown")

    elif query.data == "back_menu":
        await menu_command(update, context)

# ---------------------------------------------------------
# MATH QUIZ HANDLER
# ---------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed_chat(update):
        return

    user_id = update.effective_user.id
    if user_id in math_challenges:
        user_input = update.message.text.strip()
        challenge = math_challenges[user_id]
        
        if user_input.lstrip('-').isdigit():
            if int(user_input) == challenge["ans"]:
                job_name = challenge["job"]
                user = get_user(user_id)
                update_user(user_id, pocket=user["pocket"] - 100, job=job_name)
                del math_challenges[user_id]
                await update.message.reply_text(f"🎉 **ගණන නිවැරදියි!**\n\nඔබ **{job_name.capitalize()}** Job එක මිලදී ගත්තා!", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ පිළිතුර වැරදියි! නැවත උත්සාහ කරන්න.")
                del math_challenges[user_id]

# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("job", job_command))
    app.add_handler(CommandHandler("work", work_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot Successfully Started with MongoDB Atlas Database!")
    app.run_polling()
