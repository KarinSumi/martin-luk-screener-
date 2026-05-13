import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import warnings
import urllib.request
import requests
import os
import time
import random

warnings.filterwarnings('ignore')

def calculate_adr(high_series, low_series, period=20):
    daily_range = (high_series / low_series) - 1
    return daily_range.rolling(window=period).mean() * 100

def get_full_us_watchlist():
    print(f"[{datetime.datetime.now()}] Fetching full US stock universe...")
    try:
        url = "http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
        df = pd.read_csv(url, sep='|')
        # Filter for real stocks (Test Issue 'N'), and ensure they are not ETFs
        valid_stocks = df[(df['Test Issue'] == 'N') & (df['ETF'] == 'N')].copy()
        
        # Vectorized cleaning: exclude any ticker containing $, -, or . and ensure length <= 4
        # We use str.contains with regex to catch $, -, and .
        mask = ~valid_stocks['Symbol'].str.contains(r'[\$\-\.]', na=True)
        valid_stocks = valid_stocks[mask]
        valid_stocks = valid_stocks[valid_stocks['Symbol'].str.len() <= 4]
        
        tickers = valid_stocks['Symbol'].dropna().unique().tolist()
        print(f"[{datetime.datetime.now()}] Watchlist ready: {len(tickers)} tickers.")
        return tickers
    except Exception as e:
        print(f"Error fetching watchlist: {e}")
        # Robust fallback
        return ["NVDA", "TSLA", "PLTR", "AMD", "MSTR", "AAPL", "MSFT", "AMZN", "GOOGL", "META"]

def screen_martin_luk_pullbacks(tickers):
    matched_stocks = []
    print(f"[{datetime.datetime.now()}] Downloading data for {len(tickers)} tickers...")
    
    # Process in batches of 250
    batch_size = 250
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        print(f"[{datetime.datetime.now()}] Processing batch {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1} ({len(batch)} tickers)...")
        
        try:
            # period="7mo" to ensure we have enough data for 50-day EMA and 20-day rolling volume/ADR
            data = yf.download(batch, period="7mo", progress=False, group_by='ticker', threads=True)
            
            # Detect potential rate limits/empty returns
            if data.empty and len(batch) > 0:
                raise Exception("Empty data returned from yfinance. Potential rate limit.")

            for ticker in batch:
                try:
                    if ticker not in data or data[ticker].empty: continue
                    df = data[ticker].dropna()
                    # Need at least 60 days for 50-day EMA + some lookback
                    if len(df) < 60: continue
                    
                    # Technical Indicators
                    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
                    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
                    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
                    df['DollarVolume'] = (df['Close'] * df['Volume']).rolling(window=20).mean()
                    df['ADR'] = calculate_adr(df['High'], df['Low'], period=20)
                    
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    current_price = latest['Close']
                    
                    # 1. Volume Filter (Priority C)
                    if latest['DollarVolume'] < 10_000_000: continue
                    
                    # 2. Trend Filter (Priority B)
                    is_uptrend = (current_price > latest['EMA50']) and \
                                 (latest['EMA9'] > latest['EMA21']) and \
                                 (latest['EMA21'] > prev['EMA21'])
                    if not is_uptrend: continue
                    
                    # 3. Volatility Filter (Priority A)
                    if latest['ADR'] < 4.0: continue
                    
                    # 4. Proximity Filter (Priority D)
                    dist_to_ema9 = abs(current_price - latest['EMA9']) / latest['EMA9']
                    dist_to_ema21 = abs(current_price - latest['EMA21']) / latest['EMA21']
                    
                    if dist_to_ema9 <= 0.03 or dist_to_ema21 <= 0.03:
                        matched_stocks.append({
                            'Ticker': ticker,
                            'Price': round(float(current_price), 2),
                            'ADR': round(float(latest['ADR']), 2),
                            'Support': 'EMA 9' if dist_to_ema9 <= 0.03 else 'EMA 21',
                            'Dist': round(min(dist_to_ema9, dist_to_ema21) * 100, 2)
                        })
                except Exception:
                    continue
            
            # Normal completion of batch: brief random pause
            delay = random.uniform(10, 20)
            print(f"Batch completed. Sleeping {delay:.1f}s...")
            time.sleep(delay)

        except Exception as e:
            print(f"CRITICAL: Batch failed or rate limited: {e}")
            # Escalated random backoff: 60-180 seconds
            backoff = random.uniform(60, 180)
            print(f"Backing off for {backoff:.1f}s...")
            time.sleep(backoff)
            # We don't retry here to keep it simple, but we could in a more advanced version
            
    return pd.DataFrame(matched_stocks)


def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        if not result.get("ok"):
            print(f"Telegram API Error: {result.get('description')}")
        else:
            print("Telegram message sent successfully.")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

if __name__ == "__main__":
    # Access keys from environment exclusively for security
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    if not BOT_TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables are not set.")
    else:
        results = screen_martin_luk_pullbacks(get_full_us_watchlist())

        if not results.empty:
            results = results.sort_values(by='ADR', ascending=False)
            
            # Create a text-based table for Telegram (Monospace)
            header = "TICKER | PRICE | ADR% | SUPP | DIST%"
            separator = "-" * len(header)
            table_lines = [header, separator]
            
            for _, row in results.iterrows():
                # Format each row to fit fixed-width columns
                ticker = f"{row['Ticker']:<6}"
                price = f"{row['Price']:>7.2f}"
                adr = f"{row['ADR']:>5.1f}"
                supp = f"{'E9' if row['Support'] == 'EMA 9' else 'E21':<4}"
                dist = f"{row['Dist']:>5.1f}"
                table_lines.append(f"{ticker} | {price} | {adr} | {supp} | {dist}")
            
            table_text = "\n".join(table_lines)
            msg = f"🎯 <b>MARTIN LUK PULLBACKS</b> 🎯\n\n<pre>{table_text}</pre>"
            send_telegram_message(BOT_TOKEN, CHAT_ID, msg)
        else:
            send_telegram_message(BOT_TOKEN, CHAT_ID, "😴 No setups found today.")
