# utils.py
from config import ADMIN_ID

def isadmin(telegram_id: int) -> bool:
    return telegram_id == ADMIN_ID