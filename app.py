"""Gold Digger native Streamlit multipage entrypoint.

Run: streamlit run app.py
"""

import streamlit as st

from ui.how_it_works import render as render_methodology
from ui.main_page import render as render_gold_digger


st.set_page_config(page_title="Gold Digger", page_icon="🪙", layout="wide")


def main_page() -> None:
    render_gold_digger(methodology_page)


gold_digger_page = st.Page(
    main_page, title="Gold Digger", icon="🪙", default=True,
)
methodology_page = st.Page(
    render_methodology,
    title="How it works",
    icon=":material/menu_book:",
    url_path="how-it-works",
)

navigation = st.navigation([gold_digger_page, methodology_page])
navigation.run()
