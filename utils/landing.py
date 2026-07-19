"""The marketing landing page, rendered as the app's first screen.

`UI/Financial Coach Landing.dc.html` was authored as a standalone marketing
site: it is a design-tool export (`<x-dc>` wrapper, `sc-for` loops, `{{ }}`
interpolation, a `support.js` client runtime) whose every call-to-action
links out to `https://financialcoach.streamlit.app/`. It renders correctly
on its own, but nothing ever served it from inside the app — so until now
the product had a landing page in the repository and no landing page in the
actual user journey.

This module closes that gap by rebuilding the page in Streamlit's own
primitives rather than embedding the HTML file, for three concrete reasons:

1. `st.components.v1.html` renders into a sandboxed iframe with `srcdoc`,
   so the page's relative asset paths (`support.js`, `assets/app-demo.mp4`)
   would not resolve; inlining them means shipping a 68 KB runtime and a
   9 MB base64 video into every page load.
2. A CTA inside that iframe cannot set `st.session_state`, so it could not
   advance the user into sign-in — it would still have to link out to the
   deployed URL, which is exactly the disconnect being fixed.
3. Rebuilt in Streamlit, the page inherits `utils/theme.py`'s CSS variables
   and therefore follows the dark/light toggle, which the source page (dark
   only, no light variant) never supported.

Copy, section order, palette, and type treatment are taken from the source
page. The scroll-reveal and parallax effects are deliberately dropped: they
are JavaScript-driven in the original, and Streamlit strips `<script>` from
`st.markdown`. Pure-CSS motion (the marquee, the pulsing badge dot) is kept.

Like `utils/app_state.py`, `utils/llm.py`, `utils/auth.py`, and
`utils/theme.py`, this module is a designated Streamlit adapter and is
exempted from the no-Streamlit-in-domain-code rule in
`tests/mvp2/test_dependency_boundaries.py` on that basis.
"""

from __future__ import annotations

import os

import streamlit as st

CTA_KEY = "landing_cta_button"
_SESSION_KEY = "landing_dismissed"

_VIDEO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "UI", "assets", "app-demo.mp4")

_STEPS = [
    ("01", "⬆", "Upload", "Drop in a bank or card statement — CSV or PDF. It never leaves your session."),
    ("02", "◎", "Analyze", "Every line is read and categorized, and your real patterns are surfaced."),
    ("03", "✳", "Coach", "Get plain-language insights, trends, and the next best move for your money."),
]

_FEATURES = [
    ("Income", "See exactly what comes in, when, and how steady it really is."),
    ("Spending", "Every rupee categorized so nothing hides in the noise."),
    ("Trends", "Month-over-month shifts surfaced before they become habits."),
    ("Habits", "Recurring behaviours flagged with gentle, specific nudges."),
]

_MARQUEE = ["Upload", "Categorize", "Analyze", "Coach", "Trends", "Habits", "Budgets", "Insights"]


def was_dismissed() -> bool:
    return bool(st.session_state.get(_SESSION_KEY, False))


def dismiss() -> None:
    st.session_state[_SESSION_KEY] = True


def reset() -> None:
    """Send the user back to the landing page (used on sign-out, so a
    signed-out visitor lands where a first-time visitor does)."""
    st.session_state[_SESSION_KEY] = False


def _inject_landing_css() -> None:
    st.markdown("""
<style>
@keyframes fc-pulse {0%,100%{opacity:1}50%{opacity:.35}}
@keyframes fc-marquee {from{transform:translateX(0)}to{transform:translateX(-50%)}}

.fc-badge {
  display:inline-flex; align-items:center; gap:10px;
  font-size:11px; letter-spacing:.26em; text-transform:uppercase;
  color:var(--fc-mint); border:1px solid var(--fc-mint-line); background:var(--fc-mint-dim);
  padding:9px 18px; border-radius:999px; margin-bottom:26px;
}
.fc-badge::before {
  content:''; width:6px; height:6px; border-radius:50%;
  background:var(--fc-mint); box-shadow:0 0 10px var(--fc-mint);
  animation:fc-pulse 2.4s ease-in-out infinite;
}
.fc-hero-h1 {
  font-family:'Archivo',system-ui,sans-serif; font-weight:800; text-transform:uppercase;
  font-size:clamp(38px,6vw,82px); line-height:.98; letter-spacing:.01em; margin:0 0 24px;
}
.fc-hero-h1 .accent { color:var(--fc-mint); }
.fc-hero-sub {
  font-size:clamp(16px,1.6vw,20px); font-weight:300; line-height:1.6;
  color:var(--fc-muted); max-width:52ch; margin:0 auto 8px;
}
.fc-hero-sub strong { color:var(--fc-ink); font-weight:500; }

.fc-marquee-wrap {
  border-top:1px solid var(--fc-line); border-bottom:1px solid var(--fc-line);
  overflow:hidden; white-space:nowrap; padding:18px 0; margin:8px 0 4px;
}
.fc-marquee { display:inline-flex; gap:56px; animation:fc-marquee 26s linear infinite; }
.fc-marquee span {
  font-family:'Archivo',system-ui,sans-serif; font-weight:600; font-size:14px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--fc-muted);
}

.fc-eyebrow {
  font-size:11px; letter-spacing:.26em; text-transform:uppercase; color:var(--fc-mint);
}
.fc-h2 {
  font-family:'Archivo',system-ui,sans-serif; font-weight:800; text-transform:uppercase;
  font-size:clamp(26px,3.4vw,44px); line-height:1.04; margin:12px 0 0;
}

.fc-card {
  position:relative; height:100%;
  background:linear-gradient(180deg,var(--fc-panel),var(--fc-panel-2));
  border:1px solid var(--fc-line); border-radius:18px; padding:30px 26px 28px; overflow:hidden;
}
.fc-card-no {
  position:absolute; top:10px; right:20px; line-height:1;
  font-family:'Archivo',system-ui,sans-serif; font-weight:800; font-size:56px; color:var(--fc-mint-dim);
}
.fc-card-icon {
  width:44px; height:44px; border-radius:12px; background:var(--fc-mint-dim);
  border:1px solid var(--fc-mint-line); display:flex; align-items:center; justify-content:center;
  margin-bottom:18px; color:var(--fc-mint); font-size:18px;
}
.fc-card h3 {
  font-family:'Archivo',system-ui,sans-serif; font-weight:700; text-transform:uppercase;
  letter-spacing:.04em; font-size:17px; margin:0 0 10px; color:var(--fc-ink);
}
.fc-card p { font-size:14px; line-height:1.6; color:var(--fc-muted); font-weight:300; margin:0; }

.fc-bars { display:flex; align-items:flex-end; justify-content:center; gap:8px; height:84px; margin-bottom:20px; }
.fc-bars i {
  width:14px; background:var(--fc-mint); border-radius:4px 4px 0 0; display:block;
  box-shadow:0 0 16px rgba(94,243,206,.35);
}

.fc-final {
  position:relative; overflow:hidden; border-radius:24px; border:1px solid var(--fc-mint-line);
  background:linear-gradient(160deg,var(--fc-panel),var(--fc-bg));
  padding:64px 40px; text-align:center; margin-top:8px;
}
.fc-final h2 {
  font-family:'Archivo',system-ui,sans-serif; font-weight:800; text-transform:uppercase;
  font-size:clamp(28px,4.6vw,58px); line-height:1; margin:0; color:var(--fc-ink);
}
.fc-final h2 .accent { color:var(--fc-mint); }
.fc-final p { margin:18px auto 0; font-size:17px; color:var(--fc-muted); font-weight:300; max-width:44ch; }

.fc-foot {
  border-top:1px solid var(--fc-line); margin-top:36px; padding:26px 0 8px;
  display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px;
  font-size:13px; color:var(--fc-muted);
}
</style>
""", unsafe_allow_html=True)


def _logo_svg(size: int = 30) -> str:
    return (
        f"<svg viewBox='0 0 100 100' style='width:{size}px;height:{size}px;flex:none'>"
        "<g fill='none' stroke='currentColor' stroke-width='7' stroke-linecap='round'>"
        "<path d='M22 38 Q50 16 78 38'/><path d='M28 56 Q50 38 72 56'/><path d='M34 74 Q50 60 66 74'/>"
        "</g></svg>"
    )


def render_landing_page() -> bool:
    """Renders the landing page. Returns True when the visitor clicked the
    call to action, at which point the caller should `dismiss()` and rerun
    so the auth gate (or the app itself, when auth is disabled) takes over."""
    _inject_landing_css()

    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;color:var(--fc-mint);margin-bottom:34px'>"
        f"{_logo_svg()}"
        "<span style=\"font-family:'Archivo',system-ui,sans-serif;font-weight:700;letter-spacing:.3em;"
        "font-size:12px;text-transform:uppercase;color:var(--fc-ink)\">Financial&nbsp;Coach</span></div>",
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------------- hero --
    # One markdown block, not four: Streamlit renders each st.markdown() into
    # its own container, so a wrapper <div> opened in one call and closed in
    # another wraps nothing and its text-align never applies.
    st.markdown(
        "<div style='text-align:center'>"
        "<span class='fc-badge'>AI-powered financial analysis</span>"
        "<h1 class='fc-hero-h1'>Stop the manual struggle.<br>"
        "<span class='accent'>Start coaching.</span></h1>"
        "<p class='fc-hero-sub'>Upload your statements and let your AI coach turn raw transactions into "
        "<strong>actionable insights in seconds</strong> — no spreadsheets, no formulas, no late nights.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    cta_clicked = False
    spacer_l, cta_col, spacer_r = st.columns([1, 1, 1])
    with cta_col:
        cta_clicked = st.button("Get started free →", type="primary", key=CTA_KEY, width="stretch")

    # The real product demo from the source page, served by Streamlit rather
    # than an unreachable relative path inside an iframe.
    if os.path.isfile(_VIDEO_PATH):
        _, video_col, _ = st.columns([1, 6, 1])
        with video_col:
            st.video(_VIDEO_PATH, autoplay=True, muted=True, loop=True)

    st.markdown(
        "<div class='fc-marquee-wrap'><div class='fc-marquee'>"
        + "".join(f"<span>{item}</span>" for item in _MARQUEE * 2)
        + "</div></div>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------- how it works --
    st.markdown(
        "<div style='text-align:center;margin:44px 0 26px'>"
        "<span class='fc-eyebrow'>How it works</span>"
        "<h2 class='fc-h2'>Three steps.<br>Zero spreadsheets.</h2></div>",
        unsafe_allow_html=True,
    )
    for col, (no, icon, title, body) in zip(st.columns(3, gap="medium"), _STEPS):
        col.markdown(
            f"<div class='fc-card'><div class='fc-card-no'>{no}</div>"
            f"<div class='fc-card-icon'>{icon}</div>"
            f"<h3>{title}</h3><p>{body}</p></div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------ features --
    st.markdown(
        "<div style='text-align:center;margin:52px 0 26px'>"
        "<span class='fc-eyebrow'>What you see</span>"
        "<h2 class='fc-h2'>Every number,<br>finally in focus.</h2></div>",
        unsafe_allow_html=True,
    )
    _bar_heights = [("100%", "62%", "84%", "70%"), ("48%", "100%", "66%", "82%"),
                    ("40%", "58%", "76%", "100%"), ("70%", "52%", "90%", "64%")]
    for col, (title, body), bars in zip(st.columns(4, gap="medium"), _FEATURES, _bar_heights):
        col.markdown(
            "<div class='fc-card'><div class='fc-bars'>"
            + "".join(f"<i style='height:{h}'></i>" for h in bars)
            + f"</div><h3>{title}</h3><p>{body}</p></div>",
            unsafe_allow_html=True,
        )

    # ----------------------------------------------------------- final CTA --
    st.markdown(
        "<div class='fc-final'><h2>Take control<br><span class='accent'>of your money.</span></h2>"
        "<p>Free to start. Your first insights are seconds away.</p></div>",
        unsafe_allow_html=True,
    )
    spacer_l2, cta_col2, spacer_r2 = st.columns([1, 1, 1])
    with cta_col2:
        if st.button("Start coaching free →", type="primary", key=f"{CTA_KEY}_bottom", width="stretch"):
            cta_clicked = True

    st.markdown(
        "<div class='fc-foot'><span>© 2026 Financial Coach — AI-powered financial analysis.</span>"
        "<span>Educational guidance, not regulated financial advice.</span></div>",
        unsafe_allow_html=True,
    )

    return cta_clicked
