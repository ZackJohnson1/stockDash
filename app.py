import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
import yfinance as yf

WATCHLIST_PATH = "watchlist.json"

def load_watchlist() -> list[str]:
    if not os.path.exists(WATCHLIST_PATH):
        return ["SPY", "QQQ", "AAPL", "MSFT"]
    with open(WATCHLIST_PATH, "r") as f:
        return json.load(f)

def save_watchlist(tickers: list[str]) -> None:
    tickers = sorted(list(dict.fromkeys([t.strip().upper() for t in tickers if t.strip()])))
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(tickers, f, indent=2)

@st.cache_data(ttl=30)
def fetch_quotes(tickers: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        tk = yf.Ticker(t)

        fi = getattr(tk, "fast_info", {}) or {}
        info = {}
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        price = fi.get("last_price") or info.get("regularMarketPrice")
        prev_close = fi.get("previous_close") or info.get("regularMarketPreviousClose")
        open_ = fi.get("open") or info.get("regularMarketOpen")
        day_high = fi.get("day_high") or info.get("regularMarketDayHigh")
        day_low = fi.get("day_low") or info.get("regularMarketDayLow")
        volume = fi.get("last_volume") or info.get("regularMarketVolume")

        if price is None or prev_close in (None, 0):
            chg = None
            chg_pct = None
        else:
            chg = price - prev_close
            chg_pct = (chg / prev_close) * 100.0

        rows.append({
            "Ticker": t,
            "Price": price,
            "Change": chg,
            "Change %": chg_pct,
            "Prev Close": prev_close,
            "Open": open_,
            "Day Low": day_low,
            "Day High": day_high,
            "Volume": volume,
        })

    df = pd.DataFrame(rows)
    if "Change %" in df.columns:
        df = df.sort_values(by="Change %", ascending=False, na_position="last")
    return df

@st.cache_data(ttl=60)
def fetch_history(ticker: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.reset_index()

def autorefresh(seconds: int):
    # Streamlit versions differ; this makes refresh robust.
    if seconds <= 0:
        return
    try:
        st.autorefresh(interval=seconds * 1000, key="refresh")
    except Exception:
        st.write(f"(Auto-refresh every {seconds}s)")

st.set_page_config(page_title="stockDash", layout="wide")
st.title("📈 stockDash (delayed quotes are fine)")

watchlist = load_watchlist()

with st.sidebar:
    st.header("Watchlist")
    new_tickers = st.text_input("Add tickers (comma-separated)", placeholder="e.g., AMZN, META, AVGO")
    if st.button("Add"):
        if new_tickers.strip():
            add = [x.strip().upper() for x in new_tickers.split(",")]
            save_watchlist(watchlist + add)
            st.cache_data.clear()
            st.rerun()

    if watchlist:
        remove = st.multiselect("Remove tickers", options=watchlist)
        if st.button("Remove selected"):
            remaining = [t for t in watchlist if t not in remove]
            save_watchlist(remaining)
            st.cache_data.clear()
            st.rerun()

    st.divider()
    refresh = st.slider("Auto-refresh (seconds)", 0, 120, 30, 5)
    st.caption("Set to 0 to disable auto-refresh.")

autorefresh(refresh)

tickers_tuple = tuple(watchlist)

col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("Quotes")
    if not tickers_tuple:
        st.info("Add tickers in the sidebar.")
    else:
        df = fetch_quotes(tickers_tuple)

        fmt = {
            "Price": "{:,.2f}",
            "Change": "{:+,.2f}",
            "Change %": "{:+.2f}%",
            "Prev Close": "{:,.2f}",
            "Open": "{:,.2f}",
            "Day Low": "{:,.2f}",
            "Day High": "{:,.2f}",
            "Volume": "{:,.0f}",
        }

        st.dataframe(
            df.style.format(fmt, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (local)")

with col2:
    st.subheader("Chart")
    if tickers_tuple:
        sel = st.selectbox("Ticker", options=list(tickers_tuple))
        period = st.selectbox("Period", options=["1d", "5d", "1mo", "3mo", "6mo", "1y"], index=1)
        interval = st.selectbox("Interval", options=["1m", "5m", "15m", "30m", "1h", "1d"], index=1)

        hist = fetch_history(sel, period=period, interval=interval)
        if hist.empty:
            st.warning("No history returned for that ticker/interval.")
        else:
            time_col = hist.columns[0]
            if "Close" in hist.columns:
                st.line_chart(hist.set_index(time_col)["Close"])
            else:
                st.line_chart(hist.set_index(time_col))
    else:
        st.info("Add tickers to see a chart.")