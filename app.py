"""
app.py — точка входа, только оркестрация.

Запуск:
    streamlit run app.py
"""
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import data_engine as de
import map_builder  as mb
import ui_components as ui

st.set_page_config(
    page_title="Доступность детских садов — Алматы",
    page_icon="🏫",
    layout="wide",
)
ui.inject_styles()

# ── загрузка сырых данных (один раз) ─────────────────────────────────
@st.cache_data
def _load(pop_source_stamp: tuple[str, int, int]):
    return de.load_raw()


@st.cache_data
def _recommendations_csv(rec_records: tuple[tuple, ...]) -> bytes:
    if not rec_records:
        return b""
    rec_df = pd.DataFrame(
        rec_records,
        columns=["rank", "addr_id", "rayon", "lat", "lon", "helped_people", "gain_preschool", "helped_addr_count"],
    )
    return rec_df.to_csv(index=False).encode("utf-8-sig")

pop_raw, kg_raw = _load(de.population_source_stamp())

# ── сайдбар ───────────────────────────────────────────────────────────
with st.sidebar:
    radius = st.select_slider(
        "Радиус доступности",
        options=[300, 500, 750, 1000, 1500, 2000],
        value=1000,
        format_func=lambda x: f"{x} м",
    )
    n_rec = st.slider("Новых садов", min_value=0, max_value=20, value=5, step=1)

preschool_pct = 12
all_types = sorted(kg_raw["type"].dropna().unique().tolist())
kg_types = all_types
all_rayons = sorted(pop_raw["RAYON"].unique().tolist())
rayons = all_rayons
map_layer = "Доступность"
show_kg = True
show_rec = n_rec > 0
new_kg_radius = 300

# ── фильтрация ────────────────────────────────────────────────────────
pop_f = pop_raw[pop_raw["RAYON"].isin(rayons)].reset_index(drop=True)
kg_f = kg_raw[
    kg_raw["type"].isin(kg_types) &
    kg_raw["rayon"].isin(rayons)
].reset_index(drop=True)

# ── динамический пересчёт (KDTree пересобирается при смене фильтров) ──
@st.cache_data
def _distance_snapshot(kg_idx: tuple, pop_rayons: tuple, pop_source_stamp: tuple[str, int, int]):
    _kg  = kg_raw.loc[list(kg_idx)].reset_index(drop=True)
    _pop = pop_raw[pop_raw["RAYON"].isin(pop_rayons)].reset_index(drop=True)
    dists = de.compute_distances(_pop, _kg)
    return _pop, _kg, dists

pop_c, kg_c, dists = _distance_snapshot(
    tuple(sorted(kg_f.index.tolist())),
    tuple(sorted(rayons)),
    de.population_source_stamp(),
)

metrics = de.compute_metrics(pop_c, dists, kg_c, radius, preschool_pct)
ds      = de.compute_district_stats(pop_c, dists, kg_c, radius, preschool_pct)

# ── рекомендации ──────────────────────────────────────────────────────
@st.cache_data
def _recommend(kg_idx: tuple, pop_rayons: tuple, radius: int,
               preschool_pct: float, n: int, new_kg_radius: int, pop_source_stamp: tuple[str, int, int]):
    _pop, _kg, dists = _distance_snapshot(kg_idx, pop_rayons, pop_source_stamp)
    if _kg.empty or _pop.empty:
        return de.recommend_locations(_pop, np.array([]), _kg, radius, preschool_pct, n, new_kg_radius)
    return de.recommend_locations(_pop, dists, _kg, radius, preschool_pct, n, new_kg_radius)

if show_rec:
    with st.spinner("Считаем оптимальные места..."):
        rec = _recommend(
            tuple(sorted(kg_f.index.tolist())),
            tuple(sorted(rayons)),
            radius, preschool_pct, n_rec, new_kg_radius, de.population_source_stamp(),
        )
        rec = de.enrich_recommendations(rec, pop_c)
else:
    rec = None

# ── рендер ────────────────────────────────────────────────────────────
ui.render_header(len(kg_raw))
ui.render_kpi(metrics, radius, preschool_pct)

if pop_f.empty:
    st.warning("По выбранным районам не найдено население. Измените фильтры в боковой панели.")
elif kg_f.empty:
    st.info("По текущим фильтрам детские сады не найдены. Карта покажет зоны без покрытия и рекомендации.")

st.markdown(f'<div class="sec">Карта · {map_layer}</div>',
            unsafe_allow_html=True)
fmap = mb.build_map(
    pop_c, dists, kg_c,
    radius=radius,
    layer=map_layer,
    show_kg=show_kg,
    recommendations=rec,
    new_kg_radius=new_kg_radius,
)
st_folium(fmap, width=None, height=650, returned_objects=[])

if map_layer == "Доступность":
    st.markdown("""
    <div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:8px;font-size:0.75rem;color:#64748b;">
        <span><span style="color:#14b8a6">●</span> &lt;½ радиуса</span>
        <span><span style="color:#f59e0b">●</span> в зоне</span>
        <span><span style="color:#ef4444">●</span> чуть за зоной</span>
        <span><span style="color:#7f1d1d">●</span> далеко</span>
        <span style="margin-left:8px"><span style="color:#7c3aed">●</span> частный сад</span>
        <span><span style="color:#a855f7">●</span> государственный сад</span>
        <span><span style="color:#7c3aed">●</span> новый сад, 300 м</span>
    </div>
    """, unsafe_allow_html=True)

district_col, funnel_col = st.columns([3, 2])

with district_col:
    ui.render_district_bars(ds, radius)

with funnel_col:
    ui.render_funnel(pop_c, dists, metrics["total_pop"], radius)
    if show_rec and rec is not None:
        ui.render_recommendations(rec)
        st.download_button(
            "Скачать рекомендации CSV",
            data=_recommendations_csv(
                tuple(
                    rec[["rank", "addr_id", "rayon", "lat", "lon", "helped_people", "gain_preschool", "helped_addr_count"]]
                    .itertuples(index=False, name=None)
                )
            ),
            file_name=f"recommendations_{n_rec}_new_kindergartens.csv",
            mime="text/csv",
            width="stretch",
        )

st.markdown("<br>", unsafe_allow_html=True)
ui.render_detail_table(ds)

st.markdown("""
<div style="text-align:center;color:#64748b;font-size:0.7rem;margin-top:28px;
    font-family:'IBM Plex Mono',monospace;">
Алматы · анализ доступности дошкольного образования
</div>
""", unsafe_allow_html=True)
