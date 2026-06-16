import os
from binance.spot import Spot
from binance.error import ClientError
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class BinanceDataFetcher:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.client = Spot(
            api_key=api_key or os.getenv("BINANCE_API_KEY"),
            api_secret=api_secret or os.getenv("BINANCE_API_SECRET")
        )

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
        """Fetch historical klines/candles."""
        try:
            raw = self.client.klines(symbol=symbol.upper(), interval=interval, limit=limit)
            df = pd.DataFrame(raw, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
            numeric_cols = ["open", "high", "low", "close", "volume", "quote_volume"]
            df[numeric_cols] = df[numeric_cols].astype(float)
            return df[["open_time", "open", "high", "low", "close", "volume"]]
        except ClientError as e:
            raise RuntimeError(f"Binance API error: {e}") from e

    def get_current_price(self, symbol: str) -> float:
        """Get latest ticker price."""
        try:
            ticker = self.client.ticker_price(symbol=symbol.upper())
            return float(ticker["price"])
        except ClientError as e:
            raise RuntimeError(f"Failed to fetch price: {e}") from e

    def get_recent_data(self, symbol: str, days: int = 30, interval: str = "1h") -> pd.DataFrame:
        """Convenience method for recent data."""
        # Rough estimate: ~24 candles per day for 1h
        limit = min(days * 24 + 10, 1000)
        return self.get_klines(symbol, interval=interval, limit=limit)
