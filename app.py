"""
Gold Digger — how is your investment *really* doing?

Re-prices any ticker in ounces of gold instead of dollars, so you can see
whether the asset gained purchasing power or just rode the dollar's decline.

Run:  streamlit run app.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date

GOLD_TICKER = "GC=F"          # COMEX gold futures, USD per troy ounce
GOLD_FALLBACK = "GLD"         # ETF fallback if futures data is thin

PRESETS = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Nvidia (NVDA)": "NVDA",
    "Tesla (TSLA)": "TSLA",
    "Berkshire (BRK-B)": "BRK-B",
    "Bitcoin (BTC-USD)": "BTC-USD",
    "US Dollar Index (DX-Y.NYB)": "DX-Y.NYB",
    "Custom…": None,
}

st.set_page_config(page_title="Gold Digger", page_icon="🪙", layout="wide")
st.title("🪙 Gold Digger")
st.caption("Your investment, priced in gold. Dollars lie; ounces don't.")

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Pick an asset")
    choice = st.selectbox("Asset", list(PRESETS.keys()))
    ticker = PRESETS[choice]
    if ticker is None:
        ticker = st.text_input("Ticker symbol", value="VTI").strip().upper()

    st.header("Time window")
    start = st.date_input("Start", value=date(2015, 1, 1), min_value=date(1990, 1, 1))
    end = st.date_input("End", value=date.today())

    view = st.radio(
        "Chart view",
        ["Rebased to 100", "Raw (oz of gold per share)"],
        help="Rebased puts USD and gold-priced lines on the same starting point so you can compare them.",
    )


# ---------------------------------------------------------------- data
@st.cache_data(ttl=3600, show_spinner="Pulling prices…")
def load(ticker: str, start: date, end: date) -> pd.DataFrame:
    raw = yf.download([ticker, GOLD_TICKER], start=start, end=end,
                      progress=False, auto_adjust=True)["Close"]
    if raw.empty or GOLD_TICKER not in raw or raw[GOLD_TICKER].dropna().empty:
        raw = yf.download([ticker, GOLD_FALLBACK], start=start, end=end,
                          progress=False, auto_adjust=True)["Close"]
        raw = raw.rename(columns={GOLD_FALLBACK: GOLD_TICKER})
    df = raw.dropna().rename(columns={ticker: "asset_usd", GOLD_TICKER: "gold_usd"})
    df["asset_in_gold"] = df["asset_usd"] / df["gold_usd"]   # ounces per share
    return df


if not ticker:
    st.stop()

try:
    df = load(ticker, start, end)
except Exception as e:  # noqa: BLE001
    st.error(f"Couldn't load data for {ticker}: {e}")
    st.stop()

if df.empty or len(df) < 2:
    st.warning(f"No overlapping price history for {ticker} and gold in that window.")
    st.stop()

# ---------------------------------------------------------------- metrics
first, last = df.iloc[0], df.iloc[-1]
ret_usd = last["asset_usd"] / first["asset_usd"] - 1
ret_gold = last["asset_in_gold"] / first["asset_in_gold"] - 1
ret_gold_itself = last["gold_usd"] / first["gold_usd"] - 1

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{ticker} in USD", f"{ret_usd:+.1%}")
c2.metric(f"{ticker} in gold", f"{ret_gold:+.1%}",
          delta=f"{ret_gold - ret_usd:+.1%} vs USD view")
c3.metric("Gold in USD", f"{ret_gold_itself:+.1%}")
c4.metric("Ounces per share now", f"{last['asset_in_gold']:.4f}",
          delta=f"{last['asset_in_gold'] - first['asset_in_gold']:+.4f} oz")

verdict = "gained" if ret_gold > 0 else "lost"
st.markdown(
    f"From **{df.index[0]:%b %d, %Y}** to **{df.index[-1]:%b %d, %Y}**, "
    f"**{ticker}** {'rose' if ret_usd >= 0 else 'fell'} **{abs(ret_usd):.1%}** in dollars — "
    f"but measured in gold it **{verdict} {abs(ret_gold):.1%}** of its purchasing power."
)

# ---------------------------------------------------------------- chart
fig = go.Figure()
if view == "Rebased to 100":
    usd_line = df["asset_usd"] / first["asset_usd"] * 100
    gold_line = df["asset_in_gold"] / first["asset_in_gold"] * 100
    gold_itself = df["gold_usd"] / first["gold_usd"] * 100
    fig.add_trace(go.Scatter(x=df.index, y=usd_line, name=f"{ticker} in USD",
                             line=dict(color="#4C8BF5", width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=gold_line, name=f"{ticker} in gold",
                             line=dict(color="#D4A017", width=3)))
    fig.add_trace(go.Scatter(x=df.index, y=gold_itself, name="Gold in USD",
                             line=dict(color="#999", width=1, dash="dot")))
    fig.add_hline(y=100, line=dict(color="#666", width=1, dash="dash"))
    fig.update_yaxes(title="Rebased (start = 100)")
else:
    fig.add_trace(go.Scatter(x=df.index, y=df["asset_in_gold"],
                             name=f"{ticker} (oz of gold per share)",
                             line=dict(color="#D4A017", width=3), fill="tozeroy",
                             fillcolor="rgba(212,160,23,0.12)"))
    fig.update_yaxes(title="Troy ounces of gold per share")

fig.update_layout(height=520, hovermode="x unified", template="plotly_dark",
                  legend=dict(orientation="h", y=1.05), margin=dict(t=40, b=20))
st.plotly_chart(fig, use_container_width=True)

with st.expander("Raw data"):
    st.dataframe(df.round(4), use_container_width=True)

st.caption("Gold = COMEX front-month futures (GC=F), falling back to GLD. Prices are adjusted closes via Yahoo Finance.")
