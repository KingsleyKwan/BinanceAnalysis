# BinanceAnalysis

AI-powered cryptocurrency trading simulation and analysis tool for Binance.

## Features

- Fetch real-time and historical market data from Binance
- AI-driven analysis using technical indicators and decision engine
- Backtesting simulation for buy/sell strategies
- Signal generation for current market timing (buy/sell/hold recommendations)
- Modular design for easy extension (add ML models, strategies, etc.)

## Project Structure

```
.
├── README.md
├── requirements.txt
├── src/
│   ├── data/
│   │   └── fetcher.py          # Binance data fetching
│   ├── analysis/
│   │   └── analyzer.py         # Technical indicators & AI scoring
│   ├── simulation/
│   │   └── backtester.py       # Trade simulation engine
│   └── main.py                 # CLI entrypoint for analysis & simulation
└── data/                       # Cached historical data (optional)
```

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python src/main.py --symbol BTCUSDT --analyze
```

### Cantonese (粵語) Support

Use `--lang yue` (or `-l yue`) for written Cantonese output:

```bash
PYTHONPATH=. python src/main.py --symbol BTCUSDT --analyze --lang yue
```

## Usage Examples

Analyze current timing for BTC:

```bash
PYTHONPATH=. python src/main.py --symbol BTCUSDT --analyze --interval 1h
```

Run backtest:

```bash
PYTHONPATH=. python src/main.py --symbol ETHUSDT --backtest --days 90
```

With Cantonese output:

```bash
PYTHONPATH=. python src/main.py --symbol BTCUSDT --analyze --lang yue
```

### Long-term Live Paper Trading (starts with $900)

Run the AI trader continuously. It analyzes every 15 minutes, decides to buy/sell based on signals, and saves all trades + portfolio history to `trading.db`.

```bash
PYTHONPATH=. python src/main.py --symbol BTCUSDT --live --interval 1h
```

- Starts with $900 USD cash
- Uses ~28% of cash per strong BUY signal (when confidence ≥ 55%)
- Sells on strong SELL signals
- Saves everything to SQLite (`trading.db`)
- Press Ctrl+C to stop gracefully and see final equity

The simulation is designed for long-running sessions (days/weeks) to test if the AI strategy can grow the account over time.

## Disclaimer

This is for educational and simulation purposes only. Not financial advice. Cryptocurrency trading involves substantial risk.
