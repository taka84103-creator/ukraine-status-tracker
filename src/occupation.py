import requests
import logging

logger = logging.getLogger(__name__)

DEEPSTATE_URL = "https://deepstatemap.live/api/history/last"


def fetch_occupation_polygons() -> dict:
    """
    Завантажує GeoJSON полігони окупованих територій.
    При помилці основного джерела — пробує резервне.
    """
    polygons = _fetch_from_deepstate()
    if polygons and (polygons["occupied"] or polygons["partial"]):
        return polygons

    logger.warning("DeepStateMap не повернув полігони, пробуємо резервне джерело...")
    return {"occupied": [], "partial": [], "source": "недоступний"}


def _fetch_from_deepstate() -> dict | None:
    """Завантаження полігонів з DeepStateMap."""
    try:
        response = requests.get(DEEPSTATE_URL, timeout=30)
        response.raise_for_status()
        data = response.json()

        from shapely.geometry import shape

        # Структура відповіді: data["map"]["features"]
        map_data = data.get("map", {})
        features = map_data.get("features", [])

        logger.info(f"DeepStateMap: отримано {len(features)} об'єктів")

        occupied = []
        partial  = []

        for feature in features:
            geom  = feature.get("geometry")
            props = feature.get("properties", {})

            if not geom:
                continue

            # Логуємо перший елемент щоб бачити структуру properties
            if len(occupied) == 0 and len(partial) == 0:
                logger.info(f"Приклад properties: {props}")

            try:
                polygon = shape(geom)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)

                # Визначаємо статус за полями properties
                status = (
                    str(props.get("status", "")) or
                    str(props.get("type", "")) or
                    str(props.get("fill", "")) or
                    str(props.get("color", "")) or
                    ""
                ).lower()

                name = str(props.get("name", "")).lower()

                # Червоний колір (#e8534b або подібні) = окуповано
                fill = str(props.get("fill", "")).lower()

                if any(w in status for w in ["occupied", "окупо"]):
                    if any(w in status for w in ["partial", "частич", "contest"]):
                        partial.append(polygon)
                    else:
                        occupied.append(polygon)
                elif any(w in status for w in ["partial", "contest", "grey", "gray"]):
                    partial.append(polygon)
                elif "#e8" in fill or "#d4" in fill or "#c0" in fill:
                    # Червонуваті кольори — окуповані території
                    occupied.append(polygon)
                elif "#f5d" in fill or "#ffd" in fill or "#ff9" in fill:
                    # Жовтуваті кольори — частково окуповані
                    partial.append(polygon)
                else:
                    # Додаємо всі полігони як окуповані якщо статус незрозумілий
                    # (DeepStateMap зазвичай повертає лише окуповані зони)
                    occupied.append(polygon)

            except Exception as e:
                logger.debug(f"Помилка геометрії: {e}")
                continue

        logger.info(
            f"DeepStateMap: {len(occupied)} окупованих + {len(partial)} частково"
        )
        return {
            "occupied": occupied,
            "partial":  partial,
            "source":   "DeepStateMap"
        }

    except requests.RequestException as e:
        logger.warning(f"DeepStateMap недоступний: {e}")
        return None
