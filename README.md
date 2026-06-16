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

## Disclaimer

This is for educational and simulation purposes only. Not financial advice. Cryptocurrency trading involves substantial risk.
