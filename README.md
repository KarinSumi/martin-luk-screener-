# Martin Luk Stock Screener

A robust, full-universe US stock screener that implements the **Martin Luk Pullback** strategy alongside a high-momentum **Big Move** detector. The system runs automatically every weekday, archives results as CSV files, and sends formatted reports to Telegram.

## 🚀 Key Features

- **Full US Universe:** Screens ~6,000 tickers daily from the Nasdaq/NYSE/AMEX.
- **Dual Strategy Tracking:**
  - **Martin Luk Pullbacks:** Identifies high-energy stocks resting near key support levels.
  - **Big Move Detector:** Spots stocks with >5% daily gains on significant volume.
- **Adaptive Downloader:** Intelligent batch processing with automated rate-limit detection and randomized backoffs to ensure 100% data reliability.
- **New Arrivals Detection:** Automatically compares today's results with the previous run to highlight new opportunities.
- **Historical Archival:** Organized CSV storage in a `results/YYYY/MM/DD/` hierarchy.
- **Smart Notifications:** Formatted monospace tables sent to Telegram with automatic message splitting for large result sets.

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **Data Source:** Yahoo Finance (`yfinance`), Nasdaq FTP
- **Data Analysis:** `pandas`, `numpy`
- **Automation:** GitHub Actions
- **Notifications:** Telegram Bot API

## 📖 Screening Strategies

### 1. Martin Luk Pullbacks (🎯 PULLBACKS)
Designed to find high-volatility stocks in strong uptrends that are currently pulling back to the EMA 9 or EMA 21.
- **Volume:** 20-Day Avg Dollar Volume > $10,000,000.
- **Trend:** Price > EMA 50, EMA 9 > EMA 21, and EMA 21 must be rising.
- **Volatility:** Average Daily Range (ADR) > 4%.
- **Entry:** Price within 3% of EMA 9 or EMA 21.

### 2. Big Moves (🚀 BIG MOVES)
Designed to catch early momentum in institutional-grade stocks.
- **Price:** Current Price > $5.00.
- **Momentum:** Daily Gain > 5% vs Previous Close.
- **Liquidity:** 20-Day Avg Dollar Volume > $1,000,000.

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.10 or higher.
- A Telegram Bot (created via [@BotFather](https://t.me/botfather)).

### 2. Local Setup
```bash
# Clone the repository
git clone https://github.com/KarinSumi/martin-luk-screener-.git
cd martin-luk-screener-

# Install dependencies
pip install yfinance pandas numpy requests
```

### 3. Environment Variables
To run the script locally or in CI, the following environment variables are required:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token from BotFather |
| `TELEGRAM_CHAT_ID` | Your personal Telegram Chat ID |

---

## 🤖 GitHub Actions Automation

The screener is configured to run automatically:
- **Schedule:** Monday to Friday at 21:30 UTC.
- **Manual Trigger:** Go to the **Actions** tab -> **Martin Luk Daily Screener** -> **Run workflow**.

### GitHub Secrets Configuration
You must add your credentials to GitHub to enable notifications:
1. Go to **Settings > Secrets and variables > Actions**.
2. Add `TELEGRAM_BOT_TOKEN`.
3. Add `TELEGRAM_CHAT_ID`.

---

## 📁 Data Structure

Results are archived directly in the repository for historical tracking:
```
results/
└── 2026/
    └── 05/
        └── 08/
            ├── pullbacks.csv      # Martin Luk candidates
            ├── big_moves.csv      # Stocks with >5% gains
            └── new_additions.csv  # Stocks appearing for the first time
```

## 📜 Table Legend (Telegram)

- **ADR:** Average Daily Range (Volatility %).
- **SUPP:** Support Level being tested (E9 or E21).
- **DIST:** % Distance from the current price to the support level.
- **GAIN:** % Price increase compared to the previous day's close.
- **VOL M:** 20-Day Average Dollar Volume in Millions.

---
**Disclaimer:** This tool is for educational and research purposes only. Always perform your own due diligence before making any financial decisions.
