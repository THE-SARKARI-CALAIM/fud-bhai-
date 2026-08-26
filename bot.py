#!/usr/bin/env python3
import os, sqlite3, datetime, logging, random, string, time, asyncio
import urllib.parse
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, filters, ContextTypes
)
import subprocess
import tempfile
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ========== FUD PROCESSING ==========
FUD_SCRIPT = "fud.py"

async def process_apk_fud(input_path, output_path):
    try:
        import sys as _sys
        cmd = f"\"{_sys.executable}\" {FUD_SCRIPT} {input_path} {output_path}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            logger.error("FUD timeout 300s")
            return False
        out=stdout.decode(errors='ignore')+stderr.decode(errors='ignore')
        logger.info(f"FUD out: {out[:1000]}")
        if proc.returncode != 0:
            logger.error(f"FUD build failed rc={proc.returncode}: {out[:1000]}")
            return False
        ok=os.path.exists(output_path) and os.path.getsize(output_path)>0
        logger.info(f"FUD exists {ok} {output_path}")
        return ok
    except Exception as e:
        logger.error(f"FUD process error: {e}")
        return False
# =========================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
_admin_raw = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw if x.strip().lstrip('-').isdigit()]
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/+WKba_8fm0hM0MzNl")
PAYMENT_UPI = os.getenv("PAYMENT_UPI", "your@upi")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "X_01")
BOT_USERNAME = os.getenv("BOT_USERNAME", "DEVILESFUDBOT")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler("bot_errors.log", encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)
DB_FILE = "devil_bot.db"

PLANS = {
    "plan_5": {"points": 5, "price": 5, "label": "5 Points"},
    "plan_10": {"points": 10, "price": 10, "label": "10 Points"},
    "plan_20": {"points": 20, "price": 20, "label": "20 Points"},
    "plan_50": {"points": 50, "price": 50, "label": "50 Points"},
}

user_last_command = {}
RATE_LIMIT_SECONDS = 2

def rate_limit(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        now = time.time()
        if uid in user_last_command and now - user_last_command[uid] < RATE_LIMIT_SECONDS:
            return
        user_last_command[uid] = now
        return await func(update, context)
    return wrapper

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        points INTEGER DEFAULT 0, total_uploads INTEGER DEFAULT 0, joined_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS apk_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT,
        file_id TEXT, status TEXT DEFAULT 'pending', upload_date TEXT, points_used INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        points_bought INTEGER, plan_name TEXT, screenshot_file_id TEXT,
        status TEXT DEFAULT 'pending', request_date TEXT, approved_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_verification (
        user_id INTEGER PRIMARY KEY, verify_code TEXT, timestamp TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def save_env(key, value):
    try:
        with open(".env", "r") as f:
            lines = f.readlines()
        with open(".env", "w") as f:
            found = False
            for line in lines:
                if line.startswith(f"{key}="):
                    f.write(f"{key}={value}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"{key}={value}\n")
    except Exception as e:
        logger.error(f"save_env error: {e}")

async def is_user_in_group(user_id, context):
    global GROUP_ID
    if GROUP_ID == 0:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logger.error(f"Group check error: {e}")
        return False

def auto_register(user):
    conn = get_db()
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, first_name, points, joined_date) VALUES (?,?,?,?,?)",
                  (user.id, user.username, user.first_name, 0, now))
        logger.info(f"Auto-registered: {user.id}")
    else:
        c.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (user.username, user.first_name, user.id))
    conn.commit()
    conn.close()

def get_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_points(uid):
    u = get_user(uid)
    return u["points"] if u else 0

def add_points(uid, pts, username=None, first_name=None):
    conn = get_db()
    c = conn.cursor()
    if username and first_name:
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?,?,?,?)",
                  (uid, username, first_name, datetime.datetime.now().isoformat()))
    c.execute("UPDATE users SET points = points + ? WHERE user_id=?", (pts, uid))
    if c.rowcount == 0:
        c.execute("INSERT INTO users (user_id, username, first_name, points, joined_date) VALUES (?,?,?,?,?)",
                  (uid, username, first_name, pts, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def deduct_points(uid, pts):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if not row or row["points"] < pts:
        conn.close()
        return False
    c.execute("UPDATE users SET points = points - ? WHERE user_id=?", (pts, uid))
    conn.commit()
    conn.close()
    return True

def get_uploads(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT filename, status, upload_date FROM apk_uploads WHERE user_id=? ORDER BY upload_date DESC LIMIT 5", (uid,))
    rows = c.fetchall()
    conn.close()
    return [(r["filename"], r["status"], r["upload_date"]) for r in rows]

def log_upload(uid, fn, fid, pts):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO apk_uploads (user_id, filename, file_id, status, upload_date, points_used) VALUES (?,?,?,?,?,?)",
              (uid, fn, fid, 'pending', datetime.datetime.now().isoformat(), pts))
    conn.commit()
    conn.close()

def create_payment(uid, amt, pts, plan):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO payments (user_id, amount, points_bought, plan_name, status, request_date) VALUES (?,?,?,?,?,?)",
              (uid, amt, pts, plan, 'pending', datetime.datetime.now().isoformat()))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_pending(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, amount, points_bought, plan_name FROM payments WHERE user_id=? AND status='pending' ORDER BY request_date DESC LIMIT 1", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_pending():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, points_bought, plan_name, request_date FROM payments WHERE status='pending' ORDER BY request_date DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_payment(pid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE id=?", (pid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_payment(pid, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE payments SET status=?, approved_date=? WHERE id=?", (status, datetime.datetime.now().isoformat(), pid))
    conn.commit()
    conn.close()

def users_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM users")
    r = c.fetchone()
    conn.close()
    return r["cnt"] if r else 0

def total_points():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(points), 0) as t FROM users")
    r = c.fetchone()
    conn.close()
    return r["t"] if r else 0

def recent_payments(lim=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, points_bought, plan_name, status, request_date FROM payments ORDER BY request_date DESC LIMIT ?", (lim,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_uploads_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM apk_uploads")
    r = c.fetchone()
    conn.close()
    return r["cnt"] if r else 0

def get_all_uploads(lim=20):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, filename, status, upload_date, points_used FROM apk_uploads ORDER BY upload_date DESC LIMIT ?", (lim,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ========== TEXT HELPERS (HTML-safe) ==========
def sep():
    return "\u2550" * 32

def sep2():
    return "\u25ac" * 24

def profile_photo(user_id, context):
    try:
        return context.bot.get_user_profile_photos(user_id, limit=1)
    except:
        return None

# ========== FAST ANIMATED START ==========
ANIM_FRAMES = ["\U0001f525", "\U0001f525\U0001f525", "\U0001f525\U0001f525\U0001f525", "\u26a1 Dev\u26a1", "\u26a1Devil\u26a1", "\U0001f525 Devils Will Rise \U0001f525"]

async def safe_edit(q, text, reply_markup=None, parse_mode="HTML"):
    try:
        await q.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await q.message.delete()
        except Exception:
            pass
        await q.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

def not_joined_text():
    return "<b>DEVILS WILL RISE</b>\n<code>{}</code>\n\n\u274c <b>ACCESS DENIED</b> \u274c\n\n\u26a0\ufe0f Group join karna zaroori hai!\n\n\U0001f4cc Status: \u274c NOT JOINED\n\n<code>{}</code>\n\n\U0001f447 Neeche button dabao\n\U0001f449 Group join karo".format(sep(), sep())

def main_menu_text(user, pts, is_first=False):
    adm = " \U0001f527 Admin" if user.id in ADMIN_IDS else ""
    welcome = "WELCOME TO HELL" if is_first else "WELCOME BACK"
    uname = user.username or 'N/A'
    return "<b>DEVILS WILL RISE</b>\n<code>{}</code>\n\n\u2b50 <b>{}</b> \u2b50\n\n\U0001f464 Name: {}\n\U0001f3c3\ufe0f User: @{}\n\U0001f194 ID: <code>{}</code>\n\U0001f4b0 Points: {}\n\n\U0001f4cc Status: \u2705 VERIFIED\n\U0001f3db\ufe0f Group: \u2705 JOINED\n\n<code>{}</code>\n\n<b>Select karo kya karna hai:</b>{}".format(sep(), welcome, user.first_name, uname, user.id, pts, sep(), adm)

# ========== HANDLERS ==========
async def animated_start(update, context):
    msg = await update.message.reply_text("\U0001f525")
    for frame in ANIM_FRAMES:
        await asyncio.sleep(0.05)
        try:
            await msg.edit_text(frame)
        except:
            pass
    await asyncio.sleep(0.1)

    user = update.effective_user
    uid = user.id

    keyboard = [
        [InlineKeyboardButton("\U0001f4e2 JOIN THIS GROUP", url=GROUP_LINK)],
        [InlineKeyboardButton("\u2705 VERIFY JOINED", callback_data="check_joined")]
    ]
    await msg.edit_text(not_joined_text(), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ========== CALLBACKS ==========
async def main_cb(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    if d == "check_joined":
        joined = await is_user_in_group(uid, context)
        if not joined:
            keyboard = [
                [InlineKeyboardButton("\U0001f4e2 JOIN THIS GROUP", url=GROUP_LINK)],
                [InlineKeyboardButton("\u2705 VERIFY JOINED", callback_data="check_joined")]
            ]
            await safe_edit(q, not_joined_text(), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return

        auto_register(q.from_user)
        pts = get_points(uid)
        is_adm = uid in ADMIN_IDS
        kb = [
            [InlineKeyboardButton("\U0001f464 Profile", callback_data="profile"),
             InlineKeyboardButton("\U0001f4b0 Buy Points", callback_data="buy_points")],
            [InlineKeyboardButton("\U0001f4e4 Upload APK", callback_data="upload_apk"),
             InlineKeyboardButton("\U0001f198 Support", callback_data="support")],
        ]
        if is_adm:
            kb.append([InlineKeyboardButton("\U0001f527 Admin Panel", callback_data="admin_panel")])

        try:
            photos = await context.bot.get_user_profile_photos(uid, limit=1)
            if photos and photos.photos:
                await q.message.delete()
                await context.bot.send_photo(
                    chat_id=q.message.chat.id,
                    photo=photos.photos[0][0].file_id,
                    caption=main_menu_text(q.from_user, pts),
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="HTML"
                )
                return
        except Exception as e:
            logger.error(f"Photo error: {e}")

        await safe_edit(q, main_menu_text(q.from_user, pts),
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    joined = await is_user_in_group(uid, context)
    if not joined:
        kb = [
            [InlineKeyboardButton("\U0001f4e2 JOIN THIS GROUP", url=GROUP_LINK)],
            [InlineKeyboardButton("\u2705 VERIFY JOINED", callback_data="check_joined")]
        ]
        await safe_edit(q, not_joined_text(), reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    auto_register(q.from_user)

    if d == "profile":
        pts = get_points(uid)
        uploads = get_uploads(uid)
        txt = "<b>PROFILE</b> \U0001f464\n<code>{}</code>\n\n\U0001f194 ID: <code>{}</code>\n\U0001f4b0 Points: {}\n\U0001f4e4 Uploads: {}\n\n<code>{}</code>\n\U0001f4cb Recent:\n".format(sep(), uid, pts, len(uploads), sep2())
        for fn, st, dt in uploads:
            e = "\u2705" if st == "approved" else "\u23f3" if st == "pending" else "\u274c"
            txt += "  {} {} ({})\n".format(e, fn, dt[:10])
        if not uploads:
            txt += "  \U0001f4ed No uploads yet.\n"
        txt += "\n<code>{}</code>".format(sep2())
        kb = [[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")]]
        await safe_edit(q, txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif d == "buy_points":
        kb = []
        for pk, p in PLANS.items():
            kb.append([InlineKeyboardButton("\U0001f4b0 {} - {} Rs".format(p['label'], p['price']), callback_data="select_{}".format(pk))])
        kb.append([InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")])
        await safe_edit(q,
            "<b>BUY POINTS</b> \U0001f4b0\n<code>{}</code>\n\n\U0001f4b3 UPI: <code>{}</code>\n\n<code>{}</code>\n\U0001f4cb Select plan:".format(sep(), PAYMENT_UPI, sep2()),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

    elif d.startswith("select_"):
        pk = d.replace("select_", "")
        p = PLANS.get(pk)
        if not p:
            await safe_edit(q, "\u274c Invalid plan.", parse_mode="HTML")
            return
        pid = create_payment(uid, p["price"], p["points"], pk)
        upi_link = "upi://pay?pa={}&pn=DEVILS+WILL+RISE&am={}&cu=INR".format(PAYMENT_UPI, p["price"])
        encoded = urllib.parse.quote(upi_link, safe='')
        qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={}".format(encoded)

        kb = [
            [InlineKeyboardButton("\u2705 I Paid - Send Screenshot", callback_data="send_screenshot")],
            [InlineKeyboardButton("\u2b05 Back", callback_data="buy_points")]
        ]

        try:
            await q.message.delete()
        except:
            pass

        await context.bot.send_photo(
            chat_id=q.message.chat.id,
            photo=qr_url,
            caption=(
                "<b>PAYMENT</b> \U0001f4f1\n<code>{}</code>\n\n"
                "\U0001f4e6 Plan: <b>{}</b>\n"
                "\U0001f194 Payment ID: <code>#{}</code>\n"
                "\U0001f4b5 Amount: <b>{} Rs</b>\n"
                "\U0001f3af Points: {}\n\n"
                "<code>{}</code>\n"
                "\U0001f4b3 <b>UPI ID:</b> <code>{}</code>\n\n"
                "<code>{}</code>\n"
                "\U0001f4f8 Screenshot bhejo payment ka!\n"
                "Admin approve karega.\n\n"
                "\U0001f194 Payment ID: <code>#{}</code> yaad rakho!"
            ).format(sep(), p['label'], pid, p['price'], p['points'], sep2(), PAYMENT_UPI, sep2(), pid),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

    elif d == "upload_apk":
        pts = get_points(uid)
        await safe_edit(q,
            "<b>UPLOAD APK</b> \U0001f4e4\n<code>{}</code>\n\n\U0001f4b0 Points: {}\n\U0001f4b8 Cost: 5 pts\n\n\u26a0\ufe0f Sirf .apk (max 50MB)\n\n<code>{}</code>\nAPK bhejo! Points auto katenge.".format(sep(), pts, sep2()),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")]]),
            parse_mode="HTML"
        )

    elif d == "support":
        await safe_edit(q,
            "<b>SUPPORT</b> \U0001f198\n<code>{}</code>\n\n\U0001f464 Contact: @{}\n\U0001f4ac Ya /feedback message\n\n<code>{}</code>".format(sep(), SUPPORT_USERNAME, sep2()),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")]]),
            parse_mode="HTML"
        )

    elif d == "send_screenshot":
        pending = get_pending(uid)
        if not pending:
            await safe_edit(q, "\u274c Koi pending payment nahi.", parse_mode="HTML")
            return
        await safe_edit(q,
            "<b>SEND SCREENSHOT</b> \U0001f4f8\n<code>{}</code>\n\n"
            "\U0001f194 Payment ID: <code>#{}</code>\n"
            "\U0001f4b5 Amount: {} Rs\n\n"
            "<code>{}</code>\n"
            "\U0001f4f8 Abhi payment screenshot/photo bhejo!\n"
            "Admin approve karega.\n\n"
            "\u26a0\ufe0f Screenshot bhejne ke baad wait karo.".format(
                sep(), pending['id'], pending['amount'], sep2()
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u274c Cancel", callback_data="main_menu")]]),
            parse_mode="HTML"
        )

    elif d == "main_menu":
        pts = get_points(uid)
        is_adm = uid in ADMIN_IDS
        kb = [
            [InlineKeyboardButton("\U0001f464 Profile", callback_data="profile"),
             InlineKeyboardButton("\U0001f4b0 Buy Points", callback_data="buy_points")],
            [InlineKeyboardButton("\U0001f4e4 Upload APK", callback_data="upload_apk"),
             InlineKeyboardButton("\U0001f198 Support", callback_data="support")],
        ]
        if is_adm:
            kb.append([InlineKeyboardButton("\U0001f527 Admin Panel", callback_data="admin_panel")])
        await safe_edit(q, main_menu_text(q.from_user, pts), reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# ========== ADMIN CALLBACKS ==========
async def admin_cb(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    if uid not in ADMIN_IDS:
        await safe_edit(q, "\u274c Unauthorized.", parse_mode="HTML")
        return

    if d == "admin_panel":
        uc = users_count()
        tp = total_points()
        pending = get_all_pending()
        apk_count = get_all_uploads_count()
        kb = [
            [InlineKeyboardButton("\u23f3 Pending ({})".format(len(pending)), callback_data="admin_pending"),
             InlineKeyboardButton("\U0001f4ca Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("\u2795 Add Points", callback_data="admin_addpoints"),
             InlineKeyboardButton("\U0001f4cb All Payments", callback_data="admin_all_payments")],
            [InlineKeyboardButton("\U0001f4e4 APKs ({})".format(apk_count), callback_data="admin_uploads"),
             InlineKeyboardButton("\U0001f504 Refresh", callback_data="admin_panel")],
            [InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")],
        ]
        await safe_edit(q,
            "<b>ADMIN PANEL</b> \U0001f527\n<code>{}</code>\n\n\U0001f465 Users: {}\n\U0001f4b0 Points: {}\n\u23f3 Pending: {}\n\n<code>{}</code>\n<b>Select karo:</b>".format(sep(), uc, tp, len(pending), sep2()),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

    elif d == "admin_pending":
        pending = get_all_pending()
        if not pending:
            await safe_edit(q,
                "\u2705 Koi pending nahi!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="admin_panel")]]),
                parse_mode="HTML"
            )
            return
        txt = "<b>PENDING</b> ({}) \u23f3\n<code>{}</code>\n\n".format(len(pending), sep())
        for p in pending:
            txt += "\U0001f194 <code>#{}</code> | \U0001f464 {}\n\U0001f4b5 {} Rs -> \U0001f3af {} pts\n\U0001f4e6 {}\n\U0001f4c5 {}\n\n".format(p['id'], p['user_id'], p['amount'], p['points_bought'], p['plan_name'], p['request_date'][:16])
        txt += "<code>{}</code>\nApprove: /approve ID\nReject: /reject ID\n".format(sep2())
        await safe_edit(q, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="admin_panel")]]), parse_mode="HTML")

    elif d == "admin_stats":
        uc = users_count()
        tp = total_points()
        rp = recent_payments(5)
        txt = "<b>STATS</b> \U0001f4ca\n<code>{}</code>\n\n\U0001f465 Users: {}\n\U0001f4b0 Points: {}\n\n\U0001f4cb Recent:\n".format(sep(), uc, tp)
        for p in rp:
            e = "\u2705" if p["status"] == "approved" else "\u23f3" if p["status"] == "pending" else "\u274c"
            txt += "  {} <code>#{}</code> - {} Rs ({})\n".format(e, p['id'], p['amount'], p['status'])
        txt += "\n<code>{}</code>".format(sep2())
        await safe_edit(q, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="admin_panel")]]), parse_mode="HTML")

    elif d == "admin_addpoints":
        await safe_edit(q,
            "<b>ADD POINTS</b> \u2795\n<code>{}</code>\n\nCommand:\n<code>/addpoints USER_ID POINTS</code>\n\nExample:\n<code>/addpoints 123456789 10</code>\n\n<code>{}</code>".format(sep(), sep2()),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="admin_panel")]]),
            parse_mode="HTML"
        )

    elif d == "admin_all_payments":
        rp = recent_payments(10)
        if not rp:
            txt = "  \U0001f4ed Koi payments nahi."
        else:
            txt = "<b>ALL PAYMENTS</b> \U0001f4cb\n<code>{}</code>\n\n".format(sep())
            for p in rp:
                e = "\u2705" if p["status"] == "approved" else "\u23f3" if p["status"] == "pending" else "\u274c"
                txt += "{} <code>#{}</code> | \U0001f464 {}\n  \U0001f4b5 {} Rs -> \U0001f3af {} pts\n  \U0001f4c5 {} | {}\n\n".format(e, p['id'], p['user_id'], p['amount'], p['points_bought'], p['request_date'][:10], p['status'])
        txt += "<code>{}</code>".format(sep2())
        await safe_edit(q, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="admin_panel")]]), parse_mode="HTML")

    elif d == "admin_uploads":
        uploads = get_all_uploads(15)
        if not uploads:
            txt = "\U0001f4ed Koi uploads nahi."
        else:
            txt = "<b>ALL APK UPLOADS</b> \U0001f4e4\n<code>{}</code>\n\n".format(sep())
            for u in uploads:
                e = "\u2705" if u["status"] == "approved" else "\u23f3" if u["status"] == "pending" else "\u274c" if u["status"] == "rejected" else "\U0001f504"
                txt += "{} <code>#{}</code> | \U0001f464 <code>{}</code>\n  \U0001f4e6 {} | -{} pts\n  \U0001f4c5 {} | {}\n\n".format(e, u['id'], u['user_id'], u['filename'], u['points_used'], u['upload_date'][:10], u['status'])
        txt += "<code>{}</code>".format(sep2())
        await safe_edit(q, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="admin_panel")]]), parse_mode="HTML")

# ========== COMMANDS ==========
@rate_limit
async def cmd_start(update, context):
    await animated_start(update, context)

@rate_limit
async def cmd_getid(update, context):
    u = update.effective_user
    c = update.effective_chat
    joined = await is_user_in_group(u.id, context)
    st = "\u2705 JOINED" if joined else "\u274c NOT JOINED"
    grp = "\u2705 SET" if GROUP_ID != 0 else "\u274c NOT SET"
    uname = u.username or 'N/A'
    await update.message.reply_text(
        "<b>ID INFO</b> \U0001f194\n<code>{}</code>\n\n\U0001f464 User ID: <code>{}</code>\n\U0001f4ac Chat ID: <code>{}</code>\n\U0001f3c3\ufe0f Type: {}\n\U0001f3c3\ufe0f Username: @{}\n\U0001f3db\ufe0f Group: {}\n\u2699\ufe0f Group Config: {}\n\n<code>{}</code>\n\U0001f4cb Admin ko yeh ID bhejo!".format(
            sep(), u.id, c.id, c.type, uname, st, grp, sep2()
        ),
        parse_mode="HTML"
    )
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid,
                "<b>NEW USER</b> \U0001f194\n<code>{}</code>\n\n\U0001f464 Name: {}\n\U0001f3c3\ufe0f @{}\n\U0001f194 ID: <code>{}</code>\n\U0001f3db\ufe0f Group: {}\n<code>{}</code>".format(sep(), u.first_name, uname, u.id, st, sep2()),
                parse_mode="HTML"
            )
        except:
            pass

@rate_limit
async def cmd_profile(update, context):
    uid = update.effective_user.id
    if not (await is_user_in_group(uid, context)):
        kb = [[InlineKeyboardButton("\U0001f4e2 JOIN GROUP", url=GROUP_LINK)]]
        await update.message.reply_text("\u274c NOT JOINED! Group join karo.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    auto_register(update.effective_user)
    pts = get_points(uid)
    uploads = get_uploads(uid)
    txt = "<b>PROFILE</b> \U0001f464\n<code>{}</code>\n\n\U0001f194 <code>{}</code>\n\U0001f4b0 Points: {}\n\U0001f4e4 Uploads: {}\n\n\U0001f4cb Recent:\n".format(sep(), uid, pts, len(uploads))
    for fn, st, dt in uploads:
        e = "\u2705" if st == "approved" else "\u23f3" if st == "pending" else "\u274c"
        txt += "  {} {} ({})\n".format(e, fn, dt[:10])
    if not uploads:
        txt += "  \U0001f4ed No uploads.\n"
    txt += "\n<code>{}</code>".format(sep2())
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")]]), parse_mode="HTML")

@rate_limit
async def cmd_buy(update, context):
    uid = update.effective_user.id
    if not (await is_user_in_group(uid, context)):
        kb = [[InlineKeyboardButton("\U0001f4e2 JOIN GROUP", url=GROUP_LINK)]]
        await update.message.reply_text("\u274c NOT JOINED! Group join karo.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    kb = []
    for pk, p in PLANS.items():
        kb.append([InlineKeyboardButton("\U0001f4b0 {} - {} Rs".format(p['label'], p['price']), callback_data="select_{}".format(pk))])
    kb.append([InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")])
    await update.message.reply_text(
        "<b>BUY POINTS</b> \U0001f4b0\n<code>{}</code>\n\n\U0001f4b3 UPI: <code>{}</code>\n\n<code>{}</code>\n\U0001f4cb Select plan:".format(sep(), PAYMENT_UPI, sep2()),
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML"
    )

@rate_limit
async def cmd_upload(update, context):
    uid = update.effective_user.id
    if not (await is_user_in_group(uid, context)):
        kb = [[InlineKeyboardButton("\U0001f4e2 JOIN GROUP", url=GROUP_LINK)]]
        await update.message.reply_text("\u274c NOT JOINED! Group join karo.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    auto_register(update.effective_user)
    pts = get_points(uid)
    await update.message.reply_text(
        "<b>UPLOAD APK</b> \U0001f4e4\n<code>{}</code>\n\n\U0001f4b0 Points: {}\n\U0001f4b8 Cost: 5 pts\n\nAPK bhejo!".format(sep(), pts),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")]]),
        parse_mode="HTML"
    )

@rate_limit
async def cmd_support(update, context):
    await update.message.reply_text(
        "<b>SUPPORT</b> \U0001f198\n<code>{}</code>\n\n\U0001f464 Contact: @{}\n\U0001f4ac Ya /feedback <message>".format(sep(), SUPPORT_USERNAME),
        parse_mode="HTML"
    )

@rate_limit
async def cmd_feedback(update, context):
    msg = ' '.join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /feedback <message>")
        return
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid, "\U0001f4e9 Feedback from {}:\n{}".format(update.effective_user.id, msg))
        except:
            pass
    await update.message.reply_text("\u2705 Feedback sent!")

async def handle_apk(update, context):
    uid = update.effective_user.id
    if not (await is_user_in_group(uid, context)):
        return
    auto_register(update.effective_user)
    doc = update.message.document
    if not doc or not doc.file_name:
        return
    if not doc.file_name.lower().endswith('.apk'):
        await update.message.reply_text("\u274c Sirf .apk files!")
        return
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("\u274c Max 20MB! Telegram limit hai.")
        return
    if not deduct_points(uid, 5):
        pts = get_points(uid)
        await update.message.reply_text("\u274c Points nahi! Have: {}, Need: 5\n/buy se kharido.".format(pts))
        return

    fid = doc.file_id
    log_upload(uid, doc.file_name, fid, 5)

    msg = await update.message.reply_text(
        "\u23f3 <b>PROCESSING...</b>\n<code>{}</code>\n\n\U0001f4e6 File: {}\n\u2699\ufe0f Download ho raha hai...".format(sep(), doc.file_name),
        parse_mode="HTML"
    )

    if not os.path.exists(FUD_SCRIPT):
        await msg.edit_text(
            "<b>APK RECEIVED</b> \U0001f4e4\n<code>{}</code>\n\n\U0001f4e6 File: {}\n\U0001f4b0 Points: -5\n\u23f3 Status: PENDING\n\n<code>{}</code>\nAdmin jald approve karega.".format(sep(), doc.file_name, sep2()),
            parse_mode="HTML"
        )
    else:
        try:
            file = await context.bot.get_file(doc.file_id)
        except Exception as e:
            add_points(uid, 5)
            await msg.edit_text("\u274c File download fail! Points wapas.\nError: {}".format(str(e)[:100]))
            return
        temp_input = "temp_{}_{}.apk".format(uid, int(time.time()))
        await file.download_to_drive(temp_input)

        await msg.edit_text(
            "\u23f3 <b>PROCESSING...</b>\n<code>{}</code>\n\n\U0001f4e6 File: {}\n\u2699\ufe0f FUD ban raha hai... 2-3 min".format(sep(), doc.file_name),
            parse_mode="HTML"
        )

        temp_output = temp_input.replace(".apk", "_fud.apk")
        success = await process_apk_fud(temp_input, temp_output)

        os.remove(temp_input)

        if not success or not os.path.exists(temp_output):
            add_points(uid, 5)
            await msg.edit_text("\u274c FUD build fail! Points wapas kar diye.")
            return

        with open(temp_output, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename="FUD_{}".format(doc.file_name),
                caption="\u2705 FUD APK ready!\nPoints used: 5\nRemaining: {}".format(get_points(uid))
            )
        os.remove(temp_output)

        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE apk_uploads SET status='processed' WHERE user_id=? AND filename=?", (uid, doc.file_name))
        conn.commit()
        conn.close()
        await msg.delete()

    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid,
                "<b>APK UPLOADED</b> \U0001f4e4\n<code>{}</code>\n\n\U0001f464 User: <code>{}</code>\n\U0001f4e6 File: {}\n\u23f3 Status: PENDING\n\n<code>{}</code>".format(sep(), uid, doc.file_name, sep2()),
                parse_mode="HTML"
            )
            await context.bot.send_document(aid, fid, filename=doc.file_name)
        except Exception as e:
            logger.error(f"Admin APK notify fail: {e}")

async def handle_screenshot(update, context):
    uid = update.effective_user.id
    pending = get_pending(uid)
    if not pending:
        return
    if update.message.photo:
        fid = update.message.photo[-1].file_id
    elif update.message.document:
        fid = update.message.document.file_id
    else:
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE payments SET screenshot_file_id=? WHERE id=?", (fid, pending["id"]))
    conn.commit()
    conn.close()

    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(aid,
                "<b>NEW PAYMENT</b> \U0001f4f7\n<code>{}</code>\n\n\U0001f194 Payment ID: <code>#{}</code>\n\U0001f464 User: {}\n\U0001f4e6 Plan: {}\n\U0001f4b5 {} Rs -> \U0001f3af {} pts\n\n<code>{}</code>\n\u26a1 Approve: /approve {}\n\u26a1 Reject: /reject {}".format(
                    sep(), pending['id'], uid, pending['plan_name'], pending['amount'], pending['points_bought'], sep2(), pending['id'], pending['id']
                ),
                parse_mode="HTML"
            )
            await context.bot.send_photo(aid, fid)
        except Exception as e:
            logger.error(f"Admin notify fail: {e}")

    await update.message.reply_text(
        "<b>SCREENSHOT RECEIVED</b> \U0001f4f8\n<code>{}</code>\n\n\U0001f194 Payment ID: <code>#{}</code>\n\u23f3 Waiting for admin...\n\n<code>{}</code>".format(sep(), pending['id'], sep2()),
        parse_mode="HTML"
    )

# ========== ADMIN COMMANDS ==========
@rate_limit
async def cmd_setadmin(update, context):
    global ADMIN_IDS
    uid = update.effective_user.id
    if len(ADMIN_IDS) == 0:
        ADMIN_IDS.append(uid)
        save_env("ADMIN_IDS", str(uid))
        await update.message.reply_text(
            "<b>ADMIN SET</b> \u2705\n<code>{}</code>\n\n\U0001f194 Your ID: <code>{}</code>\n\nAb /admin se panel kholo!\n\n<code>{}</code>".format(sep(), uid, sep2()),
            parse_mode="HTML"
        )
        return
    if uid not in ADMIN_IDS:
        await update.message.reply_text("\u274c Unauthorized.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /setadmin USER_ID")
        return
    try:
        na = int(args[0])
        if na not in ADMIN_IDS:
            ADMIN_IDS.append(na)
        await update.message.reply_text("\u2705 Admin added: {}".format(na))
    except:
        await update.message.reply_text("\u274c Invalid ID.")

@rate_limit
async def cmd_admin(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("\u274c Unauthorized.")
        return
    uc = users_count()
    tp = total_points()
    pending = get_all_pending()
    grp = "\u2705 Set" if GROUP_ID != 0 else "\u274c Not Set"
    kb = [
        [InlineKeyboardButton("\u23f3 Pending ({})".format(len(pending)), callback_data="admin_pending"),
         InlineKeyboardButton("\U0001f4ca Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("\u2795 Add Points", callback_data="admin_addpoints"),
         InlineKeyboardButton("\U0001f4cb All Payments", callback_data="admin_all_payments")],
        [InlineKeyboardButton("\U0001f504 Refresh", callback_data="admin_panel"),
         InlineKeyboardButton("\u2b05\ufe0f Back", callback_data="main_menu")],
    ]
    await update.message.reply_text(
        "<b>ADMIN PANEL</b> \U0001f527\n<code>{}</code>\n\n\U0001f465 Users: {}\n\U0001f4b0 Points: {}\n\u23f3 Pending: {}\n\U0001f3db\ufe0f Group: {}\n\n<code>{}</code>\n<b>Select karo:</b>".format(sep(), uc, tp, len(pending), grp, sep2()),
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML"
    )

@rate_limit
async def cmd_approve(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("\u274c Unauthorized.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /approve PAYMENT_ID")
        return
    try:
        pid = int(args[0])
    except:
        await update.message.reply_text("\u274c Invalid ID.")
        return
    p = get_payment(pid)
    if not p:
        await update.message.reply_text("\u274c Payment not found.")
        return
    if p["status"] != 'pending':
        await update.message.reply_text("\u274c Already {}.".format(p['status']))
        return
    update_payment(pid, 'approved')
    add_points(p["user_id"], p["points_bought"])
    nb = get_points(p["user_id"])
    await update.message.reply_text(
        "<b>APPROVED</b> \u2705\n<code>{}</code>\n\n\U0001f194 Payment: <code>#{}</code>\n\U0001f464 User: {}\n\U0001f3af Points: {}\n\U0001f4b0 Balance: {}\n\n<code>{}</code>".format(sep(), pid, p['user_id'], p['points_bought'], nb, sep2()),
        parse_mode="HTML"
    )
    try:
        is_adm = p["user_id"] in ADMIN_IDS
        kb = [
            [InlineKeyboardButton("\U0001f464 Profile", callback_data="profile"),
             InlineKeyboardButton("\U0001f4b0 Buy Points", callback_data="buy_points")],
            [InlineKeyboardButton("\U0001f4e4 Upload APK", callback_data="upload_apk"),
             InlineKeyboardButton("\U0001f198 Support", callback_data="support")],
        ]
        if is_adm:
            kb.append([InlineKeyboardButton("\U0001f527 Admin Panel", callback_data="admin_panel")])
        await context.bot.send_message(p["user_id"],
            "<b>PAYMENT APPROVED</b> \u2705\n<code>{}</code>\n\n\U0001f194 Payment: <code>#{}</code>\n\U0001f3af Points: {}\n\U0001f4b0 Balance: {}\n\n<code>{}</code>\n<b>Select karo:</b>".format(sep(), pid, p['points_bought'], nb, sep2()),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Approve notify fail: {e}")

@rate_limit
async def cmd_reject(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("\u274c Unauthorized.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /reject PAYMENT_ID")
        return
    try:
        pid = int(args[0])
    except:
        await update.message.reply_text("\u274c Invalid ID.")
        return
    p = get_payment(pid)
    if not p:
        await update.message.reply_text("\u274c Payment not found.")
        return
    if p["status"] != 'pending':
        await update.message.reply_text("\u274c Already {}.".format(p['status']))
        return
    update_payment(pid, 'rejected')
    await update.message.reply_text("\u274c \u2550\u2550 REJECTED \u2550\u2550\nPayment #{}".format(pid))
    try:
        await context.bot.send_message(p["user_id"],
            "\u274c \u2550\u2550 PAYMENT REJECTED \u2550\u2550\n\U0001f194 Payment: #{}\nSupport se contact karo.".format(pid))
    except:
        pass

@rate_limit
async def cmd_addpoints(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("\u274c Unauthorized.")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /addpoints USER_ID POINTS")
        return
    try:
        tid = int(args[0])
        pts = int(args[1])
    except:
        await update.message.reply_text("\u274c Invalid numbers.")
        return
    if pts <= 0:
        await update.message.reply_text("\u274c Points must be positive.")
        return
    add_points(tid, pts)
    nb = get_points(tid)
    await update.message.reply_text(
        "<b>POINTS ADDED</b> \u2705\n<code>{}</code>\n\n\U0001f464 User: {}\n\U0001f3af Added: {}\n\U0001f4b0 Balance: {}\n\n<code>{}</code>".format(sep(), tid, pts, nb, sep2()),
        parse_mode="HTML"
    )
    try:
        await context.bot.send_message(tid,
            "<b>POINTS ADDED</b> \U0001f4b0\n<code>{}</code>\n\n\U0001f3af Added: {}\n\U0001f4b0 Balance: {}".format(sep(), pts, nb),
            parse_mode="HTML"
        )
    except:
        pass

# ========== GROUP EVENTS ==========
async def handle_new_member(update, context):
    for nm in update.message.new_chat_members:
        if nm.id == context.bot.id:
            global GROUP_ID
            if GROUP_ID == 0:
                GROUP_ID = update.message.chat.id
                save_env("GROUP_ID", str(GROUP_ID))
                logger.info(f"Auto-captured group ID: {GROUP_ID}")
                for aid in ADMIN_IDS:
                    try:
                        await context.bot.send_message(aid,
                            "<b>GROUP DETECTED</b> \U0001f3db\ufe0f\n<code>{}</code>\n\nGroup: {}\nID: <code>{}</code>\n\n<code>{}</code>\nGroup ID auto set ho gaya!".format(sep(), update.message.chat.title, GROUP_ID, sep2()),
                            parse_mode="HTML"
                        )
                    except:
                        pass
            continue
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        conn = get_db()
        c = conn.cursor()
        c.execute("REPLACE INTO group_verification (user_id, verify_code, timestamp) VALUES (?,?,?)",
                  (nm.id, code, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        kb = [[InlineKeyboardButton("\u2705 VERIFY: {}".format(code), callback_data="verify_{}_{}".format(nm.id, code))]]
        await update.message.reply_text(
            "<b>WELCOME</b> \U0001f44b\n<code>{}</code>\n\n\U0001f44b Welcome {}!\n\n\U0001f510 Verify code: <code>{}</code>\nNeeche button dabao:".format(sep(), nm.first_name, code),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

async def auto_detect_group(update, context):
    global GROUP_ID
    chat = update.effective_chat
    if chat.type in ["group", "supergroup"] and GROUP_ID == 0:
        GROUP_ID = chat.id
        save_env("GROUP_ID", str(GROUP_ID))
        logger.info(f"Auto-captured group ID from message: {GROUP_ID}")
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(aid,
                    "<b>GROUP DETECTED</b> \U0001f3db\ufe0f\n<code>{}</code>\n\nGroup: {}\nID: <code>{}</code>\n\n<code>{}</code>\nGroup ID auto set ho gaya!".format(sep(), chat.title, GROUP_ID, sep2()),
                    parse_mode="HTML"
                )
            except:
                pass

async def verify_cb(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    if not d.startswith("verify_"):
        return
    parts = d.split("_")
    tid = int(parts[1])
    code = parts[2]
    uid = q.from_user.id
    if uid != tid:
        await q.answer("\u274c Yeh tumhare liye nahi!", show_alert=True)
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT verify_code FROM group_verification WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row and row["verify_code"] == code:
        c.execute("DELETE FROM group_verification WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        auto_register(q.from_user)
        await q.edit_message_text(
            "<b>VERIFIED!</b> \u2705\n<code>{}</code>\n\n\U0001f194 ID: <code>{}</code>\n\U0001f3db\ufe0f Group: \u2705 JOINED\n\nAb bot mein /start maro!\n\n<code>{}</code>".format(sep(), uid, sep2()),
            parse_mode="HTML"
        )
    else:
        conn.close()
        await q.edit_message_text("\u274c Galat code! Admin se contact karo.")

@rate_limit
async def cmd_setgroup(update, context):
    global GROUP_ID
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("\u274c Unauthorized.")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "Usage: /setgroup CHAT_ID\n\n"
            "Bot ko group mein add karo,\n"
            "phir /getid se chat ID lo,\n"
            "phir /setgroup <chat_id> likho"
        )
        return
    try:
        gid = int(args[0])
        GROUP_ID = gid
        save_env("GROUP_ID", str(gid))
        await update.message.reply_text(
            "<b>GROUP SET!</b> \u2705\n<code>{}</code>\n\n\U0001f3db\ufe0f Group ID: <code>{}</code>\nAb group check hoga!\n\n<code>{}</code>".format(sep(), gid, sep2()),
            parse_mode="HTML"
        )
    except:
        await update.message.reply_text("\u274c Invalid ID.")

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")

async def post_init(application):
    uc = [
        BotCommand("start", "Start bot"), BotCommand("getid", "Get your ID"),
        BotCommand("profile", "Profile"), BotCommand("buy", "Buy points"),
        BotCommand("upload", "Upload APK"), BotCommand("support", "Support"),
        BotCommand("feedback", "Feedback"),
    ]
    ac = uc + [
        BotCommand("setadmin", "Add admin"),
        BotCommand("setgroup", "Set group ID"),
        BotCommand("admin", "Admin Panel"), BotCommand("approve", "Approve payment"),
        BotCommand("reject", "Reject payment"), BotCommand("addpoints", "Add points"),
    ]
    for aid in ADMIN_IDS:
        try:
            await application.bot.set_my_commands(ac, scope=BotCommandScopeChat(chat_id=aid))
        except:
            pass
    await application.bot.set_my_commands(uc)

def _health():
    port = int(os.getenv("PORT", "10000"))
    class H(BaseHTTPRequestHandler):
        def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
        def log_message(self, *a, **k): pass
    try: HTTPServer(("0.0.0.0", port), H).serve_forever()
    except Exception as e: logger.error(f"health server fail: {e}")

def main():
    threading.Thread(target=_health, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("getid", cmd_getid))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CommandHandler("upload", cmd_upload))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("feedback", cmd_feedback))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("addpoints", cmd_addpoints))
    app.add_handler(CommandHandler("setadmin", cmd_setadmin))
    app.add_handler(CommandHandler("setgroup", cmd_setgroup))

    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify_"))
    app.add_handler(CallbackQueryHandler(main_cb))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_screenshot))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_apk))
    app.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS & ~filters.COMMAND, auto_detect_group))

    app.add_error_handler(error_handler)

    print("Devils Will Rise Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()