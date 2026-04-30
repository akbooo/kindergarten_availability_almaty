"""
map_builder.py — строит folium-карту по готовым данным.
Не импортирует streamlit, только folium.
"""
import numpy as np
import pandas as pd
import folium


# ── цветовые утилиты ──────────────────────────────────────────────────

def _dist_color(dist: float, radius: int) -> tuple[str, float]:
    """Цвет и прозрачность ячейки по расстоянию до ближайшего сада."""
    ratio = dist / radius
    if ratio <= 0.5:
        return "#48bb78", 0.4   # teal  — очень близко
    elif ratio <= 1.0:
        return "#f59e0b", 0.34   # amber — в зоне
    elif ratio <= 1.5:
        return "#ef4444", 0.42   # red   — чуть за зоной
    else:
        return "#7f1d1d", 0.48   # dark red — далеко


def _pop_color(pop_val: float, vmax: float) -> str:
    """Цвет по плотности населения (синий → жёлтый)."""
    t = min(pop_val / vmax, 1.0)
    r = int(30  + t * 200)
    g = int(100 + t * 130)
    b = int(200 - t * 150)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── основная функция ──────────────────────────────────────────────────

def build_map(
    pop: pd.DataFrame,
    dists: np.ndarray,
    kg: pd.DataFrame,
    radius: int,
    layer: str,           # "Доступность" | "Плотность населения"
    show_kg: bool,
    recommendations: pd.DataFrame | None = None,
    new_kg_radius: int = 300,
    max_pop_points: int = 7000,
) -> folium.Map:

    m = folium.Map(
        location=[43.235, 76.905],
        zoom_start=11,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    # Subsample population cells for performance
    pop_draw = pop.copy()
    pop_draw["dist"] = dists
    if len(pop_draw) > max_pop_points:
        pop_draw = (
            pop_draw
            .assign(_weight=pop_draw["population"].clip(lower=1))
            .sample(max_pop_points, weights="_weight", random_state=42)
            .drop(columns="_weight")
        )

    vmax_pop = pop["population"].quantile(0.95)

    for row in pop_draw.itertuples():
        if layer == "Доступность":
            color, opacity = _dist_color(row.dist, radius)
        else:  # Плотность населения
            color   = _pop_color(row.population, vmax_pop)
            opacity = 0.55
        dist_label = f"{int(row.dist)} м" if np.isfinite(row.dist) else "нет садов по фильтру"

        folium.CircleMarker(
            location=[row.lat, row.lon],
            radius=3,
            stroke=False,
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            tooltip=(
                f"<b>{row.RAYON}</b><br>"
                f"Население: {int(row.population)}<br>"
                f"До ближ. сада: {dist_label}"
            ),
        ).add_to(m)

    # Kindergartens
    if show_kg:
        for row in kg.itertuples():
            paid   = getattr(row, "money", "") == "yes"
            color  = "#7c3aed" if paid else "#a855f7"
            label  = "частный" if paid else " государственный"
            folium.CircleMarker(
                location=[row.lat, row.lon],
                radius=7,
                color="#ffffff",
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=0.95,
                tooltip=(
                    f"<b>{row.name}</b><br>"
                    f"{row.address}<br>"
                    f"{label}"
                ),
            ).add_to(m)

    # Recommended locations
    if recommendations is not None and len(recommendations):
        for row in recommendations.itertuples():
            helped_people = getattr(row, "helped_people", 0)
            addr_id = getattr(row, "addr_id", "")
            folium.Circle(
                location=[row.lat, row.lon],
                radius=new_kg_radius,
                color="#3b82f6",
                weight=2,
                fill=True,
                fill_color="#60a5fa",
                fill_opacity=0.16,
                tooltip=(
                    f"<b>Новый сад #{row.rank}</b><br>"
                    f"ID: {addr_id}<br>"
                    f"Охват: {radius} м (текущий выбранный радиус доступа)<br>"
                    f"Отображается круг: {new_kg_radius} м<br>"
                    f"Поможет: ~{int(helped_people)} чел."
                ),
            ).add_to(m)

    return m
