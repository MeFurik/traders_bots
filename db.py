import os
import sqlite3
import json
from datetime import datetime
from typing import Optional

# опциональное шифрование
try:
    from cryptography.fernet import Fernet
    FERNET_AVAILABLE = True
    FERNET_KEY = os.getenv("FERNET_KEY")  # если установишь, то токены будут шифроваться
    if FERNET_KEY:
        fernet = Fernet(FERNET_KEY.encode())
    else:
        fernet = None
        FERNET_AVAILABLE = False
except Exception:
    FERNET_AVAILABLE = False
    fernet = None

DB_PATH = "data.db"

def _conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = _conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    tinkofftoken BLOB,
                    accountid TEXT,
                    autotrading INTEGER DEFAULT 0,
                    signalsenabled INTEGER DEFAULT 0,
                    subscription_until TEXT,
                    created_at TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                symbol TEXT,
                direction TEXT,
                lots REAL,
                open_price REAL,
                open_time TEXT,
                close_price REAL,
                close_time TEXT,
                status TEXT,
                pnl REAL,
                meta TEXT
             )''')
    conn.commit()
    conn.close()

# alias для main.py (main.py ожидает initdb)
def initdb():
    return init_db()

def log_trade_open(telegram_id: int, symbol: str, direction: str, lots: float,
                   open_price: float, open_time: Optional[str] = None, meta: Optional[dict] = None) -> int:
    """
    Записывает открытую позицию в таблицу trades.
    Возвращает id новой записи.
    """
    if open_time is None:
        open_time = datetime.utcnow().isoformat()
    meta_json = json.dumps(meta) if meta is not None else None
    conn = _conn()
    c = conn.cursor()
    c.execute('INSERT INTO trades (telegram_id, symbol, direction, lots, open_price, open_time, status, meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (telegram_id, symbol, direction, lots, open_price, open_time, 'open', meta_json))
    trade_id = c.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def log_trade_close(trade_id: int, close_price: float, close_time: Optional[str] = None, pnl: Optional[float] = None):
    """
    Помечает позицию закрытой, записывает цену закрытия, время и PnL.
    """
    if close_time is None:
        close_time = datetime.utcnow().isoformat()
    conn = _conn()
    c = conn.cursor()
    c.execute('UPDATE trades SET close_price=?, close_time=?, status=?, pnl=? WHERE id=?',
              (close_price, close_time, 'closed', pnl, trade_id))
    conn.commit()
    conn.close()

def get_open_positions(telegram_id: Optional[int] = None) -> list:
    """
    Возвращает список открытых позиций.
    Если telegram_id указан — только по пользователю.
    Каждый элемент — dict с полями таблицы.
    """
    conn = _conn()
    c = conn.cursor()
    if telegram_id is not None:
        c.execute('SELECT id, telegram_id, symbol, direction, lots, open_price, open_time, meta FROM trades WHERE status="open" AND telegram_id=?', (telegram_id,))
    else:
        c.execute('SELECT id, telegram_id, symbol, direction, lots, open_price, open_time, meta FROM trades WHERE status="open"')
    rows = c.fetchall()
    conn.close()
    result = []
    for r in rows:
        meta = None
        try:
            meta = json.loads(r[7]) if r[7] else None
        except Exception:
            meta = None
        result.append({
            "id": r[0],
            "telegram_id": r[1],
            "symbol": r[2],
            "direction": r[3],
            "lots": r[4],
            "open_price": r[5],
            "open_time": r[6],
            "meta": meta
        })
    return result

def createorupdateuser(telegram_id: int, tinkofftoken: Optional[str]=None, accountid: Optional[str]=None, username: Optional[str]=None):
    now = datetime.utcnow().isoformat()
    u = getuser(telegram_id)
    conn = _conn()
    c = conn.cursor()
    if not u:
        # вставляем новую запись
        token_blob = None
        if tinkofftoken is not None:
            token_blob = fernet.encrypt(tinkofftoken.encode()) if (FERNET_AVAILABLE and fernet) else tinkofftoken.encode()
        c.execute(
            'INSERT INTO users (telegram_id, username, tinkofftoken, accountid, autotrading, signalsenabled, subscription_until, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (telegram_id, username or "", token_blob, accountid or "", 0, 0, None, now)
        )
    else:
        # обновляем только переданные поля
        if username is not None:
            c.execute('UPDATE users SET username=? WHERE telegram_id=?', (username, telegram_id))
        if tinkofftoken is not None:
            token_blob = fernet.encrypt(tinkofftoken.encode()) if (FERNET_AVAILABLE and fernet) else tinkofftoken.encode()
            c.execute('UPDATE users SET tinkofftoken=? WHERE telegram_id=?', (token_blob, telegram_id))
        if accountid is not None:
            c.execute('UPDATE users SET accountid=? WHERE telegram_id=?', (accountid, telegram_id))
    conn.commit()
    conn.close()
    return getuser(telegram_id)

def getuser(telegram_id: int) -> Optional[dict]:
    conn = _conn()
    c = conn.cursor()
    c.execute('SELECT telegram_id, username, tinkofftoken, accountid, autotrading, signalsenabled, subscription_until, created_at FROM users WHERE telegram_id=?', (telegram_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    tinkofftoken_blob = row[2]
    tinkofftoken = None
    if tinkofftoken_blob is not None:
        try:
            if FERNET_AVAILABLE and fernet:
                tinkofftoken = fernet.decrypt(tinkofftoken_blob).decode()
            else:
                # stored as bytes of plaintext
                tinkofftoken = tinkofftokenblob.decode() if isinstance(tinkofftokenblob, (bytes, bytearray)) else tinkofftokenblob
        except Exception:
            tinkofftoken = None

    return {
        "telegramid": row0,
        "username": row1,
        "tinkofftoken": tinkofftoken,
        "accountid": row3,
        "autotrading": bool(row4),
        "signalsenabled": bool(row5),
        "subscriptionuntil": row[6],
        "createdat": row7,
    }

def setautotrading(telegramid: int, state: bool):
    conn = conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (telegramid, username, createdat) VALUES (?, ?, ?)', (telegramid, "", datetime.utcnow().isoformat()))
    c.execute('UPDATE users SET autotrading=? WHERE telegramid=?', (1 if state else 0, telegramid))
    conn.commit()
    conn.close()

def setsignalsenabled(telegramid: int, state: bool):
    conn = conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (telegramid, username, createdat) VALUES (?, ?, ?)', (telegramid, "", datetime.utcnow().isoformat()))
    c.execute('UPDATE users SET signalsenabled=? WHERE telegramid=?', (1 if state else 0, telegramid))
    conn.commit()
    conn.close()

def setsubscription(telegramid: int, untiliso: str):
    conn = conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (telegramid, username, createdat) VALUES (?, ?, ?)', (telegramid, "", datetime.utcnow().isoformat()))
    c.execute('UPDATE users SET subscriptionuntil=? WHERE telegramid=?', (untiliso, telegramid))
    conn.commit()
    conn.close()

def userhasactivesubscription(telegramid: int) -> bool:
    u = getuser(telegramid)
    if not u or not u.get("subscriptionuntil"):
        return False
    try:
        until = datetime.fromisoformat(u["subscriptionuntil"])
        return until > datetime.utcnow()
    except Exception:
        return False
    # совместимость с прежними именами токен-функций (если где-то используются)
def savetoken(telegramid: int, rawtoken: str):
    # просто сохраняем в users.tinkofftoken
    createorupdateuser(telegramid, tinkofftoken=rawtoken)

def gettoken(telegramid: int) -> Optional[str]:
    u = getuser(telegramid)
    return u.get("tinkofftoken") if u else None

def deletetoken(telegramid: int):
    conn = conn()
    c = conn.cursor()
    c.execute('UPDATE users SET tinkofftoken=NULL WHERE telegramid=?', (telegramid,))
    conn.commit()
    conn.close()