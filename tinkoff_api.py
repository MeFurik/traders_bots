# tinkoffapi.py
from tinkoff.invest import Client

class TinkoffAPI:
    def init(self, token: str):
        self.token = token

    def getportfolio(self, accountid: str):
        with Client(self.token) as client:
            pf = client.operations.getportfolio(accountid=accountid)
            return pf

    def getlastprices(self, figilist):
        with Client(self.token) as client:
            resp = client.marketdata.getlastprices(figi=figilist)
            return {
                p.figi: p.price.units + p.price.nano / 1e9
                for p in resp.lastprices
            }

    def marketbuy(self, accountid: str, figi: str, lots: int):
        with Client(self.token) as client:
            order = client.orders.postorder(
                accountid=accountid,
                figi=figi,
                quantity=lots,
                direction=1,  # BUY
                ordertype=1, # MARKET
                orderid="botbuy"+figi
            )
            return order

    def marketsell(self, accountid: str, figi: str, lots: int):
        with Client(self.token) as client:
            order = client.orders.postorder(
                accountid=accountid,
                figi=figi,
                quantity=lots,
                direction=2,  # SELL
                order_type=1, # MARKET
                order_id="bot_sell_"+figi
            )
            return order