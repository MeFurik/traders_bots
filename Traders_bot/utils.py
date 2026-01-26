# utils.py
from config import ADMIN_ID

def is_admin(telegram_id: int) -> bool:
    return telegram_id == ADMIN_ID