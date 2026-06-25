import requests
import logging
from config import OVERPASS_API, STATUS_UNKNOWN

logger = logging.getLogger(__name__)

# Запрос к Overpass API (OpenStreetMap)
# Получаем все официальные населённые пункты Украины
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

# Маппинг типов OSM → русские названия
PLACE_TYPE_MAP = {
    "city":          "Город",
    "town":          "Город",
    "village":       "Село",
    "hamlet":        "Хутор",
    "suburb":        "Посёлок",
    "urban_village": "Посёлок городского типа",
}


def fetch_settlements() -> list[dict]:
    """
    Загружает полный список населённых пунктов Украины из OpenStreetMap.
    Возвращает список словарей с полями:
      name, region, district, place_type, lat, lon
    """
    logger.info("Загрузка списка населённых пунктов из Overpass API...")
    try:
        response = requests.post(
            OVERPASS_API,
            data={"data": OVERPASS_QUERY},
            timeout=180  # большой таймаут — запрос тяжёлый
        )
        response.raise_for_status()
        data = response.json()
        settlements = []

        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name:ru") or tags.get("name") or tags.get("name:uk")
            if not name:
                continue  # пропускаем без названия

            place_type_raw = tags.get("place", "")
            place_type = PLACE_TYPE_MAP.get(place_type_raw, "Другой")

            # Область и район из тегов OSM
            region   = tags.get("addr:region", "") or _extract_admin(tags, "region")
            district = tags.get("addr:district", "") or _extract_admin(tags, "district")

            settlements.append({
                "name":       name,
                "region":     _normalize_region(region),
                "district":   district,
                "place_type": place_type,
                "lat":        element.get("lat", 0),
                "lon":        element.get("lon", 0),
                "status":     STATUS_UNKNOWN,
                "source":     "OpenStreetMap",
            })

        logger.info(f"Загружено {len(settlements)} населённых пунктов")
        return settlements

    except requests.RequestException as e:
        logger.error(f"Ошибка загрузки населённых пунктов: {e}")
        return []


def _extract_admin(tags: dict, level: str) -> str:
    """Вспомогательная — извлекает административные данные из тегов."""
    for key, value in tags.items():
        if level in key.lower():
            return value
    return ""


def _normalize_region(region: str) -> str:
    """Приводит название области к единому формату."""
    region = region.replace(" область", "").replace(" обл.", "").strip()
    # Добавляем суффикс если нужно
    if region and not region.endswith("область"):
        region = f"{region} область"
    return region
