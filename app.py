import json
import math
import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

WATCHLIST_PATH = "watchlist.json"


# -------------------------
# Utils
# -------------------------
def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def fmt_num(x, decimals=2) -> str:
    if x is None:
        return "—"
    try:
        if isinstance(x, float) and math.isnan(x):
            return "—"
        return f"{x:,.{decimals}f}"
    except Exception:
        return "—"


def fmt_int(x) -> str:
    if x is None:
        return "—"
    try:
        if isinstance(x, float) and math.isnan(x):
            return "—"
        return f"{x:,.0f}"
    except Exception:
        return "—"


def change_str(chg: float | None, chg_pct: float | None) -> str:
    if chg is None or chg_pct is None:
        return "—"
    try:
        if (isinstance(chg, float) and math.isnan(chg)) or (isinstance(chg_pct, float) and math.isnan(chg_pct)):
            return "—"
    except Exception:
        return "—"

    sign = "+" if chg >= 0 else ""
    return f"{sign}{chg:,.2f} ({sign}{chg_pct:.2f}%)"


def bg_for_change_pct(chg_pct: float | None, cap: float = 6.0) -> str:
    if chg_pct is None:
        return "rgba(255,255,255,1.0)"
    try:
        if isinstance(chg_pct, float) and math.isnan(chg_pct):
            return "rgba(255,255,255,1.0)"
    except Exception:
        return "rgba(255,255,255,1.0)"

    t = clamp(chg_pct / cap, -1.0, 1.0)
    intensity = abs(t)

    # strong contrast
    alpha = 0.22 + 0.58 * intensity

    if t >= 0:
        return f"rgba(16, 185, 129, {alpha:.3f})"
    return f"rgba(239, 68, 68, {alpha:.3f})"


def border_for_change(chg_pct: float | None) -> str:
    if chg_pct is None:
        return "rgba(0,0,0,0.18)"
    try:
        if isinstance(chg_pct, float) and math.isnan(chg_pct):
            return "rgba(0,0,0,0.18)"
    except Exception:
        return "rgba(0,0,0,0.18)"
    return "rgba(16,185,129,0.70)" if chg_pct >= 0 else "rgba(239,68,68,0.70)"


# -------------------------
# Watchlist
# -------------------------
def load_watchlist() -> list[str]:
    if not os.path.exists(WATCHLIST_PATH):
        return ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]
    with open(WATCHLIST_PATH, "r") as f:
        data = json.load(f)
    return sorted(list(dict.fromkeys([str(x).strip().upper() for x in data if str(x).strip()])))


def save_watchlist(tickers: list[str]) -> None:
    tickers = sorted(list(dict.fromkeys([t.strip().upper() for t in tickers if t.strip()])))
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(tickers, f, indent=2)


# -------------------------
# Fetching
# -------------------------
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
        day_high = fi.get("day_high") or info.get("regularMarketDayHigh")
        day_low = fi.get("day_low") or info.get("regularMarketDayLow")
        volume = fi.get("last_volume") or info.get("regularMarketVolume")

        if price is None or prev_close in (None, 0):
            chg = None
            chg_pct = None
        else:
            chg = price - prev_close
            chg_pct = (chg / prev_close) * 100.0

        rows.append(
            dict(
                Ticker=t,
                Price=price,
                Change=chg,
                ChangePct=chg_pct,
                PrevClose=prev_close,
                DayLow=day_low,
                DayHigh=day_high,
                Volume=volume,
            )
        )

    return pd.DataFrame(rows)


def normalize_period_interval(period: str, interval: str) -> tuple[str, str]:
    if period in ("6mo", "1y") and interval in ("1m", "5m", "15m", "30m"):
        return period, "1h"
    if period == "3mo" and interval == "1m":
        return period, "5m"
    return period, interval


@st.cache_data(ttl=60)
def fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    period, interval = normalize_period_interval(period, interval)
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    time_col = df.columns[0]
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col)
    return df


def extract_close_series(hist: pd.DataFrame) -> pd.Series | None:
    if hist is None or hist.empty:
        return None
    if "Close" not in hist.columns:
        return None
    close = hist["Close"]
    # If DataFrame (multi columns), take first
    if isinstance(close, pd.DataFrame):
        if close.shape[1] == 0:
            return None
        close = close.iloc[:, 0]
    if not isinstance(close, pd.Series):
        try:
            close = pd.Series(close)
        except Exception:
            return None
    return close


# -------------------------
# Cards HTML grid (RENDERED VIA components.html)
# -------------------------
def render_cards_grid(df: pd.DataFrame, cap: float, density: str):
    minw = 380 if density == "Comfortable" else 340
    title_fs = 22 if density == "Comfortable" else 20
    price_fs = 18 if density == "Comfortable" else 16
    kv_fs = 13 if density == "Comfortable" else 12

    parts = []
    parts.append(
        f"""
        <style>
          .sd-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax({minw}px, 1fr));
            gap: 18px;
            align-items: stretch;
          }}
          .sd-card {{
            border-radius: 18px;
            padding: 16px 16px 12px 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.10);
            box-sizing: border-box;
            overflow: hidden;
            min-height: 220px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Inter, Arial, sans-serif;
            color:#0B1220;
          }}
          .sd-top {{
            display:flex;
            justify-content:space-between;
            align-items:flex-start;
            gap:12px;
          }}
          .sd-ticker {{
            font-size:{title_fs}px;
            font-weight: 950;
            letter-spacing:0.2px;
            line-height:1.0;
            white-space:nowrap;
          }}
          .sd-price {{
            font-size:{price_fs}px;
            font-weight: 900;
            line-height:1.0;
            text-align:right;
            white-space:nowrap;
          }}
          .sd-chg {{
            margin-top:10px;
            font-size:{kv_fs+1}px;
            font-weight: 900;
          }}
          .sd-kvs {{
            margin-top:12px;
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px 16px;
            font-size:{kv_fs}px;
            color: rgba(11,18,32,0.92);
          }}
          .sd-kv {{
            display:flex;
            justify-content:space-between;
            gap:12px;
            white-space:nowrap;
          }}
          .sd-k {{
            opacity:0.75;
          }}
          .sd-v {{
            font-weight:900;
          }}
          .sd-time {{
            margin-top:12px;
            font-size:11px;
            color: rgba(11,18,32,0.65);
          }}
        </style>
        <div class="sd-grid">
        """
    )

    now_str = datetime.now().strftime("%H:%M:%S")

    for _, r in df.iterrows():
        bg = bg_for_change_pct(r["ChangePct"], cap=cap)
        border = border_for_change(r["ChangePct"])

        parts.append(
            f"""
            <div class="sd-card" style="background:{bg}; border:2px solid {border};">
              <div class="sd-top">
                <div class="sd-ticker">{r["Ticker"]}</div>
                <div class="sd-price">{fmt_num(r["Price"], 2)}</div>
              </div>

              <div class="sd-chg">{change_str(r["Change"], r["ChangePct"])}</div>

              <div class="sd-kvs">
                <div class="sd-kv"><span class="sd-k">Prev</span><span class="sd-v">{fmt_num(r["PrevClose"], 2)}</span></div>
                <div class="sd-kv"><span class="sd-k">Vol</span><span class="sd-v">{fmt_int(r["Volume"])}</span></div>
                <div class="sd-kv"><span class="sd-k">Low</span><span class="sd-v">{fmt_num(r["DayLow"], 2)}</span></div>
                <div class="sd-kv"><span class="sd-k">High</span><span class="sd-v">{fmt_num(r["DayHigh"], 2)}</span></div>
              </div>

              <div class="sd-time">Updated: {now_str}</div>
            </div>
            """
        )

    parts.append("</div>")

    html = "\n".join(parts)
    # Big enough height to fit grid; allow scrolling inside this component if needed
    components.html(html, height=650, scrolling=True)


# -------------------------
# App
# -------------------------
st.set_page_config(page_title="stockDash", layout="wide")
st.title("📈 stockDash")

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

    view_mode = st.selectbox("View", ["Modules", "Table"], index=0)
    sort_mode = st.selectbox("Sort by", ["% Change", "Ticker", "Price"], index=0)

    refresh = st.slider("Auto-refresh (seconds)", 0, 120, 30, 5)
    cap = st.slider("Color intensity cap (% move)", 2.0, 20.0, 6.0, 0.5)
    density = st.selectbox("Card density", ["Comfortable", "Compact"], index=0)

    st.divider()
    st.subheader("Chart")
    default_sel = watchlist[0] if watchlist else "AAPL"
    sel = st.selectbox("Ticker", options=watchlist if watchlist else [default_sel], index=0)
    period = st.selectbox("Period", options=["1d", "5d", "1mo", "3mo", "6mo", "1y"], index=4)
    interval = st.selectbox("Interval", options=["1m", "5m", "15m", "30m", "1h", "1d"], index=1)

if refresh > 0:
    try:
        st.autorefresh(interval=refresh * 1000, key="refresh")
    except Exception:
        pass

tickers_tuple = tuple(watchlist)

left, right = st.columns([2, 1], gap="large")

with left:
    st.subheader("Quotes")

    if not tickers_tuple:
        st.info("Add tickers in the sidebar.")
    else:
        df = fetch_quotes(tickers_tuple)

        if sort_mode == "% Change":
            df = df.sort_values(by="ChangePct", ascending=False, na_position="last")
        elif sort_mode == "Ticker":
            df = df.sort_values(by="Ticker", ascending=True)
        elif sort_mode == "Price":
            df = df.sort_values(by="Price", ascending=False, na_position="last")

        if view_mode == "Table":
            tdf = df.rename(
                columns={
                    "ChangePct": "Change %",
                    "PrevClose": "Prev Close",
                    "DayLow": "Day Low",
                    "DayHigh": "Day High",
                }
            )

            def row_style(row):
                bg = bg_for_change_pct(row.get("Change %"), cap=cap)
                return [f"background-color: {bg}"] * len(row)

            fmt = {
                "Price": "{:,.2f}",
                "Change": "{:+,.2f}",
                "Change %": "{:+.2f}%",
                "Prev Close": "{:,.2f}",
                "Day Low": "{:,.2f}",
                "Day High": "{:,.2f}",
                "Volume": "{:,.0f}",
            }

            st.dataframe(
                tdf.style.apply(row_style, axis=1).format(fmt, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )
        else:
            render_cards_grid(df, cap=cap, density=density)

        st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (local)")

with right:
    st.subheader("Chart")

    if not tickers_tuple:
        st.info("Add tickers to see a chart.")
    else:
        hist = fetch_history(sel, period=period, interval=interval)

        if hist.empty:
            st.warning("No chart data returned. Try another period/interval.")
        else:
            time_col = hist.columns[0]
            close = extract_close_series(hist)

            if close is None or close.empty:
                st.warning("Chart data returned but Close series is missing/empty.")
            else:
                fig = plt.figure(figsize=(6.2, 4.0), dpi=140)
                ax = fig.add_subplot(111)
                ax.plot(hist[time_col], close)
                ax.set_title(f"{sel} Close", fontsize=11)
                ax.grid(True, alpha=0.25)
                fig.autofmt_xdate()

                st.pyplot(fig, use_container_width=True)
                st.caption(f"Points: {len(hist)} | Using: period={period}, interval={interval}")