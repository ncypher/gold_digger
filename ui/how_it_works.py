"""Native Streamlit methodology page."""

import streamlit as st

from data.yardsticks import methodology_frame


def render() -> None:
    st.title("How it works")
    st.caption("The arithmetic is simple. The source conventions are where the footnotes live.")

    st.header("The core formulas")
    st.code(
        "asset_in_yardstick = asset_price_usd / yardstick_price_usd",
        language="python",
    )
    st.code(
        "units = dollars / yardstick_price_at_start\n"
        "value_today = units * yardstick_price_today",
        language="python",
    )

    st.header("Yardsticks and sources")
    st.dataframe(methodology_frame(), hide_index=True, width="stretch")

    st.header("Normalization")
    st.markdown(
        "Lower-frequency FRED and Big Mac observations are expanded and forward-filled, "
        "then aligned to business days or the asset's trading-day index for comparisons. "
        "Yahoo asset prices use dividend- and split-adjusted closes. Source results are "
        "cached for one hour."
    )

    st.header("Caveats")
    st.markdown(
        "- Gold is COMEX front-month futures, not spot gold. The GLD fallback is an "
        "approximate proxy and carries an expense ratio.\n"
        "- FRED grocery prices are US city averages, not a quote from your neighborhood store.\n"
        "- Big Mac prices are approximate and hand-maintained from The Economist's index.\n"
        "- The CPI yardstick means a dollar of purchasing power as of the selected start date.\n"
        "- None of this is investment advice."
    )

    st.header("Links")
    st.markdown(
        "- [GitHub repository](https://github.com/ncypher/gold_digger)\n"
        "- [Live app](https://gold-digger.streamlit.app/)\n"
        "- [FRED](https://fred.stlouisfed.org/)\n"
        "- [yfinance](https://github.com/ranaroussi/yfinance)"
    )
