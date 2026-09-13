import html
import os

import pandas as pd
import psycopg2
import streamlit as st

st.set_page_config(
    page_title="ExceptionIQ",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# ExceptionIQ — editorial operations console
# -----------------------------------------------------------------------------

PALETTE = {
    "ink": "#111111",
    "cream": "#F4F2EC",
    "panel": "#FBFAF6",
    "line": "#D9D6CD",
    "muted": "#77766F",
    "lime": "#D7FF45",
    "lavender": "#DCCFFF",
    "sage": "#DDE8D0",
    "warm": "#E9DCCB",
}

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,500;0,600;1,500;1,600&display=swap');

:root {
    --ink: #111111;
    --cream: #F4F2EC;
    --panel: #FBFAF6;
    --line: #D9D6CD;
    --muted: #77766F;
    --lime: #D7FF45;
    --lavender: #DCCFFF;
    --sage: #DDE8D0;
    --warm: #E9DCCB;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', system-ui, sans-serif;
}

.stApp {
    background:
        linear-gradient(rgba(244,242,236,.92), rgba(244,242,236,.92)),
        repeating-linear-gradient(0deg, transparent 0, transparent 47px, rgba(17,17,17,.035) 48px),
        repeating-linear-gradient(90deg, transparent 0, transparent 47px, rgba(17,17,17,.035) 48px);
    color: var(--ink);
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { right: 1rem; }
footer { visibility: hidden; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--ink);
    border-right: 1px solid var(--ink);
}
section[data-testid="stSidebar"] > div {
    padding: 1.6rem 1.15rem 1.25rem 1.15rem;
}
section[data-testid="stSidebar"] * { color: #F4F2EC; }
section[data-testid="stSidebar"] .stRadio label {
    padding: .55rem .7rem;
    border-radius: 12px;
    margin: .15rem 0;
    font-weight: 600;
}
section[data-testid="stSidebar"] .stRadio label:hover { background: #222222; }
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] { color: #92918B !important; }
section[data-testid="stSidebar"] .stButton button {
    border: 1px solid #3B3B3B;
    background: #181818;
    color: #F4F2EC;
    border-radius: 999px;
}
section[data-testid="stSidebar"] .stButton button:hover { border-color: var(--lime); color: var(--lime); }

/* Main canvas */
.block-container {
    max-width: 1500px;
    padding: 2.4rem 3.2rem 4rem 3.2rem;
}

h1, h2, h3, h4 { color: var(--ink) !important; }
h1 { letter-spacing: -.045em; }
h2 { letter-spacing: -.035em; }
h3 { letter-spacing: -.025em; }

/* Native Streamlit controls, made quieter */
.stSelectbox > div > div,
.stTextInput > div > div,
.stTextArea > div > div,
.stNumberInput > div > div {
    background: var(--panel) !important;
    border-color: var(--line) !important;
    border-radius: 10px !important;
}
/* Make native Streamlit controls readable after the editorial theme overrides. */
.stSelectbox [data-baseweb="select"],
.stSelectbox [data-baseweb="select"] > div,
.stSelectbox [data-baseweb="select"] [role="combobox"],
.stSelectbox [data-baseweb="select"] [role="combobox"] > div,
.stSelectbox [data-baseweb="select"] [role="combobox"] span,
.stSelectbox [data-baseweb="select"] [role="combobox"] div {
    color: var(--ink) !important;
    -webkit-text-fill-color: var(--ink) !important;
    opacity: 1 !important;
}
.stSelectbox [data-baseweb="select"] svg {
    fill: var(--ink) !important;
    color: var(--ink) !important;
    opacity: 1 !important;
}
.stTextArea textarea,
.stTextInput input,
.stNumberInput input {
    color: var(--ink) !important;
    -webkit-text-fill-color: var(--ink) !important;
    caret-color: var(--ink) !important;
}
.stTextArea textarea::placeholder,
.stTextInput input::placeholder {
    color: #9A9890 !important;
    -webkit-text-fill-color: #9A9890 !important;
}
.stSelectbox label, .stTextArea label, .stNumberInput label { color: var(--muted) !important; font-size: .78rem !important; }
.stButton button[kind="primary"] {
    background: var(--ink) !important;
    color: var(--cream) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 999px !important;
    font-weight: 700;
    padding: .6rem 1rem;
}
.stButton button[kind="primary"]:hover { background: #2A2A2A !important; }

/* Remove generic metric-box look */
[data-testid="stMetric"] {
    background: transparent;
    border: 0;
    padding: 0;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; font-size: .68rem !important; }
[data-testid="stMetricValue"] { color: var(--ink) !important; font-weight: 600; letter-spacing: -.04em; }

/* Tables */
[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
}

hr { border: 0; border-top: 1px solid var(--line); margin: 1.6rem 0; }

/* Custom components */
.eyebrow {
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-size: .68rem;
    color: var(--muted);
    margin-bottom: .45rem;
}
.hero {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 2rem;
    padding: .2rem 0 1.35rem 0;
    border-bottom: 1px solid var(--ink);
}
.hero h1 {
    margin: 0;
    font-family: 'Playfair Display', Georgia, serif;
    font-style: italic;
    font-size: clamp(2.6rem, 5vw, 5.2rem);
    line-height: .92;
    font-weight: 500;
}
.hero-copy {
    max-width: 440px;
    color: var(--muted);
    font-size: .94rem;
    line-height: 1.55;
    padding-bottom: .25rem;
}
.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 1.2rem;
    margin-bottom: 1.4rem;
}
.brand {
    font-weight: 800;
    letter-spacing: -.04em;
    font-size: 1.05rem;
}
.brand-mark {
    display: inline-flex;
    width: 22px;
    height: 22px;
    align-items: center;
    justify-content: center;
    margin-right: .45rem;
    background: var(--lime);
    border-radius: 6px;
    font-size: .7rem;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: .45rem;
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: .35rem .65rem;
    background: rgba(251,250,246,.7);
    color: var(--muted);
    font-family: 'DM Mono', monospace;
    font-size: .64rem;
    text-transform: uppercase;
    letter-spacing: .06em;
}
.status-dot { width: 7px; height: 7px; background: #789A52; border-radius: 50%; }

.kpi-strip {
    display: grid;
    grid-template-columns: 1.2fr 1fr 1fr 1.25fr 1fr;
    gap: 0;
    border-top: 1px solid var(--ink);
    border-bottom: 1px solid var(--ink);
    margin: 1.45rem 0 2.2rem;
}
.kpi {
    min-height: 118px;
    padding: 1rem 1.15rem 1.05rem;
    border-right: 1px solid var(--line);
}
.kpi:last-child { border-right: 0; }
.kpi-label { font-family: 'DM Mono', monospace; font-size: .64rem; text-transform: uppercase; letter-spacing: .09em; color: var(--muted); }
.kpi-value { font-size: 2rem; font-weight: 600; letter-spacing: -.055em; margin-top: .35rem; }
.kpi-note { font-size: .72rem; color: var(--muted); margin-top: .18rem; }
.kpi-accent { background: var(--lime); }

.section-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    margin: 2rem 0 .8rem;
}
.section-head h2 { margin: 0; font-size: 1.35rem; }
.section-head span { color: var(--muted); font-family: 'DM Mono', monospace; font-size: .68rem; text-transform: uppercase; }

.active-filter-row {
    display:flex;
    flex-wrap:wrap;
    align-items:center;
    gap:.45rem;
    margin:.7rem 0 1.05rem;
}
.active-filter-label {
    font-family:'DM Mono',monospace;
    text-transform:uppercase;
    letter-spacing:.08em;
    font-size:.61rem;
    color:var(--muted);
    margin-right:.2rem;
}
.filter-chip {
    display:inline-flex;
    align-items:center;
    padding:.32rem .58rem;
    border:1px solid var(--ink);
    border-radius:999px;
    background:var(--lime);
    color:var(--ink);
    font-size:.68rem;
    font-weight:600;
}

.queue-wrap { border-top: 1px solid var(--ink); }
.queue-row {
    display: grid;
    grid-template-columns: 70px 1.15fr 1fr 115px 110px 130px;
    gap: 1rem;
    align-items: center;
    padding: .92rem .15rem;
    border-bottom: 1px solid var(--line);
    font-size: .82rem;
}
.queue-row:hover { background: rgba(215,255,69,.12); }
.queue-head { color: var(--muted); font-family: 'DM Mono', monospace; font-size: .62rem; text-transform: uppercase; letter-spacing: .07em; }
.case-no { font-family: 'DM Mono', monospace; color: var(--muted); }
.case-type { font-weight: 700; }
.case-customer { color: var(--muted); }
.money { font-family: 'DM Mono', monospace; font-weight: 500; }
.score { font-family: 'DM Mono', monospace; font-weight: 500; }
.badge {
    display: inline-block;
    padding: .28rem .52rem;
    border-radius: 999px;
    font-family: 'DM Mono', monospace;
    font-size: .62rem;
    white-space: nowrap;
}
.badge-p1 { background: var(--lime); color: var(--ink); }
.badge-p2 { background: var(--lavender); color: var(--ink); }
.badge-p3 { background: #E7E5DE; color: #4D4C47; }
.badge-open { border: 1px solid #BEBBB1; color: #55544E; }
.badge-investigating { background: var(--warm); color: var(--ink); }
.badge-resolved { background: var(--sage); color: var(--ink); }
.badge-dismissed { background: #E4E1DA; color: #6B6962; }

.case-hero {
    border-top: 1px solid var(--ink);
    border-bottom: 1px solid var(--ink);
    padding: 1.35rem 0;
    margin: 1.3rem 0 1.5rem;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 1.5rem;
    align-items: end;
}
.case-id { font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; }
.case-title { font-family: 'Playfair Display', Georgia, serif; font-style: italic; font-size: 2.7rem; line-height: 1; margin-top: .3rem; }
.case-sub { color: var(--muted); margin-top: .55rem; }
.case-score { text-align: right; }
.case-score-num { font-size: 3rem; font-weight: 600; letter-spacing: -.07em; }

.info-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 1rem 1.1rem;
    min-height: 120px;
}
.info-label { font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .08em; font-size: .61rem; color: var(--muted); }
.info-value { margin-top: .38rem; font-size: 1.2rem; font-weight: 600; letter-spacing: -.03em; }
.info-copy { margin-top: .4rem; color: var(--muted); font-size: .78rem; line-height: 1.45; }
.action-card { background: var(--lime); border-color: var(--ink); }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.detail-list { border-top: 1px solid var(--line); }
.detail-line { display: flex; justify-content: space-between; gap: 1rem; padding: .7rem 0; border-bottom: 1px solid var(--line); font-size: .82rem; }
.detail-line span:first-child { color: var(--muted); }
.detail-line span:last-child { text-align: right; font-weight: 600; }

.outcome-banner {
    background: var(--ink);
    color: var(--cream);
    padding: 1.25rem 1.4rem;
    border-radius: 14px;
    margin: 1.3rem 0 1.8rem;
}
.outcome-banner .big { font-size: 2.2rem; font-weight: 600; letter-spacing: -.055em; }
.outcome-banner .small { color: #A8A69F; font-size: .75rem; margin-top: .15rem; }

.note {
    border-left: 3px solid var(--lime);
    padding: .65rem .85rem;
    background: rgba(215,255,69,.12);
    color: #44433E;
    font-size: .78rem;
    line-height: 1.5;
}
.workflow-hint {
    margin: -.35rem 0 1.15rem;
    color: var(--muted);
    font-size: .82rem;
    line-height: 1.5;
}
.workflow-step {
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: .09em;
    font-size: .64rem;
    color: var(--muted);
    margin: 1.5rem 0 .45rem;
}

/* Interaction system: controls should look unmistakably actionable. */
.stSelectbox [data-baseweb="select"] {
    border:1px solid #AAA79E !important;
    border-radius:12px !important;
    min-height:48px;
    background:var(--panel) !important;
    box-shadow:0 2px 0 rgba(17,17,17,.05);
}
.stSelectbox [data-baseweb="select"]:hover { border-color:var(--ink) !important; }
.stSelectbox [data-baseweb="select"] svg { opacity:1 !important; width:19px !important; height:19px !important; }

.stNumberInput > div > div {
    border:1px solid #AAA79E !important;
    border-radius:12px !important;
    background:var(--panel) !important;
    overflow:hidden;
    box-shadow:0 2px 0 rgba(17,17,17,.05);
}
.stNumberInput input,
.stNumberInput input[type="number"] {
    background:var(--panel) !important;
    color:var(--ink) !important;
    -webkit-text-fill-color:var(--ink) !important;
    font-size:1rem !important;
}
.stNumberInput button {
    color:var(--ink) !important;
    background:var(--panel) !important;
    border-left:1px solid var(--line) !important;
}
.stNumberInput button:hover { background:var(--lime) !important; }

.stTextArea textarea, .stTextInput input {
    background:var(--panel) !important;
    border:1px solid #AAA79E !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color:var(--ink) !important;
    box-shadow:0 0 0 2px rgba(215,255,69,.55) !important;
}

/* Big editorial CTAs — these are actions, not decoration. */
.stButton button {
    transition:transform .15s ease, background .15s ease, border-color .15s ease, box-shadow .15s ease !important;
}
.stButton button[kind="primary"] {
    min-height:54px !important;
    padding:.85rem 1.6rem !important;
    border-radius:999px !important;
    font-size:.96rem !important;
    font-weight:700 !important;
    letter-spacing:.01em;
    box-shadow:5px 5px 0 var(--lime) !important;
}
.stButton button[kind="primary"]:hover {
    transform:translate(-3px,-3px) !important;
    box-shadow:8px 8px 0 var(--lime) !important;
}
.stButton button[kind="primary"]:active {
    transform:translate(0,0) !important;
    box-shadow:2px 2px 0 var(--lime) !important;
}

/* Ticket hand-off CTA: deliberately oversized so the next step is obvious. */
.ticket-cta {
    margin:1.25rem 0 .35rem;
    padding:1.25rem 1.35rem 1.05rem;
    border:1px solid var(--ink);
    border-radius:18px 18px 6px 6px;
    background:var(--lime);
}
.ticket-cta .ticket-kicker {
    font-family:'DM Mono',monospace;
    text-transform:uppercase;
    letter-spacing:.1em;
    font-size:.64rem;
    font-weight:500;
    margin-bottom:.3rem;
}
.ticket-cta .ticket-title {
    font-family:'Playfair Display',Georgia,serif;
    font-style:italic;
    font-size:1.7rem;
    line-height:1.05;
    margin-bottom:.25rem;
}
.ticket-cta .ticket-copy {
    font-size:.82rem;
    line-height:1.45;
    max-width:720px;
}
.ticket-cta-action .stButton button {
    min-height:62px !important;
    border-radius:6px 6px 18px 18px !important;
    width:100% !important;
    font-size:1.02rem !important;
    box-shadow:6px 6px 0 var(--ink) !important;
}
.ticket-cta-action .stButton button:hover {
    box-shadow:9px 9px 0 var(--ink) !important;
}
.ticket-cta-action .stButton button:active {
    box-shadow:2px 2px 0 var(--ink) !important;
}

.helper-chip {
    display:inline-flex;
    width:20px;
    height:20px;
    align-items:center;
    justify-content:center;
    border:1px solid #8C8A82;
    border-radius:50%;
    font-family:'DM Mono',monospace;
    font-size:.68rem;
    color:var(--ink);
    background:var(--panel);
    vertical-align:middle;
    margin-left:.28rem;
    cursor:help;
}
.page-intro {
    display:grid;
    grid-template-columns:minmax(0,1.2fr) minmax(260px,.8fr);
    gap:2rem;
    margin:1.25rem 0 2rem;
    padding:1.35rem 0 1.55rem;
    border-bottom:1px solid var(--ink);
}
.page-intro .intro-title {
    font-family:'Playfair Display',Georgia,serif;
    font-style:italic;
    font-size:2.55rem;
    line-height:1;
}
.page-intro .intro-copy {
    color:var(--ink);
    font-size:.98rem;
    line-height:1.55;
    align-self:end;
    max-width:620px;
}
.ticket-card {
    background:var(--ink);
    color:var(--cream);
    border-radius:14px;
    padding:1rem 1.1rem;
    margin-top:1rem;
}
.ticket-card .ticket-id {
    font-family:'DM Mono',monospace;
    font-size:.65rem;
    color:#AAA79F;
    text-transform:uppercase;
    letter-spacing:.08em;
}
.ticket-card .ticket-title { font-size:1.05rem; font-weight:700; margin:.3rem 0; }
.ticket-card .ticket-copy { font-size:.76rem; color:#C8C5BC; line-height:1.45; }
@media (max-width:900px) { .page-intro { grid-template-columns:1fr; } }

@media (max-width: 900px) {
    .block-container { padding: 1.4rem 1.1rem 3rem; }
    .hero { display: block; }
    .hero-copy { margin-top: 1rem; }
    .kpi-strip { grid-template-columns: 1fr 1fr; }
    .kpi { border-bottom: 1px solid var(--line); }
    .queue-row { grid-template-columns: 55px 1fr 100px; }
    .queue-row > :nth-child(3), .queue-row > :nth-child(5), .queue-row > :nth-child(6) { display: none; }
    .detail-grid { grid-template-columns: 1fr; }
}
</style>
""",
    unsafe_allow_html=True,
)


def conn():
    # Streamlit Cloud: use the hosted PostgreSQL URL from Secrets.
    # Local development: fall back to PG* environment variables.
    database_url = None
    try:
        database_url = st.secrets.get("DATABASE_URL")
    except Exception:
        database_url = None

    database_url = database_url or os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "exceptioniq"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


@st.cache_data(ttl=30)
def q(sql, params=None):
    with conn() as c:
        return pd.read_sql_query(sql, c, params=params)


def run(sql, params=None):
    with conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
        c.commit()


def ensure_ticket_table():
    run("""
        CREATE TABLE IF NOT EXISTS analytics.exception_tickets (
            ticket_id BIGSERIAL PRIMARY KEY,
            case_id BIGINT NOT NULL REFERENCES analytics.exception_cases(case_id) ON DELETE CASCADE,
            assigned_team TEXT NOT NULL,
            priority_band TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)


def money(value, decimals=0):
    if value is None or pd.isna(value):
        return "—"
    return f"${float(value):,.{decimals}f}"


def esc(value):
    return html.escape(str(value if value is not None else "—"))


def priority_badge(value):
    classes = {
        "P1 - Immediate": "badge-p1",
        "P2 - High": "badge-p2",
        "P3 - Routine": "badge-p3",
    }
    label = {"P1 - Immediate": "P1", "P2 - High": "P2", "P3 - Routine": "P3"}.get(value, value)
    return f'<span class="badge {classes.get(value, "badge-p3")}">{esc(label)}</span>'


def status_badge(value):
    cls = {
        "Open": "badge-open",
        "Investigating": "badge-investigating",
        "Resolved": "badge-resolved",
        "Dismissed": "badge-dismissed",
    }.get(value, "badge-open")
    return f'<span class="badge {cls}">{esc(value)}</span>'


def topbar():
    st.markdown(
        """
        <div class="topbar">
            <div class="brand"><span class="brand-mark">◆</span>EXCEPTIONIQ</div>
            <div class="status-pill"><span class="status-dot"></span>PostgreSQL · Meridian Supply Co.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(kicker, title, copy):
    st.markdown(
        f"""
        <div class="hero">
            <div>
                <div class="eyebrow">{esc(kicker)}</div>
                <h1>{esc(title)}</h1>
            </div>
            <div class="hero-copy">{esc(copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_head(title, meta=""):
    st.markdown(
        f'<div class="section-head"><h2>{esc(title)}</h2><span>{esc(meta)}</span></div>',
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Connection / global metrics
# -----------------------------------------------------------------------------
try:
    s = q(
        """
        SELECT
            COUNT(*) total_cases,
            COUNT(*) FILTER(WHERE status='Open') open_cases,
            COUNT(*) FILTER(WHERE status='Investigating') investigating_cases,
            COUNT(*) FILTER(WHERE status='Resolved') resolved_cases,
            COUNT(*) FILTER(WHERE status='Dismissed') dismissed_cases,
            ROUND(SUM(estimated_recoverable),2) estimated_recoverable,
            ROUND(SUM(actual_recovered),2) actual_recovered,
            ROUND(100*SUM(actual_recovered)/NULLIF(SUM(estimated_recoverable),0),2) recovery_rate,
            ROUND(AVG(EXTRACT(EPOCH FROM(resolved_at-opened_at))/86400)
                  FILTER(WHERE resolved_at IS NOT NULL),2) avg_resolution_days
        FROM analytics.exception_cases
        """
    ).iloc[0]
except Exception as e:
    st.error("Could not connect to PostgreSQL.")
    st.code(str(e))
    st.info("Set PGHOST, PGPORT, PGDATABASE, PGUSER and PGPASSWORD, then relaunch.")
    st.stop()

try:
    ensure_ticket_table()
except Exception:
    pass

# Correct definition: unresolved exposure is the recoverable value still attached to
# Open + Investigating cases, not total recoverable less total recovered.
unresolved_row = q(
    """
    SELECT COALESCE(SUM(estimated_recoverable),0) AS unresolved_exposure
    FROM analytics.exception_cases
    WHERE status IN ('Open','Investigating')
    """
).iloc[0]
unresolved_exposure = float(unresolved_row.unresolved_exposure or 0)

p1 = q(
    """
    SELECT COUNT(*) n
    FROM analytics.exception_cases
    WHERE priority_band='P1 - Immediate'
      AND status IN ('Open','Investigating')
    """
).iloc[0].n

# -----------------------------------------------------------------------------
# Sidebar navigation
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="font-size:.68rem;color:#8D8B84;font-family:'DM Mono',monospace;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.25rem;">Operational intelligence</div>
        <div style="font-family:'Playfair Display',Georgia,serif;font-style:italic;font-size:1.9rem;line-height:1.0;margin-bottom:1.6rem;">ExceptionIQ</div>
        """,
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Workspace",
        ["Action Center", "Investigation", "Resolution", "Outcomes"],
        label_visibility="collapsed",
    )
    st.markdown("<div style='height:1.1rem'></div>", unsafe_allow_html=True)
    if st.button("↻  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown(
        """
        <div style="position:fixed;bottom:1.2rem;color:#686760;font-family:'DM Mono',monospace;font-size:.6rem;line-height:1.55;">
            V1 · O2C EXCEPTION WORKFLOW<br>
            EXCEPTION → EVIDENCE → IMPACT<br>
            → PRIORITY → ACTION → OUTCOME
        </div>
        """,
        unsafe_allow_html=True,
    )


topbar()

# -----------------------------------------------------------------------------
# ACTION CENTER
# -----------------------------------------------------------------------------
if page == "Action Center":
    hero(
        "Action Center / 01",
        "Find what needs attention.",
        "A prioritized operational queue for exceptions that can affect revenue, cash, customer commitments, or billing accuracy.",
    )

    st.markdown(
        f"""
        <div class="kpi-strip">
            <div class="kpi kpi-accent"><div class="kpi-label">Unresolved exposure</div><div class="kpi-value">{money(unresolved_exposure)}</div><div class="kpi-note">Open + investigating recoverable value</div></div>
            <div class="kpi"><div class="kpi-label">Active cases</div><div class="kpi-value">{int(s.open_cases + s.investigating_cases):,}</div><div class="kpi-note">{int(s.open_cases):,} open · {int(s.investigating_cases):,} investigating</div></div>
            <div class="kpi"><div class="kpi-label">P1 cases</div><div class="kpi-value">{int(p1):,}</div><div class="kpi-note">Immediate priority</div></div>
            <div class="kpi"><div class="kpi-label">Recovered</div><div class="kpi-value">{money(s.actual_recovered)}</div><div class="kpi-note">Synthetic realized value</div></div>
            <div class="kpi"><div class="kpi-label">Recovery rate</div><div class="kpi-value">{float(s.recovery_rate or 0):.1f}%</div><div class="kpi-note">Actual / estimated recoverable</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="page-intro"><div class="intro-title">Find the work worth doing first.</div><div class="intro-copy">Start with the highest-priority cases. Filter the queue, then open a case to understand the evidence and decide the next operational step. <span class="helper-chip" title="Priority combines recoverable value, severity, recurrence, and detection confidence.">?</span></div></div>', unsafe_allow_html=True)

    a, b, c = st.columns([1, 1, 1.5])
    with a:
        status = st.selectbox("Status  ▾", ["All", "Open", "Investigating", "Resolved", "Dismissed"])
    with b:
        priority = st.selectbox("Priority  ▾", ["All", "P1 - Immediate", "P2 - High", "P3 - Routine"])
    types = q("SELECT DISTINCT exception_type FROM analytics.exception_cases ORDER BY 1")["exception_type"].tolist()
    with c:
        et = st.selectbox("Exception type  ▾", ["All"] + types)

    active_filters = []
    if status != "All":
        active_filters.append(f"Status · {status}")
    if priority != "All":
        active_filters.append(f"Priority · {priority}")
    if et != "All":
        active_filters.append(f"Exception · {et}")
    if active_filters:
        chips = "".join(f'<span class="filter-chip">{esc(x)}</span>' for x in active_filters)
        st.markdown(
            f'<div class="active-filter-row"><span class="active-filter-label">Active filters</span>{chips}</div>',
            unsafe_allow_html=True,
        )

    cases = q(
        """
        SELECT c.case_id,c.priority_band,c.priority_score,c.exception_type,
            cu.customer_name,c.severity,c.estimated_recoverable,c.recurrence_count_30d,
            c.status,c.recommended_action
        FROM analytics.exception_cases c
        LEFT JOIN core.customers cu ON cu.customer_id=c.customer_id
        WHERE (%s='All' OR c.status=%s)
          AND (%s='All' OR c.priority_band=%s)
          AND (%s='All' OR c.exception_type=%s)
        ORDER BY c.priority_score DESC,c.estimated_recoverable DESC
        """,
        (status, status, priority, priority, et, et),
    )

    section_head("Action queue", f"{len(cases):,} cases")

    if cases.empty:
        st.markdown('<div class="note">No cases match the current filters.</div>', unsafe_allow_html=True)
    else:
        rows = [
            '<div class="queue-row queue-head"><div>Case</div><div>Exception</div><div>Customer</div><div>Recoverable</div><div>Priority</div><div>Status</div></div>'
        ]
        for _, r in cases.head(80).iterrows():
            rows.append(
                f"""
                <div class="queue-row">
                    <div class="case-no">#{int(r.case_id):05d}</div>
                    <div><div class="case-type">{esc(r.exception_type)}</div><div class="case-customer">{esc(r.severity)} · {int(r.recurrence_count_30d)}× / 30d</div></div>
                    <div class="case-customer">{esc(r.customer_name or 'Unassigned customer')}</div>
                    <div class="money">{money(r.estimated_recoverable)}</div>
                    <div>{priority_badge(r.priority_band)} <span class="score">{float(r.priority_score):.0f}</span></div>
                    <div>{status_badge(r.status)}</div>
                </div>
                """
            )
        # Use Streamlit's native HTML renderer here. Markdown can terminate an HTML
        # block when the generated rows contain blank lines, which would expose the
        # markup as literal text. st.html keeps the queue as one rendered component.
        st.html('<div class="queue-wrap">' + "".join(rows) + "</div>")
        if len(cases) > 80:
            st.caption(f"Showing the first 80 of {len(cases):,} cases, ordered by priority and recoverable exposure.")

# -----------------------------------------------------------------------------
# INVESTIGATION
# -----------------------------------------------------------------------------
elif page == "Investigation":
    hero(
        "Investigation / 02",
        "Follow the evidence.",
        "Move from a detected exception to the exact records, fields, financial exposure, and observed contributing factors behind it.",
    )

    st.markdown('<div class="page-intro"><div class="intro-title">Understand before you act.</div><div class="intro-copy">Choose a case to see what happened, how much value is at stake, and the source records behind the exception. Use this page to gather enough context to make an operational decision.</div></div>', unsafe_allow_html=True)
    ids = q("SELECT case_id FROM analytics.exception_cases ORDER BY priority_score DESC, estimated_recoverable DESC")["case_id"].tolist()
    selected = st.selectbox("Choose a case  ▾", ids, format_func=lambda x: f"Case #{int(x):05d}")

    d = q(
        """
        SELECT c.*,cu.customer_name,cu.region,cu.segment,
               cf.factor_dimension,cf.factor_value,cf.interpretation
        FROM analytics.exception_cases c
        LEFT JOIN core.customers cu ON cu.customer_id=c.customer_id
        LEFT JOIN analytics.case_contributing_factors cf ON cf.case_id=c.case_id
        WHERE c.case_id=%s
        """,
        (int(selected),),
    )
    r = d.iloc[0]

    st.markdown(
        f"""
        <div class="case-hero">
            <div>
                <div class="case-id">Case #{int(r.case_id):05d} · {esc(r.source_table)}.{esc(r.source_record_id)}</div>
                <div class="case-title">{esc(r.exception_type)}</div>
                <div class="case-sub">{esc(r.customer_name or 'Customer unavailable')} · {esc(r.region or 'Region unavailable')} · {esc(r.segment or 'Segment unavailable')}</div>
            </div>
            <div class="case-score">
                <div>{priority_badge(r.priority_band)}</div>
                <div class="case-score-num">{float(r.priority_score):.0f}<span style="font-size:1rem;color:#77766F"> / 100</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="info-card"><div class="info-label">Gross exposure</div><div class="info-value">{money(r.gross_exposure,2)}</div><div class="info-copy">Full value at risk if the exception remains unresolved.</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="info-card"><div class="info-label">Estimated recoverable</div><div class="info-value">{money(r.estimated_recoverable,2)}</div><div class="info-copy">Expected recoverable portion used in prioritization.</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="info-card action-card"><div class="info-label">Recommended action</div><div class="info-value" style="font-size:1rem">{esc(r.recommended_action)}</div></div>', unsafe_allow_html=True)

    try:
        ticket_existing = q("SELECT ticket_id, assigned_team, status, created_at FROM analytics.exception_tickets WHERE case_id=%s ORDER BY created_at DESC LIMIT 1", (int(selected),))
    except Exception:
        ticket_existing = pd.DataFrame()
    if ticket_existing.empty:
        st.markdown(
            '''
            <div class="ticket-cta">
                <div class="ticket-kicker">Next operational step</div>
                <div class="ticket-title">Hand this case to the team.</div>
                <div class="ticket-copy">Create a lightweight work ticket with the case, priority and evidence context already attached. No copy-pasting into another system.</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="ticket-cta-action">', unsafe_allow_html=True)
        create_ticket = st.button("Create ticket  →  Assign this case", type="primary", use_container_width=True, key=f"create_ticket_{selected}")
        st.markdown('</div>', unsafe_allow_html=True)

        if create_ticket:
            st.session_state[f"ticket_form_{selected}"] = True

        if st.session_state.get(f"ticket_form_{selected}", False):
            st.markdown('<div class="workflow-step">Ticket details</div>', unsafe_allow_html=True)
            ta, tb = st.columns([1, 2])
            with ta:
                team = st.selectbox(
                    "Assigned team  ▾",
                    ["Collections", "Billing", "Fulfillment", "Account Management", "Finance"],
                    key=f"ticket_team_{selected}",
                    help="The operational team responsible for the next action.",
                )
            with tb:
                title = st.text_input(
                    "Ticket title",
                    value=f"{r.exception_type} · Case #{int(selected):05d}",
                    key=f"ticket_title_{selected}",
                )
            desc = st.text_area(
                "Ticket context",
                value=f"Case #{int(selected):05d}: {r.exception_type}. Estimated recoverable value: {money(r.estimated_recoverable,2)}. Recommended action: {r.recommended_action}",
                height=90,
                key=f"ticket_desc_{selected}",
            )
            save_ticket = st.button("Create and assign ticket  →", type="primary", use_container_width=True, key=f"save_ticket_{selected}")
            if save_ticket:
                run(
                    "INSERT INTO analytics.exception_tickets (case_id,assigned_team,priority_band,title,description) VALUES (%s,%s,%s,%s,%s)",
                    (int(selected), team, r.priority_band, title, desc),
                )
                st.session_state[f"ticket_form_{selected}"] = False
                st.cache_data.clear()
                st.success("Ticket created and linked to this case.")
                st.rerun()
    else:
        t=ticket_existing.iloc[0]
        st.markdown(f"<div class='ticket-card'><div class='ticket-id'>Ticket #{int(t.ticket_id):05d} · {esc(t.status)}</div><div class='ticket-title'>Assigned to {esc(t.assigned_team)}</div><div class='ticket-copy'>This case has already been handed off. The ticket remains linked to Case #{int(selected):05d}.</div></div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    x, y = st.columns(2)
    with x:
        section_head("What happened", "case context")
        st.markdown(
            f"""
            <div class="detail-list">
                <div class="detail-line"><span>Exception type</span><span>{esc(r.exception_type)}</span></div>
                <div class="detail-line"><span>Severity</span><span>{esc(r.severity)}</span></div>
                <div class="detail-line"><span>Detection confidence</span><span>{float(r.confidence):.0%}</span></div>
                <div class="detail-line"><span>30-day recurrence</span><span>{int(r.recurrence_count_30d)} occurrence(s)</span></div>
                <div class="detail-line"><span>Current status</span><span>{status_badge(r.status)}</span></div>
                <div class="detail-line"><span>Detected</span><span>{esc(r.detected_date)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with y:
        section_head("Financial impact", "value at stake")
        st.markdown(
            f"""
            <div class="detail-list">
                <div class="detail-line"><span>Gross exposure</span><span>{money(r.gross_exposure,2)}</span></div>
                <div class="detail-line"><span>Estimated recoverable</span><span>{money(r.estimated_recoverable,2)}</span></div>
                <div class="detail-line"><span>Actual recovered</span><span>{money(r.actual_recovered,2)}</span></div>
                <div class="detail-line"><span>Priority score</span><span>{float(r.priority_score):.0f} / 100</span></div>
                <div class="detail-line"><span>Priority band</span><span>{esc(r.priority_band)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    section_head("Evidence & lineage", "source traceability")
    ev = q(
        """
        SELECT related_table,related_record_id,field_name,expected_value,
               actual_value,delta_value,evidence_description
        FROM analytics.exception_evidence
        WHERE case_id=%s ORDER BY evidence_id
        """,
        (int(selected),),
    )
    st.dataframe(
        ev.rename(columns={
            "related_table": "Source table",
            "related_record_id": "Record",
            "field_name": "Field",
            "expected_value": "Expected",
            "actual_value": "Actual",
            "delta_value": "Delta",
            "evidence_description": "Evidence",
        }),
        use_container_width=True,
        hide_index=True,
    )

    section_head("Observed contributing factors", "association, not causation")
    fac = d[["factor_dimension", "factor_value", "interpretation"]].dropna(subset=["factor_dimension"]).drop_duplicates()
    if fac.empty:
        st.markdown('<div class="note">No contributing-factor record is available for this case.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(
            fac.rename(columns={"factor_dimension": "Dimension", "factor_value": "Observed value", "interpretation": "Interpretation"}),
            use_container_width=True,
            hide_index=True,
        )

# -----------------------------------------------------------------------------
# RESOLUTION
# -----------------------------------------------------------------------------
elif page == "Resolution":
    hero(
        "Resolution / 03",
        "Close the loop.",
        "Record what happened after investigation: action, resolution reason, status, and the value actually recovered.",
    )

    open_ = q(
        """
        SELECT case_id,exception_type,priority_band,priority_score,
               estimated_recoverable,status,recommended_action
        FROM analytics.exception_cases
        WHERE status IN ('Open','Investigating')
        ORDER BY priority_score DESC,estimated_recoverable DESC
        """
    )

    if open_.empty:
        st.success("No open or investigating cases.")
        st.stop()

    st.markdown('<div class="page-intro"><div class="intro-title">Turn the investigation into an outcome.</div><div class="intro-copy">Once a case has been reviewed, record what you did, what was decided, and how much value was actually recovered. This keeps the case history useful to the next person and feeds the outcomes view.</div></div>', unsafe_allow_html=True)
    selected = st.selectbox("Choose a case to update  ▾", open_.case_id.tolist(), format_func=lambda x: f"Case #{int(x):05d}")
    r = open_[open_.case_id == selected].iloc[0]

    st.markdown(
        f"""
        <div class="case-hero">
            <div>
                <div class="case-id">Case #{int(r.case_id):05d} · {status_badge(r.status)}</div>
                <div class="case-title">{esc(r.exception_type)}</div>
                <div class="case-sub">{esc(r.recommended_action)}</div>
            </div>
            <div class="case-score">
                <div>{priority_badge(r.priority_band)}</div>
                <div class="case-score-num">{money(r.estimated_recoverable)}</div>
                <div style="font-size:.68rem;color:#77766F">estimated recoverable</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="workflow-step">01 · Record the outcome</div>', unsafe_allow_html=True)
    a, b = st.columns([1, 1])
    with a:
        ns = st.selectbox("What is the new status?  ▾", ["Investigating", "Resolved", "Dismissed"], index=0 if r.status == "Open" else 0, help="Investigating = still being worked. Resolved = corrective action completed. Dismissed = reviewed and no action is required.")
        recovered = st.number_input(
            "How much was actually recovered?",
            min_value=0.0,
            max_value=float(r.estimated_recoverable),
            value=0.0,
            step=100.0,
            help=f"Enter the money actually recovered because of the intervention. The estimated recoverable amount for this case is {money(r.estimated_recoverable, 2)}.",
        )
    with b:
        st.markdown(f'<div class="info-card" style="min-height:145px"><div class="info-label">Value at stake</div><div class="info-value">{money(r.estimated_recoverable,2)}</div><div class="info-copy">This is the estimated amount the business could realistically recover. Your <b>actual recovered</b> amount should reflect what was really recovered, not this estimate.</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="workflow-step">02 · Tell the next person what happened</div>', unsafe_allow_html=True)
    a, b = st.columns([1, 1])
    with a:
        action = st.text_area("What action was taken?", height=120, placeholder="Example: Contacted the account owner and collections; payment follow-up initiated.")
    with b:
        reason = st.text_area("Why was the case resolved or dismissed?", height=120, placeholder="Example: Customer paid $8,500; remaining balance escalated to collections.")

    st.markdown(
        '<div class="note"><b>Simple rule:</b> status tells us where the case is, action tells us what we did, reason tells us what happened, and actual recovered tells us the value we got back.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="detail-line" style="margin-top:1rem"><span>Estimated recoverable</span><span>{money(r.estimated_recoverable,2)}</span></div><div class="detail-line"><span>Actual recovered entered</span><span>{money(recovered,2)}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    if st.button("Save case update →", type="primary"):
        run(
            """
            UPDATE analytics.exception_cases
            SET status=%s,
                action_taken=%s,
                resolution_reason=%s,
                actual_recovered=%s,
                resolved_at=CASE
                    WHEN %s IN ('Resolved','Dismissed') THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END
            WHERE case_id=%s
            """,
            (ns, action or None, reason or None, recovered, ns, int(selected)),
        )
        st.cache_data.clear()
        st.success(f"Case {selected} updated.")
        st.rerun()

# -----------------------------------------------------------------------------
# OUTCOMES
# -----------------------------------------------------------------------------
else:
    hero(
        "Outcomes / 04",
        "Measure what changed.",
        "See realized recovery, resolution speed, exception mix, and the observed patterns behind recurring operational issues.",
    )

    st.markdown(
        f"""
        <div class="kpi-strip">
            <div class="kpi"><div class="kpi-label">Total cases</div><div class="kpi-value">{int(s.total_cases):,}</div><div class="kpi-note">All detected cases</div></div>
            <div class="kpi"><div class="kpi-label">Estimated recoverable</div><div class="kpi-value">{money(s.estimated_recoverable)}</div><div class="kpi-note">Total expected recovery pool</div></div>
            <div class="kpi kpi-accent"><div class="kpi-label">Actual recovered</div><div class="kpi-value">{money(s.actual_recovered)}</div><div class="kpi-note">Realized value in the demo</div></div>
            <div class="kpi"><div class="kpi-label">Recovery rate</div><div class="kpi-value">{float(s.recovery_rate or 0):.1f}%</div><div class="kpi-note">Actual / estimated</div></div>
            <div class="kpi"><div class="kpi-label">Avg resolution</div><div class="kpi-value">{f'{float(s.avg_resolution_days):.1f}d' if s.avg_resolution_days is not None else '—'}</div><div class="kpi-note">Resolved / dismissed cases</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="page-intro"><div class="intro-title">See what changed.</div><div class="intro-copy">Review what was recovered, how quickly cases were closed, what remains unresolved, and which exception patterns continue to consume attention.</div></div>', unsafe_allow_html=True)

    outcome_status = q(
        """
        SELECT status, COUNT(*) cases, ROUND(SUM(estimated_recoverable),2) exposure
        FROM analytics.exception_cases
        GROUP BY status
        ORDER BY CASE status WHEN 'Open' THEN 1 WHEN 'Investigating' THEN 2 WHEN 'Resolved' THEN 3 WHEN 'Dismissed' THEN 4 END
        """
    )
    unresolved = outcome_status[outcome_status.status.isin(["Open", "Investigating"])]
    unresolved_cases = int(unresolved.cases.sum()) if not unresolved.empty else 0
    st.markdown(
        f"""
        <div class="outcome-banner">
            <div class="big">{money(unresolved.exposure.sum() if not unresolved.empty else 0)}</div>
            <div class="small">still attached to {unresolved_cases:,} open or investigating cases · this is the Action Center unresolved exposure measure</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_head("Outcome performance by exception type", "realized value")
    perf = q(
        """
        SELECT exception_type,COUNT(*) cases,
            COUNT(*) FILTER(WHERE status='Resolved') resolved_cases,
            COUNT(*) FILTER(WHERE status='Dismissed') dismissed_cases,
            ROUND(SUM(estimated_recoverable),2) estimated_recoverable,
            ROUND(SUM(actual_recovered),2) actual_recovered,
            ROUND(100*SUM(actual_recovered)/NULLIF(SUM(estimated_recoverable),0),2) recovery_rate_pct,
            ROUND(AVG(EXTRACT(EPOCH FROM(resolved_at-opened_at))/86400)
                  FILTER(WHERE resolved_at IS NOT NULL),2) avg_resolution_days
        FROM analytics.exception_cases
        GROUP BY exception_type
        ORDER BY estimated_recoverable DESC
        """
    )
    st.dataframe(
        perf.rename(columns={
            "exception_type": "Exception",
            "cases": "Cases",
            "resolved_cases": "Resolved",
            "dismissed_cases": "Dismissed",
            "estimated_recoverable": "Estimated recoverable",
            "actual_recovered": "Actual recovered",
            "recovery_rate_pct": "Recovery rate %",
            "avg_resolution_days": "Avg resolution days",
        }),
        use_container_width=True,
        hide_index=True,
    )

    section_head("Observed contributing factors", "not causal root-cause claims")
    st.dataframe(
        q(
            """
            SELECT exception_type,factor_dimension,factor_value,cases,
                estimated_recoverable,case_share_pct,exposure_share_pct
            FROM analytics.contributing_factor_summary
            ORDER BY exception_type,case_share_pct DESC
            """
        ).rename(columns={
            "exception_type": "Exception",
            "factor_dimension": "Dimension",
            "factor_value": "Observed value",
            "cases": "Cases",
            "estimated_recoverable": "Estimated recoverable",
            "case_share_pct": "Case share %",
            "exposure_share_pct": "Exposure share %",
        }),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown(
        '<div class="note">Contributing factors are observed associations in the synthetic environment, not causal root-cause claims. Outcome values are synthetic demo results, not real Meridian business performance.</div>',
        unsafe_allow_html=True,
    )
