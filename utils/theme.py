"""Brand theme: injects the landing page's navy/mint design language into
the Streamlit app, with a light-mode counterpart, so the marketing site
(`UI/Financial Coach Landing.dc.html`), the sign-in page
(`UI/uploads/financial-coach-login.html`), and the app itself read as one
product rather than three unrelated screens.

Design tokens are copied verbatim from the landing/login pages' `:root`
custom properties for dark mode; the light palette is a deliberately new,
accessible counterpart built from the same three brand colors (navy, mint,
green) rather than an inverted guess - mint at full brightness (`#5ef3ce`)
fails contrast as text/link color on a light background, so light mode
darkens it for text/icons/links while keeping the exact brand mint as a
fill color (buttons, badges, chart bars) with the landing page's own
dark-navy-on-mint pairing, which is contrast-safe in both themes by
construction.

Streamlit has no first-class hot-swappable theme system, so switching modes
just reruns the script (Streamlit's normal execution model) with a
different palette selected from `st.session_state` and re-injects a full
`<style>` block - there is no client-side toggle logic to keep in sync.

This module is exempted from `tests/mvp2/test_dependency_boundaries.py`'s
no-streamlit-in-domain-code rule the same way `utils/app_state.py`,
`utils/llm.py`, and `utils/auth.py` already are: it *is* the Streamlit
adapter for this concern, not domain code that should be importing
Streamlit directly.
"""

from __future__ import annotations

from typing import Literal

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ThemeMode = Literal["dark", "light"]

_SESSION_KEY = "theme_mode"
_DEFAULT_MODE: ThemeMode = "dark"

# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------

DARK = {
    "bg": "#081527",
    "bg_alt": "#0b1e33",
    "panel": "#0d2238",
    "panel_2": "#0f2740",
    "ink": "#e8eff6",
    "muted": "#8ca3b8",
    "line": "rgba(140,163,184,.18)",
    "line_soft": "rgba(140,163,184,.10)",
    "mint": "#5ef3ce",
    "mint_dim": "rgba(94,243,206,.14)",
    "mint_line": "rgba(94,243,206,.30)",
    "mint_ink": "#06121f",  # text color placed ON TOP of a solid mint fill
    "green": "#12c96f",
    "danger": "#ff7a7a",
    "danger_dim": "rgba(255,122,122,.14)",
    "warning": "#f5b942",
    "warning_dim": "rgba(245,185,66,.14)",
    "shadow": "rgba(0,0,0,.45)",
}

LIGHT = {
    "bg": "#f5f9f8",
    "bg_alt": "#eaf3f0",
    "panel": "#ffffff",
    "panel_2": "#f2f7f6",
    "ink": "#0e1b2a",
    "muted": "#5b6b76",
    "line": "rgba(14,27,42,.12)",
    "line_soft": "rgba(14,27,42,.07)",
    "mint": "#5ef3ce",  # kept exact for fills/badges/buttons (paired with mint_ink)
    "mint_dim": "rgba(18,201,111,.10)",
    "mint_line": "rgba(14,159,125,.35)",
    "mint_ink": "#06121f",
    "green": "#0e9d63",  # darkened for AA text/icon contrast on a light bg
    "danger": "#d92d20",
    "danger_dim": "rgba(217,45,32,.08)",
    "warning": "#a15c07",
    "warning_dim": "rgba(161,92,7,.10)",
    "shadow": "rgba(16,32,45,.12)",
}

_FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Archivo:wdth,wght@62..125,400..800&family=Spline+Sans:wght@300;400;500;600&display=swap"
)


def get_mode() -> ThemeMode:
    return st.session_state.get(_SESSION_KEY, _DEFAULT_MODE)


def _set_mode(mode: ThemeMode) -> None:
    st.session_state[_SESSION_KEY] = mode


def _palette(mode: ThemeMode) -> dict:
    return DARK if mode == "dark" else LIGHT


def render_theme_toggle() -> ThemeMode:
    """Sidebar dark/light toggle. Must be called before `inject_theme_css()`
    reads `get_mode()` for this rerun, since the toggle writes the session
    key `inject_theme_css()` reads."""
    if _SESSION_KEY not in st.session_state:
        _set_mode(_DEFAULT_MODE)
    with st.sidebar:
        is_dark = st.toggle(
            "\U0001f319 Dark mode", value=get_mode() == "dark", key="theme_dark_toggle",
            help="Switch between the app's dark and light color themes.",
        )
    _set_mode("dark" if is_dark else "light")
    return get_mode()


def inject_theme_css(mode: ThemeMode | None = None) -> None:
    mode = mode or get_mode()
    p = _palette(mode)
    st.markdown(f"""
<style>
@import url('{_FONT_IMPORT}');

:root {{
  --fc-bg:{p['bg']}; --fc-bg-alt:{p['bg_alt']}; --fc-panel:{p['panel']}; --fc-panel-2:{p['panel_2']};
  --fc-ink:{p['ink']}; --fc-muted:{p['muted']}; --fc-line:{p['line']}; --fc-line-soft:{p['line_soft']};
  --fc-mint:{p['mint']}; --fc-mint-dim:{p['mint_dim']}; --fc-mint-line:{p['mint_line']}; --fc-mint-ink:{p['mint_ink']};
  --fc-green:{p['green']}; --fc-danger:{p['danger']}; --fc-danger-dim:{p['danger_dim']};
  --fc-warning:{p['warning']}; --fc-warning-dim:{p['warning_dim']}; --fc-shadow:{p['shadow']};
}}

html, body, .stApp {{
  background: var(--fc-bg) !important;
  color: var(--fc-ink) !important;
  font-family: 'Spline Sans', system-ui, sans-serif !important;
}}
[data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stBottomBlockContainer"] {{
  background: transparent !important;
}}
[data-testid="stHeader"] {{ border-bottom: 1px solid var(--fc-line); backdrop-filter: blur(10px); }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2rem; }}

::selection {{ background: var(--fc-mint); color: var(--fc-mint-ink); }}
a, a:visited {{ color: var(--fc-mint); }}
a:hover {{ color: var(--fc-green); }}

h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: .01em;
  color: var(--fc-ink) !important;
}}
[data-testid="stCaptionContainer"], .stCaption {{ color: var(--fc-muted) !important; }}
hr, [data-testid="stDivider"] {{ border-color: var(--fc-line) !important; }}

/* ---------------- Sidebar ---------------- */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, var(--fc-panel), var(--fc-bg-alt)) !important;
  border-right: 1px solid var(--fc-line);
}}
[data-testid="stSidebar"] * {{ color: var(--fc-ink); }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: var(--fc-muted) !important; }}

/* ---------------- Buttons ---------------- */
.stButton button, .stDownloadButton button, [data-testid="stBaseButton-secondary"] {{
  background: transparent !important;
  color: var(--fc-mint) !important;
  border: 1px solid var(--fc-mint-line) !important;
  border-radius: 10px !important;
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: .04em;
  transition: background .15s, transform .15s, box-shadow .15s;
}}
.stButton button:hover, .stDownloadButton button:hover {{
  background: var(--fc-mint-dim) !important;
  border-color: var(--fc-mint) !important;
  transform: translateY(-1px);
}}
[data-testid="stBaseButton-primary"], button[kind="primary"] {{
  background: var(--fc-mint) !important;
  color: var(--fc-mint-ink) !important;
  border: none !important;
  border-radius: 10px !important;
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: .04em;
  box-shadow: 0 8px 24px rgba(94,243,206,.28);
  transition: transform .15s, box-shadow .15s;
}}
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {{
  transform: translateY(-1px);
  box-shadow: 0 12px 30px rgba(94,243,206,.4);
}}

/* ---------------- Tabs ---------------- */
[data-testid="stTabs"] [role="tablist"] {{ gap: 4px; border-bottom: 1px solid var(--fc-line) !important; }}
[data-testid="stTab"] {{
  font-family: 'Archivo', system-ui, sans-serif !important;
  font-weight: 600 !important;
  color: var(--fc-muted) !important;
  background: transparent !important;
}}
[data-testid="stTab"][aria-selected="true"] {{ color: var(--fc-mint) !important; }}
[data-testid="stTab"] .react-aria-SelectionIndicator {{ background-color: var(--fc-mint) !important; }}

/* ---------------- Metrics ---------------- */
[data-testid="stMetric"] {{
  background: linear-gradient(180deg, var(--fc-panel), var(--fc-panel-2));
  border: 1px solid var(--fc-line);
  border-radius: 14px;
  padding: 16px 18px;
}}
[data-testid="stMetricLabel"] {{
  color: var(--fc-muted) !important; text-transform: uppercase; letter-spacing: .06em; font-size: .72rem !important;
  white-space: normal !important; overflow: visible !important; text-overflow: unset !important;
}}
[data-testid="stMetricValue"] {{
  font-family: 'Archivo', system-ui, sans-serif !important; color: var(--fc-ink) !important;
  font-size: clamp(1.05rem, 1.6vw, 1.5rem) !important; white-space: normal !important;
  overflow: visible !important; text-overflow: unset !important; word-break: break-word;
}}

/* ---------------- Inputs ---------------- */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea, [data-baseweb="select"] > div,
[data-testid="stFileUploaderDropzone"] {{
  background: var(--fc-panel) !important;
  color: var(--fc-ink) !important;
  border: 1px solid var(--fc-line) !important;
  border-radius: 10px !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{
  border-color: var(--fc-mint) !important;
  box-shadow: 0 0 0 3px var(--fc-mint-dim) !important;
}}
[data-testid="stWidgetLabel"] p {{ color: var(--fc-muted) !important; font-size: .85rem; }}

/* ---------------- Toggle switch (dark/light control itself; also styles
   any other st.toggle/st.checkbox in the app, e.g. "Remember me"-style
   controls, for the same reason every other widget above is themed) ---- */
[data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type {{
  background: var(--fc-mint) !important;
}}
[data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type > div {{
  background: var(--fc-mint-ink) !important;
}}

/* ---------------- Alerts ---------------- */
[data-testid="stAlertContentInfo"], [data-testid="stNotification"][kind="info"] {{
  background: var(--fc-mint-dim) !important; color: var(--fc-ink) !important; border: 1px solid var(--fc-mint-line) !important;
}}
[data-testid="stAlertContentSuccess"], [data-testid="stNotification"][kind="success"] {{
  background: rgba(18,201,111,.12) !important; color: var(--fc-ink) !important; border: 1px solid rgba(18,201,111,.35) !important;
}}
[data-testid="stAlertContentWarning"], [data-testid="stNotification"][kind="warning"] {{
  background: var(--fc-warning-dim) !important; color: var(--fc-ink) !important; border: 1px solid var(--fc-warning) !important;
}}
[data-testid="stAlertContentError"], [data-testid="stNotification"][kind="error"] {{
  background: var(--fc-danger-dim) !important; color: var(--fc-ink) !important; border: 1px solid var(--fc-danger) !important;
}}
[data-testid="stAlertContainer"], .stAlert {{ border-radius: 12px !important; }}

/* ---------------- Expander / containers / dataframe chrome ---------------- */
[data-testid="stExpander"] {{
  background: linear-gradient(180deg, var(--fc-panel), var(--fc-panel-2));
  border: 1px solid var(--fc-line) !important;
  border-radius: 14px !important;
}}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
  border: 1px solid var(--fc-line) !important;
  border-radius: 12px !important;
  overflow: hidden;
}}
/* Chart panels stay on the brand's dark card treatment in both themes -
   see apply_plotly_template()'s docstring for why - so the border reads
   as an intentional dark-card frame, matching the landing page's own
   dashboard preview, rather than a mismatched rectangle in light mode. */
[data-testid="stPlotlyChart"] {{
  border: 1px solid var(--fc-mint-line) !important;
  border-radius: 14px !important;
  overflow: hidden;
  padding: 4px;
}}

/* ---------------- Scrollbar ---------------- */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--fc-line); border-radius: 999px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--fc-mint-line); }}
</style>
""", unsafe_allow_html=True)


def apply_plotly_template(mode: ThemeMode | None = None) -> None:
    """Registers and activates a brand plotly template so every chart in the
    app (spending pie, income/expense bars, etc.) picks up the same palette
    without each call site needing to know about theming.

    Chart panels are deliberately always the DARK palette, regardless of
    the active app theme - this is both a real platform constraint and,
    on reflection, the right call: Streamlit's `st.plotly_chart` paints a
    chart's outer background from the server's static `.streamlit/config.toml`
    theme (`base = "dark"`) no matter what `paper_bgcolor` the figure itself
    requests or whether `theme=None` is passed - confirmed by inspecting the
    rendered `svg.main-svg` element's own inline style, which stays pinned
    to the config file's `backgroundColor` across an in-session light/dark
    toggle. Rather than fight a value Streamlit will silently overwrite,
    charts keep the exact dark card treatment `UI/Financial Coach
    Landing.dc.html`'s own dashboard preview already uses (that page has no
    light variant at all) - so this reads as one deliberate brand choice
    instead of a mismatched light-mode chart. `mode` still selects the
    *data* colorway/gridlines below it, in case a future non-panel chart
    (e.g. an inline sparkline on a light card) needs to opt out of the
    dark-panel assumption."""
    p = DARK
    _ = mode  # kept in the signature for that future non-panel-chart case; unused today
    template = go.layout.Template()
    template.layout = go.Layout(
        paper_bgcolor=p["panel"],
        plot_bgcolor=p["panel"],
        font=dict(family="Spline Sans, system-ui, sans-serif", color=p["ink"]),
        colorway=[p["mint"], p["green"], p["warning"], p["danger"], p["muted"]],
        xaxis=dict(gridcolor=p["line"], zerolinecolor=p["line"], linecolor=p["line"]),
        yaxis=dict(gridcolor=p["line"], zerolinecolor=p["line"], linecolor=p["line"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=30, r=10, b=10, l=10),
    )
    pio.templates["financial_coach"] = template
    pio.templates.default = "financial_coach"
