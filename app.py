"""Gold Digger — see how an investment performs against a chosen yardstick.

Run: streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.yardsticks import YARDSTICKS, load_yahoo_series, load_yardstick


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

CATEGORY_LABELS = {
    "commodity": "Commodity",
    "real_world": "Real world",
    "index": "Index",
    "fun": "Fun",
}


class DisplayNumber(float):
    """A float that gets readable default formatting inside roast templates."""

    def __format__(self, spec: str) -> str:
        return super().__format__(spec or ",.2f")


def yardstick_option(key: str) -> str:
    entry = YARDSTICKS[key]
    return f"{CATEGORY_LABELS[entry['category']]} · {entry['display_name']}"


def compact_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude == 0:
        return "0"
    if magnitude < 0.01:
        return f"{value:,.6f}"
    if magnitude < 10:
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def unit_count(value: float, entry: dict) -> str:
    noun = entry["unit_singular"] if abs(value - 1) < 0.005 else entry["unit_plural"]
    return f"{compact_number(value)} {noun}"


def roast_line(entry: dict, ticker: str, yardstick_return: float,
               unit_change: float, years: float, roast_mode: bool) -> str:
    if not roast_mode:
        return (
            f"Measured in {entry['unit_singular']}, {ticker} returned "
            f"{yardstick_return:+.1%} over the period."
        )
    direction = "gain" if yardstick_return >= 0 else "loss"
    templates = entry["roasts"][direction]
    template = templates[sum(ord(char) for char in ticker) % len(templates)]
    return template.format(
        ticker=ticker,
        pct=f"{abs(yardstick_return):.1%}",
        units=DisplayNumber(abs(unit_change)),
        unit_noun=entry["unit_singular"],
        years=f"{years:.1f}",
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_asset(ticker: str, start: date, end: date) -> pd.Series:
    close = load_yahoo_series(ticker, start, end).copy()
    close.name = "asset_usd"
    if len(close) < 2:
        raise ValueError(f"Yahoo returned too little price history for {ticker}")
    return close


def comparison_frame(ticker: str, yardstick_key: str,
                     start: date, end: date) -> pd.DataFrame:
    asset = load_asset(ticker, start, end)
    yardstick = load_yardstick(yardstick_key, start, end)
    yardstick = yardstick.reindex(asset.index).ffill()
    frame = pd.concat(
        [asset, yardstick.rename("yardstick_usd")], axis=1, join="inner"
    ).dropna()
    frame["asset_in_yardstick"] = frame["asset_usd"] / frame["yardstick_usd"]
    return frame


def yardstick_returns(amount: float, start: date, end: date) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict] = []
    failures: list[str] = []
    for key, entry in YARDSTICKS.items():
        try:
            series = load_yardstick(key, start, end)
            if len(series) < 2:
                raise ValueError("fewer than two observations")
            yardstick_return = series.iloc[-1] / series.iloc[0] - 1
            rows.append({
                "Yardstick": entry["display_name"],
                "value": amount * (1 + yardstick_return),
                "return": yardstick_return,
            })
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{entry['display_name']}: {exc}")
    return pd.DataFrame(rows), failures


st.set_page_config(page_title="Gold Digger", page_icon="🪙", layout="wide")
st.title("🪙 Gold Digger")
st.caption("Your investment, priced in anything. Dollars lie; yardsticks tell stranger truths.")

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Pick an asset")
    choice = st.selectbox("Asset", list(PRESETS.keys()))
    ticker = PRESETS[choice]
    if ticker is None:
        ticker = st.text_input("Ticker symbol", value="VTI").strip().upper()

    st.header("Pick a yardstick")
    yardstick_keys = list(YARDSTICKS)
    yardstick_key = st.selectbox(
        "Yardstick", yardstick_keys, index=yardstick_keys.index("gold"),
        format_func=yardstick_option,
    )
    yardstick_entry = YARDSTICKS[yardstick_key]

    st.header("Time window")
    start = st.date_input("Start", value=date(2015, 1, 1), min_value=date(1990, 1, 1))
    end = st.date_input("End", value=date.today())

    view = st.radio(
        "Chart view",
        ["Rebased to 100", f"Raw ({yardstick_entry['unit_plural']} per share)"],
        help=(
            "Rebased puts USD and yardstick-priced lines on the same starting point "
            "so you can compare them."
        ),
    )
    roast_mode = st.toggle("Roast mode", value=True)


if not ticker:
    st.stop()
if start >= end:
    st.warning("Choose an end date after the start date.")
    st.stop()

try:
    with st.spinner("Pulling prices…"):
        df = comparison_frame(ticker, yardstick_key, start, end)
except Exception as exc:  # noqa: BLE001
    st.error(f"Couldn't load {ticker} and {yardstick_entry['display_name']}: {exc}")
    st.stop()

if len(df) < 2:
    st.warning(
        f"No overlapping price history for {ticker} and "
        f"{yardstick_entry['display_name']} in that window."
    )
    st.stop()

first, last = df.iloc[0], df.iloc[-1]
ret_usd = last["asset_usd"] / first["asset_usd"] - 1
ret_yardstick = last["asset_in_yardstick"] / first["asset_in_yardstick"] - 1
ret_yardstick_itself = last["yardstick_usd"] / first["yardstick_usd"] - 1
years = (df.index[-1] - df.index[0]).days / 365.25

chart_tab, what_if_tab = st.tabs(["Chart", "What if?"])

with chart_tab:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{ticker} in USD", f"{ret_usd:+.1%}")
    c2.metric(
        f"{ticker} in {yardstick_entry['display_name']}", f"{ret_yardstick:+.1%}",
        delta=f"{ret_yardstick - ret_usd:+.1%} vs USD view",
    )
    c3.metric(
        f"{yardstick_entry['display_name']} in USD", f"{ret_yardstick_itself:+.1%}"
    )
    current_units = last["asset_in_yardstick"]
    first_units = first["asset_in_yardstick"]
    c4.metric(
        f"{yardstick_entry['unit_plural'].capitalize()} per share now",
        compact_number(current_units),
        delta=(
            f"{current_units - first_units:+,.4f} "
            f"{yardstick_entry['unit_plural']}"
        ),
    )

    st.markdown(
        roast_line(
            yardstick_entry, ticker, ret_yardstick,
            current_units - first_units, years, roast_mode,
        )
    )

    fig = go.Figure()
    if view == "Rebased to 100":
        usd_line = df["asset_usd"] / first["asset_usd"] * 100
        yardstick_line = df["asset_in_yardstick"] / first["asset_in_yardstick"] * 100
        yardstick_itself = df["yardstick_usd"] / first["yardstick_usd"] * 100
        fig.add_trace(go.Scatter(
            x=df.index, y=usd_line, name=f"{ticker} in USD",
            line=dict(color="#4C8BF5", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=yardstick_line,
            name=f"{ticker} in {yardstick_entry['display_name']}",
            line=dict(color="#D4A017", width=3),
        ))
        fig.add_trace(go.Scatter(
            x=df.index, y=yardstick_itself,
            name=f"{yardstick_entry['display_name']} in USD",
            line=dict(color="#999", width=1, dash="dot"),
        ))
        fig.add_hline(y=100, line=dict(color="#666", width=1, dash="dash"))
        fig.update_yaxes(title="Rebased (start = 100)")
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["asset_in_yardstick"],
            name=f"{ticker} ({yardstick_entry['unit_plural']} per share)",
            line=dict(color="#D4A017", width=3), fill="tozeroy",
            fillcolor="rgba(212,160,23,0.12)",
        ))
        fig.update_yaxes(
            title=f"{yardstick_entry['unit_plural'].capitalize()} per share"
        )

    fig.update_layout(
        height=520, hovermode="x unified", template="plotly_dark",
        legend=dict(orientation="h", y=1.05), margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("Raw data"):
        st.dataframe(df.round(4), width="stretch")

    source_label = {
        "yahoo": "Yahoo Finance",
        "fred": "FRED",
        "static": "The Economist Big Mac Index (approximate, hand-maintained)",
    }[yardstick_entry["source"]]
    st.caption(
        f"{yardstick_entry['display_name']} source: {source_label} "
        f"({yardstick_entry['source_id']}). Asset prices are adjusted closes via Yahoo Finance."
    )

with what_if_tab:
    st.subheader("What if you had bought the yardstick instead?")
    amount = st.number_input(
        "Starting dollars", min_value=1.0, value=10_000.0, step=1_000.0,
        format="%.2f",
    )

    asset_units = amount / first["asset_usd"]
    asset_value = asset_units * last["asset_usd"]
    selected_units = amount / first["yardstick_usd"]
    selected_value = selected_units * last["yardstick_usd"]

    try:
        cpi = load_yardstick("cpi", start, end)
        inflation_factor = cpi.iloc[-1] / cpi.iloc[0]
        cash_real_value = amount / inflation_factor
        cash_caption = (
            f"{amount:,.0f} nominal dollars · "
            f"{cash_real_value:,.0f} start-date dollars of purchasing power"
        )
    except Exception as exc:  # noqa: BLE001
        cash_real_value = None
        cash_caption = f"CPI unavailable: {exc}"

    w1, w2, w3 = st.columns(3)
    w1.metric(
        f"${amount:,.0f} in {ticker}", f"${asset_value:,.0f}",
        delta=f"{asset_value / amount - 1:+.1%}",
    )
    w1.caption(f"You would hold {compact_number(asset_units)} shares.")
    w2.metric(
        f"${amount:,.0f} in {yardstick_entry['display_name']}",
        f"${selected_value:,.0f}", delta=f"{selected_value / amount - 1:+.1%}",
    )
    w2.caption(f"You would hold {unit_count(selected_units, yardstick_entry)}.")
    w3.metric(
        f"${amount:,.0f} in cash under the mattress (CPI-adjusted)",
        "Unavailable" if cash_real_value is None else f"${cash_real_value:,.0f}",
        delta=None if cash_real_value is None else f"{cash_real_value / amount - 1:+.1%}",
    )
    w3.caption(cash_caption)

    st.subheader("The full yardstick leaderboard")
    with st.spinner("Measuring everything against everything…"):
        leaderboard, failures = yardstick_returns(amount, start, end)

    if leaderboard.empty:
        st.warning("No yardsticks loaded for the leaderboard.")
    else:
        leaderboard[f"Beat {ticker}?"] = leaderboard["return"].map(
            lambda value: "✅" if value > ret_usd else "❌"
        )
        leaderboard = leaderboard.sort_values("return", ascending=False)
        value_column = f"${amount:,.0f} would be worth today"
        leaderboard = leaderboard.rename(columns={"value": value_column, "return": "Return"})
        leaderboard["Return"] = leaderboard["Return"] * 100
        st.dataframe(
            leaderboard[["Yardstick", value_column, "Return", f"Beat {ticker}?"]],
            hide_index=True,
            column_config={
                value_column: st.column_config.NumberColumn(format="$%,.0f"),
                "Return": st.column_config.NumberColumn(format="%.1f%%"),
            },
            width="stretch",
        )

    if failures:
        with st.expander(f"{len(failures)} yardstick(s) could not be loaded"):
            for failure in failures:
                st.caption(f"• {failure}")
