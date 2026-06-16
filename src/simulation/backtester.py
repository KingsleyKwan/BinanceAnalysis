import pandas as pd
from src.analysis.analyzer import AIAnalyzer
from typing import Dict, List, Any

class SimpleBacktester:
    """Naive backtester using AI signals on historical data."""

    def __init__(self, initial_capital: float = 10000.0, fee: float = 0.001):
        self.initial_capital = initial_capital
        self.fee = fee
        self.analyzer = AIAnalyzer()

    def run(self, df: pd.DataFrame, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        if len(df) < 60:
            raise ValueError("Insufficient data for backtest (need ~60+ candles)")

        capital = self.initial_capital
        position = 0.0  # coins held
        trades: List[Dict[str, Any]] = []
        equity_curve: List[float] = []

        # Use analyzer on rolling windows
        for i in range(50, len(df)):
            window = df.iloc[: i + 1].copy()
            try:
                signal = self.analyzer.analyze(window)
            except Exception:
                continue

            price = df.iloc[i]["close"]
            action = signal["action"]
            equity = capital + position * price
            equity_curve.append(equity)

            if action == "BUY" and capital > 0 and position == 0:
                # Buy with all capital
                buy_amount = capital * (1 - self.fee)
                position = buy_amount / price
                capital = 0.0
                trades.append({
                    "type": "BUY",
                    "time": df.iloc[i]["open_time"],
                    "price": price,
                    "amount": position,
                })
            elif action == "SELL" and position > 0:
                # Sell all
                sell_value = position * price * (1 - self.fee)
                capital = sell_value
                trades.append({
                    "type": "SELL",
                    "time": df.iloc[i]["open_time"],
                    "price": price,
                    "amount": position,
                })
                position = 0.0

        # Final equity
        final_price = df.iloc[-1]["close"]
        final_equity = capital + position * final_price
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        return {
            "symbol": symbol,
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return, 2),
            "num_trades": len(trades),
            "trades": trades[-10:],  # last 10 for brevity
            "final_signal": self.analyzer.analyze(df),
        }
