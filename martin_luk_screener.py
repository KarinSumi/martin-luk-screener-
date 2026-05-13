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
        valid_stocks = df[(df['Test Issue'] == 'N') & (df['ETF'] == 'N')].copy()
        mask = ~valid_stocks['Symbol'].str.contains(r'[\$\-\.]', na=True)
        valid_stocks = valid_stocks[mask]
        valid_stocks = valid_stocks[valid_stocks['Symbol'].str.len() <= 4]
        tickers = valid_stocks['Symbol'].dropna().unique().tolist()
        print(f"[{datetime.datetime.now()}] Watchlist ready: {len(tickers)} tickers.")
        return tickers
    except Exception as e:
        print(f"Error fetching watchlist: {e}")
        return ["NVDA", "TSLA", "PLTR", "AMD", "MSTR", "AAPL", "MSFT", "AMZN", "GOOGL", "META"]

def run_multi_screener(tickers):
    pullbacks = []
    big_moves = []
    print(f"[{datetime.datetime.now()}] Downloading data for {len(tickers)} tickers...")
    
    batch_size = 250
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        print(f"[{datetime.datetime.now()}] Processing batch {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1} ({len(batch)} tickers)...")
        
        try:
            data = yf.download(batch, period="7mo", progress=False, group_by='ticker', threads=True)
            if data.empty and len(batch) > 0:
                raise Exception("Empty data returned. Potential rate limit.")

            for ticker in batch:
                try:
                    if ticker not in data or data[ticker].empty: continue
                    df = data[ticker].dropna()
                    if len(df) < 60: continue
                    
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    current_price = float(latest['Close'])
                    prev_price = float(prev['Close'])
                    
                    # Common Indicators
                    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
                    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
                    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
                    df['DollarVolume20'] = (df['Close'] * df['Volume']).rolling(window=20).mean()
                    df['ADR'] = calculate_adr(df['High'], df['Low'], period=20)
                    
                    l = df.iloc[-1]
                    p = df.iloc[-2]
                    
                    # logic 1: Martin Luk Pullback
                    is_uptrend = (current_price > l['EMA50']) and (l['EMA9'] > l['EMA21']) and (l['EMA21'] > p['EMA21'])
                    if l['DollarVolume20'] >= 10_000_000 and l['ADR'] >= 4.0 and is_uptrend:
                        dist_to_ema9 = abs(current_price - l['EMA9']) / l['EMA9']
                        dist_to_ema21 = abs(current_price - l['EMA21']) / l['EMA21']
                        if dist_to_ema9 <= 0.03 or dist_to_ema21 <= 0.03:
                            pullbacks.append({
                                'Ticker': ticker, 'Price': round(current_price, 2),
                                'ADR': round(float(l['ADR']), 2),
                                'Support': 'E9' if dist_to_ema9 <= 0.03 else 'E21',
                                'Dist': round(min(dist_to_ema9, dist_to_ema21) * 100, 2)
                            })

                    # logic 2: Big Move (>5%)
                    gain = (current_price / prev_price) - 1
                    if current_price >= 5.0 and gain >= 0.05 and l['DollarVolume20'] >= 1_000_000:
                        big_moves.append({
                            'Ticker': ticker, 'Price': round(current_price, 2),
                            'Gain': round(gain * 100, 2), 'Vol': round(l['DollarVolume20'] / 1_000_000, 1)
                        })

                except Exception: continue
            
            time.sleep(random.uniform(10, 20))

        except Exception as e:
            print(f"CRITICAL: Batch failed: {e}")
            time.sleep(random.uniform(60, 180))
            
    return pd.DataFrame(pullbacks), pd.DataFrame(big_moves)

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()
        if not result.get("ok"): print(f"Telegram Error: {result.get('description')}")
        else: print("Telegram message sent.")
    except Exception as e: print(f"Error sending message: {e}")

def format_table(title, df, columns, headers):
    if df.empty: return ""
    lines = [f"<b>{title}</b>", "<pre>"]
    lines.append(headers)
    lines.append("-" * len(headers))
    for _, row in df.iterrows():
        row_str = " | ".join([f"{str(row[col]):<{width}}" for col, width in columns])
        lines.append(row_str)
    lines.append("</pre>\n")
    return "\n".join(lines)

if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

    if not BOT_TOKEN or not CHAT_ID:
        print("Missing Credentials.")
    else:
        # 1. Send "Started" heartbeat with Legend
        legend = (
            "📖 <b>Legend:</b>\n"
            "• <b>ADR:</b> Avg Daily Range (Volatility)\n"
            "• <b>SUPP:</b> Support Level (E9=EMA9, E21=EMA21)\n"
            "• <b>DIST:</b> % Distance to Support\n"
            "• <b>GAIN:</b> % Price Increase vs Prev Close\n"
            "• <b>VOL M:</b> 20-Day Avg Dollar Volume (Millions)"
        )
        start_time = datetime.datetime.now()
        send_telegram_message(BOT_TOKEN, CHAT_ID, 
            f"🚀 <b>Screener Started</b>\nTime: {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n{legend}")
        
        try:
            tickers = get_full_us_watchlist()
            num_tickers = len(tickers)
            
            pb_df, bm_df = run_multi_screener(tickers)
            
            # Prepare content
            all_content = []
            if not pb_df.empty:
                pb_df = pb_df.sort_values(by='ADR', ascending=False)
                cols = [('Ticker', 6), ('Price', 7), ('ADR', 4), ('Support', 4), ('Dist', 4)]
                all_content.append(format_table("🎯 PULLBACKS", pb_df, cols, "TICKER | PRICE   | ADR | SUPP | DIST"))
                
            if not bm_df.empty:
                bm_df = bm_df.sort_values(by='Gain', ascending=False)
                cols = [('Ticker', 6), ('Price', 7), ('Gain', 5), ('Vol', 5)]
                all_content.append(format_table("🚀 BIG MOVES", bm_df, cols, "TICKER | PRICE   | GAIN% | VOL M"))

            # 2. Smart results dispatch
            if not all_content:
                send_telegram_message(BOT_TOKEN, CHAT_ID, f"✅ <b>Screener Finished</b>\nProcessed {num_tickers} stocks.\nResult: 😴 No setups found today.")
            else:
                for section in all_content:
                    if len(section) < 4000:
                        send_telegram_message(BOT_TOKEN, CHAT_ID, section)
                    else:
                        chunk = ""
                        for line in section.split("\n"):
                            if len(chunk) + len(line) > 3900:
                                send_telegram_message(BOT_TOKEN, CHAT_ID, chunk + "</pre>")
                                chunk = "<pre>"
                            chunk += line + "\n"
                        send_telegram_message(BOT_TOKEN, CHAT_ID, chunk)
                
                duration = (datetime.datetime.now() - start_time).seconds // 60
                send_telegram_message(BOT_TOKEN, CHAT_ID, f"✅ <b>Screener Complete</b>\nTotal: {num_tickers} stocks\nDuration: {duration} mins")
                
        except Exception as e:
            send_telegram_message(BOT_TOKEN, CHAT_ID, f"❌ <b>Screener Crashed</b>\nError: {str(e)}")
