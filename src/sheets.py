import os
import json
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import (
    HEADERS, SHEET_MAIN,
    STATUS_FREE, STATUS_OCCUPIED, STATUS_PARTIAL, STATUS_UNKNOWN,
    COLOR_FREE, COLOR_OCCUPIED, COLOR_PARTIAL, COLOR_UNKNOWN
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def connect_to_sheets() -> gspread.Spreadsheet:
    """Підключення до Google Sheets через сервісний акаунт."""
    creds_json      = os.environ["GOOGLE_CREDENTIALS"]
    spreadsheet_id  = os.environ["SPREADSHEET_ID"]
    creds_dict      = json.loads(creds_json)
    creds           = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client          = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


def setup_spreadsheet(spreadsheet: gspread.Spreadsheet):
    """
    Першочергове налаштування таблиці.
    Створює аркуш, заголовки та умовне форматування.
    Викликається тільки якщо структура ще не створена.
    """
    existing = [ws.title for ws in spreadsheet.worksheets()]

    if SHEET_MAIN not in existing:
        ws = spreadsheet.add_worksheet(SHEET_MAIN, rows=50000, cols=6)
        ws.append_row(HEADERS, value_input_option="USER_ENTERED")
        _apply_header_formatting(spreadsheet, ws)
        _apply_status_formatting(spreadsheet, ws)
        _enable_filters(spreadsheet, ws)
        logger.info(f"Створено аркуш '{SHEET_MAIN}'")
    else:
        # Аркуш вже існує — лише переконуємось що фільтр є
        ws = spreadsheet.worksheet(SHEET_MAIN)
        _enable_filters(spreadsheet, ws)


def _apply_header_formatting(spreadsheet: gspread.Spreadsheet, ws):
    """Жирний заголовок + заморожений перший рядок."""
    sheet_id = ws.id
    requests = [
        # Жирний текст заголовка
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)"
            }
        },
        # Заморожуємо перший рядок — він завжди видний при прокрутці
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        }
    ]
    spreadsheet.batch_update({"requests": requests})


def _apply_status_formatting(spreadsheet: gspread.Spreadsheet, ws):
    """Умовне форматування кольорів за статусом (стовпець Е — Статус)."""
    sheet_id = ws.id

    def color_rule(status: str, color: dict) -> dict:
        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startColumnIndex": 4,  # стовпець E (Статус)
                        "endColumnIndex": 5
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": status}]
                        },
                        "format": {"backgroundColor": color}
                    }
                },
                "index": 0
            }
        }

    spreadsheet.batch_update({"requests": [
        color_rule(STATUS_FREE,     COLOR_FREE),
        color_rule(STATUS_OCCUPIED, COLOR_OCCUPIED),
        color_rule(STATUS_PARTIAL,  COLOR_PARTIAL),
        color_rule(STATUS_UNKNOWN,  COLOR_UNKNOWN),
    ]})


def _enable_filters(spreadsheet: gspread.Spreadsheet, ws):
    """Вмикає стандартний фільтр Google Sheets на всіх стовпцях."""
    sheet_id = ws.id
    spreadsheet.batch_update({"requests": [{
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "startColumnIndex": 0,
                    "endColumnIndex": 6
                }
            }
        }
    }]})


def update_settlements(spreadsheet: gspread.Spreadsheet, settlements: list[dict]):
    """
    Розумне оновлення — змінює лише ті рядки, де статус змінився.
    Не перестворює таблицю повністю.
    """
    ws  = spreadsheet.worksheet(SHEET_MAIN)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Завантажуємо поточні дані для порівняння
    existing_data = ws.get_all_values()

    # Словник: "область|назва" → (номер рядка, поточний статус)
    existing_map: dict[str, tuple[int, str]] = {}
    for i, row in enumerate(existing_data[1:], start=2):
        if len(row) >= 5:
            key = f"{row[0]}|{row[2]}"
            existing_map[key] = (i, row[4])

    rows_to_append  = []
    cells_to_update = []

    for s in settlements:
        key = f"{s['region']}|{s['name']}"
        row_data = [
            s["region"],
            s["district"],
            s["name"],
            s["place_type"],
            s["status"],
            now,
            s["lat"],
            s["lon"],
        ]

        if key in existing_map:
            row_num, old_status = existing_map[key]
            if old_status != s["status"]:
                cells_to_update.append((row_num, row_data))
        else:
            rows_to_append.append(row_data)

    # Батч-оновлення змінених рядків
    if cells_to_update:
        batch = []
        for row_num, row_data in cells_to_update:
            for col_idx, value in enumerate(row_data, start=1):
                batch.append({
                    "range": gspread.utils.rowcol_to_a1(row_num, col_idx),
                    "values": [[value]]
                })
        ws.batch_update(batch)
        logger.info(f"Оновлено {len(cells_to_update)} записів зі зміненим статусом")

    # Додаємо нові записи
    if rows_to_append:
        ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        logger.info(f"Додано {len(rows_to_append)} нових записів")

    if not cells_to_update and not rows_to_append:
        logger.info("Змін не виявлено — таблиця актуальна")
