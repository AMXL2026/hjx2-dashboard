"""
HJX2 Jacksonville DS — Weekly Dashboard (Streamlit Cloud version)
Data lives in the data/ folder — push updated CSVs to refresh.
"""
import streamlit as st
import pandas as pd
import datetime, csv, io, os
from pathlib import Path
from collections import defaultdict

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HJX2 Jacksonville Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

STATION     = 'HJX2'
STATION_CITY = 'Jacksonville, FL'
DATA_DIR     = Path(__file__).parent / 'data'
SVC_CSV      = DATA_DIR / 'service_time_weekly.csv'
STAR_CSV     = DATA_DIR / 'star_rating_weekly.csv'
URR_CSV      = DATA_DIR / 'iaq_urr_raw.csv'
FB_CSV       = DATA_DIR / 'star_nfpr_raw.csv'

# ── Password ───────────────────────────────────────────────────────────────────
def check_password():
    if st.session_state.get("authenticated"):
        return True
    st.markdown("### 🔐 HJX2 Jacksonville Dashboard")
    pw = st.text_input("Password", type="password", key="pw_input")
    if st.button("Login"):
        if pw == "Jacksonville":
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False

if not check_password():
    st.stop()

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.section-hdr{font-size:1.1rem;font-weight:700;color:#005EB8;border-bottom:2px solid #005EB8;padding-bottom:4px;margin-bottom:12px}
.update-banner{background:#005EB8;color:#fff;padding:6px 14px;border-radius:8px;font-size:.85rem;margin-bottom:10px}
[data-testid="stMetricValue"]{font-size:1.4rem!important;font-weight:700!important}
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
def parse_visuals(fp):
    if not Path(fp).exists():
        return {}
    visuals, cid, rows, hdr = {}, None, [], None
    with open(fp, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if line.startswith('# visual '):
                if cid and hdr: visuals[cid] = {'header': hdr, 'rows': rows}
                cid, rows, hdr = line[9:].strip(), [], None
            elif not line.strip(): continue
            elif hdr is None: hdr = line.split(',')
            else:
                for row in csv.reader(io.StringIO(line)): rows.append(row)
    if cid and hdr: visuals[cid] = {'header': hdr, 'rows': rows}
    return visuals

def week_to_date(label):
    try:
        yr, wk = int(str(label)[:4]), int(str(label)[5:])
        # Weeks run Sun-Sat
        return datetime.date.fromisocalendar(yr, wk, 1) - datetime.timedelta(days=1)
    except: return None

def month_to_date(label):
    try: return datetime.date.fromisoformat(str(label)[:7] + '-01')
    except: return None

def rolling_cutoffs(period, c_start=None, c_end=None):
    today = datetime.date.today()
    if period == "Last week":
        _days_since_sun = (today.weekday() + 1) % 7
        _this_sun = today - datetime.timedelta(days=_days_since_sun)
        _last_sun = _this_sun - datetime.timedelta(days=7)
        return _last_sun, _last_sun + datetime.timedelta(days=6)
    if period == "Last 4 weeks":   return today - datetime.timedelta(weeks=4),   today
    if period == "Last 8 weeks":   return today - datetime.timedelta(weeks=8),   today
    if period == "Last 3 months":  return today - datetime.timedelta(days=91),   today
    if period == "Last 6 months":  return today - datetime.timedelta(days=183),  today
    if period == "Last 12 months": return today - datetime.timedelta(days=365),  today
    if period == "Custom range":   return c_start or today - datetime.timedelta(weeks=8), c_end or today
    return today - datetime.timedelta(weeks=8), today

# ── Color helpers ──────────────────────────────────────────────────────────────
def svc_color(val, seca):
    if pd.isna(val): return ''
    if seca == 'ROC':
        if val <= 7:  return 'background-color:#70AD47;color:#fff;font-weight:700'
        if val <= 8:  return 'background-color:#FF8C00;color:#fff;font-weight:700'
        return 'background-color:#C00000;color:#fff;font-weight:700'
    else:
        if val <= 10: return 'background-color:#70AD47;color:#fff;font-weight:700'
        if val <= 11: return 'background-color:#FF8C00;color:#fff;font-weight:700'
        return 'background-color:#C00000;color:#fff;font-weight:700'

def star_color(val):
    if pd.isna(val): return ''
    if val >= 5:  return 'background-color:#00703C;color:#fff;font-weight:700'
    if val >= 4:  return 'background-color:#70AD47;color:#fff;font-weight:700'
    if val >= 3:  return 'background-color:#FF8C00;color:#fff;font-weight:700'
    return 'background-color:#C00000;color:#fff;font-weight:700'

def urr_color(val):
    if pd.isna(val): return ''
    if val < 8:   return 'background-color:#00703C;color:#fff;font-weight:700'
    if val <= 10: return 'background-color:#FF8C00;color:#fff;font-weight:700'
    return 'background-color:#C00000;color:#fff;font-weight:700'

# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_service_time():
    svc = parse_visuals(SVC_CSV)
    rows = []
    for vid, data in svc.items():
        for row in data.get('rows', []):
            if len(row) < 6: continue
            s_dsp, seca, tgt, week, act, cnt = row[0], row[1], row[2], row[3], row[4], row[5]
            stn = s_dsp.split(' - ')[0].strip()
            if stn != STATION: continue
            try:
                rows.append({
                    'Station': stn, 'DSP': s_dsp,
                    'Metric': 'ROC' if seca == 'D:R' else 'DDU',
                    'Target': float(tgt), 'Week': week,
                    'Actual': round(float(act), 2), 'Pkgs': int(cnt),
                    'WkDate': week_to_date(week)
                })
            except: pass
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False)
def load_star_rating():
    star = parse_visuals(STAR_CSV)
    rows, net = [], []
    for vid, data in star.items():
        for row in data.get('rows', []):
            if len(row) < 4: continue
            try:
                week = row[0]
                rows.append({
                    'Week': week, 'Reviews': int(row[1]),
                    'Avg Rating': round(float(row[2]), 2),
                    '1-Star %': round(float(row[3]) * 100, 1),
                    'WkDate': week_to_date(week)
                })
            except: pass
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False)
def load_urr():
    urr = parse_visuals(URR_CSV)
    stn_rows, trend = [], []
    for vid, data in urr.items():
        for row in data.get('rows', []):
            if len(row) < 5: continue
            try:
                stn_rows.append({
                    'DSP': row[0], 'Station': row[1] if len(row) > 5 else STATION,
                    'Deliveries': int(row[2]), 'URR %': round(float(row[3]) * 100, 1),
                    'Undeliverable': int(row[4])
                })
            except: pass
    return pd.DataFrame(stn_rows)

@st.cache_data(show_spinner=False)
def load_feedback():
    fb = parse_visuals(FB_CSV)
    comments, summary = [], []
    for vid, data in fb.items():
        for row in data.get('rows', []):
            if len(row) < 5: continue
            try:
                comments.append({
                    'DSP': row[0], 'Service': row[1],
                    'Stars': int(float(row[4])) if len(row) > 4 else 0,
                    'Comment': row[3] if len(row) > 3 else ''
                })
            except: pass
    return pd.DataFrame(comments)

def data_age():
    for f in [SVC_CSV, STAR_CSV, URR_CSV, FB_CSV]:
        if f.exists():
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f))
            return mtime.strftime('%Y-%m-%d %H:%M')
    return 'No data loaded yet'

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📦 HJX2 Jacksonville")
    st.caption("Weekly Performance Dashboard")
    st.divider()
    st.markdown("**📅 Time Period**")
    today_default = datetime.date.today()
    period = st.selectbox("Period", [
        "Last week", "Last 4 weeks", "Last 8 weeks",
        "Last 3 months", "Last 6 months", "Last 12 months", "Custom range"
    ], index=1)
    c_start = c_end = None
    if period == "Custom range":
        c_start = st.date_input("From", today_default - datetime.timedelta(weeks=8), max_value=today_default)
        c_end   = st.date_input("To",   today_default, max_value=today_default)

    start_dt, end_dt = rolling_cutoffs(period, c_start, c_end)
    st.caption(f"Showing: {start_dt.strftime('%b %d')} → {end_dt.strftime('%b %d, %Y')}")
    st.divider()
    st.markdown("**📊 Service Metrics**")
    show_roc = st.checkbox("ROC", value=True)
    show_ddu = st.checkbox("DDU", value=True)
    sel_metrics = [m for m, v in [('ROC', show_roc), ('DDU', show_ddu)] if v] or ['ROC', 'DDU']
    st.divider()
    st.info(f"📅 Data last updated:\n**{data_age()}**\n\nTo refresh: update CSVs in GitHub repo and push.")
    st.divider()
    st.caption("Thresholds:\nROC ≤7🟢 7–8🟠 >8🔴\nDDU ≤10🟢 10–11🟠 >11🔴\n5★🟢 4★🟩 ≤3★🔴\nURR <8%🟢 8–10%🟠 >10%🔴")

# ── HEADER ─────────────────────────────────────────────────────────────────────
today  = datetime.date.today()
wk_lbl = f"{today.isocalendar()[0]}-{today.isocalendar()[1]:02d}"
st.markdown(
    f"## 📦 HJX2 Jacksonville DS &nbsp;<span style='background:#005EB8;color:#fff;"
    f"border-radius:16px;padding:3px 14px;font-size:14px'>WK {wk_lbl}</span>",
    unsafe_allow_html=True
)
st.markdown(
    f'<div class="update-banner">📅 Period: <b>{period}</b> &nbsp;|&nbsp; '
    f'{start_dt.strftime("%b %d")} -> {end_dt.strftime("%b %d, %Y")} &nbsp;|&nbsp; Data: {data_age()}</div>',
    unsafe_allow_html=True
)

# ── LOAD & FILTER ──────────────────────────────────────────────────────────────
with st.spinner("Loading data..."):
    df_svc_raw  = load_service_time()
    df_star_raw = load_star_rating()
    df_urr_raw  = load_urr()
    df_fb_raw   = load_feedback()

def fw(df):
    if df.empty or 'WkDate' not in df.columns: return df
    mask = (df['WkDate'] >= start_dt) & (df['WkDate'] <= end_dt)
    return df[mask].copy()

df_svc  = fw(df_svc_raw)
df_svc  = df_svc[df_svc['Metric'].isin(sel_metrics)] if not df_svc.empty else df_svc
df_star = fw(df_star_raw)

# ── KPIs ───────────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

if not df_svc.empty:
    red_n = df_svc.apply(lambda r: (r['Metric'] == 'ROC' and r['Actual'] > 8) or
                                   (r['Metric'] == 'DDU' and r['Actual'] > 11), axis=1).sum()
    k1.metric("🔴 In Red (Svc)", f"{int(red_n)}", delta=f"{len(df_svc)-int(red_n)} green", delta_color="normal")
else:
    k1.metric("🔴 In Red (Svc)", "—")

if not df_star.empty:
    k2.metric("⭐ Avg Rating", f"{df_star['Avg Rating'].mean():.2f}")
else:
    k2.metric("⭐ Avg Rating", "—")

if not df_urr_raw.empty:
    urr_val = round(df_urr_raw['Undeliverable'].sum() / df_urr_raw['Deliveries'].sum() * 100, 1) if df_urr_raw['Deliveries'].sum() > 0 else 0
    k3.metric("📦 URR", f"{urr_val:.1f}%")
else:
    k3.metric("📦 URR", "—")

if not df_fb_raw.empty:
    k4.metric("💬 NFPR Comments", f"{len(df_fb_raw)}")
else:
    k4.metric("💬 NFPR Comments", "—")

st.divider()

# ── TABS ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 Service Time", "⭐ 5-Star Rating", "📦 URR", "💬 Customer Feedback"])

# ── TAB 1: SERVICE TIME ────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-hdr">Service Time by DSP</div>', unsafe_allow_html=True)
    if df_svc.empty:
        st.info("No service time data for this period. Push updated CSVs to GitHub to refresh.")
    else:
        for metric in sel_metrics:
            df_m = df_svc[df_svc['Metric'] == metric].copy()
            if df_m.empty: continue
            threshold = 7 if metric == 'ROC' else 10
            st.markdown(f"**{metric}** (threshold {threshold} min)")
            pivot = df_m.pivot_table(index='DSP', columns='Week', values='Actual', aggfunc='mean').round(2)
            styled = pivot.style.map(lambda v: svc_color(v, metric))
            st.dataframe(styled, use_container_width=True)

            # Trend chart
            import plotly.express as px
            df_trend = df_m.dropna(subset=['WkDate']).sort_values('WkDate')
            if not df_trend.empty:
                fig = px.line(df_trend, x='Week', y='Actual', color='DSP', markers=True,
                              title=f'{metric} Service Time Trend',
                              labels={'Actual': 'Avg (min)', 'Week': 'Week'})
                fig.add_hline(y=threshold, line_dash='dash', line_color='red',
                              annotation_text=f'Threshold {threshold} min')
                fig.update_layout(height=300, plot_bgcolor='#f8f9fa', paper_bgcolor='#fff')
                st.plotly_chart(fig, use_container_width=True)
            st.markdown("---")

# ── TAB 2: STAR RATING ─────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-hdr">5-Star Rating Trend</div>', unsafe_allow_html=True)
    if df_star.empty:
        st.info("No star rating data for this period. Push updated CSVs to GitHub to refresh.")
    else:
        import plotly.express as px
        fig = px.line(df_star.sort_values('WkDate'), x='Week', y='Avg Rating', markers=True,
                      title='HJX2 Weekly Average Rating',
                      labels={'Avg Rating': 'Avg Rating', 'Week': 'Week'})
        fig.add_hline(y=4.0, line_dash='dash', line_color='orange', annotation_text='4★ target')
        fig.update_layout(height=350, yaxis=dict(range=[1, 5]))
        st.plotly_chart(fig, use_container_width=True)

        # Table
        display = df_star[['Week', 'Avg Rating', 'Reviews', '1-Star %']].sort_values('Week', ascending=False)
        styled = display.style.map(star_color, subset=['Avg Rating'])
        st.dataframe(styled, use_container_width=True, hide_index=True)

# ── TAB 3: URR ─────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-hdr">Undeliverable Rate (URR) by DSP</div>', unsafe_allow_html=True)
    if df_urr_raw.empty:
        st.info("No URR data available. Push updated CSVs to GitHub to refresh.")
    else:
        styled = df_urr_raw.style.map(urr_color, subset=['URR %'])
        st.dataframe(styled, use_container_width=True, hide_index=True)

# ── TAB 4: CUSTOMER FEEDBACK ───────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-hdr">Customer Feedback (NFPR)</div>', unsafe_allow_html=True)
    if df_fb_raw.empty:
        st.info("No feedback data available. Push updated CSVs to GitHub to refresh.")
    else:
        st.dataframe(df_fb_raw, use_container_width=True, hide_index=True)
