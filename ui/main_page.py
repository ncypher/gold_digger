"""Main Gold Digger page: charts, What-if comparisons, and The Pile."""

from __future__ import annotations

from datetime import date
from html import escape
import math

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
    return f"{CATEGORY_LABELS[entry['category']]} · {entry['emoji']} {entry['display_name']}"


def pile_option(key: str) -> str:
    entry = YARDSTICKS[key]
    return f"{entry['emoji']} {entry['display_name']}"


def compact_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude == 0:
        return "0"
    if magnitude < 0.01:
        return f"{value:,.6f}"
    if magnitude < 10:
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def pile_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def unit_count(value: float, entry: dict) -> str:
    noun = entry["unit_singular"] if abs(value - 1) < 0.005 else entry["unit_plural"]
    return f"{compact_number(value)} {noun}"


def roast_line(entry: dict, ticker: str, yardstick_return: float,
               current_units: float, unit_delta: float,
               years: float, roast_mode: bool) -> str:
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
        units=DisplayNumber(current_units),
        delta=DisplayNumber(abs(unit_delta)),
        unit_noun=entry["unit_singular"],
        years=f"{years:.1f}",
    )


def pile_roast_line(a_entry: dict, b_entry: dict, quantity: float,
                    result: float, year: int, roast_mode: bool) -> str:
    quantity_text = pile_number(quantity)
    result_text = pile_number(result)
    a_unit = a_entry["unit_singular"] if abs(quantity - 1) < 0.005 else a_entry["unit_plural"]
    if not roast_mode:
        return (
            f"In {year}, {quantity_text} {a_unit} bought "
            f"{result_text} {b_entry['unit_plural']}."
        )
    templates = b_entry["pile_roasts"]
    template = templates[year % len(templates)]
    return template.format(
        qty=quantity_text,
        a_unit=a_unit,
        n=result_text,
        b_unit=b_entry["unit_plural"],
        year=year,
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


@st.cache_data(ttl=3600, show_spinner=False)
def pile_ratio_frame(a_key: str, b_key: str, end: date) -> pd.DataFrame:
    start = date(2010, 1, 1)
    a_prices = load_yardstick(a_key, start, end)
    if a_key == b_key:
        b_prices = a_prices.copy()
    else:
        b_prices = load_yardstick(b_key, start, end)
    frame = pd.concat(
        [a_prices.rename("a_usd"), b_prices.rename("b_usd")],
        axis=1, join="inner",
    ).dropna()
    frame["ratio"] = frame["a_usd"] / frame["b_usd"]
    return frame


def clean_glyph_scale(result: float) -> int:
    """Choose a 1/2/5 × power-of-ten scale that keeps the pile at 400 glyphs."""
    if result <= 400:
        return 1
    minimum = math.ceil(result / 400)
    exponent = 10 ** math.floor(math.log10(minimum))
    for multiplier in (1, 2, 5, 10):
        candidate = multiplier * exponent
        if candidate >= minimum:
            return int(candidate)
    return int(10 * exponent)


def render_pictograph(quantity: float, a_entry: dict, result: float,
                       b_entry: dict, year: int) -> tuple[int, int]:
    scale = clean_glyph_scale(result)
    glyph_count = 0 if result <= 0 else min(400, max(1, math.ceil(result / scale)))
    glyphs = "".join(
        f'<span class="glyph" style="--i:{index}">{escape(b_entry["emoji"])}</span>'
        for index in range(glyph_count)
    )
    quantity_text = pile_number(quantity)
    a_unit = a_entry["unit_singular"] if abs(quantity - 1) < 0.005 else a_entry["unit_plural"]
    result_digits = 0 if result >= 100 else (1 if result >= 10 else 2)
    rows = max(1, math.ceil(glyph_count / 20))
    component_height = min(760, 130 + rows * 34)
    html = f"""
    <style>
      :root {{ color-scheme: dark; }}
      body {{ margin: 0; color: #f5f5f5; font-family: Inter, system-ui, sans-serif; }}
      .headline {{ font-size: 1.45rem; line-height: 1.45; margin: 0 0 16px; }}
      .headline strong {{ color: #D4A017; }}
      .grid {{ display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }}
      .glyph {{ font-size: 1.55rem; line-height: 1; opacity: 0; transform: translateY(5px);
                animation: appear 280ms ease-out forwards;
                animation-delay: calc(var(--i) * 3.5ms); }}
      @keyframes appear {{ to {{ opacity: 1; transform: translateY(0); }} }}
      @media (prefers-reduced-motion: reduce) {{
        .glyph {{ opacity: 1; transform: none; animation: none; }}
      }}
    </style>
    <div class="headline">{escape(quantity_text)} {escape(a_unit)} in {year} buys
      <strong><span id="pile-count">0</span> {escape(b_entry["unit_plural"])}</strong>
    </div>
    <div class="grid">{glyphs}</div>
    <script>
      (() => {{
        const target = {result!r};
        const digits = {result_digits};
        const output = document.getElementById('pile-count');
        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const format = value => value.toLocaleString(undefined, {{
          minimumFractionDigits: 0,
          maximumFractionDigits: digits
        }});
        if (reduced) {{ output.textContent = format(target); return; }}
        const started = performance.now();
        const tick = now => {{
          const progress = Math.min(1, (now - started) / 1000);
          const eased = 1 - Math.pow(1 - progress, 3);
          output.textContent = format(target * eased);
          if (progress < 1) requestAnimationFrame(tick);
        }};
        requestAnimationFrame(tick);
      }})();
    </script>
    """
    st.components.v1.html(html, height=component_height, scrolling=False)
    return scale, glyph_count


def render_pile(roast_mode: bool) -> None:
    st.subheader("The Pile")
    st.caption("Turn one yardstick into another, then watch the purchasing-power pile appear.")
    keys = list(YARDSTICKS)
    left, right = st.columns(2)
    with left:
        a_key = st.selectbox(
            "I have…", keys, index=keys.index("gold"),
            format_func=pile_option, key="pile_a",
        )
    with right:
        b_key = st.selectbox(
            "…which buys", keys, index=keys.index("big_mac"),
            format_func=pile_option, key="pile_b",
        )
    a_entry = YARDSTICKS[a_key]
    b_entry = YARDSTICKS[b_key]
    quantity = st.number_input(
        f"How many {a_entry['unit_plural']}?", min_value=0.01,
        value=1.0, step=1.0, key="pile_quantity",
    )

    today = date.today()
    with st.spinner("Stacking the pile…"):
        try:
            ratio_frame = pile_ratio_frame(a_key, b_key, today)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't build this pile: {exc}")
            return
    if ratio_frame.empty:
        st.warning("No overlapping price history exists for those yardsticks.")
        return

    business_ratio = ratio_frame.loc[ratio_frame.index.dayofweek < 5, "ratio"]
    available_years = sorted(
        year for year in business_ratio.index.year.unique()
        if 2010 <= int(year) <= today.year
    )
    if not available_years:
        st.warning("No business-day observations are available for this pair.")
        return

    requested_year = int(st.session_state.get("pile_year", today.year))
    nearest_year = min(available_years, key=lambda value: (abs(value - requested_year), value))
    nudged_from = None
    if requested_year not in available_years:
        nudged_from = requested_year
        st.session_state["pile_year"] = int(nearest_year)
    selected_year = st.slider(
        "Year", min_value=2010, max_value=today.year,
        value=int(nearest_year), step=1, key="pile_year",
    )
    if selected_year not in available_years:
        nearest_year = min(available_years, key=lambda value: (abs(value - selected_year), value))
        nudged_from = selected_year
        selected_year = int(nearest_year)
    if nudged_from is not None:
        st.info(
            f"No overlapping ratio was available in {nudged_from}; "
            f"using the nearest available year, {selected_year}."
        )

    if selected_year == today.year:
        target = pd.Timestamp(today)
        eligible = ratio_frame.loc[ratio_frame.index <= target, "ratio"]
    else:
        target = pd.Timestamp(date(selected_year, 12, 31))
        eligible = business_ratio.loc[
            (business_ratio.index.year == selected_year) & (business_ratio.index <= target)
        ]
    if eligible.empty:
        st.warning(f"No ratio is available for {selected_year}.")
        return
    selected_date = eligible.index[-1]
    result = float(quantity * eligible.iloc[-1])

    scale, _ = render_pictograph(quantity, a_entry, result, b_entry, selected_year)
    if scale > 1:
        st.caption(f"each {b_entry['emoji']} = {scale:,} {b_entry['unit_plural']}")
    if a_key == b_key:
        st.info("1:1, congratulations.")

    st.markdown(pile_roast_line(
        a_entry, b_entry, quantity, result, selected_year, roast_mode,
    ))

    pile_fig = go.Figure()
    pile_fig.add_trace(go.Scatter(
        x=ratio_frame.index, y=ratio_frame["ratio"],
        name=f"{a_entry['display_name']} / {b_entry['display_name']}",
        line=dict(color="#D4A017", width=2),
    ))
    pile_fig.add_trace(go.Scatter(
        x=[selected_date], y=[eligible.iloc[-1]], name=str(selected_year),
        mode="markers", marker=dict(color="#FFFFFF", size=9),
    ))
    pile_fig.add_vline(
        x=selected_date, line=dict(color="#888", width=1, dash="dash"),
    )
    pile_fig.update_layout(
        height=360, hovermode="x unified", template="plotly_dark",
        legend=dict(orientation="h", y=1.08), margin=dict(t=45, b=20),
        yaxis_title=f"{b_entry['unit_plural']} per {a_entry['unit_singular']}",
    )
    st.plotly_chart(pile_fig, width="stretch")
    st.caption(f"Selected observation: {selected_date:%b %d, %Y}.")


def render(methodology_page: st.Page) -> None:
    """Render the main Gold Digger page."""
    st.title("🪙 Gold Digger")
    st.caption("Your investment, priced in anything. Dollars lie; yardsticks tell stranger truths.")

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

    chart_tab, what_if_tab, pile_tab = st.tabs(["Chart", "What if?", "The Pile"])

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

        st.markdown(roast_line(
            yardstick_entry, ticker, ret_yardstick,
            current_units, current_units - first_units, years, roast_mode,
        ))

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

    with pile_tab:
        render_pile(roast_mode)

    st.divider()
    st.page_link(
        methodology_page,
        label="How are these numbers derived? →",
        icon=":material/menu_book:",
    )
