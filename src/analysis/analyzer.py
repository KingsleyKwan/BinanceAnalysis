import pandas as pd
import numpy as np
from typing import Dict, Any

class AIAnalyzer:
    """Technical analysis with rule-based AI scoring for buy/sell decisions."""

    def __init__(self):
        self.weights = {
            "rsi": 0.25,
            "macd": 0.25,
            "ema_trend": 0.20,
            "volume": 0.15,
            "bollinger": 0.15,
        }

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < 50:
            raise ValueError("Need at least 50 candles for reliable analysis")

        df = df.copy()
        close = df["close"]

        # Indicators (pure pandas/numpy implementations)
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD (12,26,9)
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # EMAs
        df["ema_20"] = close.ewm(span=20, adjust=False).mean()
        df["ema_50"] = close.ewm(span=50, adjust=False).mean()

        # Bollinger Bands (20, 2)
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        df["bb_lower"] = sma20 - 2 * std20
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_mid"] = sma20

        # Volume SMA
        df["volume_sma"] = df["volume"].rolling(20).mean()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Scoring components (-1 to +1 each, positive = bullish)
        scores = {}

        # RSI: oversold (<30) bullish, overbought (>70) bearish
        rsi = latest["rsi"]
        if rsi < 30:
            scores["rsi"] = 0.8
        elif rsi > 70:
            scores["rsi"] = -0.8
        else:
            scores["rsi"] = (50 - rsi) / 25  # scale around neutral

        # MACD histogram momentum
        macd_hist = latest.get("macd_hist", 0) or 0
        scores["macd"] = 1.0 if macd_hist > 0 else -0.6

        # EMA trend: price above both EMAs and EMA20 > EMA50 = strong uptrend
        ema_trend = 0.0
        if latest["close"] > latest["ema_20"] > latest["ema_50"]:
            ema_trend = 0.9
        elif latest["close"] < latest["ema_20"] < latest["ema_50"]:
            ema_trend = -0.9
        elif latest["close"] > latest["ema_20"]:
            ema_trend = 0.4
        else:
            ema_trend = -0.4
        scores["ema_trend"] = ema_trend

        # Volume confirmation
        vol_ratio = latest["volume"] / latest["volume_sma"] if latest["volume_sma"] > 0 else 1
        scores["volume"] = min((vol_ratio - 1) * 0.8, 1.0) if vol_ratio > 1 else max((vol_ratio - 1) * 1.2, -0.5)

        # Bollinger: price near lower band = potential buy, near upper = sell
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

        # Aggregate weighted score
        total_score = sum(scores[k] * self.weights[k] for k in scores)
        total_score = max(min(total_score, 1.0), -1.0)

        # Decision
        if total_score > 0.35:
            action = "BUY"
            confidence = min(total_score, 0.95)
        elif total_score < -0.35:
            action = "SELL"
            confidence = min(abs(total_score), 0.95)
        else:
            action = "HOLD"
            confidence = 0.6 + abs(total_score) * 0.3

        return {
            "action": action,
            "confidence": round(confidence, 3),
            "score": round(total_score, 3),
            "components": {k: round(v, 3) for k, v in scores.items()},
            "indicators": {
                "rsi": round(rsi, 1),
                "macd_hist": round(float(macd_hist), 4),
                "close": round(latest["close"], 2),
                "ema_20": round(latest["ema_20"], 2),
                "ema_50": round(latest["ema_50"], 2),
            },
            "timestamp": latest["open_time"].isoformat(),
        }
