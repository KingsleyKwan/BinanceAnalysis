import argparse
from src.data.fetcher import BinanceDataFetcher
from src.analysis.analyzer import AIAnalyzer
from src.simulation.backtester import SimpleBacktester
from src.simulation.live_trader import LivePaperTrader

# Translations for English and Cantonese (written Cantonese / 書面粵語)
TRANSLATIONS = {
    "en": {
        "header": "=== BinanceAnalysis | {symbol} | {interval} ===",
        "fetching": "Fetching recent data for analysis...",
        "analysis_title": "AI Analysis Result:",
        "action": "Action:",
        "confidence": "Confidence:",
        "score": "Score:",
        "components": "Components:",
        "indicators": "Indicators:",
        "time": "Time:",
        "interpretation": "Interpretation:",
        "buy": "Bullish signals detected — potential good entry point.",
        "sell": "Bearish signals detected — consider taking profits or avoiding new positions.",
        "hold": "Neutral market — wait for clearer signals or use smaller position sizing.",
        "backtest_title": "Running backtest simulation...",
        "backtest_results": "Backtest Results:",
        "symbol": "Symbol:",
        "final_equity": "Final Equity:",
        "total_return": "Total Return:",
        "num_trades": "Trades Executed:",
        "latest_signal": "Latest Signal:",
    },
    "yue": {
        "header": "=== BinanceAnalysis | {symbol} | {interval} ===",
        "fetching": "正在擷取最新市場數據...",
        "analysis_title": "AI 分析結果：",
        "action": "建議行動：",
        "confidence": "置信度：",
        "score": "綜合評分：",
        "components": "指標分數：",
        "indicators": "技術指標：",
        "time": "時間：",
        "interpretation": "分析解讀：",
        "buy": "市場偏 bullish，有入貨機會。",
        "sell": "市場偏 bearish，建議考慮獲利或暫停新倉。",
        "hold": "市場中性，建議觀望或小注試水。",
        "backtest_title": "運行回測模擬中...",
        "backtest_results": "回測結果：",
        "symbol": "交易對：",
        "final_equity": "最終資產：",
        "total_return": "總回報：",
        "num_trades": "交易次數：",
        "latest_signal": "最新訊號：",
    },
}

def main():
    parser = argparse.ArgumentParser(description="Binance AI Trading Analysis & Simulation with Self-Correction (支援粵語)")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (single) or comma-separated list for multi-coin mode")
    parser.add_argument("--analyze", action="store_true", help="Run current AI analysis")
    parser.add_argument("--backtest", action="store_true", help="Run backtest simulation")
    parser.add_argument("--interval", default="1h", help="Kline interval (1h, 4h, 1d, etc.)")
    parser.add_argument("--days", type=int, default=60, help="Days of history for backtest")
    parser.add_argument("--lang", "-l", choices=["en", "yue"], default="en",
                        help="Output language: en (English) or yue (Cantonese)")
    parser.add_argument("--live", action="store_true",
                        help="Run long-term live paper trading simulation with self-correction (multi-coin supported)")
    parser.add_argument("--initial-cash", type=float, default=376.0,
                        help="Starting stablecoin balance (FDUSD/USDT) for --live mode")
    parser.add_argument("--initial-btc", type=float, default=0.005,
                        help="Starting BTC amount held (for --live mode)")
    args = parser.parse_args()

    if args.live:
        # Support comma-separated symbols for multi-coin trading
        symbols = [s.strip().upper() for s in args.symbol.split(",") if s.strip()]

        initial_holdings = {}
        if args.initial_btc > 0:
            initial_holdings["BTCUSDT"] = {"amount": args.initial_btc, "avg_buy_price": 65000.0}

        trader = LivePaperTrader(
            symbols=symbols,
            interval=args.interval,
            initial_cash=args.initial_cash,
            initial_holdings=initial_holdings
        )
        trader.run_forever()
        return

    lang = args.lang
    t = TRANSLATIONS[lang]

    fetcher = BinanceDataFetcher()
    analyzer = AIAnalyzer()

    print(f"\n{t['header'].format(symbol=args.symbol, interval=args.interval)}\n")

    if args.analyze or not args.backtest:
        print(t["fetching"])
        df = fetcher.get_recent_data(args.symbol, days=30, interval=args.interval)
        result = analyzer.analyze(df)
        print(t["analysis_title"])
        print(f"  {t['action']}     {result['action']}")
        print(f"  {t['confidence']} {result['confidence']*100:.1f}%")
        print(f"  {t['score']}      {result['score']:+.3f}")
        print(f"  {t['components']} {result['components']}")
        print(f"  {t['indicators']} {result['indicators']}")
        print(f"  {t['time']}       {result['timestamp']}")
        print(f"\n{t['interpretation']}")
        if result["action"] == "BUY":
            print(f"  {t['buy']}")
        elif result["action"] == "SELL":
            print(f"  {t['sell']}")
        else:
            print(f"  {t['hold']}")

    if args.backtest:
        print(f"\n{t['backtest_title']}")
        df = fetcher.get_recent_data(args.symbol, days=args.days, interval=args.interval)
        bt = SimpleBacktester()
        res = bt.run(df, args.symbol)
        print(t["backtest_results"])
        print(f"  {t['symbol']}          {res['symbol']}")
        print(f"  {t['final_equity']}    ${res['final_equity']:.2f}")
        print(f"  {t['total_return']}    {res['total_return_pct']:+.2f}%")
        print(f"  {t['num_trades']} {res['num_trades']}")
        print(f"  {t['latest_signal']}   {res['final_signal']['action']} ({res['final_signal']['confidence']*100:.0f}% conf)")

if __name__ == "__main__":
    main()
