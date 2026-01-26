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

from config import TELEGRAMBOTTOKEN
from db import (
    initdb, getuser, createorupdateuser,
    setautotrading, setsignalsenabled,
    setsubscription, userhasactivesubscription
)
from utils import isadmin
from tradingloop import globaltradingloop

logging.basicConfig(level=logging.INFO)


# ---------- Главное меню ----------
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
        [
            InlineKeyboardButton("Настроить API", callback_data="menu_set_api"),
            InlineKeyboardButton("Сигналы ON/OFF", callback_data="menu_toggle_signals"),
        ],
        [
            InlineKeyboardButton("Автоторговля ON/OFF", callback_data="menu_toggle_auto"),
            InlineKeyboardButton("Статус", callback_data="menu_status"),
        ],
    ]

    if isadmin(userid):
        keyboard.append(
            [InlineKeyboardButton("Админ-панель", callback_data="menu_admin")]
        )

    markup = InlineKeyboardMarkup(keyboard)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else:
        await update.message.reply_text(text=text, reply_markup=markup)


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await showmainmenu(update, context, edit=False)


# ---------- Обработка нажатий кнопок ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    telegramid = query.from_user.id
    user = getuser(telegramid)

    # --- Главное меню / статус ---
    if data == "menu_status":
        await showmainmenu(update, context, edit=True)

    # --- Настройка API ---
    elif data == "menu_set_api":
        context.user_data["awaiting"] = "token"
        await query.edit_message_text(
            "Отправь свой Tinkoff Invest API токен.\nНапиши 'отмена' для отмены."
        )

    # --- Сигналы ON/OFF ---
    elif data == "menu_toggle_signals":
        if not user:
            await query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        newstate = not user["signals_enabled"]
        setsignalsenabled(telegramid, newstate)
        await query.edit_message_text(f"Сигналы теперь: {'ON' if newstate else 'OFF'}")
        await showmainmenu(update, context, edit=False)

    # --- Автоторговля ON/OFF ---
    elif data == "menu_toggle_auto":
        if not user:
            await query.edit_message_text("Сначала настрой API через 'Настроить API'.")
            return
        if not isadmin(telegramid) and not userhasactivesubscription(telegramid):
            await query.editmessagetext("Нет активной подписки, автоторговля недоступна.")
            return
        newstate = not user"autotrading"
        setautotrading(telegramid, newstate)
        await query.editmessagetext(f"Автоторговля теперь: {'ON' if newstate else 'OFF'}")
        await showmainmenu(update, context, edit=False)

    # --- Админ-меню ---
    elif data == "menuadmin":
        if not isadmin(telegramid):
            await query.editmessagetext("У тебя нет прав админа.")
            return

        keyboard = [
            [InlineKeyboardButton("Выдать подписку", callbackdata="admingrantsub")],
            InlineKeyboardButton("Назад", callback_data="menu_status"),
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await query.editmessagetext("Админ-панель:", replymarkup=markup)

    # --- Админ: выдача подписки (шаг 1 — ввод telegramid) ---
    elif data == "admingrantsub":
        if not isadmin(telegramid):
            await query.editmessagetext("Нет прав.")
            return
        context.userdata["awaiting"] = "grantsubuser"
        await query.editmessagetext(
            "Введи telegramid пользователя, которому выдать/продлить подписку.\n"
            "Пример: 123456789"
        )


# ---------- Обработка текстовых сообщений ----------
async def texthandler(update: Update, context: ContextTypes.DEFAULTTYPE):
    telegramid = update.effectiveuser.id
    text = update.message.text.strip()

    # отмена
    if text.lower() in ("отмена", "cancel"):
        context.userdata.pop("awaiting", None)
        context.userdata.pop("tinkofftoken", None)
        context.userdata.pop("grantsubtarget", None)
        await update.message.replytext("Отменено.")
        await showmainmenu(update, context, edit=False)
        return

    awaiting = context.userdata.get("awaiting")

    # --- Ввод API токена ---
    if awaiting == "token":
        context.userdata"tinkoff_token" = text
        context.userdata["awaiting"] = "account"
        await update.message.replytext(
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
        await update.message.replytext("API токен и accountid сохранены.")
        await showmainmenu(update, context, edit=False)
        return

    # --- Админ: ввод telegramid пользователя ---
    if awaiting == "grantsubuser" and isadmin(telegramid):
        try:
            targetid = int(text)
        except ValueError:
            await update.message.replytext("Некорректный telegramid. Введи число или 'отмена'.")
            return

        if not getuser(targetid):
            await update.message.replytext(
                "Пользователь ещё не общался с ботом. Подписка всё равно будет сохранена."
            )
        context.userdata"grant_sub_target" = targetid
        context.userdata["awaiting"] = "grantsubuntil"
        await update.message.replytext(
            "Введи дату окончания подписки в формате YYYY-MM-DD или '+N' (дней).\n"
            "Примеры:\n2026-12-31\n+30"
        )
        return

    # --- Админ: ввод срока подписки ---
    if awaiting == "grantsubuntil" and isadmin(telegramid):
        targetid = context.userdata.get("grantsubtarget")
        if not targetid:
            await update.message.replytext("Не задан пользователь, отмена.")
            context.userdata.pop("awaiting", None)
            return

        if text.startswith("+"):
            try:
                days = int(text[1:])
                until = datetime.utcnow() + timedelta(days=days)
                untiliso = until.isoformat()
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

        # сохраняем подписку
        setsubscription(targetid, until_iso)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("grant_sub_target", None)
        await update.message.reply_text(
            f"Подписка для {targetid} установлена до {until_iso}."
        )
        await showmainmenu(update, context, edit=False)
        return

    # Если не ждём никакого ввода — просто покажем меню
    await showmainmenu(update, context, edit=False)


# ---------- main ----------
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
    async def _post_init(app_):
        app_.create_task(globaltradingloop(app_))

    app.post_init = _post_init

    app.run_polling()


if __name__ == "__main__":
    main()