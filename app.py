import json
import logging
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from datasets import load_dataset, Dataset, DatasetDict
import huggingface_hub

# ---------------- CONFIG ----------------
BOT_TOKEN = "8424440635:AAEXJJNxb1kAXs3BI1cJSuh9kMloeS2TxYc"   # Replace with your bot token
ADMIN_ID = 6651395416                     # Replace with your Telegram user ID
LOG_CHANNEL_ID = -1003099533957           # Replace with your log channel ID
HF_DATASET_REPO = "your-username/your-dataset-repo"  # Replace with your HF dataset repo
HF_TOKEN = "your-huggingface-token"       # Replace with your HF token
# ----------------------------------------

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize Hugging Face dataset with authentication
try:
    # Login to Hugging Face Hub
    huggingface_hub.login(token=HF_TOKEN)
    
    # Load the dataset (will work for private datasets with proper token)
    dataset = load_dataset(HF_DATASET_REPO, use_auth_token=HF_TOKEN)
    user_data = dataset["user_data"][0] if dataset["user_data"] else {}
    logger.info("Successfully loaded dataset from Hugging Face")
except Exception as e:
    logger.error(f"Error loading dataset: {e}")
    logger.info("Initializing with empty user data")
    user_data = {}

# -------- Helper Functions --------
def load_userdata():
    """Load user data from Hugging Face dataset"""
    try:
        dataset = load_dataset(HF_DATASET_REPO, use_auth_token=HF_TOKEN)
        return dataset["user_data"][0] if dataset["user_data"] else {}
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        return {}

def save_userdata(data):
    """Save user data to Hugging Face dataset"""
    global user_data
    try:
        # Create a new dataset with the updated user data
        new_dataset = Dataset.from_dict({"user_data": [data]})
        
        # Push to Hugging Face with authentication
        new_dataset.push_to_hub(
            HF_DATASET_REPO, 
            token=HF_TOKEN,
            commit_message="Update user data from bot"
        )
        
        # Update local cache
        user_data = data
        logger.info("Successfully saved user data to Hugging Face")
        return True
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return False

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Main Menu", callback_data="menu")]
    ])

def full_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Add/Change Payment Method", callback_data="payment")],
        [InlineKeyboardButton("Check Balance / Account", callback_data="balance")],
        [InlineKeyboardButton("Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("Privacy Policy & T&C", url="https://example.com/t&c")],
        [InlineKeyboardButton("Contact Admin", callback_data="contact_admin")],
        [InlineKeyboardButton("Start Earning", callback_data="start_earning")],
    ])

# -------- Handlers --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    name = user.first_name

    # Store user in Hugging Face dataset
    users = load_userdata()
    if user_id not in users:
        users[user_id] = {"name": name, "balance": 0, "verified": False}
        if save_userdata(users):
            await update.message.reply_text(
                f"Hello {name}, welcome to the Cash4Corn bot! 👋",
                reply_markup=full_menu()
            )
        else:
            await update.message.reply_text(
                "Sorry, there was an error initializing your account. Please try again later."
            )
    else:
        await update.message.reply_text(
            f"Welcome back {name}! 👋",
            reply_markup=full_menu()
        )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    user_id = str(user.id)

    if data == "menu":
        await query.edit_message_text("📍 Main Menu", reply_markup=full_menu())

    elif data == "withdraw":
        await query.edit_message_text("Enter the amount you want to withdraw:", reply_markup=main_menu())
        context.user_data["withdraw_mode"] = True

    elif data == "payment":
        keyboard = [
            [InlineKeyboardButton("Bank", callback_data="pay_bank")],
            [InlineKeyboardButton("PayPal", callback_data="pay_paypal")],
            [InlineKeyboardButton("Visa", callback_data="pay_visa")],
            [InlineKeyboardButton("Crypto", callback_data="pay_crypto")],
        ]
        await query.edit_message_text("Select your payment method:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "balance":
        users = load_userdata()
        info = users.get(user_id, {})
        name = info.get("name", "Unknown")
        balance = info.get("balance", 0)
        verified = "✅ Verified" if info.get("verified") else "❌ Not Verified"
        details = f"📊 *Account Details*\n\n👤 Name: {name}\n🆔 ID: {user_id}\n💰 Balance: ${balance}\n🔒 Status: {verified}"
        await query.edit_message_text(details, parse_mode="Markdown", reply_markup=main_menu())

    elif data == "contact_admin":
        await query.edit_message_text("Please send me your message for the admin:", reply_markup=main_menu())
        context.user_data["contact_mode"] = True

    elif data == "start_earning":
        await query.edit_message_text("Please enter a *Title* for your content:", parse_mode="Markdown", reply_markup=main_menu())
        context.user_data["earning_step"] = "title"

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    name = user.first_name
    message = update.message

    # Withdraw request
    if context.user_data.get("withdraw_mode"):
        context.user_data["withdraw_mode"] = False
        amount = message.text
        await message.reply_text("✅ Your withdraw request has been sent to admin.", reply_markup=main_menu())
        await context.bot.send_message(LOG_CHANNEL_ID, f"💸 Withdraw Request from {name} ({user_id}): {amount}")
        return

    # Contact admin flow
    if context.user_data.get("contact_mode"):
        context.user_data["contact_mode"] = False
        forward_text = f"📩 Message from {name} ({user_id}):\n\n{message.text}"
        await context.bot.send_message(ADMIN_ID, forward_text)
        await context.bot.send_message(LOG_CHANNEL_ID, f"[USER → ADMIN]\n{forward_text}")
        await message.reply_text("Your message has been sent to the admin.", reply_markup=main_menu())
        return

    # Content upload flow
    if context.user_data.get("earning_step"):
        step = context.user_data["earning_step"]

        if step == "title":
            context.user_data["content_title"] = message.text
            context.user_data["earning_step"] = "description"
            await message.reply_text("Now enter a *Description* for your content:", parse_mode="Markdown", reply_markup=main_menu())
            return

        elif step == "description":
            context.user_data["content_desc"] = message.text
            context.user_data["earning_step"] = "media"
            await message.reply_text("Now please upload your *Video/Content*:", parse_mode="Markdown", reply_markup=main_menu())
            return

        elif step == "media":
            if message.video or message.document or message.photo or message.animation:
                title = context.user_data.get("content_title")
                desc = context.user_data.get("content_desc")
                await message.reply_text("✅ Content received! Admin will review it.", reply_markup=main_menu())
                await context.bot.send_message(
                    LOG_CHANNEL_ID,
                    f"📤 New Content Submission from {name} ({user_id}):\n\n*Title:* {title}\n*Description:* {desc}",
                    parse_mode="Markdown"
                )
                await context.bot.forward_message(LOG_CHANNEL_ID, message.chat_id, message.message_id)
                context.user_data["earning_step"] = None
            else:
                await message.reply_text("❌ Please upload a valid video or media file.", reply_markup=main_menu())
            return

    # ID verification steps
    if context.user_data.get("idver_step"):
        step = context.user_data["idver_step"]

        if step == "name":
            context.user_data["idver_step"] = "idphoto"
            await message.reply_text("Upload your *ID Photo*:", parse_mode="Markdown", reply_markup=main_menu())
            await context.bot.send_message(LOG_CHANNEL_ID, f"🆔 Name from {name} ({user_id}): {message.text}")
            return

        elif step == "idphoto":
            if message.photo or message.document:
                context.user_data["idver_step"] = "selfie_id"
                await message.reply_text("Now upload a *Selfie holding your ID*:", parse_mode="Markdown", reply_markup=main_menu())
                await context.bot.forward_message(LOG_CHANNEL_ID, message.chat_id, message.message_id)
            else:
                await message.reply_text("❌ Please upload a valid ID photo.", reply_markup=main_menu())
            return

        elif step == "selfie_id":
            if message.photo:
                context.user_data["idver_step"] = "selfie_paper"
                await message.reply_text("Now upload a *Selfie holding paper with your name/username*:", parse_mode="Markdown", reply_markup=main_menu())
                await context.bot.forward_message(LOG_CHANNEL_ID, message.chat_id, message.message_id)
            else:
                await message.reply_text("❌ Please upload a valid selfie.", reply_markup=main_menu())
            return

        elif step == "selfie_paper":
            if message.photo:
                context.user_data["idver_step"] = None
                await message.reply_text("✅ Your ID documents have been submitted for review.", reply_markup=main_menu())
                await context.bot.forward_message(LOG_CHANNEL_ID, message.chat_id, message.message_id)
            else:
                await message.reply_text("❌ Please upload a valid photo.", reply_markup=main_menu())
            return

# -------- Admin Commands --------
async def admin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /msg <userid> <message>")
        return
    target_id = context.args[0]
    text_msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(int(target_id), text_msg, reply_markup=main_menu())
        await update.message.reply_text(f"Message sent to {target_id}.")
        await context.bot.send_message(LOG_CHANNEL_ID, f"[ADMIN → USER {target_id}]\n{text_msg}")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_userdata()
    if not users:
        await update.message.reply_text("No users registered yet.")
        return
    msg_lines = ["👥 Registered Users:"]
    for uid, info in users.items():
        name = info.get("name", "Unknown")
        balance = info.get("balance", 0)
        verified = "✅" if info.get("verified") else "❌"
        msg_lines.append(f"- {name} ({uid}) | Balance: ${balance} | Verified: {verified}")
    await update.message.reply_text("\n".join(msg_lines))

async def idver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /idver <userid>")
        return
    target_id = int(context.args[0])
    await context.bot.send_message(target_id, "🆔 Please start ID Verification.\nSend me your *Full Name*:", parse_mode="Markdown", reply_markup=main_menu())
    context.user_data["idver_step"] = "name"

async def idpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /idpass <userid>")
        return
    target_id = int(context.args[0])
    users = load_userdata()
    if str(target_id) in users:
        users[str(target_id)]["verified"] = True
        if save_userdata(users):
            await context.bot.send_message(target_id, "✅ You have been verified!", reply_markup=main_menu())
            await update.message.reply_text(f"User {target_id} marked as verified.")
        else:
            await update.message.reply_text("Error saving verification status.")
    else:
        await update.message.reply_text(f"User {target_id} not found.")

async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /paid <userid>")
        return
    target_id = int(context.args[0])
    await context.bot.send_message(target_id, "💰 Your withdrawal request has been fulfilled by Admin.", reply_markup=main_menu())
    await update.message.reply_text(f"Payment confirmed for {target_id}.")

# -------- Main --------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("msg", admin_msg))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CommandHandler("idver", idver))
    app.add_handler(CommandHandler("idpass", idpass))
    app.add_handler(CommandHandler("paid", paid))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.ALL, handle_messages))

    logger.info("Bot started with Hugging Face dataset integration...")
    app.run_polling()

if __name__ == "__main__":
    main()
