"""
ui_components.py — HTML/CSS блоки и компоненты Streamlit.
Без бизнес-логики.
"""
import streamlit as st
import pandas as pd


STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #f7fafc; color: #172033; }
.main .block-container { padding-top: 1.5rem; }

div[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e3e8f0;
}
div[data-testid="stSidebar"] .stMarkdown p {
    color: #64748b;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.kpi { 
    background: #ffffff;
    border: 1px solid #e1e7ef;
    border-radius: 10px;
    padding: 16px 18px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}
.kpi::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
}
.kpi.teal::before  { background: linear-gradient(90deg, #4fd1c5, #38b2ac); }
.kpi.blue::before  { background: linear-gradient(90deg, #667eea, #764ba2); }
.kpi.amber::before { background: linear-gradient(90deg, #f6ad55, #ed8936); }
.kpi.red::before   { background: linear-gradient(90deg, #fc8181, #e53e3e); }
.kpi.green::before { background: linear-gradient(90deg, #68d391, #48bb78); }

.kpi-val {
    font-family: 'Unbounded', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 6px;
}
.kpi.teal  .kpi-val { color: #4fd1c5; }
.kpi.blue  .kpi-val { color: #818cf8; }
.kpi.amber .kpi-val { color: #f6ad55; }
.kpi.red   .kpi-val { color: #fc8181; }
.kpi.green .kpi-val { color: #68d391; }

.kpi-label { font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; }
.kpi-sub   { font-size: 0.78rem; color: #94a3b8; margin-top: 3px; }

/* Section headers */
.sec { 
    font-family: 'Unbounded', sans-serif;
    font-size: 0.85rem;
    color: #0f766e;
    border-left: 2px solid #14b8a6;
    padding-left: 10px;
    margin: 20px 0 12px 0;
    letter-spacing: 0.04em;
}

/* District bars */
.district-row { padding: 10px 0; border-bottom: 1px solid #e6edf5; }
.district-name { font-size: 0.84rem; color: #243047; font-weight: 600; }
.district-bar-bg { background: #e8eef6; border-radius: 3px; height: 5px; margin: 5px 0; }
.district-meta { font-size: 0.72rem; color: #64748b; }

/* Funnel bars */
.funnel-row { display: flex; align-items: center; gap: 10px; margin: 4px 0; }
.funnel-label { width: 48px; font-size: 0.75rem; color: #64748b; font-family: 'IBM Plex Mono', monospace; }
.funnel-bar-bg { flex: 1; background: #e8eef6; border-radius: 2px; height: 5px; }
.funnel-pct { width: 40px; font-size: 0.75rem; text-align: right; font-family: 'IBM Plex Mono', monospace; }

/* Recommend table */
.rec-row {
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #e6edf5;
    gap: 12px;
}
.rec-rank {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    color: #e879f9;
    width: 24px;
}
.rec-gain {
    font-family: 'Unbounded', sans-serif;
    font-size: 0.85rem;
    color: #e879f9;
    font-weight: 600;
}
.rec-coords { font-size: 0.72rem; color: #64748b; font-family: 'IBM Plex Mono', monospace; }
.summary-strip {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin: 0 0 14px 0;
}
.summary-pill {
    background:#ffffff;
    border:1px solid #e1e7ef;
    border-radius:999px;
    padding:7px 12px;
    color:#243047;
    font-size:0.76rem;
}
.summary-pill strong {
    color:#0f766e;
    font-weight:600;
}
</style>
"""


def inject_styles():
    st.markdown(STYLES, unsafe_allow_html=True)


def render_header(total_kg: int):
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <h1 style="font-family:'Unbounded',sans-serif; font-size:1.5rem; margin:0;
            background:linear-gradient(90deg,#4fd1c5 0%,#818cf8 60%,#e879f9 100%);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            Доступность детских садов
        </h1>
    </div>
    """, unsafe_allow_html=True)


def render_filter_summary(
    selected_rayons: list[str],
    selected_types: list[str],
    visible_kg: int,
    total_population: float,
):
    rayon_label = ", ".join(selected_rayons[:2])
    if len(selected_rayons) > 2:
        rayon_label += f" +{len(selected_rayons) - 2}"

    type_label = ", ".join(selected_types[:2])
    if len(selected_types) > 2:
        type_label += f" +{len(selected_types) - 2}"

    st.markdown(f"""
    <div class="summary-strip">
        <div class="summary-pill"><strong>Районы:</strong> {rayon_label or "не выбраны"}</div>
        <div class="summary-pill"><strong>Типы:</strong> {type_label or "не выбраны"}</div>
        <div class="summary-pill"><strong>Садов на карте:</strong> {visible_kg}</div>
        <div class="summary-pill"><strong>Жителей:</strong> {int(total_population):,}</div>
    </div>
    """, unsafe_allow_html=True)


def render_kpi(metrics: dict, radius: int, preschool_pct: float):
    m = metrics
    cols = st.columns(6)
    median_dist = f"{m['median_dist']} м" if m["median_dist"] is not None else "—"

    cards = [
        ("blue",  f"{int(m['total_pop']):,}", "Жителей", "almaty_clip.tif"),
        ("teal",  f"{m['access_pct']:.1f}%",     "Доступность",    f"в радиусе {radius} м"),
        ("green", str(m["total_kg"]),             "Детских садов",  f"{m['paid_kg']} платных"),
        ("amber", f"{m['total_preschool']:,.0f}".replace(",", " "), "Дошкольников", f"{preschool_pct}% от жителей"),
        ("red",   median_dist,                    "Медиана пути",   "до ближ. сада"),
        ("green", f"{m['uncovered_pop']:,.0f}".replace(",", " "), "Без доступа", f">{radius} м до сада"),
    ]

    for col, (cls, val, label, sub) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div class="kpi {cls}">
                <div class="kpi-val">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """, unsafe_allow_html=True)


def render_district_bars(ds: pd.DataFrame, radius: int):
    st.markdown('<div class="sec">По районам</div>', unsafe_allow_html=True)
    if ds.empty:
        st.caption("Нет данных по районам для текущих фильтров.")
        return

    for row in ds.sort_values("access_pct", ascending=False).itertuples():
        pct = row.access_pct
        color = "#48bb78" if pct >= 97 else "#f6ad55" if pct >= 90 else "#fc8181"
        median_dist = "—" if pd.isna(row.median_dist) else f"{int(row.median_dist)} м"
        st.markdown(f"""
        <div class="district-row">
            <div style="display:flex;justify-content:space-between;">
                <span class="district-name">{row.RAYON}</span>
                <span style="font-size:0.84rem;color:{color};font-weight:700;">{pct:.1f}%</span>
            </div>
            <div class="district-bar-bg">
                <div style="width:{pct}%;height:5px;border-radius:3px;background:{color};"></div>
            </div>
            <div class="district-meta">
                🏫 {row.kg_count} садов &nbsp;·&nbsp;
                👥 {int(row.population/1000)}к чел &nbsp;·&nbsp;
                ↔ {median_dist} медиана
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_funnel(pop, dists, total_pop: int, current_radius: int):
    st.markdown('<div class="sec">Охват по радиусам</div>', unsafe_allow_html=True)
    if total_pop <= 0 or len(dists) == 0:
        st.caption("Недостаточно данных для расчёта охвата.")
        return

    thresholds = [(300, "300м"), (500, "500м"), (750, "750м"),
                  (1000, "1 км"), (1500, "1.5км"), (2000, "2 км")]
    for r_val, label in thresholds:
        pct = (dists <= r_val).sum() / len(dists) * 100  # по ячейкам
        # взвешенное по населению
        pct_w = pop["population"].values[dists <= r_val].sum() / total_pop * 100
        active = r_val == current_radius
        color  = "#14b8a6" if active else "#cbd5e1"
        text_c = "#0f766e" if active else "#64748b"
        st.markdown(f"""
        <div class="funnel-row">
            <span class="funnel-label" style="color:{text_c};">{label}</span>
            <div class="funnel-bar-bg">
                <div style="width:{pct_w:.1f}%;height:5px;border-radius:2px;background:{color};"></div>
            </div>
            <span class="funnel-pct" style="color:{text_c};">{pct_w:.1f}%</span>
        </div>
        """, unsafe_allow_html=True)


def render_recommendations(rec: pd.DataFrame):
    if rec is None or len(rec) == 0:
        st.info("Нет рекомендаций — все зоны покрыты!")
        return

    st.markdown('<div class="sec">Новые сады</div>', unsafe_allow_html=True)

    for row in rec.itertuples():
        helped_people = getattr(row, "helped_people", 0)
        helped_addr_count = getattr(row, "helped_addr_count", 0)
        addr_id = getattr(row, "addr_id", "")
        st.markdown(f"""
        <div class="rec-row">
            <span class="rec-rank">#{row.rank}</span>
            <div style="flex:1;">
                <div class="rec-gain">~{int(helped_people):,} чел.</div>
                <div class="rec-coords">ID {addr_id} · {getattr(row, "rayon", "")} · {helped_addr_count} адресов · {row.lat:.5f}, {row.lon:.5f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_detail_table(ds: pd.DataFrame):
    st.markdown('<div class="sec">Детальная таблица</div>', unsafe_allow_html=True)
    if ds.empty:
        st.caption("Таблица пуста для текущих фильтров.")
        return

    disp = ds[["RAYON", "population", "kg_count", "preschool", "kids_per_kg",
               "access_pct", "median_dist"]].copy()
    disp.columns = ["Район", "Население", "Садов",
                    "Дошкольников", "Детей/сад", "Доступ %", "Медиана (м)"]
    disp["Население"]    = disp["Население"].apply(lambda x: f"{int(x):,}".replace(",", " "))
    disp["Дошкольников"] = disp["Дошкольников"].apply(lambda x: f"{int(x):,}".replace(",", " "))
    disp["Доступ %"]     = disp["Доступ %"].apply(lambda x: f"{x:.1f}%")
    disp["Медиана (м)"]  = disp["Медиана (м)"].apply(lambda x: "—" if pd.isna(x) else int(x))
    st.dataframe(disp, width="stretch", hide_index=True)
