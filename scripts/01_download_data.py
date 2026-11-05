"""Шаг 1. Скачиваем данные из OpenStreetMap и Wikidata.

1. Границы 18 районов Санкт-Петербурга (OSM, admin_level=5).
2. Все заведения amenity=cafe в прямоугольнике вокруг города (OSM).
   Прямоугольник специально берём шире города, чтобы потом честно
   отфильтровать точки, которые лежат за его границей.
3. Население районов (Wikidata, свойство P1082 «население»).

Сохраняем «сырые» ответы в data/raw/ как есть, без обработки.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# Представляемся сервисам: так просят правила Overpass и Wikidata
USER_AGENT = "spb-coffee-map/1.0 (portfolio project; Python urllib)"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Районы: все административные границы 5-го уровня внутри области
# «Санкт-Петербург» (сам город в OSM — это admin_level=4, как субъект РФ)
QUERY_DISTRICTS = """
[out:json][timeout:180];
area["name"="Санкт-Петербург"]["admin_level"="4"]["boundary"="administrative"]->.spb;
rel(area.spb)["boundary"="administrative"]["admin_level"="5"];
out geom;
"""

# Кафе: точки (node) и здания/контуры (way, relation) в прямоугольнике
# юг, запад, север, восток. out center — для контура вернуть его центр.
BBOX = "59.60,29.40,60.30,30.80"
QUERY_CAFES = f"""
[out:json][timeout:180];
nwr["amenity"="cafe"]({BBOX});
out center tags;
"""


def overpass(query):
    """Отправляем запрос в Overpass. Если сервер перегружен, пробуем ещё раз
    или другой сервер."""
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(3):
        for url in OVERPASS_URLS:
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    return json.load(resp)
            except Exception as err:  # сервер занят или ответил ошибкой
                print(f"  {url} не ответил ({err}), пробую дальше")
                time.sleep(10)
    raise SystemExit("Overpass недоступен, попробуйте запустить позже.")


def wikidata_population(qids):
    """Для каждого района берём все значения населения с датами."""
    values = " ".join(f"wd:{q}" for q in qids)
    query = f"""
    SELECT ?item ?pop ?date WHERE {{
      VALUES ?item {{ {values} }}
      ?item p:P1082 ?st .
      ?st ps:P1082 ?pop .
      OPTIONAL {{ ?st pq:P585 ?date }}
    }}"""
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
        {"query": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def main():
    # Снимок данных уже лежит в репозитории, и анализ в README сделан по нему.
    # Перекачиваем только по явной просьбе: python scripts/01_download_data.py --refresh
    if (RAW / "cafes.json").exists() and "--refresh" not in sys.argv:
        print("Снимок данных уже есть в data/raw/ (дата:",
              (RAW / "downloaded_at.txt").read_text().strip() + ").",
              "Чтобы скачать свежие данные, добавьте --refresh.")
        return

    print("Скачиваю границы районов...")
    districts = overpass(QUERY_DISTRICTS)
    (RAW / "districts.json").write_text(json.dumps(districts, ensure_ascii=False), encoding="utf-8")
    print("  районов:", len(districts["elements"]))

    print("Скачиваю кафе...")
    cafes = overpass(QUERY_CAFES)
    (RAW / "cafes.json").write_text(json.dumps(cafes, ensure_ascii=False), encoding="utf-8")
    print("  объектов amenity=cafe:", len(cafes["elements"]))

    print("Скачиваю население районов из Wikidata...")
    qids = [e["tags"]["wikidata"] for e in districts["elements"] if "wikidata" in e["tags"]]
    population = wikidata_population(qids)
    (RAW / "population_wikidata.json").write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
    print("  записей о населении:", len(population["results"]["bindings"]))

    # Запоминаем дату выгрузки: OSM меняется каждый день
    (RAW / "downloaded_at.txt").write_text(time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()) + "\n")


if __name__ == "__main__":
    main()
