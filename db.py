# db.py
import sqlite3
from datetime import datetime

DBPATH = "trades.db"


def initdb():
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()

    # Таблица пользователей
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegramid INTEGER UNIQUE,
        tinkofftoken TEXT,
        accountid TEXT,
        subscriptionuntil TEXT,
        autotrading INTEGER DEFAULT 0,
        signalsenabled INTEGER DEFAULT 1
    )
    """)

    # Таблица сделок
    c.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegramid INTEGER,
        figi TEXT,
        qty INTEGER,
        entryprice REAL,
        sl REAL,
        tp REAL,
        opentime TEXT,
        closeprice REAL,
        closetime TEXT,
        pnl REAL
    )
    """)

    conn.commit()
    conn.close()


# ---------- USERS ----------

def getuser(telegramid: int):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
        SELECT telegramid, tinkofftoken, accountid,
               subscriptionuntil, autotrading, signalsenabled
        FROM users WHERE telegramid=?
    """, (telegramid,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "telegramid": row[0],
        "tinkofftoken": row[1],
        "accountid": row[2],
        "subscriptionuntil": row[3],
        "autotrading": bool(row[4]),
        "signalsenabled": bool(row5),
    }


def createorupdateuser(
    telegramid: int,
    tinkofftoken: str | None = None,
    accountid: str | None = None
):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (telegramid, tinkofftoken, accountid)
        VALUES (?, ?, ?)
        ON CONFLICT(telegramid) DO UPDATE SET
            tinkofftoken = COALESCE(?, tinkofftoken),
            accountid    = COALESCE(?, accountid)
    """, (telegramid, tinkofftoken, accountid,
          tinkofftoken, accountid))
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
    return datetime.fromisoformat(user["subscriptionuntil"]) > datetime.utcnow()


# ---------- TRADES ----------

def log_trade_open(telegramid, figi, qty, entryprice, sl, tp):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
    INSERT INTO trades (telegramid, figi, qty, entryprice, sl, tp, opentime)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (telegramid, figi, qty, entryprice, sl, tp, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def log_trade_close(telegramid, figi, closeprice, pnl):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
    UPDATE trades
    SET closeprice=?, closetime=?, pnl=?
    WHERE telegramid=? AND figi=? AND closetime IS NULL
    """, (closeprice, datetime.utcnow().isoformat(), pnl, telegramid, figi))
    conn.commit()
    conn.close()


def get_open_positions(telegramid):
    conn = sqlite3.connect(DBPATH)
    c = conn.cursor()
    c.execute("""
    SELECT figi, qty, entryprice, sl, tp FROM trades
    WHERE telegramid=? AND closetime IS NULL
    """, (telegramid,))
    rows = c.fetchall()
    conn.close()
    return [
    {"figi": r[0], "qty": r[1], "entryprice": r[2], "sl": r[3], "tp": r[4]}
    for r in rows
]