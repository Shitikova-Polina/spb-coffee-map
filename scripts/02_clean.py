"""Шаг 2. Превращаем сырые ответы OSM в таблицы, проверяем качество и чистим.

На выходе:
  data/processed/districts.geojson — 18 районов с населением и площадью
  data/processed/cafes.geojson     — очищенные кафе с привязкой к району
  results/01_cleaning_log.txt      — что и сколько убрано
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, polygonize, unary_union

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

# Метрическая проекция UTM зона 36N: в ней расстояния и площади в метрах.
# В обычных координатах (широта/долгота) площадь в км² не посчитать.
METRIC_CRS = "EPSG:32636"
DUPLICATE_DISTANCE_M = 50  # одинаковые названия ближе 50 м считаем дублем

log = []  # журнал очистки


def say(text):
    print(text)
    log.append(text)


# ---------- 1. Районы ----------
def relation_to_polygon(relation):
    """В OSM район — это «отношение» из многих линий (ways).
    Внешние линии (role=outer) складываем в контур, внутренние (role=inner)
    вырезаем как дырки."""
    outer, inner = [], []
    for member in relation["members"]:
        if member["type"] != "way" or "geometry" not in member:
            continue
        line = LineString([(p["lon"], p["lat"]) for p in member["geometry"]])
        (inner if member["role"] == "inner" else outer).append(line)
    outer_poly = unary_union(list(polygonize(linemerge(outer))))
    if inner:
        outer_poly = outer_poly.difference(unary_union(list(polygonize(linemerge(inner)))))
    return outer_poly


districts_raw = json.loads((RAW / "districts.json").read_text(encoding="utf-8"))["elements"]
districts = gpd.GeoDataFrame(
    {
        "district": [r["tags"]["name"] for r in districts_raw],
        "wikidata": [r["tags"].get("wikidata") for r in districts_raw],
        "geometry": [relation_to_polygon(r) for r in districts_raw],
    },
    crs="EPSG:4326",
)
districts["area_km2"] = districts.to_crs(METRIC_CRS).area / 1_000_000
say(f"Районов (admin_level=5): {len(districts)}, общая площадь {districts['area_km2'].sum():.0f} км²")

# Население: из всех значений P1082 берём самое свежее по дате
pop_raw = json.loads((RAW / "population_wikidata.json").read_text(encoding="utf-8"))
pop = pd.DataFrame(
    {
        "wikidata": [b["item"]["value"].split("/")[-1] for b in pop_raw["results"]["bindings"]],
        "population": [float(b["pop"]["value"]) for b in pop_raw["results"]["bindings"]],
        "pop_date": [b.get("date", {}).get("value", "")[:10] for b in pop_raw["results"]["bindings"]],
    }
)
pop = pop.sort_values("pop_date").groupby("wikidata").tail(1)  # последняя дата в каждом районе
districts = districts.merge(pop, on="wikidata", how="left")
say(f"Население найдено для {districts['population'].notna().sum()} из {len(districts)} районов, "
    f"даты: {sorted(districts['pop_date'].unique())}, всего {districts['population'].sum():,.0f} чел.")

# ---------- 2. Кафе ----------
cafes_raw = json.loads((RAW / "cafes.json").read_text(encoding="utf-8"))["elements"]
rows = []
for e in cafes_raw:
    # У точки координаты в lat/lon, у здания — в center
    lat = e.get("lat", e.get("center", {}).get("lat"))
    lon = e.get("lon", e.get("center", {}).get("lon"))
    tags = e.get("tags", {})
    rows.append({
        "osm_id": f"{e['type']}/{e['id']}",
        "name": tags.get("name", "").strip(),
        "brand": tags.get("brand", "").strip(),
        "cuisine": tags.get("cuisine", ""),
        "geometry": Point(lon, lat),
    })
cafes = gpd.GeoDataFrame(rows, crs="EPSG:4326")
say(f"\nВсего объектов amenity=cafe в прямоугольнике вокруг города: {len(cafes)}")

# 2.1 Точки за пределами города: привязываем каждую точку к району.
# sjoin ищет, внутри какого многоугольника лежит точка.
cafes = gpd.sjoin(cafes, districts[["district", "geometry"]], how="left", predicate="within")
cafes = cafes.drop(columns="index_right")
outside = cafes["district"].isna()
say(f"За границей города (ни в одном районе): {outside.sum()} — убраны")
cafes = cafes[~outside].copy()

# 2.2 Точки без названия: не убираем (кафе есть, у него нет подписи),
# но их нельзя отнести к сетевым или несетевым.
no_name = cafes["name"] == ""
say(f"Без названия: {no_name.sum()} ({no_name.mean():.1%}) — оставлены, сетевой признак для них «неизвестно»")

# 2.3 Дубли: одно и то же кафе нарисовано дважды (например, точкой и зданием).
# Правило: одинаковое название (без учёта регистра) и расстояние меньше 50 м.
cafes["name_norm"] = cafes["name"].str.lower().str.replace("ё", "е")
cafes_m = cafes.to_crs(METRIC_CRS)
is_dup = pd.Series(False, index=cafes.index)
for name, group in cafes_m[cafes_m["name_norm"] != ""].groupby("name_norm"):
    kept = []  # точки этого названия, которые уже оставили
    for idx, point in group.geometry.items():
        if any(point.distance(k) < DUPLICATE_DISTANCE_M for k in kept):
            is_dup[idx] = True
        else:
            kept.append(point)
say(f"Дубли (то же название ближе {DUPLICATE_DISTANCE_M} м): {is_dup.sum()} — убраны")
cafes = cafes[~is_dup].copy()
say(f"Осталось после очистки: {len(cafes)}")

# ---------- 3. Сохраняем ----------
districts.to_file(OUT / "districts.geojson", driver="GeoJSON")
cafes.to_file(OUT / "cafes.geojson", driver="GeoJSON")
(RESULTS / "01_cleaning_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
