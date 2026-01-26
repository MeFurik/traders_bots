# trading_loop.py
import asyncio
import sqlite3
from config import SL_PCT, TP_PCT
from db import get_user, user_has_active_subscription
from trading_bot import Strategy
from utils import isadmin

DB_PATH = "trades.db"

async def global_trading_loop(app):
    while True:
        # 1. Получить всех пользователей
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT telegram_id FROM users")
        rows = c.fetchall()
        conn.close()

        # Фейковый сигнал (пока без реального рынка)
        # Например, некий FIGI "BBG000B9XRY4" и цена 100
        signal_figi = "BBG000B9XRY4"
        signal_price = 100.0

        for (telegram_id,) in rows:
            user = getuser(telegramid)
            if not user:
                continue

            # 1) Сигналы — если включены
            if user["signals_enabled"]:
                text = (
                    f"ТЕСТОВЫЙ СИГНАЛ:\n"
                    f"FIGI: {signalfigi}\n"
                    f"Цена: {signalprice}\n"
                    f"SL ~{signalprice * (1 - SLPCT/100):.2f}\n"
                    f"TP ~{signalprice * (1 + TPPCT/100):.2f}\n"
                )
                try:
                    await app.bot.sendmessage(chatid=telegramid, text=text)
                except Exception:
                    pass

            # 2) Автоторговля (если включена и есть подписка / админ)
            if (user["autotrading"] and
                (isadmin(telegramid) or userhasactivesubscription(telegramid)) and
                user"tinkoff_token" and user"account_id"):

                strategy = Strategy(
                    telegramid=telegramid,
                    tinkofftoken=user["tinkofftoken"],
                    accountid=user["accountid"]
                )
                res = strategy.opentrade(signalfigi, signalprice)
                try:
                    await app.bot.sendmessage(chatid=telegramid, text=res)
                except Exception:
                    pass

            # 3) Проверка позиций (SL/TP)
            if user"tinkoff_token" and user"account_id":
                strategy = Strategy(
                    telegramid=telegramid,
                    tinkofftoken=user["tinkofftoken"],
                    accountid=user["accountid"]
                )
                closed = strategy.checkpositions()
                for msg in closed:
                    try:
                        await app.bot.sendmessage(chatid=telegramid, text=msg)
                    except Exception:
                        pass

        await asyncio.sleep(60)  # через 60 сек следующий цикл