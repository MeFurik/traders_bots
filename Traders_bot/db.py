# db.py
import sqlite3
from datetime import datetime

DB_PATH = "trades.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Таблица сделок
    c.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        figi TEXT,
        qty INTEGER,
        entry_price REAL,
        sl REAL,
        tp REAL,
        open_time TEXT,
        close_price REAL,
        close_time TEXT,
        pnl REAL
    )
    """)

    # Таблица пользователей
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        tinkoff_token TEXT,
        account_id TEXT,
        subscription_until TEXT,
        auto_trading INTEGER DEFAULT 0,
        signals_enabled INTEGER DEFAULT 1
    )
    """)

    conn.commit()
    conn.close()

# ---------- USERS ----------

def get_user(telegram_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id, tinkoff_token, account_id,
               subscription_until, auto_trading, signals_enabled
        FROM users WHERE telegram_id=?
    """, (telegram_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "telegram_id": row[0],
        "tinkoff_token": row[1],
        "account_id": row[2],
        "subscription_until": row[3],
        "auto_trading": bool(row[4]),
        "signals_enabled": bool(row[5]),
    }

def create_or_update_user(telegram_id: int,
                          tinkoff_token: str = None,
                          accountid: str = None):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (telegramid, tinkofftoken, accountid)
        VALUES (?, ?, ?)
        ON CONFLICT(telegramid) DO UPDATE SET
            tinkofftoken=COALESCE(?, tinkofftoken),
            accountid=COALESCE(?, accountid)
    """, (telegramid, tinkofftoken, accountid, tinkofftoken, accountid))
    conn.commit()
    conn.close()

def setsubscription(telegramid: int, untiliso: str):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
        UPDATE users SET subscriptionuntil=? WHERE telegramid=?
    """, (untiliso, telegramid))
    conn.commit()
    conn.close()

def setautotrading(telegramid: int, enabled: bool):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
        UPDATE users SET autotrading=? WHERE telegramid=?
    """, (1 if enabled else 0, telegramid))
    conn.commit()
    conn.close()

def setsignalsenabled(telegramid: int, enabled: bool):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
        UPDATE users SET signalsenabled=? WHERE telegramid=?
    """, (1 if enabled else 0, telegramid))
    conn.commit()
    conn.close()

def userhasactivesubscription(telegramid: int) -> bool:
    user = getuser(telegramid)
    if not user or not user["subscriptionuntil"]:
        return False
    return datetime.fromisoformat(user"subscription_until") > datetime.utcnow()

# ---------- TRADES ----------

def logtradeopen(telegramid, figi, qty, entryprice, sl, tp):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
    INSERT INTO trades (telegramid, figi, qty, entryprice, sl, tp, opentime)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (telegramid, figi, qty, entryprice, sl, tp, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def logtradeclose(telegramid, figi, closeprice, pnl):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
    UPDATE trades
    SET closeprice=?, closetime=?, pnl=?
    WHERE telegramid=? AND figi=? AND closetime IS NULL
    """, (closeprice, datetime.utcnow().isoformat(), pnl, telegramid, figi))
    conn.commit()
    conn.close()

def getopenpositions(telegramid):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
    SELECT figi, qty, entryprice, sl, tp FROM trades
    WHERE telegramid=? AND closetime IS NULL
    """, (telegramid,))
    rows = c.fetchall()
    conn.close()
    return [
        {"figi": r[0], "qty": r[1], "entryprice": r2, "sl": r3, "tp": r4}
        for r in rows
    ]