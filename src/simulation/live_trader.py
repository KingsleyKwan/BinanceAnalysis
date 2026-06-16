import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dotenv import load_dotenv
from src.data.fetcher import BinanceDataFetcher
from src.analysis.fast_deepseek import FastDeepSeekAnalyzer
from src.analysis.deep_xai import DeepXAIAnalyzer
from src.analysis.real_deepseek import RealDeepSeekAnalyzer
from src.analysis.real_xai import RealXAIAnalyzer
from src.simulation.database import TradingDB
from src.analysis.real_xai import RealXAIAnalyzer as _RealXAIAnalyzer  # for isinstance check

load_dotenv()

FEE_RATE = 0.001
POLL_INTERVAL_SEC = 60          # 1 minute
DEEP_INTERVAL = 15              # every 15 cycles = 15 minutes
POSITION_SIZE_PCT = 0.30
MIN_CONF_FAST = 0.50
MIN_CONF_DEEP = 0.65

class LivePaperTrader:
    """
    Long-term paper trader with dual-model analysis:
    - Every 1 minute  : FastDeepSeekAnalyzer (cheap, quick)
    - Every 15 minutes: DeepXAIAnalyzer (more thoughtful, can return BOTH)
    Decision types: BUY, SELL, BOTH, HOLD
    """

    def __init__(self, symbols: List[str] = None, interval: str = "1h", initial_cash: float = 900.0):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        self.interval = interval
        self.fetcher = BinanceDataFetcher()
        self.db = TradingDB()
        self.cash = initial_cash
        self.holdings: Dict[str, Dict] = {}
        self.cycle_count = 0

        # Choose real LLM or local rule-based based on API keys
        use_real_deepseek = bool(os.getenv("DEEPSEEK_API_KEY"))
        use_real_xai = bool(os.getenv("XAI_API_KEY"))

        self.fast_analyzer = RealDeepSeekAnalyzer() if use_real_deepseek else FastDeepSeekAnalyzer()
        self.deep_analyzer = RealXAIAnalyzer() if use_real_xai else DeepXAIAnalyzer()

        if use_real_deepseek or use_real_xai:
            print(f"[LLM] Using real APIs → DeepSeek: {use_real_deepseek}, xAI: {use_real_xai}")
        else:
            print("[LLM] Using local rule-based analyzers (no API keys found)")

        self._load_state()

    def _load_state(self):
        portfolio = self.db.get_latest_portfolio()
        self.cash = portfolio["cash"]
        self.holdings = self.db.get_holdings()
        print(f"[INIT] Cash=${self.cash:.2f} | Holdings={self.holdings or 'none'}")

    def _total_equity(self, prices: Dict[str, float]) -> float:
        eq = self.cash
        for sym, h in self.holdings.items():
            price = prices.get(sym, h.get("avg_buy_price", 0))
            eq += h["amount"] * price
        return eq

    def _execute_decision(self, symbol: str, decision: Dict, current_price: float, is_deep: bool = False):
        action = decision["action"]
        conf = decision["confidence"]
        model = decision.get("model", "unknown")
        min_conf = MIN_CONF_DEEP if is_deep else MIN_CONF_FAST

        if conf < min_conf:
            return

        holding = self.holdings.get(symbol, {"amount": 0, "avg_buy_price": 0})
        amount_held = holding["amount"]
        now = datetime.now(timezone.utc).isoformat()

        # Always log the signal
        self.db.log_signal(
            now, symbol, action, decision["score"], conf,
            decision["indicators"]["rsi"],
            decision["indicators"]["macd_hist"],
            current_price, model
        )

        if action == "BUY" and self.cash > 40 and amount_held == 0:
            invest = self.cash * POSITION_SIZE_PCT
            if invest < 25:
                return
            amt = invest / current_price
            fee = invest * FEE_RATE
            self.cash -= (invest + fee)
            self.holdings[symbol] = {"amount": amt, "avg_buy_price": current_price}
            self.db.update_holding(symbol, amt, current_price, now)
            self.db.log_trade(now, symbol, "BUY", current_price, amt, invest, fee, f"{model}-buy")
            print(f"  [{model.upper()}] BUY {amt:.5f} {symbol} @ ${current_price:,.2f}")

        elif action == "SELL" and amount_held > 0:
            usd_val = amount_held * current_price
            fee = usd_val * FEE_RATE
            self.cash += (usd_val - fee)
            pnl = (current_price - holding["avg_buy_price"]) * amount_held
            self.db.log_trade(now, symbol, "SELL", current_price, amount_held, usd_val, fee, f"{model}-sell pnl=${pnl:+.2f}")
            print(f"  [{model.upper()}] SELL {amount_held:.5f} {symbol} @ ${current_price:,.2f} | PnL ${pnl:+.2f}")
            self.holdings[symbol] = {"amount": 0, "avg_buy_price": 0}
            self.db.update_holding(symbol, 0, 0, now)

        elif action == "BOTH":
            # Deep model wants to rotate: sell current holdings, buy this symbol (or strongest other)
            if amount_held > 0:
                usd_val = amount_held * current_price
                fee = usd_val * FEE_RATE
                self.cash += (usd_val - fee)
                pnl = (current_price - holding["avg_buy_price"]) * amount_held
                self.db.log_trade(now, symbol, "SELL", current_price, amount_held, usd_val, fee, f"{model}-BOTH-sell")
                print(f"  [{model.upper()}] BOTH-SELL {amount_held:.5f} {symbol} | PnL ${pnl:+.2f}")
                self.holdings[symbol] = {"amount": 0, "avg_buy_price": 0}
                self.db.update_holding(symbol, 0, 0, now)

            # Then buy this symbol with fresh capital
            if self.cash > 50:
                invest = self.cash * POSITION_SIZE_PCT
                amt = invest / current_price
                fee = invest * FEE_RATE
                self.cash -= (invest + fee)
                self.holdings[symbol] = {"amount": amt, "avg_buy_price": current_price}
                self.db.update_holding(symbol, amt, current_price, now)
                self.db.log_trade(now, symbol, "BUY", current_price, amt, invest, fee, f"{model}-BOTH-buy")
                print(f"  [{model.upper()}] BOTH-BUY {amt:.5f} {symbol} @ ${current_price:,.2f}")

    def run_once(self):
        self.cycle_count += 1
        is_deep_cycle = (self.cycle_count % DEEP_INTERVAL == 0)
        analyzer = self.deep_analyzer if is_deep_cycle else self.fast_analyzer
        model_name = analyzer.name.upper()

        print(f"\n=== Cycle {self.cycle_count} | {'DEEP-XAI' if is_deep_cycle else 'FAST-DEEPSEEK'} | {datetime.now().strftime('%H:%M')} ===")

        prices = {}
        for symbol in self.symbols:
            try:
                df = self.fetcher.get_recent_data(symbol, days=8, interval=self.interval)
                holdings_context = self.holdings if isinstance(analyzer, _RealXAIAnalyzer) else None
                decision = analyzer.analyze(df, symbol, holdings=holdings_context) if holdings_context else analyzer.analyze(df, symbol)
                current_price = df.iloc[-1]["close"]
                prices[symbol] = current_price

                print(f"{symbol}: {decision['action']} (conf {decision['confidence']*100:.0f}%) | ${current_price:,.2f}")
                self._execute_decision(symbol, decision, current_price, is_deep=is_deep_cycle)
            except Exception as e:
                print(f"Error on {symbol}: {e}")

        total = self._total_equity(prices)
        now = datetime.now(timezone.utc).isoformat()
        self.db.save_snapshot(now, self.cash, total)
        print(f"Equity: ${total:.2f} | Cash: ${self.cash:.2f} | Holdings: { {k: round(v['amount'],4) for k,v in self.holdings.items()} }")

    def run_forever(self):
        print("Dual-model paper trader started (1-min DeepSeek + 15-min xAI). Ctrl+C to stop.")
        print(f"Symbols: {self.symbols} | Initial capital: ${self.cash:.2f}")
        try:
            while True:
                self.run_once()
                time.sleep(POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\nStopped by user.")
            final = self.db.get_latest_portfolio()
            print(f"Final equity: ${final['total_equity']:.2f}")
        finally:
            self.db.close()
