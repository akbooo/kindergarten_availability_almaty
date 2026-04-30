"""
data_engine.py — вся математика, без Streamlit.
Загружает сырые данные один раз, предоставляет функции пересчёта.
"""
import json
from functools import lru_cache
from pathlib import Path
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import rasterio
from scipy.spatial import KDTree


# ── координатный масштаб для Алматы (43°N) ───────────────────────────
LAT_M = 111_000          # 1° широты  ≈ 111 км
LON_M = 85_000           # 1° долготы ≈ 85 км  при 43°N


GRAPH_CACHE_PATH = Path("almaty_walk_q01_q99.graphml")
GRAPH_MARGIN_DEG = 0.03
BBOX_LOW_Q = 0.01
BBOX_HIGH_Q = 0.99
ROUTING_NETWORK_TYPE = "walk"
ALLOW_GRAPH_DOWNLOAD = False
POP_RASTER_PATH = Path("almaty_clip.tif")


def _to_xy(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """lat/lon → метрические координаты (N×2)."""
    return np.column_stack([lon * LON_M, lat * LAT_M])


def _resolve_existing_path(candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def population_source_stamp() -> tuple[str, int, int]:
    path = POP_RASTER_PATH if POP_RASTER_PATH.exists() else _resolve_existing_path(["pop_data.json", "population.csv"])
    if path is None:
        return ("missing", 0, 0)
    stat = path.stat()
    return (path.name, int(stat.st_mtime), int(stat.st_size))


def _bbox_with_margin(pop: pd.DataFrame, kg: pd.DataFrame) -> tuple[float, float, float, float]:
    lat_values = np.concatenate([pop["lat"].to_numpy(), kg["lat"].to_numpy()])
    lon_values = np.concatenate([pop["lon"].to_numpy(), kg["lon"].to_numpy()])
    south = float(np.quantile(lat_values, BBOX_LOW_Q)) - GRAPH_MARGIN_DEG
    north = float(np.quantile(lat_values, BBOX_HIGH_Q)) + GRAPH_MARGIN_DEG
    west = float(np.quantile(lon_values, BBOX_LOW_Q)) - GRAPH_MARGIN_DEG
    east = float(np.quantile(lon_values, BBOX_HIGH_Q)) + GRAPH_MARGIN_DEG
    return north, south, east, west


@lru_cache(maxsize=1)
def _load_cached_graph() -> nx.MultiDiGraph:
    return ox.load_graphml(GRAPH_CACHE_PATH)


def _load_routing_graph(pop: pd.DataFrame, kg: pd.DataFrame) -> nx.MultiDiGraph:
    if GRAPH_CACHE_PATH.exists():
        return _load_cached_graph()

    if not ALLOW_GRAPH_DOWNLOAD:
        raise FileNotFoundError(
            f"Routing graph cache not found: {GRAPH_CACHE_PATH}. "
            "Online download is disabled, so direct-distance fallback will be used."
        )

    north, south, east, west = _bbox_with_margin(pop, kg)
    graph = ox.graph_from_bbox(
        (north, south, east, west),
        network_type=ROUTING_NETWORK_TYPE,
        simplify=True,
    )
    ox.save_graphml(graph, GRAPH_CACHE_PATH)
    _load_cached_graph.cache_clear()
    return _load_cached_graph()


def _nearest_graph_nodes(
    graph: nx.MultiDiGraph,
    lat: np.ndarray,
    lon: np.ndarray,
) -> np.ndarray:
    return np.asarray(_nearest_graph_nodes_cached(tuple(np.round(lat, 6)), tuple(np.round(lon, 6))))


@lru_cache(maxsize=64)
def _nearest_graph_nodes_cached(
    lat: tuple[float, ...],
    lon: tuple[float, ...],
) -> tuple[int, ...]:
    graph = _load_cached_graph()
    nodes = ox.distance.nearest_nodes(graph, X=np.asarray(lon), Y=np.asarray(lat))
    return tuple(int(node) for node in np.asarray(nodes).tolist())


def _load_population_table() -> pd.DataFrame:
    pop_json = Path("pop_data.json")
    if pop_json.exists():
        with pop_json.open(encoding="utf-8") as f:
            pop = pd.DataFrame(json.load(f))
    else:
        pop_csv = Path("population.csv")
        if not pop_csv.exists():
            raise FileNotFoundError(
                "Не найден источник населения: ожидался pop_data.json или population.csv."
            )
        pop = pd.read_csv(pop_csv)
        if "geometry" in pop.columns:
            coords = pop["geometry"].str.extract(r"POINT \(([-\d.]+) ([-\d.]+)\)")
            pop["lon"] = pd.to_numeric(coords[0], errors="coerce")
            pop["lat"] = pd.to_numeric(coords[1], errors="coerce")

    pop = pop.dropna(subset=["lat", "lon", "population", "RAYON"]).reset_index(drop=True)
    pop["population"] = pd.to_numeric(pop["population"], errors="coerce").fillna(0)
    if "addr_id" not in pop.columns:
        pop["addr_id"] = [f"addr_{idx:06d}" for idx in range(len(pop))]
    return pop


def _load_population_from_raster(reference_pop: pd.DataFrame) -> pd.DataFrame:
    with rasterio.open(POP_RASTER_PATH) as src:
        band = src.read(1, masked=True)
        rows, cols = np.where((~band.mask) & (band.data > 0))
        values = band.data[rows, cols].astype(float)
        xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="center")

    pop = pd.DataFrame(
        {
            "addr_id": [f"tif_{int(row):04d}_{int(col):04d}" for row, col in zip(rows, cols)],
            "lat": np.asarray(ys, dtype=float),
            "lon": np.asarray(xs, dtype=float),
            "population": values,
        }
    )

    ref_xy = _to_xy(reference_pop["lat"].to_numpy(), reference_pop["lon"].to_numpy())
    raster_xy = _to_xy(pop["lat"].to_numpy(), pop["lon"].to_numpy())
    _, nearest_idx = KDTree(ref_xy).query(raster_xy, k=1)
    pop["RAYON"] = reference_pop.iloc[np.asarray(nearest_idx)]["RAYON"].to_numpy()
    return pop.dropna(subset=["lat", "lon", "population", "RAYON"]).reset_index(drop=True)


def _load_population() -> pd.DataFrame:
    reference_pop = _load_population_table()
    if POP_RASTER_PATH.exists():
        return _load_population_from_raster(reference_pop)
    return reference_pop


def _assign_kindergarten_rayon(pop: pd.DataFrame, kg: pd.DataFrame) -> pd.DataFrame:
    if kg.empty:
        kg["rayon"] = pd.Series(dtype="object")
        return kg

    pop_xy = _to_xy(pop["lat"].to_numpy(), pop["lon"].to_numpy())
    kg_xy = _to_xy(kg["lat"].to_numpy(), kg["lon"].to_numpy())
    pop_tree = KDTree(pop_xy)
    _, nearest_idx = pop_tree.query(kg_xy, k=1)
    kg["rayon"] = pop.iloc[np.asarray(nearest_idx)]["RAYON"].to_numpy()
    return kg


def _load_kindergartens(pop: pd.DataFrame) -> pd.DataFrame:
    kg_json = Path("kg_data.json")
    if kg_json.exists():
        with kg_json.open(encoding="utf-8") as f:
            kg = pd.DataFrame(json.load(f))
    else:
        csv_path = _resolve_existing_path(
            [
                "kindergardens_result.csv",
                "kindergartens_almaty_private_osm_matched_final.csv",
                "kindergartens_almaty_osm_matched_final.csv",
                "kindergartens_almaty_osm_matched_final11.csv",
            ]
        )
        if csv_path is None:
            raise FileNotFoundError(
                "Не найден источник детских садов: ожидался kg_data.json или один из CSV-файлов."
            )
        kg = pd.read_csv(csv_path)

    kg["lat"] = pd.to_numeric(kg["lat"], errors="coerce")
    kg["lon"] = pd.to_numeric(kg["lon"], errors="coerce")
    kg = kg.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    defaults = {
        "name": "Без названия",
        "address": "Адрес не указан",
        "type": "Не указан",
        "money": "unknown",
    }
    for column, default in defaults.items():
        if column not in kg.columns:
            kg[column] = default
        kg[column] = kg[column].fillna(default)

    if "rayon" not in kg.columns or kg["rayon"].isna().all():
        kg = _assign_kindergarten_rayon(pop, kg)
    else:
        kg["rayon"] = kg["rayon"].fillna("Неизвестно")

    return kg


# ── загрузка ──────────────────────────────────────────────────────────

def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Читает доступные источники и возвращает (pop, kg)."""
    pop = _load_population()
    kg = _load_kindergartens(pop)
    return pop, kg


def build_kg_tree(kg: pd.DataFrame) -> KDTree:
    """KDTree по отфильтрованным садам."""
    if kg.empty:
        raise ValueError("Нельзя построить KDTree для пустого набора детских садов.")
    xy = _to_xy(kg["lat"].values, kg["lon"].values)
    return KDTree(xy)


# ── динамический пересчёт ─────────────────────────────────────────────

def _compute_direct_distances(pop: pd.DataFrame, kg: pd.DataFrame) -> np.ndarray:
    """
    Для каждой ячейки населения — расстояние (м) до ближайшего сада
    в текущем наборе kg_tree.
    """
    if pop.empty:
        return np.array([], dtype=np.float32)
    if kg.empty:
        return np.full(len(pop), np.inf, dtype=np.float32)

    kg_tree = build_kg_tree(kg)
    pop_xy = _to_xy(pop["lat"].values, pop["lon"].values)
    dists, _ = kg_tree.query(pop_xy, k=1)
    return dists.astype(np.float32)


def compute_distances(pop: pd.DataFrame, kg: pd.DataFrame) -> np.ndarray:
    """
    Для каждой ячейки населения — расстояние до ближайшего сада по дорожной сети.
    Если граф дорог недоступен, используется запасной расчет по прямой.
    """
    if pop.empty:
        return np.array([], dtype=np.float32)
    if kg.empty:
        return np.full(len(pop), np.inf, dtype=np.float32)

    try:
        graph = _load_routing_graph(pop, kg)
        kg_nodes = _nearest_graph_nodes(graph, kg["lat"].to_numpy(), kg["lon"].to_numpy())
        pop_nodes = _nearest_graph_nodes(graph, pop["lat"].to_numpy(), pop["lon"].to_numpy())
        lengths = nx.multi_source_dijkstra_path_length(
            graph,
            sources=set(kg_nodes.tolist()),
            weight="length",
        )
        return np.fromiter(
            (lengths.get(node, np.inf) for node in pop_nodes.tolist()),
            dtype=np.float32,
            count=len(pop_nodes),
        )
    except Exception:
        return _compute_direct_distances(pop, kg)


def compute_metrics(
    pop: pd.DataFrame,
    dists: np.ndarray,
    kg: pd.DataFrame,
    radius: int,
    preschool_pct: float,
) -> dict:
    """
    Глобальные KPI по текущим параметрам.
    dists — результат compute_distances (уже пересчитан для текущего kg).
    """
    pop_vals  = pop["population"].values
    total_pop = pop_vals.sum()

    covered_mask    = dists <= radius
    covered_pop     = pop_vals[covered_mask].sum()
    uncovered_pop   = total_pop - covered_pop
    access_pct      = covered_pop / total_pop * 100 if total_pop > 0 else 0.0

    total_preschool = total_pop * preschool_pct / 100
    total_kg        = len(kg)
    kids_per_kg     = total_preschool / total_kg if total_kg > 0 else 0.0

    # медиана расстояния до ближайшего сада
    finite_dists = dists[np.isfinite(dists)]
    median_dist = float(np.median(finite_dists)) if len(finite_dists) else None

    return dict(
        total_pop=int(total_pop),
        covered_pop=int(covered_pop),
        uncovered_pop=int(uncovered_pop),
        access_pct=round(access_pct, 2),
        total_preschool=round(total_preschool),
        total_kg=total_kg,
        kids_per_kg=round(kids_per_kg, 1),
        median_dist=round(median_dist) if median_dist is not None else None,
        paid_kg=int((kg["money"] == "yes").sum()),
    )


def compute_district_stats(
    pop: pd.DataFrame,
    dists: np.ndarray,
    kg: pd.DataFrame,
    radius: int,
    preschool_pct: float,
) -> pd.DataFrame:
    """
    Пересчёт статистики по районам с текущими параметрами и текущим kg.
    """
    df = pop.copy()
    df["dist"] = dists
    df["preschool"] = df["population"] * preschool_pct / 100

    rows = []
    for rayon, g in df.groupby("RAYON"):
        pop_sum     = g["population"].sum()
        pre_sum     = g["preschool"].sum()
        kg_r        = kg[kg["rayon"] == rayon]
        kg_count    = len(kg_r)
        access_pct = (
            g.loc[g["dist"] <= radius, "population"].sum() / pop_sum * 100
            if pop_sum > 0 else 0
        )
        kids_per_kg = pre_sum / kg_count if kg_count > 0 else 0
        finite_dist = g.loc[np.isfinite(g["dist"]), "dist"]

        rows.append(dict(
            RAYON=rayon,
            population=round(pop_sum),
            preschool=round(pre_sum),
            kg_count=kg_count,
            access_pct=round(access_pct, 1),
            kids_per_kg=round(kids_per_kg, 1),
            median_dist=round(finite_dist.median()) if len(finite_dist) else None,
        ))

    if not rows:
        return pd.DataFrame(
            columns=["RAYON", "population", "preschool", "kg_count", "access_pct", "kids_per_kg", "median_dist"]
        )

    return pd.DataFrame(rows).sort_values("access_pct")


# ── рекомендации новых садов ──────────────────────────────────────────

def recommend_locations(
    pop: pd.DataFrame,
    dists: np.ndarray,
    kg: pd.DataFrame,
    radius: int,
    preschool_pct: float,
    n_recommend: int = 10,
    new_kg_radius: int = 300,
) -> pd.DataFrame:
    """Select real address cells for new kindergartens and count helped people by address id.

    The coverage for a new kindergarten is computed with the selected access radius
    (`radius`), while `new_kg_radius` is only used for map visualization.
    """
    result_columns = [
        "rank", "addr_id", "lat", "lon", "rayon",
        "helped_people", "gain_preschool", "helped_addr_count",
    ]
    if pop.empty or n_recommend <= 0:
        return pd.DataFrame(columns=result_columns)

    pop = pop.reset_index(drop=True).copy()
    if "addr_id" not in pop.columns:
        pop["addr_id"] = [f"addr_{idx:06d}" for idx in range(len(pop))]

    pop_xy = _to_xy(pop["lat"].values, pop["lon"].values)
    pop_people = pop["population"].values
    pop_preschool = pop_people * preschool_pct / 100

    if len(dists) != len(pop):
        dists = np.full(len(pop), np.inf, dtype=np.float32)
    remaining_uncovered = ~(dists <= radius)
    candidate_idx = np.flatnonzero(remaining_uncovered)
    if len(candidate_idx) == 0:
        return pd.DataFrame(columns=result_columns)

    pop_tree = KDTree(pop_xy)
    results = []
    used_addr_ids: set[str] = set()

    for step in range(n_recommend):
        best_idx = -1
        best_gain = -1.0
        best_people = 0.0
        best_helped_count = 0

        for pi in candidate_idx:
            addr_id = str(pop.at[int(pi), "addr_id"])
            if addr_id in used_addr_ids:
                continue

            idxs = np.asarray(pop_tree.query_ball_point(pop_xy[int(pi)], radius), dtype=int)
            if len(idxs) == 0:
                continue
            helped = idxs[remaining_uncovered[idxs]]
            if len(helped) == 0:
                continue

            gain = float(pop_preschool[helped].sum())
            if gain > best_gain:
                best_idx = int(pi)
                best_gain = gain
                best_people = float(pop_people[helped].sum())
                best_helped_count = int(len(helped))

        if best_idx < 0 or best_people < 1:
            break

        row = pop.iloc[best_idx]
        addr_id = str(row["addr_id"])
        used_addr_ids.add(addr_id)
        results.append(dict(
            rank=step + 1,
            addr_id=addr_id,
            lat=round(float(row["lat"]), 6),
            lon=round(float(row["lon"]), 6),
            rayon=row.get("RAYON", ""),
            helped_people=round(best_people),
            gain_preschool=round(best_gain),
            helped_addr_count=best_helped_count,
        ))

        newly_covered = np.asarray(pop_tree.query_ball_point(pop_xy[best_idx], radius), dtype=int)
        remaining_uncovered[newly_covered] = False
        candidate_idx = candidate_idx[remaining_uncovered[candidate_idx]]
        if len(candidate_idx) == 0:
            break

    return pd.DataFrame(results, columns=result_columns)

def enrich_recommendations(rec: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    columns = ["rank", "addr_id", "rayon", "lat", "lon", "helped_people", "gain_preschool", "helped_addr_count"]
    if rec is None or rec.empty:
        return pd.DataFrame(columns=columns)

    rec = rec.copy()
    if "rayon" not in rec.columns or rec["rayon"].isna().any() or (rec["rayon"].astype(str) == "").any():
        pop_xy = _to_xy(pop["lat"].to_numpy(), pop["lon"].to_numpy())
        rec_xy = _to_xy(rec["lat"].to_numpy(), rec["lon"].to_numpy())
        pop_tree = KDTree(pop_xy)
        _, nearest_idx = pop_tree.query(rec_xy, k=1)
        rec["rayon"] = pop.iloc[np.asarray(nearest_idx)]["RAYON"].to_numpy()
    rec["helped_people"] = rec["helped_people"].astype(int)
    rec["gain_preschool"] = rec["gain_preschool"].astype(int)
    rec["helped_addr_count"] = rec["helped_addr_count"].astype(int)
    return rec[columns]
