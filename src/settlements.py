import requests
import logging
from config import STATUS_UNKNOWN

logger = logging.getLogger(__name__)

# Офіційний реєстр КОАТУУ з data.gov.ua
KOATUU_URL = (
    "https://data.gov.ua/en/dataset/dc081fb0-f504-4696-916c-a5b24312ab6e"
    "/resource/296adb7a-476a-40c8-9de6-211327cb3aa1/download/koatuu.json"
)

# Резервне джерело — Overpass API
OVERPASS_API  = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Україна"]["admin_level"="2"]->.ukraine;
(
  node["place"~"city|town|village|hamlet|suburb|urban_village"]
     (area.ukraine);
);
out body;
"""

# Коди категорій КОАТУУ
# Перший символ коду рівня 3 визначає тип
KOATUU_TYPE_MAP = {
    "М": "Місто",
    "Т": "Селище міського типу",
    "С": "Село",
    "Х": "Хутір",
    "С/Р": "Селище",
}

PLACE_TYPE_MAP = {
    "city":          "Місто",
    "town":          "Місто",
    "village":       "Село",
    "hamlet":        "Хутір",
    "suburb":        "Селище",
    "urban_village": "Селище міського типу",
}


def fetch_settlements() -> list[dict]:
    """
    Завантажує офіційний список населених пунктів з КОАТУУ.
    При помилці — використовує Overpass API як резерв.
    """
    settlements = _fetch_from_koatuu()
    if settlements:
        logger.info(f"Використано КОАТУУ: {len(settlements)} унікальних пунктів")
        return settlements

    logger.warning("КОАТУУ недоступний, використовуємо Overpass API...")
    return _fetch_from_overpass()


def _fetch_from_koatuu() -> list[dict]:
    """
    Завантажує дані з офіційного реєстру КОАТУУ.
    Структура: [{Код, Назва, Категорія}, ...]
    Код: 10 цифр, де перші 2 — область, 4 — район, решта — пункт
    """
    try:
        response = requests.get(KOATUU_URL, timeout=60)
        response.raise_for_status()
        data = response.json()

        settlements = []
        regions     = {}   # код_2 → назва області
        districts   = {}   # код_4 → назва району

        # Перший прохід — збираємо області і райони
        for item in data:
            code = str(item.get("Код", "")).strip()
            name = str(item.get("Назва", "")).strip()
            cat  = str(item.get("Категорія", "")).strip()

            if not code or not name:
                continue

            # Область: код закінчується на 00000000 (8 нулів)
            if code.endswith("00000000"):
                regions[code[:2]] = _normalize_region(name)

            # Район: код закінчується на 000000 (6 нулів) але не область
            elif code.endswith("000000") and not code.endswith("00000000"):
                districts[code[:4]] = name

        # Другий прохід — збираємо населені пункти
        seen_names = set()

        for item in data:
            code = str(item.get("Код", "")).strip()
            name = str(item.get("Назва", "")).strip()
            cat  = str(item.get("Категорія", "")).strip()

            if not code or not name:
                continue

            # Населені пункти: не закінчуються на 000000
            if code.endswith("000000"):
                continue

            # Визначаємо тип за категорією
            place_type = KOATUU_TYPE_MAP.get(cat, "Інший")

            # Визначаємо область і район за кодом
            region_key   = code[:2]
            district_key = code[:4]
            region   = regions.get(region_key, "")
            district = districts.get(district_key, "")

            # Унікальний ключ: назва + область (є однакові назви в різних областях)
            unique_key = f"{name.lower()}|{region}"
            if unique_key in seen_names:
                continue
            seen_names.add(unique_key)

            settlements.append({
                "name":       name,
                "region":     region,
                "district":   district,
                "place_type": place_type,
                "lat":        0,   # КОАТУУ не містить координат
                "lon":        0,
                "status":     STATUS_UNKNOWN,
            })

        logger.info(f"КОАТУУ: завантажено {len(settlements)} населених пунктів")
        return settlements

    except Exception as e:
        logger.error(f"Помилка завантаження КОАТУУ: {e}")
        return []


def _fetch_from_overpass() -> list[dict]:
    """Резервне джерело — OpenStreetMap Overpass API."""
    try:
        response = requests.post(
            OVERPASS_API,
            data={"data": OVERPASS_QUERY},
            timeout=180,
            headers={
                "User-Agent": "UkraineStatusTracker/1.0",
                "Accept":     "application/json"
            }
        )
        response.raise_for_status()
        data     = response.json()
        elements = data.get("elements", [])

        settlements = []
        seen_ids    = set()
        seen_coords = set()

        for element in elements:
            osm_id = element.get("id")
            if osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)

            tags = element.get("tags", {})
            name = (
                tags.get("name:uk") or
                tags.get("name") or
                tags.get("name:ru")
            )
            if not name:
                continue

            lat = round(float(element.get("lat", 0)), 4)
            lon = round(float(element.get("lon", 0)), 4)

            coord_key = (name.lower(), lat, lon)
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)

            place_type = PLACE_TYPE_MAP.get(tags.get("place", ""), "Інший")
            region     = _get_osm_region(tags)
            district   = tags.get("addr:district") or tags.get("is_in:district") or ""

            settlements.append({
                "name":       name,
                "region":     region,
                "district":   district,
                "place_type": place_type,
                "lat":        lat,
                "lon":        lon,
                "status":     STATUS_UNKNOWN,
            })

        logger.info(f"Overpass: {len(settlements)} населених пунктів після дедублікації")
        return settlements

    except Exception as e:
        logger.error(f"Помилка Overpass API: {e}")
        return []


def _normalize_region(name: str) -> str:
    """Приводить назву області до єдиного формату."""
    name = name.replace(" ОБЛАСТЬ", "").replace(" область", "").strip()
    name = name.capitalize()
    return f"{name} область"


def _get_osm_region(tags: dict) -> str:
    region = (
        tags.get("addr:region") or
        tags.get("is_in:region") or ""
    )
    region = region.replace(" область", "").replace(" обл.", "").strip()
    return f"{region} область" if region else ""
