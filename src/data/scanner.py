from typing import List
from src.data.fetcher import BinanceDataFetcher

class CoinScanner:
    """
    Dynamically discovers tradable coins on Binance.
    Goal: find coins with strong momentum/volume even when most of the market is down.
    """

    def __init__(self, min_quote_volume: float = 5_000_000, top_n: int = 15):
        self.fetcher = BinanceDataFetcher()
        self.min_quote_volume = min_quote_volume   # minimum 24h volume in USDT
        self.top_n = top_n

    def discover(self, quote_asset: str = "USDT") -> List[str]:
        """
        Returns a list of symbols (e.g. ['BTCUSDT', 'SOLUSDT', ...])
        ranked by a combination of volume and 24h price change.
        """
        try:
            tickers = self.fetcher.client.ticker_24hr()
        except Exception as e:
            print(f"[Scanner] Failed to fetch 24hr tickers: {e}")
            return ["BTCUSDT", "ETHUSDT"]  # fallback

        candidates = []
        for t in tickers:
            symbol = t["symbol"]
            if not symbol.endswith(quote_asset):
                continue
            try:
                vol = float(t["quoteVolume"])
                change = float(t["priceChangePercent"])
            except:
                continue

            if vol < self.min_quote_volume:
                continue

            # Score = volume * (1 + |change|) to favor both liquid + moving coins
            score = vol * (1 + abs(change) / 100)
            candidates.append((symbol, score, change, vol))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        symbols = [c[0] for c in candidates[: self.top_n]]
        print(f"[Scanner] Discovered {len(symbols)} coins: {symbols}")
        return symbols
