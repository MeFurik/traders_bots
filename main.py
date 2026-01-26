# main.py
import logging
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

from config import TELEGRAM_BOT_TOKEN
from db import (
    initdb, getuser, createorupdateuser,
    setautotrading, setsignalsenabled,
    setsubscription, userhasactivesubscription
)
from utils import isadmin
from trading_loop import global_trading_loop

logging.basicConfig(level=logging.INFO)


async def showmainmenu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    userid = update.effective_user.id
    user = getuser(userid)
    subok = userhasactivesubscription(userid) if user else False

    text = "Главное меню:\n"
    if isadmin(userid):
        text += "Роль: АДМИН\n"
    if user:
        text += f"Подписка: {'активна' if subok or isadmin(userid) else 'нет'}\n"
        text += f"Автоторговля: {'ON' if user['autotrading'] else 'OFF'}\n"
        text += f"Сигналы: {'ON' if user['signals_enabled'] else 'OFF'}\n"
    else:
        text += "Пользователь ещё не настроен. Нажми 'Настроить API'.\n"

    keyboard = [
        [InlineKeyboardButton("Настроить API", callback_data="menu_set_api")],
        [
            InlineKeyboardButton("Сигналы ON/OFF", callback_data="menu_toggle_signals"),
            InlineKeyboardButton("Автоторговля ON/OFF", callback_data="menu_toggle_auto"),
        ],
        [InlineKeyboardButton("Статус", callback_data="menu_status")],
    ]
    if isadmin(userid):
        keyboard.append([InlineKeyboardButton("Админ-панель", callback_data="menu_admin")])

    markup = InlineKeyboardMarkup(keyboard)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else:
        await update.message.reply_text(text=text, reply_markup=markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await showmainmenu(update, context, edit=False)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    telegram_id = query.from_user.id
    user = getuser(telegram_id)

    if data == "menu_status":
        await showmainmenu(update, context, edit=True)

    elif data == "menu_set_api":
        context.user_data["awaiting"] = "token"
        await query.edit_message_text(
            "Отправь свой Tinkoff Invest API токен.\nНапиши 'отмена' для отмены."
        )

    elif data == "menu_toggle_signals":
        if not user:
            await query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        new_state = not user["signals_enabled"]
        setsignalsenabled(telegram_id, new_state)
        await query.edit_message_text(f"Сигналы теперь: {'ON' if new_state else 'OFF'}")
        await showmainmenu(update, context, edit=False)

    elif data == "menu_toggle_auto":
        if not user:
            await query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        if not isadmin(telegram_id) and not userhasactivesubscription(telegram_id):
            await query.edit_message_text("Нет активной подписки, автоторговля недоступна.")
            return
        new_state = not user["autotrading"]
        setautotrading(telegram_id, new_state)
        await query.edit_message_text(f"Автоторговля теперь: {'ON' if new_state else 'OFF'}")
        await showmainmenu(update, context, edit=False)

    elif data == "menu_admin":
        if not isadmin(telegram_id):
            await query.edit_message_text("У тебя нет прав админа.")
            return
        keyboard = [
            [InlineKeyboardButton("Выдать подписку", callback_data="admin_grant_sub")],
            [InlineKeyboardButton("Назад", callback_data="menu_status")],
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Админ-панель:", reply_markup=markup)

    elif data == "admin_grant_sub":
        if not isadmin(telegram_id):
            await query.edit_message_text("Нет прав.")
            return
        context.user_data["awaiting"] = "grant_sub_user"
        await query.edit_message_text(
            "Введи telegram_id пользователя, которому выдать/продлить подписку.\nПример: 123456789"
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    # отмена
    if text.lower() in ("отмена", "cancel"):
        context.user_data.pop("awaiting", None)
        context.user_data.pop("tinkoff_token", None)
        context.user_data.pop("grant_sub_target", None)
        await update.message.reply_text("Отменено.")
        await showmainmenu(update, context, edit=False)
        return

    awaiting = context.user_data.get("awaiting")

    # --- Ввод API токена ---
    if awaiting == "token":
        context.user_data["tinkoff_token"] = text
        context.user_data["awaiting"] = "account"
        await update.message.reply_text(
            "Токен сохранён. Теперь отправь свой account_id."
        )
        return

    # --- Ввод account_id ---
    if awaiting == "account":
        token = context.user_data.get("tinkoff_token")
        account_id = text
        createorupdateuser(telegram_id, tinkofftoken=token, accountid=account_id)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("tinkoff_token", None)
        await update.message.reply_text("API токен и account_id сохранены.")
        await showmainmenu(update, context, edit=False)
        return

    # --- Админ: ввод telegram_id пользователя ---
    if awaiting == "grant_sub_user" and isadmin(telegram_id):
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("Некорректный telegram_id. Введи число или 'отмена'.")
            return

        if not getuser(target_id):
            await update.message.reply_text(
                "Пользователь ещё не общался с ботом. Подписка всё равно будет сохранена."
            )
        context.user_data["grant_sub_target"] = target_id
        context.user_data["awaiting"] = "grant_sub_until"
        await update.message.reply_text(
            "Введи дату окончания подписки в формате YYYY-MM-DD или '+N' (дней).\n"
            "Примеры:\n2026-12-31\n+30"
        )
        return

    # --- Админ: ввод срока подписки ---
    if awaiting == "grant_sub_until" and isadmin(telegram_id):
        target_id = context.user_data.get("grant_sub_target")
        if not target_id:
            await update.message.reply_text("Не задан пользователь, отмена.")
            context.user_data.pop("awaiting", None)
            return

        until_iso = None
        if text.startswith("+"):
            try:
                days = int(text[1:])
                until = datetime.utcnow() + timedelta(days=days)
                until_iso = until.isoformat()
            except ValueError:
                await update.message.reply_text("Некорректный формат '+N'.")
                return
        else:
            try:
                d = datetime.strptime(text, "%Y-%m-%d")
                d = d.replace(hour=23, minute=59, second=59)
                until_iso = d.isoformat()
            except ValueError:
                await update.message.reply_text("Неверный формат. Нужен YYYY-MM-DD или '+N'.")
                return

        setsubscription(target_id, until_iso)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("grant_sub_target", None)
        await update.message.reply_text(
            f"Подписка для {target_id} установлена до {until_iso}."
        )
        await showmainmenu(update, context, edit=False)
        return

    # Если не ждём никакого ввода
    await showmainmenu(update, context, edit=False)


def main():
    initdb()

    app = ApplicationBuilder().token(TELEGRAMBOTTOKEN).build()

    # /start
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex("^/start$"), start))

    # Кнопки
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Глобальный торговый цикл
    async def post_init(application):
        application.create_task(globaltradingloop(application))

    app.post_init = post_init

    app.run_polling()


if __name__ == "__main__":
    main()