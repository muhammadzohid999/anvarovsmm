import asyncio
import csv
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ==========================================
# 🛠 SOZLAMALAR (SIZNING MA'LUMOTLARINGIZ)
# ==========================================
BOT_TOKEN = "9092091643:AAFHohne903GXjP2tP9JFPMmR_53EEevKNU"

ADMIN_ID = 9051195824
ADMIN_USERNAME = "@muhammadzoxidanvarov"
CHANNEL_LINK = "https://t.me/AnvarovMuhammadzoxid"


def is_admin(user_id: int) -> bool:
    return int(user_id) == ADMIN_ID


# ==========================================
# 🗄 MA'LUMOTLAR BAZASI (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            joined_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            username TEXT,
            service_name TEXT,
            details TEXT,
            file_id TEXT,
            file_type TEXT,
            phone TEXT,
            status TEXT DEFAULT '🆕 Yangi',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_user(user_id: int, full_name: str, username: str):
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, full_name, username, joined_at) VALUES (?, ?, ?, ?)",
        (user_id, full_name, username, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()


def create_order(user_id, full_name, username, service_name, details, file_id, file_type, phone) -> int:
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, full_name, username, service_name, details, file_id, file_type, phone, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '🆕 Yangi', ?)
    """, (user_id, full_name, username, service_name, details, file_id, file_type, phone, datetime.now().strftime("%Y-%m-%d %H:%M")))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def update_order_status(order_id: int, status_text: str):
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status_text, order_id))
    conn.commit()
    cur.execute("SELECT user_id, service_name FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_order_by_id(order_id: int):
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, full_name, username, service_name, details, file_id, file_type, phone, status, created_at
        FROM orders WHERE id = ?
    """, (order_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_orders_by_filter(filter_type: str, limit: int = 10):
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    if filter_type == "new":
        cur.execute("""
            SELECT id, user_id, full_name, username, service_name, details, file_id, file_type, phone, status, created_at
            FROM orders WHERE status = '🆕 Yangi' ORDER BY id DESC LIMIT ?
        """, (limit,))
    elif filter_type == "active":
        cur.execute("""
            SELECT id, user_id, full_name, username, service_name, details, file_id, file_type, phone, status, created_at
            FROM orders WHERE status IN ('✅ Qabul qilindi', '⏳ Jarayonda') ORDER BY id DESC LIMIT ?
        """, (limit,))
    else:
        cur.execute("""
            SELECT id, user_id, full_name, username, service_name, details, file_id, file_type, phone, status, created_at
            FROM orders ORDER BY id DESC LIMIT ?
        """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_orders(user_id: int):
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT id, service_name, status, created_at FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_detailed_stats():
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status = '🆕 Yangi'")
    new_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status IN ('✅ Qabul qilindi', '⏳ Jarayonda')")
    active_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status = '🎉 Bajarildi'")
    done_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status = '❌ Rad etildi'")
    rejected_orders = cur.fetchone()[0]
    conn.close()
    return users_count, total_orders, new_orders, active_orders, done_orders, rejected_orders


def get_all_users():
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    return users


def export_orders_to_csv(filename="buyurtmalar.csv"):
    conn = sqlite3.connect("smm_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, full_name, username, phone, service_name, details, status, created_at FROM orders ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    with open(filename, mode="w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["ID", "User ID", "Mijoz ismi", "Username", "Telefon", "Xizmat turi", "Tafsilotlar", "Holati", "Sana"])
        writer.writerows(rows)
    return filename


# ==========================================
# 📋 XIZMATLAR LUG'ATI VA MATNLAR
# ==========================================
SERVICES_TEXT = (
    "💎 <b>BIZNING XIZMATLARIMIZ:</b>\n\n"
    "🎓 <b>Talabalar uchun:</b>\n"
    "▫️ Akademik taqdimotlarning (slaydlar) professional va tizimli tarzda tayyorlanishi\n"
    "▫️ Murakkab matnli ma'lumotlarni tushunarli formatga keltirish\n\n"
    "🚀 <b>Onlayn sotuvchilar uchun:</b>\n"
    "▫️ Xaridorlar e'tiborini jalb etuvchi va sotuv hajmini oshiruvchi infografikalar yaratish\n"
    "▫️ Buyurtmalarni qabul qilish va jarayonlarni avtomatlashtirish uchun Telegram botlar ishlab chiqish\n\n"
    "🎬 <b>Kontent makerlar uchun:</b>\n"
    "▫️ Instagram Reels uchun jozibali muqovalar (cover) tayyorlash\n"
    "▫️ Videolar ko'rilishini oshiruvchi professional prevyular (thumbnail) yaratish\n"
    "▫️ Shaxsiy brend uchun professional logotip va bannerlar dizayni\n\n"
    "🎮 <b>Geymerlar uchun:</b>\n"
    "▫️ O'yinlar uchun ichki valyutalarni (UC, Diamonds, CP va h.k.) to'ldirib berish\n"
    "▫️ O'yin akkauntlari uchun tezkor, ishonchli va hamyonbop top-up xizmatlari\n\n"
    "👇 <b>Buyurtma berish uchun kerakli yo'nalishni tanlang:</b>"
)

SERVICES = {
    "srv:slide": {
        "title": "🎓 Akademik taqdimotlar (Slaydlar)",
        "prompt": "✍️ <b>Slayd mavzusi va talablarni yozib yuboring:</b>\n<i>(Fan nomi, slaydlar soni, tili va muddatni ko'rsating. Qo'shimcha fayl yoki rasm bo'lsa, biriktirib yuborishingiz mumkin)</i>"
    },
    "srv:text": {
        "title": "🎓 Matnli ma'lumotlarni formatlash",
        "prompt": "✍️ <b>Matn mavzusi yoki topshiriq shartlarini yuboring:</b>\n<i>(Kerakli format, sahifalar soni yoki tahrirlanishi kerak bo'lgan faylni yuborishingiz mumkin)</i>"
    },
    "srv:info": {
        "title": "🚀 Sotuvchi infografika dizayni",
        "prompt": "🛍 <b>Mahsulotingiz haqida ma'lumot yuboring:</b>\n<i>(Mahsulot nomi, asosiy afzalliklari, qaysi platforma uchunligi va mahsulot rasmini biriktirib yuboring)</i>"
    },
    "srv:tgbot": {
        "title": "🚀 Biznes uchun Telegram bot",
        "prompt": "🤖 <b>Qanday bot kerakligini qisqacha ta'riflang:</b>\n<i>(Savdo boti, katalog bot, buyurtma qabul qiluvchi bot yoki kerakli funksiyalar haqida yozing)</i>"
    },
    "srv:reels": {
        "title": "🎬 Instagram Reels muqovasi (Cover)",
        "prompt": "📱 <b>Reels mavzusi va muqovaga yoziladigan matnni yuboring:</b>\n<i>(Agar muqovada o'zingizning rasmingiz bo'lishini xohlasangiz, rasmni ham biriktirib yuboring)</i>"
    },
    "srv:thumb": {
        "title": "🎬 Professional Prevyu (Thumbnail)",
        "prompt": "🖼 <b>Video mavzusi, prevyudagi yozuv va g'oyangizni yozing:</b>\n<i>(Kerakli rasm yoki kadr bo'lsa, xabarga biriktirib yuborishingiz mumkin)</i>"
    },
    "srv:logo": {
        "title": "🎬 Logotip va Banner dizayni",
        "prompt": "✨ <b>Brendingiz nomi, sohasi va yoqtirgan ranglaringiz haqida yozing:</b>\n<i>(Logotip kerakmi yoki banner? Uslub bo'yicha fikrlaringizni qoldiring)</i>"
    },
    "srv:uc": {
        "title": "🎮 O'yin valyutalari (UC, Diamonds, CP)",
        "prompt": "🪙 <b>O'yin nomini, qancha valyuta kerakligini va o'yin ID (Player ID) raqamingizni yozing:</b>\n<i>(Masalan: PUBG Mobile - 660 UC - ID: 5123456789)</i>"
    },
    "srv:topup": {
        "title": "🎮 O'yin akkauntlariga tezkor Top-up",
        "prompt": "⚡️ <b>Qaysi o'yin yoki xizmat uchun Top-up/Pass kerakligini hamda akkaunt ID ma'lumotlarini yozing:</b>"
    }
}

STATUS_MAP = {
    "accept": "✅ Qabul qilindi",
    "work": "⏳ Jarayonda",
    "done": "🎉 Bajarildi",
    "reject": "❌ Rad etildi"
}


# ==========================================
# 🔄 FSM HOLATLARI (STATES)
# ==========================================
class OrderState(StatesGroup):
    waiting_for_details = State()
    waiting_for_phone = State()
    waiting_for_confirm = State()


class AdminState(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_reply = State()
    waiting_for_order_id = State()


# ==========================================
# ⌨️ KLAVIATURALAR (KEYBOARDS)
# ==========================================
def main_menu_kb(user_id: int = 0):
    kb = [
        [KeyboardButton(text="💎 Bizning xizmatlarimiz")],
        [KeyboardButton(text="🗂 Mening buyurtmalarim"), KeyboardButton(text="🌟 Portfolio")],
        [KeyboardButton(text="☎️ Bog'lanish")]
    ]
    if is_admin(user_id):
        kb.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def categories_inline_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎓 Talabalar uchun", callback_data="cat:stud")],
            [InlineKeyboardButton(text="🚀 Onlayn sotuvchilar uchun", callback_data="cat:sell")],
            [InlineKeyboardButton(text="🎬 Kontent makerlar uchun", callback_data="cat:cont")],
            [InlineKeyboardButton(text="🎮 Geymerlar uchun", callback_data="cat:game")],
        ]
    )


def sub_services_kb(category: str):
    buttons = []
    if category == "cat:stud":
        buttons = [
            [InlineKeyboardButton(text="▫️ Akademik taqdimotlar (Slaydlar)", callback_data="srv:slide")],
            [InlineKeyboardButton(text="▫️ Matnli ma'lumotlarni formatlash", callback_data="srv:text")],
        ]
    elif category == "cat:sell":
        buttons = [
            [InlineKeyboardButton(text="▫️ Sotuvchi infografikalar yaratish", callback_data="srv:info")],
            [InlineKeyboardButton(text="▫️ Avtomatlashtirilgan Telegram botlar", callback_data="srv:tgbot")],
        ]
    elif category == "cat:cont":
        buttons = [
            [InlineKeyboardButton(text="▫️ Instagram Reels muqovalar (Cover)", callback_data="srv:reels")],
            [InlineKeyboardButton(text="▫️ Professional Prevyular (Thumbnail)", callback_data="srv:thumb")],
            [InlineKeyboardButton(text="▫️ Logotip va Bannerlar dizayni", callback_data="srv:logo")],
        ]
    elif category == "cat:game":
        buttons = [
            [InlineKeyboardButton(text="▫️ O'yin valyutalari (UC, Diamonds, CP)", callback_data="srv:uc")],
            [InlineKeyboardButton(text="▫️ Tezkor va ishonchli Top-up xizmati", callback_data="srv:topup")],
        ]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga qaytish", callback_data="back:cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )


def confirm_order_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash va yuborish", callback_data="order:confirm"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="order:cancel")
            ]
        ]
    )


def admin_order_kb(order_id: int, user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"st:{order_id}:accept"),
                InlineKeyboardButton(text="⏳ Jarayonda", callback_data=f"st:{order_id}:work")
            ],
            [
                InlineKeyboardButton(text="🎉 Bajarildi", callback_data=f"st:{order_id}:done"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"st:{order_id}:reject")
            ],
            [
                InlineKeyboardButton(text="✉️ Mijozga xabar / fayl yuborish", callback_data=f"reply:{user_id}:{order_id}")
            ]
        ]
    )


def admin_panel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆕 Yangi buyurtmalar", callback_data="adm:list:new"),
                InlineKeyboardButton(text="⏳ Jarayondagilar", callback_data="adm:list:active")
            ],
            [
                InlineKeyboardButton(text="📦 Oxirgi 10 ta buyurtma", callback_data="adm:list:all"),
                InlineKeyboardButton(text="🔍 ID orqali topish", callback_data="adm:search")
            ],
            [
                InlineKeyboardButton(text="📊 Statistika (Yangilash)", callback_data="adm:stats"),
                InlineKeyboardButton(text="📥 Excel (CSV) yuklash", callback_data="adm:export")
            ],
            [
                InlineKeyboardButton(text="📢 Barchaga xabar yuborish (Reklama)", callback_data="adm:broadcast")
            ]
        ]
    )


def format_admin_order_text(oid, uid, fname, uname, sname, details, phone, status, cdate):
    uname_display = f"@{uname}" if uname and uname != "yo'q" else "Mavjud emas"
    return (
        f"🔔 <b>BUYURTMA #{oid}</b>\n"
        f"📊 <b>Holati:</b> {status}\n"
        f"─────────────────\n"
        f"👤 <b>Mijoz:</b> <a href='tg://user?id={uid}'>{fname}</a> ({uname_display})\n"
        f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n"
        f"💎 <b>Xizmat:</b> {sname}\n"
        f"📝 <b>Tafsilotlar:</b>\n{details}\n"
        f"─────────────────\n"
        f"🕒 <b>Sana:</b> {cdate}"
    )


async def send_order_card_to_admin(bot: Bot, order_row):
    oid, uid, fname, uname, sname, details, file_id, file_type, phone, status, cdate = order_row
    text = format_admin_order_text(oid, uid, fname, uname, sname, details, phone, status, cdate)
    kb = admin_order_kb(oid, uid)

    if file_type == "photo" and file_id:
        await bot.send_photo(ADMIN_ID, photo=file_id, caption=text, reply_markup=kb)
    elif file_type == "document" and file_id:
        await bot.send_document(ADMIN_ID, document=file_id, caption=text, reply_markup=kb)
    else:
        await bot.send_message(ADMIN_ID, text, reply_markup=kb)


# ==========================================
# 🚀 ROUTER VA ASOSIY BUYRUQLAR
# ==========================================
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    add_user(
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username or "yo'q"
    )
    welcome_text = (
        f"✨ Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        f"<b>Anvarov Muhammadzoxid || SMM</b> rasmiy xizmatlar botiga xush kelibsiz.\n\n"
        f"Biz orqali o'qish, biznes, ijtimoiy tarmoqlar va o'yinlar uchun professional raqamli xizmatlarga tezkor buyurtma berishingiz mumkin.\n\n"
        f"👇 Xizmatlar bilan tanishish va buyurtma berish uchun pastdagi <b>«💎 Bizning xizmatlarimiz»</b> tugmasini bosing:"
    )
    await message.answer(welcome_text, reply_markup=main_menu_kb(message.from_user.id))


@router.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Amal bekor qilindi. Asosiy menyudasiz:", reply_markup=main_menu_kb(message.from_user.id))


@router.message(F.text == "💎 Bizning xizmatlarimiz")
async def show_services(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(SERVICES_TEXT, reply_markup=categories_inline_kb())


@router.message(F.text == "🌟 Portfolio")
async def show_portfolio(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Rasmiy kanalga o'tish", url=CHANNEL_LINK)]]
    )
    await message.answer(
        "🌟 <b>Bizning bajarilgan ishlarimiz, namunalar va foydali ma'lumotlar bilan rasmiy kanalimizda tanishishingiz mumkin:</b>",
        reply_markup=kb
    )


@router.message(F.text == "☎️ Bog'lanish")
async def show_contact(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✈️ Bevosita yozish", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton(text="📢 Rasmiy kanal", url=CHANNEL_LINK)]
        ]
    )
    await message.answer(
        f"☎️ <b>Biz bilan bog'lanish:</b>\n\n"
        f"👤 Muallif: <b>Anvarov Muhammadzoxid</b>\n"
        f"✈️ Telegram: {ADMIN_USERNAME}\n"
        f"📢 Kanal: {CHANNEL_LINK}\n\n"
        f"<i>Savollaringiz bo'lsa, bevosita murojaat qilishingiz yoki bot orqali buyurtma qoldirishingiz mumkin!</i>",
        reply_markup=kb
    )


@router.message(F.text == "🗂 Mening buyurtmalarim")
async def my_orders(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(
            "📭 Sizda hozircha buyurtmalar mavjud emas.\n\n"
            "Buyurtma berish uchun <b>«💎 Bizning xizmatlarimiz»</b> tugmasini bosing."
        )
        return

    text = "🗂 <b>Sizning buyurtmalaringiz:</b>\n\n"
    for oid, sname, status, cdate in orders:
        text += (
            f"🆔 <b>Buyurtma #{oid}</b>\n"
            f"▫️ Xizmat: {sname}\n"
            f"📊 Holati: <b>{status}</b>\n"
            f"🕒 Sana: {cdate}\n"
            f"─────────────────\n"
        )
    await message.answer(text)


# ==========================================
# 🗂 KATEGORIYALAR VA XIZMAT TANLASH
# ==========================================
@router.callback_query(F.data.startswith("cat:"))
async def select_category(call: CallbackQuery):
    cat = call.data
    titles = {
        "cat:stud": "🎓 <b>Talabalar uchun xizmatlar:</b>\nKerakli xizmat turini tanlang:",
        "cat:sell": "🚀 <b>Onlayn sotuvchilar uchun xizmatlar:</b>\nKerakli xizmat turini tanlang:",
        "cat:cont": "🎬 <b>Kontent makerlar uchun xizmatlar:</b>\nKerakli xizmat turini tanlang:",
        "cat:game": "🎮 <b>Geymerlar uchun xizmatlar:</b>\nKerakli xizmat turini tanlang:",
    }
    await call.message.edit_text(titles.get(cat, "Xizmatni tanlang:"), reply_markup=sub_services_kb(cat))
    await call.answer()


@router.callback_query(F.data == "back:cats")
async def back_to_categories(call: CallbackQuery):
    await call.message.edit_text(SERVICES_TEXT, reply_markup=categories_inline_kb())
    await call.answer()


@router.callback_query(F.data.startswith("srv:"))
async def select_service(call: CallbackQuery, state: FSMContext):
    srv_code = call.data
    service_info = SERVICES.get(srv_code)
    if not service_info:
        await call.answer("Xatolik yuz berdi!", show_alert=True)
        return

    await state.update_data(service_name=service_info["title"])
    await state.set_state(OrderState.waiting_for_details)

    await call.message.delete()
    await call.message.answer(
        f"✨ Tanlangan xizmat: <b>{service_info['title']}</b>\n\n{service_info['prompt']}",
        reply_markup=cancel_kb()
    )
    await call.answer()


# ==========================================
# 📝 BUYURTMA MA'LUMOTLARINI QABUL QILISH
# ==========================================
@router.message(OrderState.waiting_for_details)
async def process_details(message: Message, state: FSMContext):
    details_text = message.text or message.caption or "Matnsiz fayl biriktirildi"
    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    await state.update_data(details=details_text, file_id=file_id, file_type=file_type)
    await state.set_state(OrderState.waiting_for_phone)

    await message.answer(
        "📱 <b>Siz bilan bog'lanishimiz uchun telefon raqamingizni yuboring:</b>\n"
        "<i>(Pastdagi «📱 Telefon raqamni yuborish» tugmasini bosing yoki raqamingizni +998901234567 ko'rinishida yozib yuboring)</i>",
        reply_markup=phone_kb()
    )


@router.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()
    else:
        await message.answer("❗️ Iltimos, telefon raqamingizni yozib yuboring yoki pastdagi tugmani bosing.")
        return

    await state.update_data(phone=phone)
    data = await state.get_data()
    await state.set_state(OrderState.waiting_for_confirm)

    summary = (
        "📋 <b>BUYURTMA MA'LUMOTLARINI TASDIQLANG:</b>\n\n"
        f"💎 <b>Xizmat:</b> {data['service_name']}\n"
        f"📝 <b>Tafsilotlar:</b> {data['details']}\n"
        f"📎 <b>Biriktirilgan fayl:</b> {'Mavjud ✅' if data.get('file_id') else 'Yo`q'}\n"
        f"📞 <b>Telefon:</b> {phone}\n\n"
        "<i>Ma'lumotlar to'g'ri bo'lsa, tasdiqlash tugmasini bosing:</i>"
    )
    await message.answer("⏳ Ma'lumotlar tekshirilmoqda...", reply_markup=ReplyKeyboardRemove())
    await message.answer(summary, reply_markup=confirm_order_kb())


@router.callback_query(OrderState.waiting_for_confirm, F.data.startswith("order:"))
async def confirm_or_cancel_order(call: CallbackQuery, state: FSMContext, bot: Bot):
    action = call.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await call.message.edit_text("❌ Buyurtma bekor qilindi.")
        await call.message.answer("Asosiy menyu:", reply_markup=main_menu_kb(call.from_user.id))
        await call.answer()
        return

    data = await state.get_data()
    user = call.from_user
    order_id = create_order(
        user_id=user.id,
        full_name=user.full_name,
        username=user.username or "yo'q",
        service_name=data["service_name"],
        details=data["details"],
        file_id=data.get("file_id"),
        file_type=data.get("file_type"),
        phone=data["phone"]
    )
    await state.clear()

    await call.message.edit_text(
        f"✅ <b>Buyurtmangiz muvaffaqiyatli qabul qilindi! (ID: #{order_id})</b>\n\n"
        f"Tez orada <b>Anvarov Muhammadzoxid</b> ({ADMIN_USERNAME}) siz bilan bog'lanadi.\n"
        f"Buyurtma holatini «🗂 Mening buyurtmalarim» bo'limida kuzatishingiz mumkin."
    )
    await call.message.answer("Asosiy menyudasiz:", reply_markup=main_menu_kb(user.id))

    # Adminga (9051195824) darhol xabar yuborish
    order_row = get_order_by_id(order_id)
    if order_row:
        try:
            await send_order_card_to_admin(bot, order_row)
        except Exception as e:
            logging.error(f"Adminga buyurtmani yuborishda xatolik: {e}")

    await call.answer("Buyurtma yuborildi!")


# ==========================================
# 👑 MUKAMMAL ADMIN PANEL VA BOSHQARUV
# ==========================================
def build_admin_dashboard_text():
    u_count, total_o, new_o, active_o, done_o, rej_o = get_detailed_stats()
    now_str = datetime.now().strftime("%d.%m.%Y | %H:%M:%S")
    return (
        f"👑 <b>BOSHQARUV PANELI (ADMIN)</b>\n"
        f"🕒 <i>Yangilangan vaqt: {now_str}</i>\n"
        f"─────────────────\n"
        f"👥 <b>Jami obunachilar:</b> {u_count} ta\n"
        f"📦 <b>Jami buyurtmalar:</b> {total_o} ta\n\n"
        f"🆕 <b>Yangi (ko'rilmagan):</b> {new_o} ta\n"
        f"⏳ <b>Jarayonda / Qabul qilingan:</b> {active_o} ta\n"
        f"🎉 <b>Bajarilgan:</b> {done_o} ta\n"
        f"❌ <b>Rad etilgan:</b> {rej_o} ta\n"
        f"─────────────────\n"
        f"👇 Kerakli bo'limni tanlang:"
    )


@router.message(Command("admin"))
@router.message(F.text == "👑 Admin Panel")
async def open_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Kechirasiz, bu bo'lim faqat bot administratori uchun!")
        return

    await message.answer(build_admin_dashboard_text(), reply_markup=admin_panel_kb())


@router.callback_query(F.data == "adm:stats")
async def refresh_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    try:
        await call.message.edit_text(build_admin_dashboard_text(), reply_markup=admin_panel_kb())
    except TelegramBadRequest:
        pass
    await call.answer("📊 Statistika yangilandi!")


@router.callback_query(F.data.startswith("adm:list:"))
async def admin_list_orders(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return

    filter_type = call.data.split(":")[2]
    orders = get_orders_by_filter(filter_type, limit=10)

    if not orders:
        titles = {
            "new": "🆕 Hozircha yangi buyurtmalar yo'q!",
            "active": "⏳ Hozircha jarayondagi buyurtmalar yo'q!",
            "all": "📭 Bazada buyurtmalar mavjud emas!"
        }
        await call.answer(titles.get(filter_type, "Buyurtmalar yo'q!"), show_alert=True)
        return

    await call.answer()
    for order_row in orders:
        await send_order_card_to_admin(bot, order_row)
        await asyncio.sleep(0.05)


@router.callback_query(F.data == "adm:search")
async def admin_search_order_prompt(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_order_id)
    await call.message.answer(
        "🔍 <b>Qidirilayotgan buyurtma ID raqamini yozib yuboring:</b>\n<i>(Masalan: 1, 5, 12)</i>",
        reply_markup=cancel_kb()
    )
    await call.answer()


@router.message(AdminState.waiting_for_order_id)
async def admin_search_order_process(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    raw_id = message.text.strip().lstrip("#")
    if not raw_id.isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting (masalan: <code>1</code>) yoki «❌ Bekor qilish» tugmasini bosing.")
        return

    order_row = get_order_by_id(int(raw_id))
    await state.clear()

    if not order_row:
        await message.answer(f"❌ <b>#{raw_id}</b> raqamli buyurtma topilmadi.", reply_markup=main_menu_kb(message.from_user.id))
        return

    await message.answer(f"✅ <b>#{raw_id}</b> raqamli buyurtma topildi:", reply_markup=main_menu_kb(message.from_user.id))
    await send_order_card_to_admin(bot, order_row)


@router.callback_query(F.data == "adm:export")
async def admin_export_csv(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    await call.answer("📥 Fayl tayyorlanmoqda...")
    filename = export_orders_to_csv()
    try:
        doc = FSInputFile(filename)
        await bot.send_document(
            ADMIN_ID,
            document=doc,
            caption=f"📊 <b>Barcha buyurtmalar ro'yxati (Excel/CSV)</b>\n🕒 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
    finally:
        if os.path.exists(filename):
            os.remove(filename)


@router.callback_query(F.data.startswith("st:"))
async def change_order_status(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return

    _, order_id_str, status_code = call.data.split(":")
    order_id = int(order_id_str)
    new_status = STATUS_MAP.get(status_code, "✅ Qabul qilindi")

    update_order_status(order_id, new_status)
    order_row = get_order_by_id(order_id)

    if order_row:
        oid, uid, fname, uname, sname, details, file_id, file_type, phone, status, cdate = order_row
        updated_text = format_admin_order_text(oid, uid, fname, uname, sname, details, phone, status, cdate)

        # Admin xabaridagi statusni darhol yangilash
        try:
            if call.message.caption is not None:
                await call.message.edit_caption(caption=updated_text, reply_markup=admin_order_kb(oid, uid))
            else:
                await call.message.edit_text(text=updated_text, reply_markup=admin_order_kb(oid, uid))
        except TelegramBadRequest:
            pass

        # Mijozga bildirishnoma yuborish
        try:
            await bot.send_message(
                uid,
                f"🔔 <b>Buyurtmangiz holati yangilandi!</b>\n\n"
                f"🆔 Buyurtma: <b>#{oid}</b>\n"
                f"💎 Xizmat: {sname}\n"
                f"📊 Yangi holat: <b>{new_status}</b>\n\n"
                f"<i>Bog'lanish uchun: {ADMIN_USERNAME}</i>"
            )
        except Exception:
            pass

    await call.answer(f"Buyurtma #{order_id} holati '{new_status}' ga o'zgartirildi!", show_alert=True)


@router.callback_query(F.data.startswith("reply:"))
async def start_reply_to_user(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    user_id = int(parts[1])
    order_id = int(parts[2]) if len(parts) > 2 else 0

    await state.update_data(target_user_id=user_id, target_order_id=order_id)
    await state.set_state(AdminState.waiting_for_reply)
    await call.message.answer(
        f"✉️ <b>Mijozga (ID: <code>{user_id}</code> | Buyurtma #{order_id}) yubormoqchi bo'lgan xabaringizni, rasm yoki tayyor faylni yuboring:</b>",
        reply_markup=cancel_kb()
    )
    await call.answer()


@router.message(AdminState.waiting_for_reply)
async def send_reply_to_user(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    target_id = data.get("target_user_id")
    order_id = data.get("target_order_id")
    await state.clear()

    header = f"✉️ <b>Admindan xabar (Buyurtma #{order_id}):</b>\n\n" if order_id else "✉️ <b>Admindan xabar:</b>\n\n"
    footer = f"\n\n<i>👤 Muallif bilan aloqa: {ADMIN_USERNAME}</i>"

    try:
        if message.photo:
            caption = f"{header}{message.caption or ''}{footer}"
            await bot.send_photo(target_id, photo=message.photo[-1].file_id, caption=caption)
        elif message.document:
            caption = f"{header}{message.caption or ''}{footer}"
            await bot.send_document(target_id, document=message.document.file_id, caption=caption)
        elif message.video:
            caption = f"{header}{message.caption or ''}{footer}"
            await bot.send_video(target_id, video=message.video.file_id, caption=caption)
        else:
            await bot.send_message(target_id, f"{header}{message.text}{footer}")

        await message.answer("✅ Xabar / fayl mijozga muvaffaqiyatli yetkazildi!", reply_markup=main_menu_kb(message.from_user.id))
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi (Mijoz botni bloklagan bo'lishi mumkin): {e}", reply_markup=main_menu_kb(message.from_user.id))


@router.callback_query(F.data == "adm:broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.waiting_for_broadcast)
    await call.message.answer(
        "📢 <b>Barcha bot foydalanuvchilariga yuboriladigan xabar, rasm yoki videoni yuboring:</b>",
        reply_markup=cancel_kb()
    )
    await call.answer()


@router.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    users = get_all_users()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"⏳ Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")

    for uid in users:
        try:
            await message.copy_to(uid)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.delete()
    await message.answer(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"🟢 Yetkazildi: <b>{sent} ta</b>\n"
        f"🔴 Yetkazilmadi (bloklaganlar): <b>{failed} ta</b>",
        reply_markup=main_menu_kb(message.from_user.id)
    )


# ==========================================
# ▶️ BOTNI ISHGA TUSHIRISH
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    print("🚀 Anvarov Muhammadzoxid || SMM boti to'liq ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    # Render port talabini qondirish uchun kichik veb-server
    import os
    from aiohttp import web
    
    async def handle(request):
        return web.Response(text="Bot is running!")
    
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
