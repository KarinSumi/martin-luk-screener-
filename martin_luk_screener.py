import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import warnings
import urllib.request
import requests
import os

warnings.filterwarnings('ignore')

def calculate_adr(high_series, low_series, period=20):
    daily_range = (high_series / low_series) - 1
    return daily_range.rolling(window=period).mean() * 100

def get_full_us_watchlist():
    print(f"[{datetime.datetime.now()}] Fetching full US stock universe...")
    try:
        url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt"
        df = pd.read_csv(url, sep='|')
        valid_stocks = df[df['Test Issue'] == 'N']
        tickers = valid_stocks['Symbol'].dropna().tolist()
        tickers = [str(t).replace('.','-') for t in tickers if " " not in str(t)]
        return tickers
    except Exception as e:
        print(f"Error fetching watchlist: {e}")
        return ["NVDA", "TSLA", "PLTR", "AMD", "MSTR"]

def screen_martin_luk_pullbacks(tickers):
    matched_stocks = []
    print(f"[{datetime.datetime.now()}] Downloading data for {len(tickers)} tickers...")
    data = yf.download(tickers, period="6mo", progress=False, group_by='ticker')

    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 50: continue
            
            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['DollarVolume'] = (df['Close'] * df['Volume']).rolling(window=20).mean()
            df['ADR'] = calculate_adr(df['High'], df['Low'], period=20)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            current_price = latest['Close']
            
            if latest['DollarVolume'] < 10_000_000 or latest['ADR'] < 4.0: continue
            
            is_uptrend = (current_price > latest['EMA50']) and \
                         (latest['EMA9'] > latest['EMA21']) and \
                         (latest['EMA21'] > prev['EMA21'])
            if not is_uptrend: continue
            
            dist_to_ema9 = abs(current_price - latest['EMA9']) / latest['EMA9']
            dist_to_ema21 = abs(current_price - latest['EMA21']) / latest['EMA21']
            
            if dist_to_ema9 <= 0.03 or dist_to_ema21 <= 0.03:
                matched_stocks.append({
                    'Ticker': ticker,
                    'Price': round(current_price, 2),
                    'ADR': round(latest['ADR'], 2),
                    'Support': 'EMA 9' if dist_to_ema9 <= 0.03 else 'EMA 21',
                    'Dist': round(min(dist_to_ema9, dist_to_ema21) * 100, 2)
                })
        except: continue
    return pd.DataFrame(matched_stocks)


def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8779755957:AAG_54Z21eVmQwLmY589eejU6F8GW7__bFQ")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    if not CHAT_ID:
        print("Error: TELEGRAM_CHAT_ID environment variable is not set.")
    else:
        results = screen_martin_luk_pullbacks(get_full_us_watchlist())

        if not results.empty:
            results = results.sort_values(by='ADR', ascending=False)
            msg = "🎯 <b>MARTIN LUK PULLBACKS</b> 🎯\n\n"
            for _, row in results.iterrows():
                msg += f"🔹 <b>{row['Ticker']}</b>: ${row['Price']}\n"
                msg += f"   • Support: {row['Support']} ({row['Dist']}%)\n"
                msg += f"   • ADR: {row['ADR']}%\n\n"
            send_telegram_message(BOT_TOKEN, CHAT_ID, msg)
        else:
            send_telegram_message(BOT_TOKEN, CHAT_ID, "😴 No setups found today.")
