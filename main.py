# main.py
import logging
import threading
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
)

from config import TELEGRAM_BOT_TOKEN
from db import (
    init_db, getuser, createorupdateuser,
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
        text += f"Сигналы: {'ON' if user['signalsenabled'] else 'OFF'}\n"
    else:
        text += "Пользователь ещё не настроен. Нажми 'Настроить API'.\n"

    # единая клавиатура (callback_data согласованы с callbackhandler)
    keyboard = [
        [InlineKeyboardButton("Настроить API", callback_data="menusetapi")],
        [
            InlineKeyboardButton("Сигналы ON/OFF", callback_data="menutogglesignals"),
            InlineKeyboardButton("Автоторговля ON/OFF", callback_data="menutoggleauto"),
        ],
        [InlineKeyboardButton("Статус", callback_data="menustatus")],
    ]
    if isadmin(userid):
        keyboard.append([InlineKeyboardButton("Админ-панель", callback_data="menuadmin")])

    markup = InlineKeyboardMarkup(keyboard)

    if edit and update.callback_query:
        update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else:
        update.message.reply_text(text=text, reply_markup=markup)


def start(update: Update, context: CallbackContext):
    showmainmenu(update, context, edit=False)


def callbackhandler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    telegramid = query.from_user.id
    user = getuser(telegramid)

    if data == "menustatus":
        showmainmenu(update, context, edit=True)

    elif data == "menusetapi":
        context.user_data["awaiting"] = "token"
        query.edit_message_text(
            "Отправь свой Tinkoff Invest API токен.\nНапиши 'отмена' для отмены."
        )

    elif data == "menutogglesignals":
        if not user:
            query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        newstate = not user["signalsenabled"]
        setsignalsenabled(telegramid, newstate)
        query.edit_message_text(f"Сигналы теперь: {'ON' if newstate else 'OFF'}")
        showmainmenu(update, context, edit=False)

    elif data == "menutoggleauto":
        if not user:
            query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        if not isadmin(telegramid) and not userhasactivesubscription(telegramid):
            query.edit_message_text("Нет активной подписки, автоторговля недоступна.")
            return
        newstate = not user["autotrading"]
        setautotrading(telegramid, newstate)
        query.edit_message_text(f"Автоторговля теперь: {'ON' if newstate else 'OFF'}")
        showmainmenu(update, context, edit=False)

    elif data == "menuadmin":
        if not isadmin(telegramid):
            query.editmessagetext("У тебя нет прав админа.")
            return
        keyboard = [
                [InlineKeyboardButton("Выдать подписку", callback_data="admingrantsub")],
                [InlineKeyboardButton("Назад", callback_data="menustatus")],
        ]
        markup = InlineKeyboardMarkup(keyboard)
        query.editmessagetext("Админ-панель:", replymarkup=markup)

    elif data == "admingrantsub":
        # инициируем ввод telegram id для выдачи подписки
        if not isadmin(telegramid):
            query.editmessagetext("У тебя нет прав админа.")
            return
        context.userdata["awaiting"] = "grantsubuser"
        query.editmessagetext("Введи telegram id пользователя, которому выдать подписку (или 'отмена').")


def texthandler(update: Update, context: CallbackContext):
    telegramid = update.effective_user.id
    text = update.message.text.strip()

    # отмена
    if text.lower() in ("отмена", "cancel"):
        context.user_data.pop("awaiting", None)
        context.user_data.pop("tinkofftoken", None)
        context.user_data.pop("grantsubtarget", None)
        update.message.reply_text("Отменено.")
        showmainmenu(update, context, edit=False)
        return

    awaiting = context.user_data.get("awaiting")

    # --- Ввод API токена ---
    if awaiting == "token":
        context.user_data["tinkofftoken"] = text
        context.user_data["awaiting"] = "account"
        update.message.reply_text(
            "Токен сохранён. Теперь отправь свой accountid."
        )
        return

    # --- Ввод accountid ---
    if awaiting == "account":
        token = context.user_data.get("tinkofftoken")
        accountid = text
        createorupdateuser(telegramid, tinkofftoken=token, accountid=accountid)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("tinkofftoken", None)
        update.message.reply_text("API токен и accountid сохранены.")
        showmainmenu(update, context, edit=False)
        return

    # --- Админ: ввод telegramid пользователя ---
    if awaiting == "grantsubuser" and isadmin(telegramid):
        try:
            targetid = int(text)
        except ValueError:
            update.message.reply_text("Некорректный telegramid. Введи число или 'отмена'.")
            return

        if not getuser(targetid):
            update.message.reply_text(
                "Пользователь ещё не общался с ботом. Подписка всё равно будет сохранена."
            )
        context.user_data["grantsubtarget"] = targetid
        context.user_data["awaiting"] = "grantsubuntil"
        update.message.reply_text(
            "Введи дату окончания подписки в формате YYYY-MM-DD или '+N' (дней).\n"
            "Примеры:\n2026-12-31\n+30"
        )
        return

    # --- Админ: ввод срока подписки ---
    if awaiting == "grantsubuntil" and isadmin(telegramid):
        targetid = context.user_data.get("grantsubtarget")
        if not targetid:
            update.message.reply_text("Не задан пользователь, отмена.")
            context.user_data.pop("awaiting", None)
            return

        if text.startswith("+"):
            try:
                days = int(text[1:])
                until = datetime.utcnow() + timedelta(days=days)
                untiliso = until.isoformat()
            except ValueError:
                update.message.reply_text("Некорректный формат '+N'.")
                return
        else:
            try:
                d = datetime.strptime(text, "%Y-%m-%d")
                d = d.replace(hour=23, minute=59, second=59)
                untiliso = d.isoformat()
            except ValueError:
                update.message.reply_text("Неверный формат. Нужен YYYY-MM-DD или '+N'.")
                return

        setsubscription(targetid, untiliso)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("grantsubtarget", None)
        update.message.reply_text(
            f"Подписка для {targetid} установлена до {untiliso}."
        )
        showmainmenu(update, context, edit=False)
        return

    # Если не ждём никакого ввода
    showmainmenu(update, context, edit=False)


def run_trading_loop_in_thread(updater: Updater):
    """
    Отдельный поток с собственным asyncio loop’ом,
    в котором крутится global_trading_loop(updater).
    """
    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(global_trading_loop(updater))
        loop.close()

    th = threading.Thread(target=_runner, daemon=True)
    th.start()


def main():
    # TELEGRAMBOTTOKEN должен быть определён в config.py (строка: TELEGRAMBOTTOKEN = "123:ABC...")
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан в config.py")
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(callbackhandler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, texthandler))

    updater.start_polling()
    updater.idle()



if __name__ == "__main__":
    main()