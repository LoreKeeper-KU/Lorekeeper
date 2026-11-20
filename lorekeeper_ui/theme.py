# Authored by Faris
"""LoreKeeper's look: the shield logo and the stylesheet.

Everything injected as HTML from this package is either a constant defined here or a
fragment built in components.py from constants, numbers and html-escaped text. Generated
story text is never passed through unsafe_allow_html.
"""

import base64
from pathlib import Path

import streamlit as st

STYLESHEET = Path(__file__).with_name("styles.css")

# A crimson shield with an open book: the archive that keeps a world consistent.
_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 72">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#b5223b"/><stop offset="1" stop-color="#5c1220"/>
</linearGradient></defs>
<path d="M32 3 L58 12 V34 C58 52 46 64 32 69 C18 64 6 52 6 34 V12 Z"
 fill="url(#g)" stroke="#c2a45d" stroke-width="2.5" stroke-linejoin="round"/>
<path d="M32 27 C27 24 21 24 16 26 V46 C21 44 27 44 32 47 C37 44 43 44 48 46 V26 C43 24 37 24 32 27 Z"
 fill="none" stroke="#e3cf9a" stroke-width="2.2" stroke-linejoin="round"/>
<path d="M32 27 V47" stroke="#e3cf9a" stroke-width="2.2"/>
</svg>"""

_LOGO_URI = "data:image/svg+xml;base64," + base64.b64encode(_LOGO_SVG.encode()).decode()


def logo_html(size: int, css_class: str = "lk-logo") -> str:
    """The shield as an <img>, so no inline SVG has to survive the markdown sanitiser."""
    return (
        f'<img class="{css_class}" src="{_LOGO_URI}" alt="LoreKeeper shield" '
        f'width="{size}" height="{round(size * 72 / 64)}">'
    )


def load_css() -> str:
    """The stylesheet without blank lines, which would end an HTML block in markdown."""
    css = STYLESHEET.read_text(encoding="utf-8")
    return "\n".join(line for line in css.splitlines() if line.strip())


def inject_css() -> None:
    st.markdown(f"<style>\n{load_css()}\n</style>", unsafe_allow_html=True)
