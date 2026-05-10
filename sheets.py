"""
Google Sheets 영구 저장 백엔드.

연결 실패 시 RuntimeError 를 던집니다 — 호출 측에서 try/except 로 잡고
session_state 폴백으로 동작하세요.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st


WEIGHT_SHEET = "weight_log"
MEAL_SHEET = "meal_log"
EXERCISE_SHEET = "exercise_log"

WEIGHT_HEADERS = ["date", "weight"]
MEAL_HEADERS = ["timestamp", "food_name", "calories", "protein", "carbs", "fat"]
EXERCISE_HEADERS = ["timestamp", "course", "distance", "duration", "calories"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def is_configured() -> bool:
    """secrets에 시트 연결 정보가 모두 있는지 확인 (가벼운 체크)."""
    try:
        return bool(
            st.secrets.get("spreadsheet_id")
            and st.secrets.get("gcp_service_account")
        )
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _get_spreadsheet():
    """gspread Spreadsheet 객체. 시트별로 1번만 인증/오픈."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as e:
        raise RuntimeError(f"gspread/google-auth 미설치: {e}")

    if not is_configured():
        raise RuntimeError("secrets에 spreadsheet_id 또는 gcp_service_account 가 없습니다.")

    sa_info = dict(st.secrets["gcp_service_account"])
    spreadsheet_id = str(st.secrets["spreadsheet_id"])

    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


def _get_or_create_worksheet(name: str, headers: list[str]):
    sh = _get_spreadsheet()
    try:
        ws = sh.worksheet(name)
    except Exception:
        # 없으면 만들고 헤더 채워넣기
        ws = sh.add_worksheet(title=name, rows=1000, cols=max(10, len(headers)))
        ws.update(values=[headers], range_name="A1")
        return ws

    # 헤더가 비어있으면 채워넣기
    first_row = ws.row_values(1)
    if not first_row:
        ws.update(values=[headers], range_name="A1")
    return ws


# ─────────────────────────────────────────────────────────────
# Load
# ─────────────────────────────────────────────────────────────
def load_weights() -> list[dict]:
    ws = _get_or_create_worksheet(WEIGHT_SHEET, WEIGHT_HEADERS)
    rows = ws.get_all_records()
    out = []
    for r in rows:
        try:
            d = pd.to_datetime(str(r["date"])).date()
            w = float(r["weight"])
            out.append({"date": d, "weight": w})
        except (ValueError, TypeError, KeyError):
            continue
    return out


def load_meals() -> list[dict]:
    ws = _get_or_create_worksheet(MEAL_SHEET, MEAL_HEADERS)
    rows = ws.get_all_records()
    out = []
    for r in rows:
        try:
            ts = pd.to_datetime(str(r["timestamp"])).to_pydatetime()
            out.append(
                {
                    "datetime": ts,
                    "name": str(r.get("food_name", "")),
                    "calories": int(float(r.get("calories", 0) or 0)),
                    "protein_g": int(float(r.get("protein", 0) or 0)),
                    "carbs_g": int(float(r.get("carbs", 0) or 0)),
                    "fat_g": int(float(r.get("fat", 0) or 0)),
                    "note": "sheets",
                }
            )
        except (ValueError, TypeError, KeyError):
            continue
    return out


def load_exercises() -> list[dict]:
    ws = _get_or_create_worksheet(EXERCISE_SHEET, EXERCISE_HEADERS)
    rows = ws.get_all_records()
    out = []
    for r in rows:
        try:
            ts = pd.to_datetime(str(r["timestamp"]))
            out.append(
                {
                    "date": ts.date(),
                    "course": str(r.get("course", "")),
                    "distance_km": float(r.get("distance", 0) or 0),
                    "minutes": int(float(r.get("duration", 0) or 0)),
                }
            )
        except (ValueError, TypeError, KeyError):
            continue
    return out


# ─────────────────────────────────────────────────────────────
# Append
# ─────────────────────────────────────────────────────────────
def _to_iso_date(d: Any) -> str:
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y-%m-%d")
    return str(d)


def _to_iso_ts(t: Any) -> str:
    if isinstance(t, datetime):
        return t.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(t, date):
        return t.strftime("%Y-%m-%d 00:00:00")
    return str(t)


def upsert_weight(d: date, weight: float) -> None:
    """같은 날짜는 덮어쓰기."""
    ws = _get_or_create_worksheet(WEIGHT_SHEET, WEIGHT_HEADERS)
    iso = _to_iso_date(d)
    rows = ws.get_all_records()
    target_row = None
    for i, r in enumerate(rows, start=2):
        if str(r.get("date")) == iso:
            target_row = i
            break
    if target_row:
        ws.update(values=[[iso, float(weight)]], range_name=f"A{target_row}:B{target_row}")
    else:
        ws.append_row([iso, float(weight)], value_input_option="USER_ENTERED")


def append_meal(meal: dict) -> None:
    ws = _get_or_create_worksheet(MEAL_SHEET, MEAL_HEADERS)
    ws.append_row(
        [
            _to_iso_ts(meal["datetime"]),
            meal["name"],
            int(meal["calories"]),
            int(meal["protein_g"]),
            int(meal["carbs_g"]),
            int(meal["fat_g"]),
        ],
        value_input_option="USER_ENTERED",
    )


def append_exercise(ex: dict) -> None:
    ws = _get_or_create_worksheet(EXERCISE_SHEET, EXERCISE_HEADERS)
    # calories 는 입력에 없어서 거리 기반 간이 추정 (5km≈250kcal)
    est_cal = int(round(float(ex["distance_km"]) * 55))
    ws.append_row(
        [
            _to_iso_ts(ex["date"]),
            ex["course"],
            float(ex["distance_km"]),
            int(ex["minutes"]),
            est_cal,
        ],
        value_input_option="USER_ENTERED",
    )
