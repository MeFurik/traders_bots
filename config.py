# config.py

TELEGRAM_BOT_TOKEN = "8316501495:AAFao4moFOeKWx1JyV8ulPmLrw4LaO03ffo"

GPT_API_KEY = "GPT_API_KEY_ЕСЛИ_ЕСТЬ_ИЛИ_ОСТАВЬ_ПУСТОЙ"

# Твой Telegram ID (узнаёшь через @userinfobot и т.п.)
ADMIN_ID = 1291693026  # замени на свой ID

# Параметры стратегии по умолчанию
PUMP_LOOKBACK_MIN = 5        # за сколько минут анализируем рост
PUMP_MIN_CHANGE_PCT = 2.0    # минимальный рост цены (%) за lookback
PUMP_MIN_VOLUME_MULT = 1.5   # объём в X раз выше среднего

RISK_PER_TRADE_PCT = 1.0     # риск на сделку (% от капитала)
SL_PCT = 1.0                 # Stop-loss 1%
TP_PCT = 2.0                 # Take-profit 2%
MAX_OPEN_POSITIONS = 5       # максимум одновременных позиций