"""Шаг 4. Интерактивная карта (results/coffee_map.html) и графики (figures/)."""
from pathlib import Path

import folium
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")  # рисуем в файл, без окна
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

districts = gpd.read_file(PROC / "districts.geojson")
cafes = gpd.read_file(PROC / "cafes_with_chain.geojson")  # с признаком сети из шага 3
table = pd.read_csv(RESULTS / "02_districts.csv")
districts = districts[["district", "geometry"]].merge(table, on="district")

COLORS = {"сетевое": "#2a78d6", "несетевое": "#eb6834", "неизвестно": "#8a8984"}

# ---------- Интерактивная карта ----------
m = folium.Map(location=[59.94, 30.31], zoom_start=10, tiles="OpenStreetMap")

# Раскраска районов по числу кафе на 10 000 жителей. Границы интервалов
# заданы вручную: значения распределены неравномерно (от 2,5 до 40).
folium.Choropleth(
    geo_data=districts.to_json(),
    data=districts,
    columns=["district", "per_10k"],
    key_on="feature.properties.district",
    bins=[0, 3, 4, 6, 10, 20, 45],
    fill_color="Blues",
    fill_opacity=0.6,
    line_opacity=0.6,
    legend_name="Кафе на 10 000 жителей",
    name="Районы: кафе на 10 000 жителей",
).add_to(m)

# Подсказка при наведении на район
folium.GeoJson(
    districts.to_json(),
    style_function=lambda f: {"fillOpacity": 0, "weight": 0},
    control=False,  # служебный слой, в списке слоёв не показываем
    tooltip=folium.GeoJsonTooltip(
        fields=["district", "cafes", "per_10k", "per_km2", "chain_share"],
        aliases=["Район", "Кафе", "На 10 тыс. жителей", "На 1 км²", "Доля сетевых"],
        localize=True,
    ),
).add_to(m)

# Точки кафе: три слоя, которые можно включать и выключать
for status, color in COLORS.items():
    layer = folium.FeatureGroup(name=f"Кафе: {status} ({(cafes['chain'] == status).sum()})")
    for _, cafe in cafes[cafes["chain"] == status].iterrows():
        name = cafe["name"] if isinstance(cafe["name"], str) and cafe["name"] else "без названия"
        # Обратная кавычка ` в названии (например, «Stefano`s») ломает JavaScript
        # на странице карты, поэтому заменяем её на обычный апостроф
        name = name.replace("`", "'")
        folium.CircleMarker(
            location=[cafe.geometry.y, cafe.geometry.x],
            radius=2.5, color=color, fill=True, fill_opacity=0.8, weight=0,
            tooltip=name,
        ).add_to(layer)
    layer.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(RESULTS / "coffee_map.html")
print("Карта:", RESULTS / "coffee_map.html")

# ---------- Графики ----------
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "text.color": "#0b0b0b",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "x", "grid.color": "#e8e7e3",
    "font.size": 10,
})
short = table.assign(name=table["district"].str.replace(" район", ""))

# График 1. Кафе на 10 000 жителей
data = short.sort_values("per_10k")
fig, ax = plt.subplots(figsize=(8, 6))
bars = ax.barh(data["name"], data["per_10k"], color="#2a78d6", height=0.7)
ax.bar_label(bars, labels=[f"{v:.1f}" for v in data["per_10k"]], padding=3, fontsize=9)
city = table["cafes"].sum() / table["population"].sum() * 10_000
ax.axvline(city, color="#52514e", linestyle="--", linewidth=1)
ax.text(city + 0.5, 0, f"в среднем по городу {city:.1f}", color="#52514e", fontsize=9)
ax.set_xlabel("Кафе на 10 000 жителей")
ax.set_title("1. Сколько кафе приходится на 10 000 жителей района")
fig.tight_layout()
fig.savefig(FIG / "1_cafes_per_10k.png", dpi=150)
plt.close(fig)

# График 2. Кафе на 1 км²
data = short.sort_values("per_km2")
fig, ax = plt.subplots(figsize=(8, 6))
bars = ax.barh(data["name"], data["per_km2"], color="#2a78d6", height=0.7)
ax.bar_label(bars, labels=[f"{v:.1f}" for v in data["per_km2"]], padding=3, fontsize=9)
ax.set_xlabel("Кафе на 1 км² площади района")
ax.set_title("2. Плотность кафе на квадратный километр")
fig.tight_layout()
fig.savefig(FIG / "2_cafes_per_km2.png", dpi=150)
plt.close(fig)

# График 3. Сетевые и несетевые (доли среди кафе с названием)
data = short.assign(ind_share=1 - short["chain_share"]).sort_values("chain_share")
fig, ax = plt.subplots(figsize=(8, 6))
ax.barh(data["name"], data["chain_share"] * 100, color=COLORS["сетевое"], label="сетевые", height=0.7)
ax.barh(data["name"], data["ind_share"] * 100, left=data["chain_share"] * 100,
        color=COLORS["несетевое"], label="несетевые", height=0.7)
for y, v in enumerate(data["chain_share"] * 100):
    ax.text(v - 1, y, f"{v:.0f}%", ha="right", va="center", color="white", fontsize=8)
ax.set_xlim(0, 100)
ax.set_xlabel("% кафе с названием")
ax.set_title("3. Доля сетевых кафе по районам")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
fig.tight_layout()
fig.savefig(FIG / "3_chain_share.png", dpi=150)
plt.close(fig)
print("Графики сохранены в", FIG)
