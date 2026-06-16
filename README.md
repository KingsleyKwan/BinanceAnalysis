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
# Single coin
PYTHONPATH=. python src/main.py --symbol BTCUSDT --live --interval 1h \
  --initial-cash 376 --initial-btc 0.005

# Multi-coin mode (recommended for maximum profit potential)
PYTHONPATH=. python src/main.py --symbol "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT" \
  --live --interval 1h --initial-cash 376 --initial-btc 0.005

# Fully automatic discovery mode (no coin limit)
# The system will scan the entire Binance market every 15 minutes and trade any coin showing strong signals
PYTHONPATH=. python src/main.py --live --auto-discover --interval 1h \
  --initial-cash 376 --initial-btc 0.005
```

**Features**
- **Auto-Discover mode** (`--auto-discover`): System dynamically finds tradable coins across the whole market. No need to specify symbols. Ideal when "almost all coins go down but some go up".
- Multi-coin trading supported — system can hold and rotate between multiple assets
- Custom initial portfolio supported (example: 376 FDUSD + 0.005 BTC)
- `BOTH` decision from the 15-min xAI model = sell current holding + buy the new opportunity
- Per-coin risk limit (~28% of total equity max per position)
- All decisions, trades, and equity history saved to `trading.db`
- Press Ctrl+C to stop

The goal of the system is to **maximize profit** by letting the dual-model AI (deepseek-v4-flash + grok-4.3) dynamically allocate across multiple high-quality coins (or any coin the scanner discovers) while the self-correction mechanism continuously improves decision quality.

### Telegram Notifications (Optional)

The system can send real-time trade alerts and portfolio updates via Telegram.

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot).
3. Add to `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=987654321
```

Notifications include:
- Every trade (BUY / SELL / BOTH) with price, amount, PnL
- Self-correction events (when mistakes are found and lessons are added)
- Portfolio summary every 2 hours

If the variables are not set, notifications are silently disabled.

Example output:
```
=== Cycle 15 | DEEP-XAI | 10:45 ===
BTCUSDT: BOTH (conf 78%) | $66,050.00
  [XAI] BOTH-SELL 0.01345 BTCUSDT | PnL +$12.30
  [XAI] BOTH-BUY 0.00412 ETHUSDT @ $3,450.00
```

This setup lets you test whether the combination of fast cheap signals + periodic deep thinking can profitably grow the account over days or weeks.

### Using Real DeepSeek + xAI APIs (Optional but Recommended)

By default the system uses local rule-based analyzers (no cost).

To use real LLMs:

1. Copy `.env.example` → `.env`
2. Add your keys:

```bash
DEEPSEEK_API_KEY=sk-...
XAI_API_KEY=xai-...
```

3. Re-run the live trader. It will automatically switch to real APIs when keys are detected.

**Important cost notes (three-tier schedule)**
- `deepseek-v4-flash` every 1 minute (very cheap)
- `deepseek-v4-pro` every 15 minutes (still cheap)
- `grok-4.3` only every 2 hours (expensive) + self-correction review
- This schedule dramatically reduces cost while keeping high-quality reasoning periodically.
- You can override models via environment variables in `.env`.
- Monitor your usage. The system falls back to local analyzers if API fails.

### Self-Correction System (Unique Feature)

Every 15 minutes, **grok-4.3** automatically reviews all decisions made by **deepseek-v4-flash** in the previous window.

- It compares each decision against what actually happened in the next 15 minutes.
- If DeepSeek made a mistake, the system **pauses**, xAI generates a concise lesson, and appends it to `src/analysis/deepseek_lessons.md`.
- The lesson is automatically included in all future DeepSeek prompts (few-shot learning).
- After the correction, the system resumes automatically.

This creates a continuously improving trading agent that learns from its own mistakes in real time.

## Disclaimer

This is for educational and simulation purposes only. Not financial advice. Cryptocurrency trading involves substantial risk.
