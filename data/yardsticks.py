"""Yardstick registry and price loaders.

Every series returned by :func:`load_yardstick` is a daily USD price for one
physical (or conceptual) unit of the selected yardstick. Lower-frequency data
is carried forward between observations.
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st


def _roasts(gain_one: str, gain_two: str, loss_one: str, loss_two: str) -> dict[str, list[str]]:
    return {"gain": [gain_one, gain_two], "loss": [loss_one, loss_two]}


YARDSTICKS: dict[str, dict] = {
    "gold": {
        "key": "gold", "display_name": "Gold", "unit_singular": "troy ounce",
        "unit_plural": "troy ounces", "source": "yahoo", "source_id": "GC=F",
        "category": "commodity", "emoji": "🪙", "native_frequency": "Daily",
        "notes": "COMEX front-month futures; GLD fallback is an approximate ounce proxy.",
        "fallback_source_id": "GLD", "fallback_quote_scale": 10.0,
        "pile_roasts": [
            "That pile becomes {n} {b_unit} in {year}. Fort Knox remains calm.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in gold terms. The alchemists remain unemployed.",
            "Your {ticker} position now buys {units} troy ounces. Fort Knox has not called.",
            "{ticker} lost {pct} measured in gold. The shiny rock kept the receipt.",
            "Your shares buy {units} troy ounces after {years} years. Heavy is the portfolio that wears the crown.",
        ),
    },
    "silver": {
        "key": "silver", "display_name": "Silver", "unit_singular": "troy ounce",
        "unit_plural": "troy ounces", "source": "yahoo", "source_id": "SI=F",
        "category": "commodity", "emoji": "🥈", "native_frequency": "Daily",
        "notes": "COMEX silver futures, quoted in USD per troy ounce.",
        "pile_roasts": [
            "{qty} {a_unit} buys {n} {b_unit}. Silver takes second place gracefully.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in silver. Second place has excellent liquidity.",
            "You can claim {units} troy ounces of silver. The werewolves have been notified.",
            "{ticker} lost {pct} in silver terms. Even the understudy stole the scene.",
            "After {years} years, your shares buy {units} troy ounces. The silver lining is itemized separately.",
        ),
    },
    "crude_oil": {
        "key": "crude_oil", "display_name": "Crude oil", "unit_singular": "barrel",
        "unit_plural": "barrels", "source": "yahoo", "source_id": "CL=F",
        "category": "commodity", "emoji": "🛢️", "native_frequency": "Daily",
        "notes": "WTI crude-oil futures, quoted in USD per barrel.",
        "pile_roasts": [
            "In {year}, that is {n} {b_unit}. Storage and emissions are separate problems.",
        ],
        "roasts": _roasts(
            "{ticker} is up {pct} in oil terms. Your portfolio is running smoothly, emissions pending.",
            "Your shares buy {units} barrels of crude. Storage is very much your problem.",
            "{ticker} lost {pct} measured in oil. The portfolio needs a tune-up.",
            "After {years} years you have {units} barrels' worth. The dipstick has opinions.",
        ),
    },
    "copper": {
        "key": "copper", "display_name": "Copper", "unit_singular": "pound",
        "unit_plural": "pounds", "source": "yahoo", "source_id": "HG=F",
        "category": "commodity", "emoji": "🟠", "native_frequency": "Daily",
        "notes": "COMEX copper futures, quoted in USD per pound.",
        "pile_roasts": [
            "The {year} exchange yields {n} {b_unit}. Please leave the wiring installed.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in copper. Electrifying, by spreadsheet standards.",
            "Your position buys {units} pounds of copper. Please leave the wiring in the walls.",
            "{ticker} lost {pct} in copper terms. The pennies are judging.",
            "You have {units} pounds after {years} years. Conductivity was not the issue.",
        ),
    },
    "wheat": {
        "key": "wheat", "display_name": "Wheat", "unit_singular": "bushel",
        "unit_plural": "bushels", "source": "yahoo", "source_id": "ZW=F",
        "category": "commodity", "emoji": "🌾", "native_frequency": "Daily",
        "notes": "CBOT wheat futures; cents-per-bushel quotes are converted to USD.",
        "quote_scale": 0.01,
        "pile_roasts": [
            "{qty} {a_unit} becomes {n} {b_unit} in {year}. The chaff was removed.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in wheat. The portfolio has risen, no yeast required.",
            "Your shares buy {units} bushels. This is how diversification becomes sourdough.",
            "{ticker} lost {pct} in wheat terms. The market separated the chaff efficiently.",
            "After {years} years you can buy {units} bushels. The bread line is metaphorical.",
        ),
    },
    "corn": {
        "key": "corn", "display_name": "Corn", "unit_singular": "bushel",
        "unit_plural": "bushels", "source": "yahoo", "source_id": "ZC=F",
        "category": "commodity", "emoji": "🌽", "native_frequency": "Daily",
        "notes": "CBOT corn futures; cents-per-bushel quotes are converted to USD.",
        "quote_scale": 0.01,
        "pile_roasts": [
            "That buys {n} {b_unit} in {year}. A-maize-ing remains a compliance violation.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in corn. A-maize-ing was rejected by compliance.",
            "Your position buys {units} bushels of corn. The cob allocation is fully funded.",
            "{ticker} lost {pct} in corn terms. The kernels had the better quarter.",
            "After {years} years, {units} bushels remain within reach. Pop accordingly.",
        ),
    },
    "coffee": {
        "key": "coffee", "display_name": "Coffee", "unit_singular": "pound",
        "unit_plural": "pounds", "source": "yahoo", "source_id": "KC=F",
        "category": "commodity", "emoji": "☕", "native_frequency": "Daily",
        "notes": "Coffee futures; cents-per-pound quotes are converted to USD.",
        "quote_scale": 0.01,
        "pile_roasts": [
            "The pile converts to {n} {b_unit}. Sleep was not included in the model.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in coffee. The returns are fully caffeinated.",
            "Your shares buy {units} pounds of coffee. Sleep is now an opportunity cost.",
            "{ticker} lost {pct} in coffee terms. The market chose the darker roast.",
            "After {years} years you can buy {units} pounds. Grounds for an appeal were denied.",
        ),
    },
    "live_cattle": {
        "key": "live_cattle", "display_name": "Live cattle", "unit_singular": "pound",
        "unit_plural": "pounds", "source": "yahoo", "source_id": "LE=F",
        "category": "commodity", "emoji": "🐄", "native_frequency": "Daily",
        "notes": "Live-cattle futures; cents-per-pound quotes are converted to USD.",
        "quote_scale": 0.01,
        "pile_roasts": [
            "In {year}, {qty} {a_unit} buys {n} {b_unit}. Delivery is discouraged.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in cattle terms. The herd approves this allocation.",
            "Your shares buy {units} pounds of live cattle. Delivery is discouraged.",
            "{ticker} lost {pct} to cattle. The cows displayed stronger fundamentals.",
            "After {years} years, {units} pounds are yours in theory. The theory moos.",
        ),
    },
    "bitcoin": {
        "key": "bitcoin", "display_name": "Bitcoin", "unit_singular": "bitcoin",
        "unit_plural": "bitcoin", "source": "yahoo", "source_id": "BTC-USD",
        "category": "index", "emoji": "₿", "native_frequency": "Daily",
        "notes": "Yahoo Finance BTC-USD adjusted close; trades seven days a week.",
        "pile_roasts": [
            "The conversion produces {n} {b_unit}. The decimal places are doing the work.",
        ],
        "roasts": _roasts(
            "Measured in Bitcoin, {ticker} did {pct}. Everything does {pct} measured in Bitcoin.",
            "Your shares buy {units} bitcoin. The decimal places are doing most of the work.",
            "Measured in Bitcoin, {ticker} lost {pct}. The laser eyes remain untroubled.",
            "After {years} years, {ticker} buys {units} bitcoin. Please zoom in responsibly.",
        ),
    },
    "sp500": {
        "key": "sp500", "display_name": "S&P 500", "unit_singular": "index unit",
        "unit_plural": "index units", "source": "yahoo", "source_id": "^GSPC",
        "category": "index", "emoji": "📈", "native_frequency": "Daily",
        "notes": "S&P 500 index level from Yahoo Finance.",
        "pile_roasts": [
            "{qty} {a_unit} bought {n} {b_unit} in {year}. The benchmark accepts your tribute.",
        ],
        "roasts": _roasts(
            "You beat the index by {pct}. Congratulations, you are a hedge fund.",
            "{ticker} gained {pct} against the S&P 500. The benchmark has requested a recount.",
            "The index beat you by {pct}. Congratulations, you are a hedge fund.",
            "{ticker} lost {pct} to the S&P 500. Passive investing has entered the chat.",
        ),
    },
    "eggs": {
        "key": "eggs", "display_name": "Dozen eggs", "unit_singular": "dozen eggs",
        "unit_plural": "dozen eggs", "source": "fred", "source_id": "APU0000708111",
        "category": "real_world", "emoji": "🥚", "native_frequency": "Monthly",
        "notes": "US city-average retail price per dozen from FRED.",
        "pile_roasts": [
            "That is {n} {b_unit} in {year}. The chickens have reviewed the arithmetic.",
        ],
        "roasts": _roasts(
            "Your {ticker} shares buy {delta} more dozen eggs than {years} years ago. The chickens acknowledge defeat.",
            "{ticker} gained {pct} in egg terms. Your nest egg is now more literal.",
            "Your {ticker} shares buy {delta} fewer dozen eggs than {years} years ago. The chickens won.",
            "{ticker} lost {pct} to eggs. The portfolio was briefly over-easy.",
        ),
    },
    "bacon": {
        "key": "bacon", "display_name": "Pound of bacon", "unit_singular": "pound of bacon",
        "unit_plural": "pounds of bacon", "source": "fred", "source_id": "APU0000704111",
        "category": "real_world", "emoji": "🥓", "native_frequency": "Monthly",
        "notes": "US city-average retail price per pound from FRED.",
        "pile_roasts": [
            "The pile buys {n} {b_unit}. Please consult a cardiologist before taking delivery.",
        ],
        "roasts": _roasts(
            "{ticker} is up {pct} in bacon terms. That's {units} lbs of bacon. Please consult a cardiologist.",
            "Your shares buy {units} pounds of bacon. The balanced portfolio is served with toast.",
            "{ticker} lost {pct} in bacon terms. Breakfast outperformed again.",
            "After {years} years you can buy {units} pounds of bacon. The sizzle exceeded the return.",
        ),
    },
    "gas": {
        "key": "gas", "display_name": "Regular gasoline", "unit_singular": "gallon",
        "unit_plural": "gallons", "source": "fred", "source_id": "GASREGW",
        "category": "real_world", "emoji": "⛽", "native_frequency": "Weekly",
        "notes": "US regular gasoline price per gallon from FRED.",
        "pile_roasts": [
            "In {year}, that buys {n} {b_unit}. Road-trip governance is out of scope.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in gasoline. The portfolio has mileage left.",
            "Your shares buy {units} gallons. Road-trip governance is outside scope.",
            "{ticker} lost {pct} at the pump. The low-fuel light is now a KPI.",
            "After {years} years, {units} gallons remain. The market took the scenic route.",
        ),
    },
    "ground_beef": {
        "key": "ground_beef", "display_name": "Pound of ground beef", "unit_singular": "pound of ground beef",
        "unit_plural": "pounds of ground beef", "source": "fred", "source_id": "APU0000703112",
        "category": "real_world", "emoji": "🥩", "native_frequency": "Monthly",
        "notes": "US city-average retail price per pound from FRED.",
        "pile_roasts": [
            "{qty} {a_unit} becomes {n} {b_unit}. Buns remain a separate asset class.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in ground-beef terms. The returns are well done.",
            "Your position buys {units} pounds of ground beef. Buns remain a separate asset class.",
            "{ticker} lost {pct} to ground beef. The market had a beef with your thesis.",
            "After {years} years, you can buy {units} pounds. The result is medium rare at best.",
        ),
    },
    "median_home": {
        "key": "median_home", "display_name": "Median US home", "unit_singular": "median home",
        "unit_plural": "median homes", "source": "fred", "source_id": "MSPUS",
        "category": "real_world", "emoji": "🏠", "native_frequency": "Quarterly",
        "notes": "Median US home sale price from FRED; one unit is a full median home.",
        "pile_roasts": [
            "That is {n} {b_unit} in {year}. Fractional bathrooms remain theoretical.",
        ],
        "roasts": _roasts(
            "You could have bought {units} median American homes. Or {units:.2f}, which is a bathroom.",
            "{ticker} gained {pct} in housing terms. The down payment has a down payment.",
            "{ticker} lost {pct} measured in median homes. The bathroom is now shared.",
            "Your shares buy {units} median homes after {years} years. Location remains everything.",
        ),
    },
    "cpi": {
        "key": "cpi", "display_name": "US CPI", "unit_singular": "dollar of purchasing power as of the start date",
        "unit_plural": "dollars of purchasing power as of the start date", "source": "fred", "source_id": "CPIAUCSL",
        "category": "index", "emoji": "💵", "native_frequency": "Monthly",
        "notes": "CPI is rebased so one unit is a dollar of start-date purchasing power.",
        "pile_roasts": [
            "The boring answer is {n} {b_unit}. Inflation filed the paperwork.",
        ],
        "roasts": _roasts(
            "The boring truth: after inflation, {ticker} returned {pct}.",
            "{ticker} gained {pct} in real terms. The spreadsheet permits one quiet nod.",
            "The boring truth: after inflation, {ticker} lost {pct}.",
            "{ticker} trailed purchasing power by {pct}. Inflation sent a thank-you note.",
        ),
    },
    "big_mac": {
        "key": "big_mac", "display_name": "Big Mac", "unit_singular": "Big Mac",
        "unit_plural": "Big Macs", "source": "static", "source_id": "economist-big-mac-us",
        "category": "fun", "emoji": "🍔", "native_frequency": "~Semiannual",
        "notes": "Approximate US Big Mac price, hand-maintained from The Economist index.",
        "pile_roasts": [
            "{qty} {a_unit} becomes {n} {b_unit} in {year}. Fries remain outside the model.",
        ],
        "roasts": _roasts(
            "{ticker} gained {pct} in Big Macs. The special sauce compounds annually.",
            "Your shares buy {units} Big Macs. Fries were not included in the model.",
            "{ticker} lost {pct} in Big Mac terms. The two all-beef patties prevailed.",
            "After {years} years you can buy {units} Big Macs. The arches remain golden.",
        ),
    },
}


# Approximate US-dollar observations from The Economist's Big Mac Index.
# The series is intentionally small and hand-maintained; values between releases
# are forward-filled. These are approximate reference values, not audit data.
BIG_MAC_USD = {
    "2010-01-01": 3.58, "2010-07-01": 3.73,
    "2011-01-01": 4.07, "2011-07-01": 4.07,
    "2012-01-01": 4.20, "2012-07-01": 4.33,
    "2013-01-01": 4.37, "2013-07-01": 4.56,
    "2014-01-01": 4.62, "2014-07-01": 4.80,
    "2015-01-01": 4.79, "2015-07-01": 4.79,
    "2016-01-01": 4.93, "2016-07-01": 5.04,
    "2017-01-01": 5.06, "2017-07-01": 5.30,
    "2018-01-01": 5.28, "2018-07-01": 5.51,
    "2019-01-01": 5.58, "2019-07-01": 5.74,
    "2020-01-01": 5.67, "2020-07-01": 5.71,
    "2021-01-01": 5.66, "2021-07-01": 5.65,
    "2022-01-01": 5.81, "2022-07-01": 5.15,
    "2023-01-01": 5.36, "2023-07-01": 5.58,
    "2024-01-01": 5.69, "2024-07-01": 5.69,
    "2025-01-01": 5.79, "2025-07-01": 5.79,
    "2026-01-01": 5.79,
}


def _daily(series: pd.Series, start: date, end: date) -> pd.Series:
    series = series.copy()
    series.index = pd.to_datetime(series.index).tz_localize(None)
    series = series[~series.index.duplicated(keep="last")].sort_index()
    daily_index = pd.date_range(start=pd.Timestamp(start), end=pd.Timestamp(end), freq="D")
    expanded = series.reindex(series.index.union(daily_index)).sort_index().ffill()
    return expanded.reindex(daily_index).dropna().astype(float)


@st.cache_data(ttl=3600, show_spinner=False)
def load_yahoo_series(symbol: str, start: date, end: date) -> pd.Series:
    """Load adjusted closes from Yahoo's public chart endpoint."""
    fetch_start = start - timedelta(days=10)
    period1 = int(pd.Timestamp(fetch_start, tz="UTC").timestamp())
    period2 = int(pd.Timestamp(end + timedelta(days=1), tz="UTC").timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
    response = requests.get(
        url,
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,splits",
        },
        headers={"User-Agent": "Mozilla/5.0 (compatible; Gold-Digger/1.0)"},
        timeout=30,
    )
    response.raise_for_status()
    chart = response.json().get("chart", {})
    if chart.get("error"):
        description = chart["error"].get("description", "unknown Yahoo error")
        raise ValueError(f"Yahoo error for {symbol}: {description}")
    results = chart.get("result") or []
    if not results:
        raise ValueError(f"Yahoo returned no prices for {symbol}")
    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    adjusted = indicators.get("adjclose") or []
    values = adjusted[0].get("adjclose", []) if adjusted else []
    if not values:
        quotes = indicators.get("quote") or []
        values = quotes[0].get("close", []) if quotes else []
    if not timestamps or not values:
        raise ValueError(f"Yahoo returned no closing prices for {symbol}")
    index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize()
    series = pd.Series(values, index=index, name=symbol, dtype=float).dropna()
    series = series.loc[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]
    if series.empty:
        raise ValueError(f"Yahoo returned no prices for {symbol} in the selected window")
    return series


def _load_yahoo(entry: dict, start: date, end: date) -> pd.Series:
    try:
        return load_yahoo_series(entry["source_id"], start, end) * entry.get("quote_scale", 1.0)
    except (requests.RequestException, ValueError):
        fallback = entry.get("fallback_source_id")
        if not fallback:
            raise
        return load_yahoo_series(fallback, start, end) * entry.get("fallback_quote_scale", 1.0)


def _load_fred(entry: dict, start: date, end: date) -> pd.Series:
    fetch_start = start - timedelta(days=400)
    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={entry['source_id']}&cosd={fetch_start:%Y-%m-%d}&coed={end:%Y-%m-%d}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    if frame.shape[1] < 2:
        raise ValueError(f"FRED returned no observations for {entry['source_id']}")
    values = pd.to_numeric(frame.iloc[:, 1], errors="coerce")
    series = pd.Series(values.to_numpy(), index=pd.to_datetime(frame.iloc[:, 0])).dropna()
    if series.empty:
        raise ValueError(f"FRED returned no numeric observations for {entry['source_id']}")
    return series


@st.cache_data(ttl=3600, show_spinner=False)
def load_yardstick(key: str, start: date, end: date) -> pd.Series:
    """Return the daily USD price of one yardstick unit for an inclusive window."""
    if key not in YARDSTICKS:
        raise KeyError(f"Unknown yardstick: {key}")
    if start > end:
        raise ValueError("Start date must be on or before end date")

    entry = YARDSTICKS[key]
    if entry["source"] == "yahoo":
        source = _load_yahoo(entry, start, end)
    elif entry["source"] == "fred":
        source = _load_fred(entry, start, end)
    elif entry["source"] == "static":
        source = pd.Series(BIG_MAC_USD, dtype=float)
        source.index = pd.to_datetime(source.index)
    else:
        raise ValueError(f"Unsupported yardstick source: {entry['source']}")

    daily = _daily(source, start, end)
    if daily.empty:
        raise ValueError(f"No {entry['display_name']} data overlaps the selected window")

    if key == "cpi":
        daily = daily / daily.iloc[0]
    daily.name = key
    return daily


def methodology_frame() -> pd.DataFrame:
    """Build the source-methodology table directly from the registry."""
    category_names = {
        "commodity": "Commodity",
        "real_world": "Real world",
        "index": "Index",
        "fun": "Fun",
    }
    rows = []
    for entry in YARDSTICKS.values():
        source_name = {
            "yahoo": "Yahoo Finance",
            "fred": "FRED",
            "static": "The Economist Big Mac Index",
        }[entry["source"]]
        rows.append({
            "Yardstick": f"{entry['emoji']} {entry['display_name']}",
            "Category": category_names[entry["category"]],
            "Unit": entry["unit_singular"],
            "Source": source_name,
            "Series/ticker": entry["source_id"],
            "Native frequency": entry["native_frequency"],
            "Notes": entry["notes"],
        })
    return pd.DataFrame(rows)
