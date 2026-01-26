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
        "signalsenabled": bool(row[5]),
    }


def createorupdateuser(telegramid: int,
                       tinkofftoken: str = None,
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
    try:
        return datetime.fromisoformat(user["subscriptionuntil"]) > datetime.utcnow()
    except ValueError:
        return False