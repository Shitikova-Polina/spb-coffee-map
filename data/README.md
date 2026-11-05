# Данные

В `data/raw/` лежит снимок данных от 4 ноября 2026 года (точное время — в `downloaded_at.txt`).
Он положен в репозиторий специально: OpenStreetMap меняется каждый день, а сервер Overpass
часто перегружен. Со снимком результаты совпадают с README.

| Файл | Что внутри | Источник | Лицензия |
|---|---|---|---|
| `raw/districts.json` | границы 18 районов города (`boundary=administrative`, `admin_level=5`) | OpenStreetMap через Overpass API | ODbL 1.0, © участники OpenStreetMap |
| `raw/cafes.json` | все объекты `amenity=cafe` в прямоугольнике 59.60–60.30 с.ш., 29.40–30.80 в.д. | OpenStreetMap через Overpass API | ODbL 1.0, © участники OpenStreetMap |
| `raw/population_wikidata.json` | население районов (свойство P1082) с датами | Wikidata, SPARQL | CC0 |

Скачать свежие данные (результаты могут немного отличаться от README):

```bash
python scripts/01_download_data.py --refresh
```

Папка `data/processed/` создаётся скриптами и в репозиторий не попадает.
