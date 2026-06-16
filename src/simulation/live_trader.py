import os
import time
from datetime import datetime, timezone
from pathlib import Path
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

    def __init__(self, symbols: List[str] = None, interval: str = "1h",
                 initial_cash: float = 376.0,
                 initial_holdings: Dict[str, Dict] = None):
        """
        initial_cash: starting stablecoin balance (FDUSD / USDT)
        initial_holdings: e.g. {"BTCUSDT": {"amount": 0.005, "avg_buy_price": 65000.0}}
        """
        self.symbols = symbols or ["BTCUSDT"]
        self.interval = interval
        self.fetcher = BinanceDataFetcher()
        self.db = TradingDB()
        self.cash = initial_cash
        self.holdings: Dict[str, Dict] = initial_holdings or {}
        self.cycle_count = 0

        # Choose real LLM or local rule-based based on API keys
        use_real_deepseek = bool(os.getenv("DEEPSEEK_API_KEY"))
        use_real_xai = bool(os.getenv("XAI_API_KEY"))

        self.fast_analyzer = RealDeepSeekAnalyzer() if use_real_deepseek else FastDeepSeekAnalyzer()
        self.deep_analyzer = RealXAIAnalyzer() if use_real_xai else DeepXAIAnalyzer()

        self.paused = False
        self.current_window_decision_ids = []

        if use_real_deepseek or use_real_xai:
            print(f"[LLM] Using real APIs → DeepSeek: {use_real_deepseek}, xAI: {use_real_xai}")
            print("[Self-Correction] xAI will review DeepSeek decisions every 15 minutes")
        else:
            print("[LLM] Using local rule-based analyzers (no API keys found)")

        self._load_state()

    def _load_state(self):
        portfolio = self.db.get_latest_portfolio()
        if portfolio["timestamp"] is None:
            # First run → seed with user-provided initial state
            print(f"[INIT] First run detected. Seeding with provided initial portfolio...")
            now = datetime.now(timezone.utc).isoformat()
            self.db.save_snapshot(now, self.cash, self.cash)  # initial equity = cash
            for sym, h in self.holdings.items():
                self.db.update_holding(sym, h["amount"], h.get("avg_buy_price", 0), now)
            print(f"[INIT] Seeded: Cash=${self.cash:.2f} | Holdings={self.holdings}")
        else:
            self.cash = portfolio["cash"]
            self.holdings = self.db.get_holdings()
            print(f"[INIT] Resumed from DB: Cash=${self.cash:.2f} | Holdings={self.holdings or 'none'}")

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
        if self.paused:
            print("[PAUSED] Self-correction in progress. Press Ctrl+C or wait for auto-resume...")
            time.sleep(10)
            return

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

                # Log DeepSeek decisions for later xAI review
                if "deepseek" in analyzer.name.lower() and decision.get("model", "").startswith("deepseek"):
                    from src.analysis.fast_deepseek import FastDeepSeekAnalyzer
                    # Only log real DeepSeek decisions
                    if not isinstance(analyzer, FastDeepSeekAnalyzer):
                        ema_trend = "above" if current_price > df.iloc[-1].get("ema_20", 0) else "below"
                        vol_ratio = df.iloc[-1].get("volume", 0) / max(df.iloc[-1].get("volume_sma", 1), 1)
                        self.db.log_deepseek_decision(
                            datetime.now(timezone.utc).isoformat(),
                            symbol,
                            decision["action"],
                            decision["confidence"],
                            decision.get("reason", ""),
                            current_price,
                            decision["indicators"]["rsi"],
                            decision["indicators"]["macd_hist"],
                            ema_trend,
                            vol_ratio
                        )
                        # keep track for current window
                        self.current_window_decision_ids.append(symbol)  # simplified
            except Exception as e:
                print(f"Error on {symbol}: {e}")

        total = self._total_equity(prices)
        now = datetime.now(timezone.utc).isoformat()
        self.db.save_snapshot(now, self.cash, total)
        print(f"Equity: ${total:.2f} | Cash: ${self.cash:.2f} | Holdings: { {k: round(v['amount'],4) for k,v in self.holdings.items()} }")

        # === Self-correction review every 15 minutes ===
        if is_deep_cycle and isinstance(self.deep_analyzer, _RealXAIAnalyzer):
            self._perform_self_correction_review(prices)

    def _perform_self_correction_review(self, current_prices: dict):
        """xAI reviews the last 15 minutes of DeepSeek decisions and teaches it if wrong."""
        print("\n" + "="*60)
        print("[SELF-CORRECTION] xAI (grok-4.3) reviewing DeepSeek decisions from last 15 min...")
        print("="*60)

        unreviewed = self.db.get_unreviewed_deepseek_decisions(limit=20)
        if not unreviewed:
            print("[Self-Correction] No unreviewed DeepSeek decisions.")
            return

        # Fetch latest price for each decision's symbol
        review_prices = {}
        for d in unreviewed:
            try:
                latest = self.fetcher.get_current_price(d["symbol"])
                review_prices[d["symbol"]] = latest
            except:
                review_prices[d["symbol"]] = d["close_price"]

        # Ask xAI to review
        review_result = self.deep_analyzer.review_deepseek_decisions(unreviewed, review_prices)

        has_errors = False
        lessons_to_add = []

        for j in review_result.get("judgments", []):
            decision_id = j.get("id")
            judgment = j.get("judgment", "CORRECT")
            explanation = j.get("explanation", "")
            lesson = j.get("lesson", "")

            if judgment == "WRONG":
                has_errors = True
                print(f"\n[ERROR DETECTED] Decision #{decision_id} was WRONG")
                print(f"  Explanation: {explanation}")
                if lesson:
                    lessons_to_add.append(lesson)
                    print(f"  Lesson for DeepSeek: {lesson}")

            # Update DB
            sym = next((d["symbol"] for d in unreviewed if d["id"] == decision_id), "BTCUSDT")
            self.db.update_deepseek_judgment(
                decision_id,
                review_prices.get(sym, 0),
                judgment,
                explanation
            )

        if has_errors and lessons_to_add:
            print("\n" + "!"*60)
            print("[PAUSING SYSTEM] Mistakes found. xAI will now teach DeepSeek...")
            self.paused = True

            # Append lessons to the skill file
            self._append_lessons_to_skill(lessons_to_add)

            print("[Self-Correction] Lessons added to deepseek_lessons.md")
            print("[Self-Correction] System will resume in 30 seconds...")
            time.sleep(30)
            self.paused = False
            print("[Self-Correction] Resuming trading loop.\n" + "="*60)
        else:
            print("[Self-Correction] All DeepSeek decisions in this window were correct. No lessons needed.")

    def _append_lessons_to_skill(self, lessons: list):
        """Append new lessons to the DeepSeek skill file."""
        skill_path = Path(__file__).parent.parent / "analysis" / "deepseek_lessons.md"
        if not skill_path.exists():
            return

        with open(skill_path, "a", encoding="utf-8") as f:
            f.write("\n")
            for lesson in lessons:
                f.write(f"- {lesson}\n")
            f.write(f"\n<!-- Reviewed at {datetime.now().isoformat()} by grok-4.3 -->\n")

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
