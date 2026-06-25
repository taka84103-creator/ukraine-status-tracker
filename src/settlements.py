import requests
import logging
from config import OVERPASS_API, STATUS_UNKNOWN

logger = logging.getLogger(__name__)

OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Україна"]["admin_level"="2"]->.ukraine;
(
  node["place"~"city|town|village|hamlet|suburb|urban_village"]
     (area.ukraine);
);
out body;
"""

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
    Завантажує список населених пунктів України.
    Автоматично видаляє дублікати за координатами та назвою.
    """
    logger.info("Завантаження списку населених пунктів з Overpass API...")
    try:
        response = requests.post(
            OVERPASS_API,
            data={"data": OVERPASS_QUERY},
            timeout=180,
            headers={
                "User-Agent": "UkraineStatusTracker/1.0",
                "Accept": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()
        elements = data.get("elements", [])
        logger.info(f"Отримано {len(elements)} елементів з OSM (до дедублікації)")

        settlements = []

        # Два рівні захисту від дублікатів:
        # 1. За OSM id (один і той самий вузол)
        # 2. За координатами з округленням до 4 знаків (~11м точність)
        seen_ids    = set()
        seen_coords = set()

        for element in elements:
            osm_id = element.get("id")
            if osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)

            tags = element.get("tags", {})

            # Пріоритет назви: українська → загальна → російська
            name = (
                tags.get("name:uk") or
                tags.get("name") or
                tags.get("name:ru")
            )
            if not name:
                continue

            lat = round(float(element.get("lat", 0)), 4)
            lon = round(float(element.get("lon", 0)), 4)

            # Пропускаємо якщо вже є населений пункт з такою самою
            # назвою на відстані менше ~11 метрів
            coord_key = (name.lower(), lat, lon)
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)

            place_type_raw = tags.get("place", "")
            place_type = PLACE_TYPE_MAP.get(place_type_raw, "Інший")

            region   = _get_region(tags)
            district = _get_district(tags)

            settlements.append({
                "name":       name,
                "region":     region,
                "district":   district,
                "place_type": place_type,
                "lat":        lat,
                "lon":        lon,
                "status":     STATUS_UNKNOWN,
            })

        logger.info(f"Після дедублікації: {len(settlements)} унікальних населених пунктів")
        return settlements

    except requests.RequestException as e:
        logger.error(f"Помилка завантаження населених пунктів: {e}")
        return []


def _get_region(tags: dict) -> str:
    """Витягує назву області з тегів OSM."""
    region = (
        tags.get("addr:region") or
        tags.get("is_in:region") or
        tags.get("addr:state") or
        ""
    )
    region = region.replace(" область", "").replace(" обл.", "").strip()
    if region:
        return f"{region} область"
    return ""


def _get_district(tags: dict) -> str:
    """Витягує назву району з тегів OSM."""
    return (
        tags.get("addr:district") or
        tags.get("is_in:district") or
        ""
    )
