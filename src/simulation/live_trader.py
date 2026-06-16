import time
from datetime import datetime, timezone
from typing import List, Dict
from src.data.fetcher import BinanceDataFetcher
from src.analysis.analyzer import AIAnalyzer
from src.simulation.database import TradingDB

FEE_RATE = 0.001  # 0.1% taker fee
POLL_INTERVAL_SEC = 15 * 60  # 15 minutes
POSITION_SIZE_PCT = 0.28     # Use ~28% of available cash on strong BUY
MIN_CONFIDENCE = 0.55        # Only act on reasonably confident signals

class LivePaperTrader:
    def __init__(self, symbols: List[str] = None, interval: str = "1h", initial_cash: float = 900.0):
        self.symbols = symbols or ["BTCUSDT"]
        self.interval = interval
        self.fetcher = BinanceDataFetcher()
        self.analyzer = AIAnalyzer()
        self.db = TradingDB()
        self.cash = initial_cash
        self.holdings: Dict[str, Dict] = {}  # symbol -> {amount, avg_buy_price}
        self._load_state()

    def _load_state(self):
        portfolio = self.db.get_latest_portfolio()
        self.cash = portfolio["cash"]
        self.holdings = self.db.get_holdings()
        print(f"[INIT] Loaded state: Cash=${self.cash:.2f}, Holdings={self.holdings or 'none'}")

    def _calculate_total_equity(self, prices: Dict[str, float]) -> float:
        equity = self.cash
        for sym, h in self.holdings.items():
            price = prices.get(sym, h.get("avg_buy_price", 0))
            equity += h["amount"] * price
        return equity

    def _decide_and_trade(self, symbol: str, signal: Dict, current_price: float):
        action = signal["action"]
        conf = signal["confidence"]
        score = signal["score"]

        holding = self.holdings.get(symbol, {"amount": 0, "avg_buy_price": 0})
        amount_held = holding["amount"]

        now = datetime.now(timezone.utc).isoformat()

        # Log signal always
        self.db.log_signal(
            now, symbol, action, score, conf,
            signal["indicators"]["rsi"],
            signal["indicators"]["macd_hist"],
            current_price
        )

        if conf < MIN_CONFIDENCE:
            return  # Too uncertain, skip

        if action == "BUY" and self.cash > 50 and amount_held == 0:
            # Strong buy signal + no position
            invest_usd = self.cash * POSITION_SIZE_PCT
            if invest_usd < 20:
                return
            amount_to_buy = invest_usd / current_price
            fee = invest_usd * FEE_RATE
            self.cash -= (invest_usd + fee)
            new_avg = current_price  # first buy
            self.holdings[symbol] = {"amount": amount_to_buy, "avg_buy_price": new_avg}
            self.db.update_holding(symbol, amount_to_buy, new_avg, now)
            self.db.log_trade(now, symbol, "BUY", current_price, amount_to_buy,
                              invest_usd, fee, f"score={score:.2f}")
            print(f"  [TRADE] BUY {amount_to_buy:.6f} {symbol} @ ${current_price:.2f} (invest ${invest_usd:.2f})")

        elif action == "SELL" and amount_held > 0:
            # Sell everything
            usd_value = amount_held * current_price
            fee = usd_value * FEE_RATE
            self.cash += (usd_value - fee)
            pnl = (current_price - holding["avg_buy_price"]) * amount_held
            self.db.log_trade(now, symbol, "SELL", current_price, amount_held,
                              usd_value, fee, f"pnl=${pnl:.2f}")
            print(f"  [TRADE] SELL {amount_held:.6f} {symbol} @ ${current_price:.2f} | PnL ${pnl:+.2f}")
            self.holdings[symbol] = {"amount": 0, "avg_buy_price": 0}
            self.db.update_holding(symbol, 0, 0, now)

    def run_once(self):
        print(f"\n=== Live Paper Trader Cycle | {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        prices = {}
        for symbol in self.symbols:
            try:
                df = self.fetcher.get_recent_data(symbol, days=10, interval=self.interval)
                signal = self.analyzer.analyze(df)
                current_price = df.iloc[-1]["close"]
                prices[symbol] = current_price

                print(f"{symbol}: {signal['action']} (conf {signal['confidence']*100:.0f}%, score {signal['score']:+.2f}) | ${current_price:,.2f}")
                self._decide_and_trade(symbol, signal, current_price)
            except Exception as e:
                print(f"Error processing {symbol}: {e}")

        total_equity = self._calculate_total_equity(prices)
        now = datetime.now(timezone.utc).isoformat()
        self.db.save_snapshot(now, self.cash, total_equity)
        print(f"Portfolio: Cash=${self.cash:.2f} | Equity=${total_equity:.2f} | Holdings: {self.holdings}")

    def run_forever(self):
        print("Starting long-term paper trading simulation (Ctrl+C to stop)...")
        print(f"Initial capital: ${self.cash:.2f}")
        try:
            while True:
                self.run_once()
                print(f"Sleeping {POLL_INTERVAL_SEC // 60} minutes until next cycle...\n")
                time.sleep(POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\nSimulation stopped by user.")
            final = self.db.get_latest_portfolio()
            print(f"Final equity: ${final['total_equity']:.2f}")
            print("Trade history saved to trading.db")
        finally:
            self.db.close()
