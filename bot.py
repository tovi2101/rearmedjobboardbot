"""
Telegram Job Board Bot
Members submit jobs via DM → bot posts summary to channel → users expand for full details.
Admins can delete any posting.
"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters,
)
import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# Conversation states
TITLE, SHORT_DESC, FULL_DESC, BUDGET, CONTACT, CONFIRM = range(6)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])  # e.g. -1001234567890
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
# Optional: topic/thread ID inside a forum supergroup. Leave unset for regular channels.
_thread = os.environ.get("THREAD_ID", "").strip()
THREAD_ID = int(_thread) if _thread else None


# ---------- Basic commands ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to the Job Board!*\n\n"
        "*Commands:*\n"
        "/post — Post a new job\n"
        "/myjobs — List jobs you've posted\n"
        "/cancel — Cancel current action\n"
        + ("\n*Admin:*\n/delete `<job_id>` — Remove a job" if update.effective_user.id in ADMIN_IDS else ""),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ---------- /post conversation ----------

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("Please DM me to post a job.")
        return ConversationHandler.END
    await update.message.reply_text(
        "📝 *Let's post a job.*\n\nStep 1/5 — Send the *job title* (max 100 chars):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return TITLE


async def post_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 100:
        await update.message.reply_text("Too long. Max 100 chars — try again:")
        return TITLE
    context.user_data["title"] = text
    await update.message.reply_text(
        "Step 2/5 — Send a *short description* (max 200 chars).\n"
        "_This is what members see in the channel notification._",
        parse_mode=ParseMode.MARKDOWN,
    )
    return SHORT_DESC


async def post_short_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 200:
        await update.message.reply_text("Too long. Max 200 chars — try again:")
        return SHORT_DESC
    context.user_data["short_desc"] = text
    await update.message.reply_text(
        "Step 3/5 — Send the *full job details* (requirements, timeline, location, etc — max 3000 chars):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return FULL_DESC


async def post_full_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 3000:
        await update.message.reply_text("Too long. Max 3000 chars — try again:")
        return FULL_DESC
    context.user_data["full_desc"] = text
    await update.message.reply_text(
        "Step 4/5 — Send the *budget* (e.g. `$2000`, `$50/hr`, `€1k-2k`, `Negotiable` — max 50 chars):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return BUDGET


async def post_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 50:
        await update.message.reply_text("Too long. Max 50 chars — try again:")
        return BUDGET
    context.user_data["budget"] = text
    await update.message.reply_text(
        "Step 5/5 — Send *contact info* (email, @handle, link, etc):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return CONTACT


async def post_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 200:
        await update.message.reply_text("Too long. Max 200 chars — try again:")
        return CONTACT
    context.user_data["contact"] = text

    d = context.user_data
    preview = (
        f"*Preview:*\n\n"
        f"💼 *{_esc(d['title'])}*\n"
        f"💰 *Budget:* {_esc(d['budget'])}\n\n"
        f"{_esc(d['short_desc'])}\n\n"
        f"📄 *Details:*\n{_esc(d['full_desc'])}\n\n"
        f"📞 *Contact:* {_esc(d['contact'])}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Post it", callback_data="confirm_post"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_post"),
    ]])
    await update.message.reply_text(preview, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM


async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_post":
        context.user_data.clear()
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END

    d = context.user_data
    user = update.effective_user
    job_id = db.create_job(
        user_id=user.id,
        username=user.username or "",
        title=d["title"],
        short_desc=d["short_desc"],
        full_desc=d["full_desc"],
        budget=d["budget"],
        contact=d["contact"],
    )

    channel_text = (
        f"💼 *{_esc(d['title'])}*\n"
        f"💰 *Budget:* {_esc(d['budget'])}\n\n"
        f"{_esc(d['short_desc'])}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 View Full Details", callback_data=f"view:{job_id}"),
    ]])
    try:
        send_kwargs = dict(
            chat_id=CHANNEL_ID,
            text=channel_text,
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN,
        )
        if THREAD_ID is not None:
            send_kwargs["message_thread_id"] = THREAD_ID
        msg = await context.bot.send_message(**send_kwargs)
        db.set_message_id(job_id, msg.message_id)
        await query.edit_message_text(
            f"✅ *Posted!* Job ID: `{job_id}`\n\nUse /myjobs to see your posts.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.error(f"Failed to post to channel: {e}")
        db.delete_job(job_id)
        await query.edit_message_text(f"❌ Failed to post: {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ---------- Expand / collapse in channel ----------

async def handle_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, job_id_str = query.data.split(":")
    job_id = int(job_id_str)
    job = db.get_job(job_id)
    if not job:
        await query.answer("This job was deleted.", show_alert=True)
        return
    await query.answer()

    if action == "view":
        text = (
            f"💼 *{_esc(job['title'])}*\n"
            f"💰 *Budget:* {_esc(job.get('budget') or '—')}\n\n"
            f"{_esc(job['short_desc'])}\n\n"
            f"📄 *Details:*\n{_esc(job['full_desc'])}\n\n"
            f"📞 *Contact:* {_esc(job['contact'])}\n\n"
            f"_Posted by @{job['username'] or 'anonymous'} · ID {job_id}_"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Collapse", callback_data=f"hide:{job_id}"),
        ]])
    else:  # hide
        text = (
            f"💼 *{_esc(job['title'])}*\n"
            f"💰 *Budget:* {_esc(job.get('budget') or '—')}\n\n"
            f"{_esc(job['short_desc'])}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 View Full Details", callback_data=f"view:{job_id}"),
        ]])

    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.warning(f"edit failed: {e}")


# ---------- Admin / user commands ----------

async def delete_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Admins only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: `/delete <job_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return
    job = db.get_job(job_id)
    if not job:
        await update.message.reply_text("Job not found.")
        return
    if job.get("message_id"):
        try:
            await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=job["message_id"])
        except Exception as e:
            log.warning(f"channel delete failed: {e}")
    db.delete_job(job_id)
    await update.message.reply_text(f"✅ Deleted job `{job_id}`.", parse_mode=ParseMode.MARKDOWN)


async def my_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = db.get_user_jobs(update.effective_user.id)
    if not jobs:
        await update.message.reply_text("You haven't posted any jobs yet. Use /post to create one.")
        return
    lines = [f"`{j['id']}` — {_esc(j['title'])}" for j in jobs]
    await update.message.reply_text(
        "📋 *Your jobs:*\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------- Helpers ----------

def _esc(s: str) -> str:
    """Escape Markdown v1 special chars."""
    if not s:
        return ""
    return s.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")


# ---------- Main ----------

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            TITLE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, post_title)],
            SHORT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_short_desc)],
            FULL_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, post_full_desc)],
            BUDGET:     [MessageHandler(filters.TEXT & ~filters.COMMAND, post_budget)],
            CONTACT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, post_contact)],
            CONFIRM:    [CallbackQueryHandler(confirm_post, pattern="^(confirm_post|cancel_post)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("delete", delete_job))
    app.add_handler(CommandHandler("myjobs", my_jobs))
    app.add_handler(CallbackQueryHandler(handle_view, pattern=r"^(view|hide):\d+$"))

    log.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
