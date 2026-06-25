import requests
import logging
from config import OVERPASS_API, STATUS_UNKNOWN

logger = logging.getLogger(__name__)

OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Україна"]["admin_level"="2"]->.ukraine;
(
  node["place"~"city|town|village|hamlet|suburb"]
     (area.ukraine);
  node["place"="urban_village"](area.ukraine);
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
    Завантажує повний список населених пунктів України з OpenStreetMap.
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
        settlements = []

        for element in data.get("elements", []):
            tags = element.get("tags", {})

            # Пріоритет: українська назва → загальна → російська
            name = (
                tags.get("name:uk") or
                tags.get("name") or
                tags.get("name:ru")
            )
            if not name:
                continue

            place_type_raw = tags.get("place", "")
            place_type = PLACE_TYPE_MAP.get(place_type_raw, "Інший")

            # Область і район
            region   = _get_region(tags)
            district = _get_district(tags)

            settlements.append({
                "name":       name,
                "region":     region,
                "district":   district,
                "place_type": place_type,
                "lat":        element.get("lat", 0),
                "lon":        element.get("lon", 0),
                "status":     STATUS_UNKNOWN,
            })

        logger.info(f"Завантажено {len(settlements)} населених пунктів")
        return settlements

    except requests.RequestException as e:
        logger.error(f"Помилка завантаження населених пунктів: {e}")
        return []


def _get_region(tags: dict) -> str:
    """Витягує назву області з тегів OSM."""
    region = (
        tags.get("addr:region") or
        tags.get("is_in:region") or
        ""
    )
    # Прибираємо дублювання слова "область"
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
