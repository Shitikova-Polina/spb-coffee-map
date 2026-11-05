"""Шаг 3. Считаем показатели по районам.

Для каждого района: число кафе, кафе на 10 000 жителей, кафе на 1 км²,
доля сетевых. Результат — results/02_districts.csv и results/03_top_chains.csv.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

districts = gpd.read_file(PROC / "districts.geojson")
cafes = gpd.read_file(PROC / "cafes.geojson")
cafes["name_norm"] = cafes["name_norm"].fillna("")
cafes["brand"] = cafes["brand"].fillna("")

# ---------- Сетевое или нет ----------
# Правило (два признака, достаточно любого):
#  1) у заведения в OSM заполнен тег brand — добровольцы отметили, что это сеть;
#  2) такое же название встречается в городе 5 раз и чаще.
# Исключение для признака 2: названия-типы заведений («столовая», «шаверма»),
# это не бренд, а просто вид кафе.
CHAIN_MIN_COUNT = 5
GENERIC_NAMES = {
    "столовая", "шаверма", "шашлычная", "бистро", "пышки", "кафе", "кофейня",
    "кофе", "coffee", "пекарня", "кулинария", "буфет", "блинная", "чебуречная",
    "пирожковая", "шаурма", "кондитерская", "хинкальная", "пельменная",
    "кофе с собой", "чайхона",
}
name_counts = cafes.loc[cafes["name_norm"] != "", "name_norm"].value_counts()
frequent_names = set(name_counts[name_counts >= CHAIN_MIN_COUNT].index) - GENERIC_NAMES


def chain_status(row):
    if row["name_norm"] == "":
        return "неизвестно"  # без названия не определить
    if row["brand"] != "" or row["name_norm"] in frequent_names:
        return "сетевое"
    return "несетевое"


cafes["chain"] = cafes.apply(chain_status, axis=1)
print("Сетевой признак по всему городу:")
print(cafes["chain"].value_counts().to_string())

# Какие названия оказались в сетях — для проверки правила глазами
chains = (cafes[cafes["chain"] == "сетевое"]
          .groupby("name_norm").size().sort_values(ascending=False)
          .rename("cafes").reset_index())
chains.to_csv(RESULTS / "03_top_chains.csv", index=False)
generic_found = sorted(GENERIC_NAMES & set(name_counts[name_counts >= CHAIN_MIN_COUNT].index))
print("Названия-типы, исключённые из сетей:", generic_found)

# ---------- Показатели по районам ----------
counts = cafes.groupby("district").agg(
    cafes=("osm_id", "count"),
    chain=("chain", lambda s: (s == "сетевое").sum()),
    independent=("chain", lambda s: (s == "несетевое").sum()),
    unknown=("chain", lambda s: (s == "неизвестно").sum()),
).reset_index()

table = districts[["district", "population", "area_km2"]].merge(counts, on="district", how="left")
table["per_10k"] = table["cafes"] / table["population"] * 10_000
table["per_km2"] = table["cafes"] / table["area_km2"]
# Долю сетевых считаем только среди кафе с известным статусом
table["chain_share"] = table["chain"] / (table["chain"] + table["independent"])
table = table.sort_values("per_10k", ascending=False)
table.round(3).to_csv(RESULTS / "02_districts.csv", index=False)

# Итог по городу
total = table[["population", "area_km2", "cafes", "chain", "independent", "unknown"]].sum()
summary = [
    f"Кафе в городе после очистки: {int(total['cafes'])}",
    f"На 10 000 жителей по городу: {total['cafes'] / total['population'] * 10_000:.2f}",
    f"На 1 км² по городу: {total['cafes'] / total['area_km2']:.2f}",
    f"Сетевых: {int(total['chain'])}, несетевых: {int(total['independent'])}, без названия: {int(total['unknown'])}",
    f"Доля сетевых среди кафе с названием: {total['chain'] / (total['chain'] + total['independent']):.1%}",
    f"Порог сети по названию: {CHAIN_MIN_COUNT}+ точек, названий-сетей: {len(chains)}",
    "",
    "По районам (сортировка по кафе на 10 000 жителей):",
    table[["district", "cafes", "per_10k", "per_km2", "chain_share"]].round(2).to_string(index=False),
]
(RESULTS / "04_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
print("\n".join(summary))
