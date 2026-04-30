#!/usr/bin/env python3
"""
Telegram-бот для бюро перекладів "Ціль" (м. Львів)
Повністю працюючі: /start, кнопки, збір контактів, додавання текстів/файлів, підтвердження.
"""

import json
import os
import re
import tempfile
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

BOT_TOKEN = "8691460243:AAEfbdE1udGWF7ECdQCbZVSi935c6brflWo"
ADMIN_CHAT_ID = 2013977358
ORDERS_CHANNEL = "@perecrlad"

USERS_FILE = os.path.join(tempfile.gettempdir(), "telegram_bot_users.json")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- Робота з користувачами ----
def load_users() -> set:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_users(users: set):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f, ensure_ascii=False)
    except:
        pass

def register_user(user_id: int):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        save_users(users)

def get_user_count() -> int:
    return len(load_users())

# ---- Клавіатури ----
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Переклади", callback_data="menu_translate")],
        [InlineKeyboardButton("🔏 Апостиль", callback_data="menu_apostille")],
        [InlineKeyboardButton("📞 Контакти", callback_data="menu_contacts")],
    ])

WELCOME = (
    "🌍 *Бюро перекладів Ціль*\n\n"
    "Ціль — сучасне бюро перекладів, що базується у Львові та успішно працює з клієнтами "
    "по всій Україні й за її межами. Надаємо професійні послуги перекладу з будь-якої мови "
    "світу, забезпечуючи високу точність і відповідність міжнародним стандартам.\n\n"
    "Окрім перекладів, пропонуємо повний супровід документів: нотаріальне засвідчення, "
    "проставлення апостиля та консульську легалізацію. Працюємо швидко, надійно та конфіденційно.\n\n"
    "Оберіть розділ 👇"
)

CONTACTS = (
    "📞 *Контакти*\n\n"
    "📱 +38 097 33 42 577 (Київстар)\n"
    "📱 +38 050 18 71 316 (МТС)\n\n"
    "📍 Адреса: м. Львів, вул. Нечуя-Левицького 15, оф. 1Б\n"
    "✉️ info@cil.org.ua\n✉️ pereclad@gmail.com"
)

# ---- Допоміжна функція пересилання ----
async def send_order(context, user, contact, service, items):
    username = f"@{user.username}" if user.username else "немає"
    txt = (
        f"📬 <b>НОВЕ ЗАМОВЛЕННЯ</b>\n\n"
        f"👤 Ім'я: {contact.get('name', 'не вказано')}\n"
        f"📞 Телефон: {contact.get('phone', 'не вказано')}\n"
        f"✉️ Email: {contact.get('email', 'не вказано')}\n"
        f"🆔 {user.full_name} ({username}) | ID: <code>{user.id}</code>\n\n"
        f"─────────────────\n"
        f"<b>Послуга:</b>\n{service}\n\n"
        f"<b>Деталі:</b>\n"
    )
    try:
        await context.bot.send_message(ADMIN_CHAT_ID, txt, parse_mode="HTML")
        if ORDERS_CHANNEL:
            await context.bot.send_message(ORDERS_CHANNEL, txt, parse_mode="HTML")
        for it in items:
            if it['type'] == 'text':
                await context.bot.send_message(ADMIN_CHAT_ID, it['content'], parse_mode="HTML")
                if ORDERS_CHANNEL:
                    await context.bot.send_message(ORDERS_CHANNEL, it['content'], parse_mode="HTML")
            elif it['type'] == 'document':
                await context.bot.send_document(ADMIN_CHAT_ID, it['file_id'], caption=it.get('caption', ''), parse_mode="HTML")
                if ORDERS_CHANNEL:
                    await context.bot.send_document(ORDERS_CHANNEL, it['file_id'], caption=it.get('caption', ''), parse_mode="HTML")
            elif it['type'] == 'photo':
                await context.bot.send_photo(ADMIN_CHAT_ID, it['file_id'], caption=it.get('caption', ''), parse_mode="HTML")
                if ORDERS_CHANNEL:
                    await context.bot.send_photo(ORDERS_CHANNEL, it['file_id'], caption=it.get('caption', ''), parse_mode="HTML")
        logger.info("Замовлення надіслано")
    except Exception as e:
        logger.error(f"Помилка надсилання: {e}")

# ---- ОСНОВНІ КОМАНДИ ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user.id)
    await update.message.reply_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Доступ заборонено.")
        return
    await update.message.reply_text(f"👥 Користувачів бота: {get_user_count()}", parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Скасовано.", reply_markup=main_menu())

# ---- ОБРОБНИК ВСІХ CALLBACK (КНОПОК) ----
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ---------- ГОЛОВНЕ МЕНЮ ----------
    if data == "menu_translate":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Переклад з нот.засв. (300+400грн)", callback_data="service_trans_notary")],
            [InlineKeyboardButton("🏢 Переклад з печ.агенства (300грн)", callback_data="service_trans_agency")],
            [InlineKeyboardButton("🇵🇱 Переклад присяжним (1000грн/стор)", callback_data="service_trans_sworn")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
        ])
        await query.edit_message_text("📝 *Переклади*\nОберіть тип:", parse_mode="Markdown", reply_markup=kb)

    elif data == "menu_apostille":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚖️ Міністерство Юстиції", callback_data="apostille_justice")],
            [InlineKeyboardButton("🌐 Міністерство Закордонних Справ", callback_data="apostille_mfa")],
            [InlineKeyboardButton("🎓 Міністерство Освіти і Науки", callback_data="apostille_edu")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
        ])
        text = (
            "🔏 *Апостиль*\n\n"
            "Що ж таке той апостиль народною мовою?\n\n"
            "Апостиль — це підтвердження, що документ дійсно виданий тою країною, з якої він походить. "
            "Це штамп, який прирівнює документ до аналогічних у країнах Гаазької конвенції 1961 р.\n\n"
            "Терміни: від 2 до 7 робочих днів.\n\n"
            "Оберіть орган 👇"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif data == "menu_contacts":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
        await query.edit_message_text(CONTACTS, parse_mode="Markdown", reply_markup=kb)

    elif data == "main_menu":
        await query.edit_message_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu())

    # ---------- ПЕРЕКЛАДИ (послуги) ----------
    elif data in ("service_trans_notary", "service_trans_agency", "service_trans_sworn"):
        service_map = {
            "service_trans_notary": "📄 Переклад з нотаріальним засвідченням\n🌐 Всі мови\n💰 300 грн + 400 грн за документ",
            "service_trans_agency": "🏢 Переклад з печаткою агенства\n🌐 Всі мови\n💰 300 грн",
            "service_trans_sworn": "🇵🇱 Переклад присяжним перекладачем (польська)\n💰 1000 грн за сторінку"
        }
        context.user_data["selected_service"] = service_map[data]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Замовити", callback_data="start_order")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_translate")],
        ])
        await query.edit_message_text(service_map[data], parse_mode="Markdown", reply_markup=kb)

    # ---------- АПОСТИЛЬ ----------
    elif data == "apostille_justice":
        # Унікальні callback для кожного документа
        items = [
            ("Свідоцтво про народження", "ap_justice_birth"),
            ("Свідоцтво про одруження", "ap_justice_marriage"),
            ("Свідоцтво про розлучення", "ap_justice_divorce"),
            ("Свідоцтво про смерть", "ap_justice_death"),
            ("Свідоцтво про зміну імені", "ap_justice_name_change"),
            ("Свідоцтво про зміну прізвища", "ap_justice_surname_change"),
            ("Нотаріальні документи", "ap_justice_notary"),
            ("Інші документи (заява, довіреність, копія)", "ap_justice_other"),
        ]
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(name, callback_data=cb)] for name, cb in items] +
            [[InlineKeyboardButton("◀️ Назад", callback_data="menu_apostille")]]
        )
        await query.edit_message_text(
            "⚖️ *Міністерство Юстиції*\nОберіть документ:",
            parse_mode="Markdown",
            reply_markup=kb
        )

    # Обробка всіх документів Міністерства Юстиції (унікальні назви)
    elif data in {
        "ap_justice_birth", "ap_justice_marriage", "ap_justice_divorce",
        "ap_justice_death", "ap_justice_name_change", "ap_justice_surname_change",
        "ap_justice_notary", "ap_justice_other"
    }:
        doc_names = {
            "ap_justice_birth": "Свідоцтво про народження",
            "ap_justice_marriage": "Свідоцтво про одруження",
            "ap_justice_divorce": "Свідоцтво про розлучення",
            "ap_justice_death": "Свідоцтво про смерть",
            "ap_justice_name_change": "Свідоцтво про зміну імені",
            "ap_justice_surname_change": "Свідоцтво про зміну прізвища",
            "ap_justice_notary": "Нотаріальні документи",
            "ap_justice_other": "Інші документи (заява, довіреність, копія)",
        }
        doc_name = doc_names[data]
        service = (
            f"⚖️ Апостиль – Міністерство Юстиції\n"
            f"📄 {doc_name}\n"
            f"⏱ до 5 роб.днів + 2 дні доставка\n"
            f"💰 1500 грн"
        )
        context.user_data["selected_service"] = service
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Замовити", callback_data="start_order")],
            [InlineKeyboardButton("◀️ Назад", callback_data="apostille_justice")],
        ])
        await query.edit_message_text(service, parse_mode="Markdown", reply_markup=kb)

    elif data == "apostille_mfa":
        service = "🌐 Апостиль на витяг про несудимість\n⏱ 5‑7 роб.днів\n💰 950 грн"
        context.user_data["selected_service"] = service
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Замовити", callback_data="start_order")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_apostille")],
        ])
        await query.edit_message_text(service, parse_mode="Markdown", reply_markup=kb)

    elif data == "apostille_edu":
        items = [
            ("МОН (загальне) – 5‑7 днів / 950 грн", "edu_general"),
            ("Довідки зі шкіл – 5‑20 днів / 800 грн", "edu_school"),
            ("Атестати/дипломи новий взірець – від 3 днів / 2000 грн", "edu_new"),
            ("Атестати/дипломи – від 10 днів / 1400 грн", "edu_old"),
            ("Документи під запит (до 20 днів) – 1400 грн", "edu_request20"),
            ("Документи під запит (до 30 днів) – 1400 грн", "edu_request30"),
            ("Нострифікація – від 90 днів / від 5000 грн", "edu_nostr"),
        ]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(name, callback_data=cb)] for name, cb in items] + [[InlineKeyboardButton("◀️ Назад", callback_data="menu_apostille")]])
        await query.edit_message_text("🎓 *Міністерство Освіти і Науки*", parse_mode="Markdown", reply_markup=kb)

    elif data in ("edu_general", "edu_school", "edu_new", "edu_old", "edu_request20", "edu_request30", "edu_nostr"):
        edu_map = {
            "edu_general": "Міністерство Освіти і Науки (загальне)\n⏱ 5‑7 днів\n💰 950 грн",
            "edu_school": "Апостиль на довідки зі шкіл/установ\n⏱ 5‑20 днів\n💰 800 грн",
            "edu_new": "Апостиль на атестати/дипломи нового взірця\n⏱ від 3 днів\n💰 2000 грн",
            "edu_old": "Апостиль на атестати/дипломи\n⏱ від 10 днів\n💰 1400 грн",
            "edu_request20": "Апостиль на документи під запит (до 20 днів)\n💰 1400 грн",
            "edu_request30": "Апостиль на документи під запит (до 30 днів)\n💰 1400 грн",
            "edu_nostr": "Нострифікація атестатів/дипломів\n⏱ від 90 днів\n💰 від 5000 грн",
        }
        context.user_data["selected_service"] = edu_map[data]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Замовити", callback_data="start_order")],
            [InlineKeyboardButton("◀️ Назад", callback_data="apostille_edu")],
        ])
        await query.edit_message_text(edu_map[data], parse_mode="Markdown", reply_markup=kb)

    # ---------- ЗАМОВЛЕННЯ: ПОЧАТИ ЗБІР КОНТАКТІВ ----------
    elif data == "start_order":
        if not context.user_data.get("selected_service"):
            await query.edit_message_text("⚠️ Помилка. Оберіть послугу знову.", reply_markup=main_menu())
            return
        context.user_data["step"] = "contact_phone"
        context.user_data["contact"] = {}
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")]])
        await query.edit_message_text(
            "📞 *Для замовлення вкажіть номер телефону.*\nНадішліть номер (напр. +380971234567 або 0971234567):",
            parse_mode="Markdown", reply_markup=kb
        )

    elif data == "cancel_order":
        context.user_data.pop("last_count_message_id", None)
        context.user_data.clear()
        await query.edit_message_text("❌ Замовлення скасовано.", reply_markup=main_menu())

# ---- ОБРОБНИК ПОВІДОМЛЕНЬ (контакти, потім контент) ----
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip() if msg.text else None
    step = context.user_data.get("step")

    # ---- ЕТАП 1: ЗБІР КОНТАКТІВ ----
    if step == "contact_phone":
        if not text or not re.search(r'\d{5,}', text):
            await msg.reply_text("❌ Невірний номер. Спробуйте ще раз (хоча б 5 цифр):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")]]))
            return
        context.user_data["contact"]["phone"] = text
        context.user_data["step"] = "contact_name"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏩ Пропустити", callback_data="skip_name")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")]
        ])
        await msg.reply_text("✏️ Вкажіть ваше ім'я (необов'язково) або натисніть «Пропустити»:", reply_markup=kb)

    elif step == "contact_name":
        if text:
            context.user_data["contact"]["name"] = text
        else:
            await msg.reply_text("Будь ласка, надішліть ім'я текстом або натисніть кнопку «Пропустити».")
            return
        context.user_data["step"] = "contact_email"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏩ Пропустити", callback_data="skip_email")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")]
        ])
        await msg.reply_text("✉️ Вкажіть email (необов'язково) або «Пропустити»:", reply_markup=kb)

    elif step == "contact_email":
        if text and '@' not in text:
            await msg.reply_text("❌ Невірний email. Спробуйте ще раз:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏩ Пропустити", callback_data="skip_email")]]))
            return
        context.user_data["contact"]["email"] = text if text else "не вказано"
        # Переходимо до збору контенту
        context.user_data["step"] = "collecting_items"
        context.user_data["items"] = []
        # Показуємо підсумок контактів і запрошення додавати контент
        c = context.user_data["contact"]
        await msg.reply_text(
            f"✅ *Контакти збережено:*\n📞 {c['phone']}\n👤 {c.get('name','не вказано')}\n✉️ {c.get('email','не вказано')}\n\n"
            "Тепер надсилайте текст, файли, фото – кожне повідомлення додасться до замовлення.\n"
            "Коли закінчите, натисніть *«Підтвердити»*.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Підтвердити замовлення", callback_data="confirm_order")],
                [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")],
                [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
            ])
        )

    # ---- ЕТАП 2: ЗБІР КОНТЕНТУ (текст, файли, фото) ----
    elif step == "collecting_items":
        items = context.user_data.get("items", [])
        if msg.text and not msg.text.startswith('/'):
            items.append({'type': 'text', 'content': msg.text})
            await msg.reply_text("✅ Текст додано.")
        elif msg.document:
            items.append({'type': 'document', 'file_id': msg.document.file_id, 'caption': msg.caption or ""})
            await msg.reply_text("✅ Файл додано.")
        elif msg.photo:
            items.append({'type': 'photo', 'file_id': msg.photo[-1].file_id, 'caption': msg.caption or ""})
            await msg.reply_text("✅ Фото додано.")
        else:
            await msg.reply_text("❌ Непідтримуваний тип. Надішліть текст, файл або фото.")
            return

        context.user_data["items"] = items

        # Видаляємо попереднє повідомлення-лічильник (якщо було)
        last_msg_id = context.user_data.get("last_count_message_id")
        if last_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=last_msg_id
                )
            except Exception:
                pass

        # Відправляємо новий лічильник і запам'ятовуємо його ID
        reply_msg = await msg.reply_text(
            f"📦 У замовленні {len(items)} елемент(ів).\n"
            "Додайте ще або натисніть «Підтвердити».",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Підтвердити замовлення", callback_data="confirm_order")],
                [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")],
                [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
            ])
        )
        context.user_data["last_count_message_id"] = reply_msg.message_id

    else:
        # Якщо не в процесі замовлення – пропонуємо /start
        await msg.reply_text("Скористайтесь /start для вибору послуги.", reply_markup=main_menu())

# ---- ОБРОБНИК ПРОПУСКУ ТА ПІДТВЕРДЖЕННЯ (через callback) ----
async def extra_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Пропустити ім'я
    if data == "skip_name":
        if context.user_data.get("step") == "contact_name":
            context.user_data["contact"]["name"] = "не вказано"
            context.user_data["step"] = "contact_email"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏩ Пропустити", callback_data="skip_email")],
                [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")]
            ])
            await query.edit_message_text("✉️ Вкажіть email (необов'язково) або «Пропустити»:", reply_markup=kb)
        else:
            await query.edit_message_text("Помилка стану. Почніть замовлення заново.", reply_markup=main_menu())

    # Пропустити email
    elif data == "skip_email":
        if context.user_data.get("step") == "contact_email":
            context.user_data["contact"]["email"] = "не вказано"
            context.user_data["step"] = "collecting_items"
            context.user_data["items"] = []
            c = context.user_data["contact"]
            await query.edit_message_text(
                f"✅ *Контакти збережено:*\n📞 {c['phone']}\n👤 {c.get('name','не вказано')}\n✉️ {c.get('email','не вказано')}\n\n"
                "Тепер надсилайте текст, файли, фото.\n"
                "Коли закінчите – натисніть «Підтвердити».",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Підтвердити замовлення", callback_data="confirm_order")],
                    [InlineKeyboardButton("❌ Скасувати", callback_data="cancel_order")],
                    [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
                ])
            )
        else:
            await query.edit_message_text("Помилка стану.", reply_markup=main_menu())

    # Підтвердження замовлення
    elif data == "confirm_order":
        context.user_data.pop("last_count_message_id", None)
        if context.user_data.get("step") == "collecting_items" and context.user_data.get("items"):
            user = update.effective_user
            contact = context.user_data.get("contact", {})
            service = context.user_data.get("selected_service", "Послуга не вказана")
            items = context.user_data.get("items", [])
            await send_order(context, user, contact, service, items)
            context.user_data.clear()
            await query.edit_message_text(
                "✅ *Замовлення надіслано!* Менеджер зв'яжеться з вами.\n\n"
                f"{CONTACTS}\n\nПовернутись у меню /start",
                parse_mode="Markdown",
                reply_markup=main_menu()
            )
        else:
            await query.edit_message_text("❌ Немає чого підтверджувати. Почніть замовлення заново.", reply_markup=main_menu())

    elif data == "cancel_order":
        context.user_data.pop("last_count_message_id", None)
        context.user_data.clear()
        await query.edit_message_text("❌ Замовлення скасовано.", reply_markup=main_menu())

    elif data == "main_menu":
        context.user_data.pop("last_count_message_id", None)
        context.user_data.clear()
        await query.edit_message_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu())

# ---- ЗАПУСК ----
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(?!skip_name|skip_email|confirm_order|cancel_order|main_menu).*"))
    app.add_handler(CallbackQueryHandler(extra_callback, pattern="^(skip_name|skip_email|confirm_order|cancel_order|main_menu)$"))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    print("✅ Бот запущено. /start працює, всі кнопки активні.")
    app.run_polling()

if __name__ == "__main__":
    main()
