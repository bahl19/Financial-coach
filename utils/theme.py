"""Brand theme: the navy/mint design language from the landing page, applied
across the app in both light and dark mode.

**How theming works here, and why it changed.** The first version of this
module declared a single static *dark* theme in `.streamlit/config.toml` and
tried to repaint everything else at runtime with injected CSS, driven by a
custom sidebar toggle. That could not work, for two reasons found by
inspecting the rendered DOM rather than by reading the code:

1. Several widgets take their colours straight from `config.toml`, not from
   the page's CSS - the number-input steppers rendered `rgb(13,34,56)`, which
   is precisely the old `secondaryBackgroundColor`. In light mode they stayed
   navy no matter what the stylesheet said.
2. Some override rules matched nothing at all. `[data-baseweb="select"] > div`
   selected zero elements in this Streamlit version, so the select dropdown
   was never being styled in the first place.

Streamlit 1.59 supports real per-mode theming (`[theme]` plus `[theme.dark]`),
so the palette now lives there and Streamlit applies it to its own widgets -
including the canvas-rendered dataframe grid, which CSS cannot reach at all.
This module reads the active mode through `st.context.theme.type` and injects
only the *brand* layer on top: fonts, headings, cards, accents, and spacing.

**The custom sidebar toggle is gone.** It could not drive Streamlit's native
theme (there is no Python API to set it), so keeping it would have meant the
CSS layer and the widget layer disagreeing - which is exactly the bug being
fixed. Mode is now switched through Streamlit's own Appearance setting
(top-right menu → Settings → Appearance), which additionally follows the
operating system preference by default.

**Colours are contrast-checked, not eyeballed.** Brand mint `#5ef3ce` is a
*fill* colour: measured as text on the light background it is 1.3:1, far
below WCAG AA's 4.5:1, which is why light mode read as broken. Light mode
therefore uses a deep teal-green (`#0a7057`, 5.7:1) wherever the accent
carries text or an icon, and reserves solid fills for buttons where it pairs
with white (6.1:1). Dark mode keeps mint, which is 13.2:1 on navy.

Like `utils/app_state.py`, `utils/llm.py`, `utils/auth.py`, and
`utils/landing.py`, this is a designated Streamlit adapter and is exempt from
the no-Streamlit-in-domain-code rule in
`tests/mvp2/test_dependency_boundaries.py` on that basis.
"""

from __future__ import annotations

from typing import Literal

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ThemeMode = Literal["dark", "light"]

_DEFAULT_MODE: ThemeMode = "light"  # matches [theme] base in .streamlit/config.toml

# --------------------------------------------------------------------------
# Palettes - kept in step with .streamlit/config.toml, which owns the same
# values for Streamlit's own widgets. Change both together.
# --------------------------------------------------------------------------

DARK = {
    "bg": "#081527",
    "bg_alt": "#0b1e33",
    "panel": "#0d2238",
    "panel_2": "#0f2740",
    "ink": "#e8eff6",
    "muted": "#8ca3b8",
    "line": "rgba(140,163,184,.18)",
    "accent_text": "#5ef3ce",   # 13.2:1 on navy
    "accent_fill": "#5ef3ce",
    "accent_fill_ink": "#06121f",
    "accent_dim": "rgba(94,243,206,.14)",
    "accent_line": "rgba(94,243,206,.30)",
    "green": "#12c96f",
    "danger": "#ff7a7a",
    "warning": "#f5b942",
}

LIGHT = {
    "bg": "#f5f9f8",
    "bg_alt": "#eaf3f0",
    "panel": "#ffffff",
    "panel_2": "#f2f7f6",
    "ink": "#0e1b2a",
    "muted": "#5b6b76",         # 5.2:1
    "line": "#d7e3e0",
    "accent_text": "#0a7057",   # 5.7:1 on bg, 6.1:1 on card
    "accent_fill": "#0a7057",
    "accent_fill_ink": "#ffffff",  # 6.1:1 on the fill
    "accent_dim": "rgba(10,112,87,.09)",
    "accent_line": "rgba(10,112,87,.28)",
    "green": "#0a7057",
    "danger": "#d92d20",
    "warning": "#a15c07",
}

_FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Archivo:wdth,wght@62..125,400..800&family=Spline+Sans:wght@300;400;500;600&display=swap"
)


def get_mode() -> ThemeMode:
    """The mode Streamlit is actually rendering in. Falls back to the
    `[theme]` base when unavailable (e.g. outside a script run, as in some
    tests), so callers never have to handle `None`."""
    try:
        mode = st.context.theme.type
    except Exception:
        return _DEFAULT_MODE
    return "dark" if mode == "dark" else "light" if mode == "light" else _DEFAULT_MODE


def palette(mode: ThemeMode | None = None) -> dict:
    return DARK if (mode or get_mode()) == "dark" else LIGHT


def render_theme_hint() -> None:
    """Points at Streamlit's native Appearance switcher, since this app no
    longer ships its own (see the module docstring)."""
    with st.sidebar:
        st.caption("Light or dark: top-right menu → Settings → Appearance.")


def inject_theme_css(mode: ThemeMode | None = None) -> None:
    mode = mode or get_mode()
    p = palette(mode)
    st.markdown(f"""
<style>
@import url('{_FONT_IMPORT}');

:root {{
  --fc-bg:{p['bg']}; --fc-bg-alt:{p['bg_alt']}; --fc-panel:{p['panel']}; --fc-panel-2:{p['panel_2']};
  --fc-ink:{p['ink']}; --fc-muted:{p['muted']}; --fc-line:{p['line']};
  --fc-accent:{p['accent_text']}; --fc-accent-fill:{p['accent_fill']}; --fc-accent-ink:{p['accent_fill_ink']};
  --fc-accent-dim:{p['accent_dim']}; --fc-accent-line:{p['accent_line']};
  --fc-green:{p['green']}; --fc-danger:{p['danger']}; --fc-warning:{p['warning']};
}}

/* ---------------- Type ---------------- */
html, body, .stApp, [data-testid="stMarkdownContainer"] {{
  font-family: 'Spline Sans', system-ui, sans-serif;
}}
h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: .01em;
}}

/* ---------------- Breathing room ----------------
   The default block gap packs controls together; these give sections and
   widgets room without changing any layout structure. */
[data-testid="stMainBlockContainer"] {{
  padding-top: 3rem !important;
  padding-bottom: 5rem !important;
  max-width: 1240px;
}}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {{ gap: 1.15rem; }}
[data-testid="stMarkdownContainer"] h2 {{ margin-top: 2.4rem; margin-bottom: .35rem; }}
[data-testid="stMarkdownContainer"] h3 {{ margin-top: 1.6rem; margin-bottom: .3rem; }}
[data-testid="stHeadingContainer"] {{ margin-bottom: .4rem; }}
[data-testid="stHorizontalBlock"] {{ gap: 1.25rem; }}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{ gap: .9rem; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 1.5rem; }}
hr {{ margin: 1.8rem 0; }}

/* ---------------- Accent ---------------- */
a, a:visited {{ color: var(--fc-accent); }}
[data-testid="stMarkdownContainer"] strong {{ color: var(--fc-ink); }}

/* ---------------- Buttons ---------------- */
.stButton button, .stDownloadButton button {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: .03em;
  border-radius: 10px !important;
  padding: .55rem 1.1rem !important;
  transition: transform .15s, box-shadow .15s, background .15s;
}}
.stButton button:hover, .stDownloadButton button:hover {{ transform: translateY(-1px); }}
[data-testid="stBaseButton-primary"] {{
  background: var(--fc-accent-fill) !important;
  color: var(--fc-accent-ink) !important;
  border: none !important;
}}
[data-testid="stBaseButton-primary"]:hover {{ box-shadow: 0 10px 26px var(--fc-accent-dim); }}

/* ---------------- Tabs ---------------- */
[data-testid="stTabs"] [role="tablist"] {{ gap: .35rem; margin-bottom: .6rem; }}
[data-testid="stTab"] {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 600 !important;
  padding: .5rem .9rem !important;
}}
[data-testid="stTab"][aria-selected="true"] {{ color: var(--fc-accent) !important; }}
[data-testid="stTab"] .react-aria-SelectionIndicator {{ background-color: var(--fc-accent) !important; }}

/* ---------------- Metrics ---------------- */
[data-testid="stMetric"] {{
  background: var(--fc-panel);
  border: 1px solid var(--fc-line);
  border-radius: 14px;
  padding: 1.05rem 1.15rem;
}}
[data-testid="stMetricLabel"] {{
  color: var(--fc-muted) !important; text-transform: uppercase; letter-spacing: .06em;
  font-size: .72rem !important; white-space: normal !important; overflow: visible !important;
  text-overflow: unset !important;
}}
[data-testid="stMetricValue"] {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-size: clamp(1.05rem, 1.6vw, 1.5rem) !important;
  white-space: normal !important; overflow: visible !important; text-overflow: unset !important;
  word-break: break-word;
}}

/* ---------------- Containers ---------------- */
[data-testid="stExpander"] {{ border-radius: 14px !important; }}
[data-testid="stExpander"] summary {{ padding: .7rem .95rem !important; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border-radius: 12px !important; overflow: hidden; }}
[data-testid="stAlertContainer"], .stAlert {{ border-radius: 12px !important; padding: .85rem 1rem !important; }}
[data-testid="stPlotlyChart"] {{
  border: 1px solid var(--fc-line) !important;
  border-radius: 14px !important;
  overflow: hidden;
  padding: .35rem;
}}

/* ---------------- Icons ----------------
   Material icons render as text, so they inherit colour automatically. This
   only nudges optical alignment against adjacent text. */
[data-testid="stIconMaterial"] {{ vertical-align: -.18em; }}

/* ---------------- Inputs ---------------- */
[data-testid="stWidgetLabel"] p {{ color: var(--fc-muted) !important; font-size: .85rem; }}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{
  box-shadow: 0 0 0 3px var(--fc-accent-dim) !important;
}}

/* ---------------- Scrollbar ---------------- */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--fc-line); border-radius: 999px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--fc-accent-line); }}
</style>
""", unsafe_allow_html=True)


def apply_plotly_template(mode: ThemeMode | None = None) -> None:
    """Registers and activates a brand Plotly template so every chart picks
    up the palette without its call site knowing about theming.

    Charts now follow the active mode. The earlier version pinned them to the
    dark palette in both, because Streamlit's single static dark theme
    overrode the figure's own background. With per-mode theming in
    `config.toml` and `st.plotly_chart(..., theme=None)` at the call sites,
    the figure's own colours are honoured and that workaround is obsolete."""
    mode = mode or get_mode()
    p = palette(mode)
    template = go.layout.Template()
    template.layout = go.Layout(
        paper_bgcolor=p["panel"],
        plot_bgcolor=p["panel"],
        font=dict(family="Spline Sans, system-ui, sans-serif", color=p["ink"], size=13),
        colorway=[p["accent_text"], p["green"], p["warning"], p["danger"], p["muted"]],
        xaxis=dict(gridcolor=p["line"], zerolinecolor=p["line"], linecolor=p["line"]),
        yaxis=dict(gridcolor=p["line"], zerolinecolor=p["line"], linecolor=p["line"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=34, r=14, b=14, l=14),
    )
    pio.templates["financial_coach"] = template
    pio.templates.default = "financial_coach"
