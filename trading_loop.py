# trading_loop.py
import asyncio
import sqlite3

from config import SL_PCT, TP_PCT
from db import getuser, userhasactivesubscription
from trading_bot import Strategy
from utils import isadmin

DBPATH = "trades.db"


async def global_trading_loop(app):
    while True:
        # 1. Получаем всех пользователей
        conn = sqlite3.connect(DBPATH)
        c = conn.cursor()
        c.execute("SELECT telegramid FROM users")
        rows = c.fetchall()
        conn.close()

        # Фейковый сигнал (заглушка)
        signalfigi = "BBG000B9XRY4"
        signalprice = 100.0

        for (telegramid,) in rows:
            user = getuser(telegramid)
            if not user:
                continue

            # 1) Сигналы -- если включены
            if user["signals_enabled"]:
                text = (
                    f"ТЕСТОВЫЙ СИГНАЛ:\n"
                    f"FIGI: {signalfigi}\n"
                    f"Цена: {signalprice}\n"
                    f"SL ~{signalprice * (1 - SL_PCT / 100):.2f}\n"
                    f"TP ~{signalprice * (1 + TP_PCT / 100):.2f}\n"
                )
                try:
                    await app.bot.send_message(chat_id=telegramid, text=text)
                except Exception:
                    # например, пользователь заблокировал бота -- пропускаем
                    pass

            # 2) Автоторговля (если включена и есть подписка / админ)
            if (
                user["autotrading"]
                and (isadmin(telegramid) or userhasactivesubscription(telegramid))
                and user["tinkoff_token"]
                and user["account_id"]
            ):
                strategy = Strategy(
                    telegramid=telegramid,
                    tinkofftoken=user["tinkoff_token"],
                    accountid=user["account_id"],
                )
                res = strategy.opentrade(signalfigi, signalprice)
                try:
                    await app.bot.send_message(chat_id=telegramid, text=res)
                except Exception:
                    pass

            # 3) Проверка позиций (SL/TP)
            if user["tinkoff_token"] and user["account_id"]:
                strategy = Strategy(
                    telegramid=telegramid,
                    tinkofftoken=user["tinkoff_token"],
                    accountid=user["account_id"],
                )
                closed = strategy.checkpositions()
                for msg in closed:
                    try:
                        await app.bot.send_message(chat_id=telegramid, text=msg)
                    except Exception:
                        pass

        await asyncio.sleep(60)  # следующий цикл через 60 секунд