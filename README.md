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

### Long-term Live Paper Trading with Dual-Model Analysis (starts with $900)

The trader now uses two different "models" at different frequencies:

- **Every 1 minute** — `deepseek` (FastDeepSeekAnalyzer): quick, permissive signals
- **Every 15 minutes** — `xai` (DeepXAIAnalyzer): deeper, more conservative analysis that can return **BOTH** (rotate position)

```bash
PYTHONPATH=. python src/main.py --symbol BTCUSDT,ETHUSDT --live --interval 1h
```

**Features**
- Starts with $900 USD
- Supports multiple symbols (BTCUSDT + ETHUSDT by default)
- `BOTH` decision from the 15-min xAI model = sell current holding + buy the new opportunity
- All decisions, trades, and equity history saved to `trading.db`
- Press Ctrl+C to stop

Example output:
```
=== Cycle 15 | DEEP-XAI | 10:45 ===
BTCUSDT: BOTH (conf 78%) | $66,050.00
  [XAI] BOTH-SELL 0.01345 BTCUSDT | PnL +$12.30
  [XAI] BOTH-BUY 0.00412 ETHUSDT @ $3,450.00
```

This setup lets you test whether the combination of fast cheap signals + periodic deep thinking can profitably grow the account over days or weeks.

## Disclaimer

This is for educational and simulation purposes only. Not financial advice. Cryptocurrency trading involves substantial risk.
