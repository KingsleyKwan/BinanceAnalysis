import argparse
from src.data.fetcher import BinanceDataFetcher
from src.analysis.analyzer import AIAnalyzer
from src.simulation.backtester import SimpleBacktester

def main():
    parser = argparse.ArgumentParser(description="Binance AI Trading Analysis & Simulation")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--analyze", action="store_true", help="Run current AI analysis")
    parser.add_argument("--backtest", action="store_true", help="Run backtest simulation")
    parser.add_argument("--interval", default="1h", help="Kline interval (1h, 4h, 1d, etc.)")
    parser.add_argument("--days", type=int, default=60, help="Days of history for backtest")
    args = parser.parse_args()

    fetcher = BinanceDataFetcher()
    analyzer = AIAnalyzer()

    print(f"\n=== BinanceAnalysis | {args.symbol} | {args.interval} ===\n")

    if args.analyze or not args.backtest:
        print("Fetching recent data for analysis...")
        df = fetcher.get_recent_data(args.symbol, days=30, interval=args.interval)
        result = analyzer.analyze(df)
        print("AI Analysis Result:")
        print(f"  Action:     {result['action']}")
        print(f"  Confidence: {result['confidence']*100:.1f}%")
        print(f"  Score:      {result['score']:+.3f}")
        print(f"  Components: {result['components']}")
        print(f"  Indicators: {result['indicators']}")
        print(f"  Time:       {result['timestamp']}")
        print("\nInterpretation:")
        if result["action"] == "BUY":
            print("  Bullish signals detected — potential good entry point.")
        elif result["action"] == "SELL":
            print("  Bearish signals detected — consider taking profits or avoiding new positions.")
        else:
            print("  Neutral market — wait for clearer signals or use smaller position sizing.")

    if args.backtest:
        print("\nRunning backtest simulation...")
        df = fetcher.get_recent_data(args.symbol, days=args.days, interval=args.interval)
        bt = SimpleBacktester()
        res = bt.run(df, args.symbol)
        print("Backtest Results:")
        print(f"  Symbol:          {res['symbol']}")
        print(f"  Final Equity:    ${res['final_equity']:.2f}")
        print(f"  Total Return:    {res['total_return_pct']:+.2f}%")
        print(f"  Trades Executed: {res['num_trades']}")
        print(f"  Latest Signal:   {res['final_signal']['action']} ({res['final_signal']['confidence']*100:.0f}% conf)")

if __name__ == "__main__":
    main()
