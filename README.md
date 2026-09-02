# 🪙 Gold Digger

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gold-digger.streamlit.app/)

Try it: <https://gold-digger.streamlit.app/>

**See what your investments are really doing.**

![Gold Digger](docs/screenshot.png)

Dollars are a rubber ruler. Gold Digger re-prices any stock, ETF, index, or crypto in
troy ounces of gold, so you can see whether an asset actually gained purchasing power
or just rode the currency's decline.

> Since 2015, Apple is up ~1,245% in dollars — but only ~266% in gold.
> Three-quarters of that "gain" was the measuring stick shrinking.

## Features

- Pick a preset asset (SPY, QQQ, AAPL, NVDA, BTC-USD, …) or type any Yahoo Finance ticker
- Set any date window
- **Rebased view** — the asset in USD, the asset in gold, and gold itself, all starting at 100
- **Raw view** — ounces of gold one share buys, over time
- Headline metrics: USD return, gold-denominated return, gold's own return, ounces-per-share now
- One plain-English sentence with the verdict

## Yardsticks

- **Commodities:** gold, silver, crude oil, copper, wheat, corn, coffee, and live cattle from Yahoo Finance
- **Real world:** eggs, bacon, regular gasoline, ground beef, and the median US home price from FRED
- **Indexes:** Bitcoin and the S&P 500 from Yahoo Finance, plus CPI from FRED
- **Fun:** the US Big Mac price from The Economist's Big Mac Index; approximate and hand-maintained

## What if?

See what $10,000 invested in SPY, your selected yardstick, or cash under the mattress would be worth today, then compare every yardstick on one leaderboard.

## The Pile

Turn one yardstick into another and see the purchasing power as a literal pile of icons, with a history chart for context. For example, choose one troy ounce of gold and Big Macs, then slide between 2012 and today to watch the burger pile change.

## How the numbers are derived

```text
asset_in_yardstick = asset_price_usd / yardstick_price_usd

units = dollars / yardstick_price_at_start
value_today = units * yardstick_price_today
```

<!-- YARDSTICK_TABLE_START -->
| Yardstick | Category | Unit | Source | Series/ticker | Native frequency | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 🪙 Gold | Commodity | troy ounce | Yahoo Finance | GC=F | Daily | COMEX front-month futures; GLD fallback is an approximate ounce proxy. |
| 🥈 Silver | Commodity | troy ounce | Yahoo Finance | SI=F | Daily | COMEX silver futures, quoted in USD per troy ounce. |
| 🛢️ Crude oil | Commodity | barrel | Yahoo Finance | CL=F | Daily | WTI crude-oil futures, quoted in USD per barrel. |
| 🟠 Copper | Commodity | pound | Yahoo Finance | HG=F | Daily | COMEX copper futures, quoted in USD per pound. |
| 🌾 Wheat | Commodity | bushel | Yahoo Finance | ZW=F | Daily | CBOT wheat futures; cents-per-bushel quotes are converted to USD. |
| 🌽 Corn | Commodity | bushel | Yahoo Finance | ZC=F | Daily | CBOT corn futures; cents-per-bushel quotes are converted to USD. |
| ☕ Coffee | Commodity | pound | Yahoo Finance | KC=F | Daily | Coffee futures; cents-per-pound quotes are converted to USD. |
| 🐄 Live cattle | Commodity | pound | Yahoo Finance | LE=F | Daily | Live-cattle futures; cents-per-pound quotes are converted to USD. |
| ₿ Bitcoin | Index | bitcoin | Yahoo Finance | BTC-USD | Daily | Yahoo Finance BTC-USD adjusted close; trades seven days a week. |
| 📈 S&P 500 | Index | index unit | Yahoo Finance | ^GSPC | Daily | S&P 500 index level from Yahoo Finance. |
| 🥚 Dozen eggs | Real world | dozen eggs | FRED | APU0000708111 | Monthly | US city-average retail price per dozen from FRED. |
| 🥓 Pound of bacon | Real world | pound of bacon | FRED | APU0000704111 | Monthly | US city-average retail price per pound from FRED. |
| ⛽ Regular gasoline | Real world | gallon | FRED | GASREGW | Weekly | US regular gasoline price per gallon from FRED. |
| 🥩 Pound of ground beef | Real world | pound of ground beef | FRED | APU0000703112 | Monthly | US city-average retail price per pound from FRED. |
| 🏠 Median US home | Real world | median home | FRED | MSPUS | Quarterly | Median US home sale price from FRED; one unit is a full median home. |
| 💵 US CPI | Index | dollar of purchasing power as of the start date | FRED | CPIAUCSL | Monthly | CPI is rebased so one unit is a dollar of start-date purchasing power. |
| 🍔 Big Mac | Fun | Big Mac | The Economist Big Mac Index | economist-big-mac-us | ~Semiannual | Approximate US Big Mac price, hand-maintained from The Economist index. |
<!-- YARDSTICK_TABLE_END -->

Lower-frequency FRED and Big Mac observations are expanded and forward-filled, then aligned to business days or the asset's trading-day index for comparisons. Yahoo asset prices use dividend- and split-adjusted closes, and source results are cached for one hour.

Caveats:

- Gold is COMEX front-month futures, not spot gold. The GLD fallback is an approximate proxy and carries an expense ratio.
- FRED grocery prices are US city averages, not a quote from your neighborhood store.
- Big Mac prices are approximate and hand-maintained from The Economist's index.
- The CPI yardstick means a dollar of purchasing power as of the selected start date.
- None of this is investment advice.

## Quick start

```bash
git clone https://github.com/ncypher/gold_digger.git
cd gold_digger
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

## How it works

```
asset_in_gold = asset_close_usd / gold_close_usd
```

That's it — ounces of gold per share. Everything else is presentation.

- **Gold price:** COMEX front-month futures (`GC=F`), falling back to the `GLD` ETF if futures history is thin for the window
- **Asset prices:** dividend/split-adjusted closes from Yahoo Finance via [`yfinance`](https://github.com/ranaroussi/yfinance)
- Data is cached for one hour per ticker/window

## Caveats

- `yfinance` is free and unofficial. Fine for a demo; swap in a real market-data provider if this grows legs.
- Gold futures ≠ spot, and `GLD` carries an expense ratio. Both are close enough for the purpose here.
- This is an analysis toy, not investment advice.

## Origin

Sparked by a podcast aside — the idea that a stock chart priced in gold shows you
something a dollar chart hides. Built in an afternoon to see if it was true. It was.

## License

MIT
