import pandas as pd
import numpy as np
from typing import Dict, Any
from src.analysis.base_analyzer import BaseAnalyzer

class FastDeepSeekAnalyzer(BaseAnalyzer):
    """
    Fast, lightweight analyzer intended to run every minute.
    Uses the original rule-based scoring with relatively permissive thresholds.
    Model name: 'deepseek'
    """

    name = "deepseek"

    def __init__(self):
        self.min_confidence = 0.50
        self.weights = {
            "rsi": 0.25,
            "macd": 0.25,
            "ema_trend": 0.20,
            "volume": 0.15,
            "bollinger": 0.15,
        }

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        if len(df) < 50:
            return {"action": "HOLD", "confidence": 0.0, "score": 0.0, "reason": "insufficient data", "model": self.name}

        df = df.copy()
        close = df["close"]

        # Same indicator calculations as before (RSI, MACD, EMA, BB, Volume)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        df["ema_20"] = close.ewm(span=20, adjust=False).mean()
        df["ema_50"] = close.ewm(span=50, adjust=False).mean()

        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df["bb_lower"] = sma20 - 2 * std20
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_mid"] = sma20
        df["volume_sma"] = df["volume"].rolling(20).mean()

        latest = df.iloc[-1]
        rsi = latest["rsi"]
        macd_hist = latest.get("macd_hist", 0) or 0

        # Scoring (same as original)
        scores = {}
        if rsi < 30:
            scores["rsi"] = 0.8
        elif rsi > 70:
            scores["rsi"] = -0.8
        else:
            scores["rsi"] = (50 - rsi) / 25

        scores["macd"] = 1.0 if macd_hist > 0 else -0.6

        if latest["close"] > latest["ema_20"] > latest["ema_50"]:
            ema_trend = 0.9
        elif latest["close"] < latest["ema_20"] < latest["ema_50"]:
            ema_trend = -0.9
        elif latest["close"] > latest["ema_20"]:
            ema_trend = 0.4
        else:
            ema_trend = -0.4
        scores["ema_trend"] = ema_trend

        vol_ratio = latest["volume"] / latest["volume_sma"] if latest["volume_sma"] > 0 else 1
        scores["volume"] = min((vol_ratio - 1) * 0.8, 1.0) if vol_ratio > 1 else max((vol_ratio - 1) * 1.2, -0.5)

        bb_lower = latest.get("bb_lower", latest["close"] * 0.95)
        bb_upper = latest.get("bb_upper", latest["close"] * 1.05)
        bb_mid = latest.get("bb_mid", (bb_upper + bb_lower) / 2)
        if latest["close"] < bb_lower * 1.02:
            scores["bollinger"] = 0.7
        elif latest["close"] > bb_upper * 0.98:
            scores["bollinger"] = -0.7
        else:
            bb_range = bb_upper - bb_lower if bb_upper != bb_lower else 1
            scores["bollinger"] = (bb_mid - latest["close"]) / bb_range * 0.6

        total_score = sum(scores[k] * self.weights[k] for k in scores)
        total_score = max(min(total_score, 1.0), -1.0)

        if total_score > 0.30:
            action = "BUY"
            confidence = min(abs(total_score), 0.92)
        elif total_score < -0.30:
            action = "SELL"
            confidence = min(abs(total_score), 0.92)
        else:
            action = "HOLD"
            confidence = 0.55 + abs(total_score) * 0.25

        reason = f"deepseek-fast | score={total_score:.2f} | rsi={rsi:.1f}"

        return {
            "action": action,
            "confidence": round(confidence, 3),
            "score": round(total_score, 3),
            "reason": reason,
            "model": self.name,
            "indicators": {
                "rsi": round(rsi, 1),
                "macd_hist": round(float(macd_hist), 4),
                "close": round(latest["close"], 2),
            },
        }
