# main.py
import logging
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler,
    ConversationHandler, CallbackContext
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


def showmainmenu(update: Update, context: CallbackContext, edit: bool = False):
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
        update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else:
        update.message.reply_text(text=text, reply_markup=markup)


def start(update: Update, context: CallbackContext):
    showmainmenu(update, context, edit=False)


def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    telegram_id = query.from_user.id
    user = getuser(telegram_id)

    if data == "menu_status":
        showmainmenu(update, context, edit=True)

    elif data == "menu_set_api":
        context.user_data["awaiting"] = "token"
        query.edit_message_text(
            "Отправь свой Tinkoff Invest API токен.\nНапиши 'отмена' для отмены."
        )

    elif data == "menu_toggle_signals":
        if not user:
            query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        new_state = not user["signals_enabled"]
        setsignalsenabled(telegram_id, new_state)
        query.edit_message_text(f"Сигналы теперь: {'ON' if new_state else 'OFF'}")
        showmainmenu(update, context, edit=False)

    elif data == "menu_toggle_auto":
        if not user:
            query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        if not isadmin(telegram_id) and not userhasactivesubscription(telegram_id):
            query.edit_message_text("Нет активной подписки, автоторговля недоступна.")
            return
        new_state = not user["autotrading"]
        setautotrading(telegram_id, new_state)
        query.edit_message_text(f"Автоторговля теперь: {'ON' if new_state else 'OFF'}")
        showmainmenu(update, context, edit=False)

    elif data == "menu_admin":
        if not isadmin(telegram_id):
            query.edit_message_text("У тебя нет прав админа.")
            return
        keyboard = [
            [InlineKeyboardButton("Выдать подписку", callback_data="admin_grant_sub")],
            [InlineKeyboardButton("Назад", callback_data="menu_status")],
        ]
        markup = InlineKeyboardMarkup(keyboard)
        query.editmessagetext("Админ-панель:", replymarkup=markup)

    elif data == "admingrantsub":
        if not isadmin(telegramid):
            query.editmessagetext("Нет прав.")
            return
        context.userdata["awaiting"] = "grantsubuser"
        query.editmessagetext(
            "Введи telegramid пользователя, которому выдать/продлить подписку.\nПример: 123456789"
        )


def texthandler(update: Update, context: CallbackContext):
    telegramid = update.effectiveuser.id
    text = update.message.text.strip()

    # отмена
    if text.lower() in ("отмена", "cancel"):
        context.userdata.pop("awaiting", None)
        context.userdata.pop("tinkofftoken", None)
        context.userdata.pop("grantsubtarget", None)
        update.message.replytext("Отменено.")
        showmainmenu(update, context, edit=False)
        return

    awaiting = context.userdata.get("awaiting")

    # --- Ввод API токена ---
    if awaiting == "token":
        context.userdata["tinkoff_token"] = text
        context.userdata["awaiting"] = "account"
        update.message.replytext(
            "Токен сохранён. Теперь отправь свой accountid."
        )
        return

    # --- Ввод accountid ---
    if awaiting == "account":
        token = context.userdata.get("tinkofftoken")
        accountid = text
        createorupdateuser(telegramid, tinkofftoken=token, accountid=accountid)
        context.userdata.pop("awaiting", None)
        context.userdata.pop("tinkofftoken", None)
        update.message.replytext("API токен и accountid сохранены.")
        showmainmenu(update, context, edit=False)
        return

    # --- Админ: ввод telegramid пользователя ---
    if awaiting == "grantsubuser" and isadmin(telegramid):
        try:
            targetid = int(text)
        except ValueError:
            update.message.replytext("Некорректный telegramid. Введи число или 'отмена'.")
            return

        if not getuser(targetid):
            update.message.replytext(
                "Пользователь ещё не общался с ботом. Подписка всё равно будет сохранена."
            )
        context.userdata["grant_sub_target"] = targetid
        context.userdata["awaiting"] = "grantsubuntil"
        update.message.replytext(
            "Введи дату окончания подписки в формате YYYY-MM-DD или '+N' (дней).\n"
            "Примеры:\n2026-12-31\n+30"
        )
        return

    # --- Админ: ввод срока подписки ---
    if awaiting == "grantsubuntil" and isadmin(telegramid):
        targetid = context.userdata.get("grantsubtarget")
        if not targetid:
            update.message.replytext("Не задан пользователь, отмена.")
            context.userdata.pop("awaiting", None)
            return

        untiliso = None
        if text.startswith("+"):
            try:
                days = int(text1)
                until = datetime.utcnow() + timedelta(days=days)
                untiliso = until.isoformat()
            except ValueError:
                update.message.replytext("Некорректный формат '+N'.")
                return
        else:
            try:
                d = datetime.strptime(text, "%Y-%m-%d")
                d = d.replace(hour=23, minute=59, second=59)
                untiliso = d.isoformat()
            except ValueError:
                update.message.replytext("Неверный формат. Нужен YYYY-MM-DD или '+N'.")
                return

        setsubscription(targetid, untiliso)
        context.userdata.pop("awaiting", None)
        context.userdata.pop("grantsubtarget", None)
        update.message.replytext(
            f"Подписка для {targetid} установлена до {untiliso}."
        )
        showmainmenu(update, context, edit=False)
        return

    # Если не ждём никакого ввода
    showmainmenu(update, context, edit=False)


def main():
    initdb()

    # создаём Updater и dispatcher для v13
    updater = Updater(TELEGRAMBOTTOKEN, usecontext=True)
    dispatcher = updater.dispatcher

    # /start
    dispatcher.add_handler(CommandHandler("start", start))

    # Кнопки
    dispatcher.add_handler(CallbackQueryHandler(callback_handler))

    # Текстовые сообщения
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    # Глобальный торговый цикл – запускаем в фоне
    # В v13 нет .post_init, используем job_queue или отдельный поток.
    # Если global_trading_loop у тебя обычная синхронная функция – достаточно:
    dispatcher.job_queue.run_once(
        lambda ctx: global_trading_loop(dispatcher),
        when=0
    )

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()