# trading_bot.py
from config import (
    RISK_PER_TRADE_PCT, SL_PCT, TP_PCT, MAX_OPEN_POSITIONS
)
from tinkoff_api import TinkoffAPI
from db import log_trade_open, log_trade_close, get_open_positions

class Strategy:
    def __init__(self, telegram_id: int, tinkoff_token: str, account_id: str):
        self.telegram_id = telegram_id
        self.api = TinkoffAPI(tinkoff_token)
        self.account_id = account_id

    def get_capital(self) -> float:
        pf = self.api.get_portfolio(self.account_id)
        return (
            pf.total_amount_currencies.units +
            pf.total_amount_currencies.nano / 1e9
        )

    def calc_position_size(self, price: float, capital: float) -> int:
        risk_money = capital * (RISK_PER_TRADE_PCT / 100.0)
        sl_price = price * (1 - SL_PCT / 100.0)
        risk_per_share = price - sl_price
        if risk_per_share <= 0:
            return 0
        qty = int(risk_money // risk_per_share)
        return max(qty, 0)

    def open_trade(self, figi: str, price: float) -> str:
        capital = self.get_capital()
        open_positions = get_open_positions(self.telegram_id)
        if len(open_positions) >= MAX_OPEN_POSITIONS:
            return "Max positions reached"

        qty = self.calc_position_size(price, capital)
        if qty <= 0:
            return "Qty=0, skip"

        order = self.api.market_buy(self.account_id, figi, qty)

        avg_price = (
            order.executed_order_price.units +
            order.executed_order_price.nano / 1e9
        )

        sl = avg_price * (1 - SL_PCT / 100.0)
        tp = avg_price * (1 + TP_PCT / 100.0)

        log_trade_open(
            telegram_id=self.telegram_id,
            figi=figi,
            qty=qty,
            entry_price=avg_price,
            sl=sl,
            tp=tp,
        )
        return f"Opened {figi}, qty={qty}, entry={avg_price:.2f}, SL={sl:.2f}, TP={tp:.2f}"

    def check_positions(self):
        open_positions = get_open_positions(self.telegram_id)
        if not open_positions:
            return []

        figis = [p["figi"] for p in open_positions]
        prices = self.api.get_last_prices(figis)

        closed_msgs = []
        for pos in open_positions:
            current_price = prices[pos["figi"]]
            if current_price <= pos["sl"] or current_price >= pos["tp"]:
                self.api.market_sell(self.account_id, pos["figi"], pos["qty"])
                pnl = (current_price - pos["entry_price"]) * pos["qty"]
                log_trade_close(
                    telegram_id=self.telegram_id,
                    figi=pos["figi"],
                    close_price=current_price,
                    pnl=pnl
                )
                closed_msgs.append(
                    f"{pos['figi']} closed at {current_price:.2f}, PnL={pnl:.2f}"
                )
        return closed_msgs