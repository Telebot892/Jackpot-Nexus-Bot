import os
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

# Koyeb Environment Variable එකෙන් Token එක ලබා ගැනීම
BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("💰 ආර්ථිකය (Economy)", callback_data="economy"),
            InlineKeyboardButton("🎰 කැසිනෝ (Casino)", callback_data="games")
        ],
        [
            InlineKeyboardButton("🏆 දක්ෂතම ක්‍රීඩකයෝ", callback_data="leaderboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🎰 **Jackpot Nexus Bot වෙත සාදරයෙන් පිළිගනිමු!** 🎲\n\n"
        "ඔබේ කැසිනෝ සහ මුදල් ගනුදෙනු සියල්ල මෙතැනින් සිදු කළ හැක. "
        "පහත මෙනුවෙන් ඔබට අවශ්‍ය දේ තෝරන්න:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "economy":
        await query.edit_message_text(
            "💰 **ඔබේ ගිණුම් විස්තර**\n\n"
            "💵 අතේ ඇති මුදල: 1,000 Coins\n"
            "🏦 බැංකු තැන්පතු: 0 Coins\n"
            "💎 Stars ප්‍රමාණය: 0",
            parse_mode="Markdown"
        )
    elif query.data == "games":
        keyboard = [
            [InlineKeyboardButton("🎲 කැටය කරකවන්න (Roll Dice)", callback_data="play_dice")],
            [InlineKeyboardButton("⬅️ ආපසු මුල් පිටුවට", callback_data="back_home")]
        ]
        await query.edit_message_text(
            "🎰 **කැසිනෝ ක්‍රීඩා**\n\nසෙල්ලම් කිරීමට අවශ්‍ය ක්‍රීඩාව තෝරන්න:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif query.data == "play_dice":
        user_score = random.randint(1, 6)
        bot_score = random.randint(1, 6)
        
        result = f"🎲 **දැදු කැටයේ ප්‍රතිඵලය**\n\nඔබේ අගය: {user_score}\nබොට්ගේ අගය: {bot_score}\n\n"
        if user_score > bot_score:
            result += "🎉 **සුබ පැතුම්! ඔබ දිනුවා! (+50 Coins)**"
        elif user_score < bot_score:
            result += "❌ **කණගාටුයි! ඔබ පරාජය වුණා! (-50 Coins)**"
        else:
            result += "🤝 **ජය පරාජයෙන් තොරයි!**"
            
        keyboard = [[InlineKeyboardButton("🔄 නැවත සෙල්ලම් කරන්න", callback_data="play_dice")]]
        await query.edit_message_text(result, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "leaderboard":
        await query.edit_message_text(
            "🏆 **ඉහළින්ම සිටින ක්‍රීඩකයෝ**\n\n"
            "1. ක්‍රීඩකයා 1 - 50,000 Coins\n"
            "2. ක්‍රීඩකයා 2 - 35,000 Coins\n"
            "3. ක්‍රීඩකයා 3 - 20,000 Coins",
            parse_mode="Markdown"
        )
    elif query.data == "back_home":
        await start(update, context)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    
    print("Jackpot Nexus Bot ක්‍රියාත්මක වේ...")
    app.run_polling()
