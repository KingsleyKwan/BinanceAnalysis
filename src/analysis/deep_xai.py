import pandas as pd
import numpy as np
from typing import Dict, Any
from src.analysis.base_analyzer import BaseAnalyzer

class DeepXAIAnalyzer(BaseAnalyzer):
    """
    Deeper, more conservative analyzer intended to run every 15 minutes.
    Higher thresholds, prefers HOLD unless signal is very strong.
    Can return "BOTH" when it wants to switch from current holding to another opportunity.
    Model name: 'xai'
    """

    name = "xai"

    def __init__(self):
        self.min_confidence = 0.68   # stricter than deepseek
        self.weights = {
            "rsi": 0.20,
            "macd": 0.30,
            "ema_trend": 0.25,
            "volume": 0.10,
            "bollinger": 0.15,
        }

    def analyze(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        if len(df) < 60:
            return {"action": "HOLD", "confidence": 0.0, "score": 0.0, "reason": "insufficient data", "model": self.name}

        df = df.copy()
        close = df["close"]

        # Same indicators
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

        scores = {}
        if rsi < 28:
            scores["rsi"] = 0.85
        elif rsi > 72:
            scores["rsi"] = -0.85
        else:
            scores["rsi"] = (50 - rsi) / 22

        scores["macd"] = 1.0 if macd_hist > 0 else -0.65

        if latest["close"] > latest["ema_20"] > latest["ema_50"]:
            ema_trend = 0.95
        elif latest["close"] < latest["ema_20"] < latest["ema_50"]:
            ema_trend = -0.95
        elif latest["close"] > latest["ema_20"]:
            ema_trend = 0.5
        else:
            ema_trend = -0.5
        scores["ema_trend"] = ema_trend

        vol_ratio = latest["volume"] / latest["volume_sma"] if latest["volume_sma"] > 0 else 1
        scores["volume"] = min((vol_ratio - 1) * 0.9, 1.0) if vol_ratio > 1.15 else max((vol_ratio - 1) * 1.3, -0.6)

        bb_lower = latest.get("bb_lower", latest["close"] * 0.95)
        bb_upper = latest.get("bb_upper", latest["close"] * 1.05)
        bb_mid = latest.get("bb_mid", (bb_upper + bb_lower) / 2)
        if latest["close"] < bb_lower * 1.015:
            scores["bollinger"] = 0.75
        elif latest["close"] > bb_upper * 0.985:
            scores["bollinger"] = -0.75
        else:
            bb_range = bb_upper - bb_lower if bb_upper != bb_lower else 1
            scores["bollinger"] = (bb_mid - latest["close"]) / bb_range * 0.5

        total_score = sum(scores[k] * self.weights[k] for k in scores)
        total_score = max(min(total_score, 1.0), -1.0)

        # Stricter decision boundaries
        if total_score > 0.42:
            action = "BUY"
            confidence = min(total_score, 0.96)
        elif total_score < -0.42:
            action = "SELL"
            confidence = min(abs(total_score), 0.96)
        else:
            action = "HOLD"
            confidence = 0.60 + abs(total_score) * 0.2

        reason = f"xai-deep | score={total_score:.2f} | strong_trend={abs(ema_trend) > 0.9}"

        # Special case: if we have a very strong opposite signal while holding something,
        # the caller can interpret this as potential "BOTH" (switch).
        if abs(total_score) > 0.55 and abs(ema_trend) > 0.9:
            if total_score > 0:
                action = "BOTH"  # strong bullish while possibly holding bearish position
            else:
                action = "BOTH"  # strong bearish while holding bullish position

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
