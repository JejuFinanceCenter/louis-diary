"""
루이와 함께하는 다이어트 다이어리
제주 한경면 낙조길 · Streamlit App
"""
from __future__ import annotations

import base64
import io
import json
import os
import random
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import sheets

# ─────────────────────────────────────────────────────────────
# 설정 & 테마
# ─────────────────────────────────────────────────────────────
WARM_ORANGE = "#FF8C42"
CALM_BLUE = "#4A90E2"
SOFT_PEACH = "#FFE0CC"
SOFT_SKY = "#D6E6F7"
INK = "#3A3A3A"

COURSES = ["낙조길", "월성사", "보라매 공원"]

def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("ANTHROPIC_API_KEY", "")).strip()
    except Exception:
        return ""


ANTHROPIC_API_KEY = _load_api_key()
DEMO_MODE = ANTHROPIC_API_KEY == ""

st.set_page_config(
    page_title="루이와 함께하는 다이어트 다이어리",
    page_icon="🌅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 커스텀 CSS – 제주 노을 테마
st.markdown(
    f"""
    <style>
        .stApp {{
            background: linear-gradient(180deg, #FFF6EE 0%, #F2F8FF 100%);
        }}
        h1, h2, h3 {{ color: {INK}; }}
        .louis-hero {{
            background: linear-gradient(120deg, {WARM_ORANGE} 0%, {CALM_BLUE} 120%);
            padding: 28px 32px;
            border-radius: 20px;
            color: white;
            box-shadow: 0 8px 24px rgba(255, 140, 66, 0.18);
            margin-bottom: 18px;
        }}
        .louis-hero h1 {{
            color: white;
            margin: 0;
            font-size: 1.9rem;
            line-height: 1.35;
        }}
        .louis-hero p {{
            color: rgba(255,255,255,0.92);
            margin: 8px 0 0 0;
            font-size: 0.98rem;
        }}
        .stat-card {{
            background: white;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 4px 14px rgba(74,144,226,0.08);
            border: 1px solid rgba(255,140,66,0.12);
        }}
        .stat-card .label {{
            color: #888; font-size: 0.85rem; margin-bottom: 6px;
        }}
        .stat-card .value {{
            color: {INK}; font-size: 1.6rem; font-weight: 700;
        }}
        .louis-bubble {{
            background: {SOFT_PEACH};
            border-left: 4px solid {WARM_ORANGE};
            padding: 14px 18px;
            border-radius: 12px;
            margin: 12px 0;
            color: {INK};
            font-size: 0.95rem;
            line-height: 1.55;
        }}
        .louis-bubble.cool {{
            background: {SOFT_SKY};
            border-left-color: {CALM_BLUE};
        }}
        div[data-testid="stMetricValue"] {{ color: {WARM_ORANGE}; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
        .stTabs [data-baseweb="tab"] {{
            background: white;
            border-radius: 10px 10px 0 0;
            padding: 10px 18px;
            border: 1px solid rgba(74,144,226,0.15);
        }}
        .stTabs [aria-selected="true"] {{
            background: {WARM_ORANGE} !important;
            color: white !important;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
# Session state 초기화
# ─────────────────────────────────────────────────────────────
def _seed_demo_weights() -> list[dict]:
    today = date.today()
    base = 53.0
    rows = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        # 자연스러운 변동: 약간씩 감소 + 노이즈
        w = base - (13 - i) * 0.08 + random.uniform(-0.25, 0.25)
        rows.append({"date": d, "weight": round(w, 1)})
    return rows


def _seed_demo_exercise() -> list[dict]:
    today = date.today()
    rows = []
    for i in range(7, -1, -1):
        d = today - timedelta(days=i)
        course = random.choice(COURSES)
        rows.append(
            {
                "date": d,
                "course": course,
                "distance_km": round(random.uniform(2.0, 4.5), 1),
                "minutes": random.randint(28, 55),
            }
        )
    return rows


def _try_load_from_sheets() -> tuple[dict, str]:
    """시트에서 데이터 로드 시도. (data_dict, status_message) 반환.
    status가 빈 문자열이면 성공, 아니면 폴백 사유."""
    if not sheets.is_configured():
        return ({}, "no_config")
    try:
        return (
            {
                "weights": sheets.load_weights(),
                "meals": sheets.load_meals(),
                "exercises": sheets.load_exercises(),
            },
            "",
        )
    except Exception as e:
        return ({}, f"connect_failed: {type(e).__name__}: {e}")


def init_state() -> None:
    if "profile" not in st.session_state:
        st.session_state.profile = {
            "name": "아내",
            "dog": "루이",
            "height_cm": 163.0,
            "current_kg": 53.0,
            "goal_kg": 50.0,
            "preference": "한식",
        }

    # 시트 1회 로드 시도 (전체 세션에 1번)
    if "sheets_status" not in st.session_state:
        loaded, status = _try_load_from_sheets()
        st.session_state.sheets_status = status  # ""=ok, 그 외 사유

        if status == "":
            # 성공: 시트 데이터로 채우기, 비어있으면 시드
            random.seed(42)
            st.session_state.weights = loaded["weights"] or _seed_demo_weights()
            st.session_state.meals = loaded["meals"] or [
                {
                    "datetime": datetime.now() - timedelta(hours=5),
                    "name": "현미밥 + 된장찌개 + 시금치나물",
                    "calories": 520,
                    "protein_g": 22,
                    "carbs_g": 78,
                    "fat_g": 12,
                    "note": "데모 시드",
                }
            ]
            random.seed(7)
            st.session_state.exercises = loaded["exercises"] or _seed_demo_exercise()
        else:
            # 폴백: 데모 시드
            random.seed(42)
            st.session_state.weights = _seed_demo_weights()
            st.session_state.meals = [
                {
                    "datetime": datetime.now() - timedelta(hours=5),
                    "name": "현미밥 + 된장찌개 + 시금치나물",
                    "calories": 520,
                    "protein_g": 22,
                    "carbs_g": 78,
                    "fat_g": 12,
                    "note": "데모 시드",
                }
            ]
            random.seed(7)
            st.session_state.exercises = _seed_demo_exercise()


init_state()


def sheets_ok() -> bool:
    return st.session_state.get("sheets_status") == ""


def try_persist(label: str, fn, *args, **kwargs) -> None:
    """시트 저장 시도. 실패하면 토스트만 띄우고 조용히 넘어감."""
    if not sheets_ok():
        return
    try:
        fn(*args, **kwargs)
    except Exception as e:
        st.toast(f"📋 시트 저장 실패 ({label}) — 이번 세션에만 보관됩니다", icon="⚠️")
        st.session_state.sheets_status = f"write_failed: {type(e).__name__}"


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────
def hours_since_last_meal() -> float | None:
    if not st.session_state.meals:
        return None
    last = max(m["datetime"] for m in st.session_state.meals)
    return round((datetime.now() - last).total_seconds() / 3600, 1)


def today_macros() -> dict:
    today = date.today()
    todays = [m for m in st.session_state.meals if m["datetime"].date() == today]
    return {
        "calories": sum(m["calories"] for m in todays),
        "protein_g": sum(m["protein_g"] for m in todays),
        "carbs_g": sum(m["carbs_g"] for m in todays),
        "fat_g": sum(m["fat_g"] for m in todays),
        "count": len(todays),
    }


def snack_recommendation(hours: float | None, macros: dict) -> tuple[str, str]:
    """근손실 방지 우선 — 단백질 위주 추천"""
    protein_today = macros["protein_g"]
    target_protein = 70  # 50kg 목표 × 1.4g/kg
    needs_protein = protein_today < target_protein * 0.6

    if hours is None:
        return ("☕ 오늘 첫 끼 어때요?", "달걀 2개 + 그릭요거트 한 컵으로 가볍게 시작해볼까요?")

    if hours < 2:
        return (
            "🍵 방금 드셨으니 잠깐 쉬어가요",
            "산책하기 딱 좋은 타이밍이에요. 루이도 꼬리 흔들고 있을걸요? 🐶",
        )
    if hours < 4:
        return (
            "💧 물 한 잔 어떠세요?",
            "지금 간식보다는 따뜻한 물이나 보리차가 좋아요. 식욕도 차분해져요.",
        )
    if hours < 6:
        if needs_protein:
            return (
                "🥚 단백질 보충 타이밍!",
                "삶은 달걀 1~2개 또는 두유 200ml. 근손실은 우리의 적이니까요.",
            )
        return (
            "🍎 살짝 출출하면 가볍게",
            "방울토마토 한 줌 + 견과류 5~6알이면 충분해요.",
        )
    # 6시간 이상 공복
    return (
        "🚨 공복이 길어요 — 챙겨 드세요",
        "그릭요거트 + 닭가슴살 슬라이스 또는 두부 부침. 근육 지키는 게 우선이에요!",
    )


def hero_header() -> None:
    st.markdown(
        """
        <div class="louis-hero">
            <h1>🌅 오늘도 루이와 함께 즐겁게 걸어볼까요?</h1>
            <p>제주 한경면 낙조길 · 천천히, 꾸준히, 즐겁게</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def louis_says(msg: str, cool: bool = False) -> None:
    cls = "louis-bubble cool" if cool else "louis-bubble"
    st.markdown(f'<div class="{cls}">🐶 <b>루이의 한마디</b><br>{msg}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Anthropic Vision (식단 분석)
# ─────────────────────────────────────────────────────────────
def analyze_food_image(image_bytes: bytes) -> dict:
    """이미지를 Anthropic Vision으로 분석. 데모 모드면 mock 반환."""
    if DEMO_MODE:
        # 한식 데모 응답
        return {
            "demo": True,
            "dish": "비빔밥 (예시 분석)",
            "items": ["현미밥", "나물 모듬", "달걀 후라이", "고추장", "참기름"],
            "calories": 580,
            "protein_g": 21,
            "carbs_g": 88,
            "fat_g": 14,
            "comment": "탄수화물이 다소 높지만 채소가 풍부해요. 단백질을 +10g 정도 더 추가하면 균형이 좋아져요. 다음 끼니에 두부나 달걀을 곁들여보세요.",
        }

    try:
        import anthropic
    except ImportError:
        return {"error": "anthropic 패키지가 설치되지 않았습니다."}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    prompt = (
        "이 한식 사진을 분석해서 JSON으로만 답해주세요. 형식:\n"
        "{\n"
        '  "dish": "음식 이름",\n'
        '  "items": ["구성 재료1", "재료2", ...],\n'
        '  "calories": 추정 kcal (정수),\n'
        '  "protein_g": 단백질 g (정수),\n'
        '  "carbs_g": 탄수화물 g (정수),\n'
        '  "fat_g": 지방 g (정수),\n'
        '  "comment": "다이어트/근손실 방지 관점의 따뜻한 한 줄 코멘트"\n'
        "}\n"
        "JSON 외 다른 텍스트는 절대 포함하지 마세요."
    )

    try:
        msg = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=600,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        data["demo"] = False
        return data
    except Exception as e:
        return {"error": f"분석 실패: {e}"}


# ─────────────────────────────────────────────────────────────
# 사이드바 (프로필)
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👩 프로필")
    p = st.session_state.profile
    p["height_cm"] = st.number_input("키 (cm)", 140.0, 200.0, p["height_cm"], 0.5)
    p["current_kg"] = st.number_input("현재 체중 (kg)", 35.0, 120.0, p["current_kg"], 0.1)
    p["goal_kg"] = st.number_input("목표 체중 (kg)", 35.0, 120.0, p["goal_kg"], 0.1)
    p["preference"] = st.text_input("선호 식단", p["preference"])

    st.divider()
    st.markdown("### 🐶 산책 친구")
    st.write(f"**{p['dog']}** 와 함께 걷는 코스")
    for c in COURSES:
        st.write(f"• {c}")

    st.divider()
    if DEMO_MODE:
        st.info("🧪 데모 모드\n\n`ANTHROPIC_API_KEY` 환경변수를 설정하면 실제 Vision 분석이 활성화돼요.")
    else:
        st.success("✅ Vision 분석 활성화")

    st.divider()
    if sheets_ok():
        st.success("☁️ Google Sheets 연결됨\n\n입력 즉시 영구 저장됩니다.")
    else:
        reason = st.session_state.get("sheets_status", "unknown")
        if reason == "no_config":
            st.info("💾 로컬 모드\n\nGoogle Sheets 연동을 설정하면 데이터가 영구 저장돼요. README 참고.")
        else:
            st.warning(f"⚠️ 시트 연결 실패\n\n로컬 세션에만 저장 중. 사유: `{reason}`")


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
hero_header()

tab1, tab2, tab3, tab4 = st.tabs(["📊 대시보드", "📷 식단 분석", "⚖️ 체중 기록", "🏃 운동 기록"])


# ── 탭 1: 대시보드 ──────────────────────────────────────────
with tab1:
    p = st.session_state.profile
    weights_df = pd.DataFrame(st.session_state.weights).sort_values("date")
    latest_w = weights_df.iloc[-1]["weight"]
    delta_to_goal = latest_w - p["goal_kg"]
    week_delta = (
        weights_df.iloc[-1]["weight"] - weights_df.iloc[-7]["weight"]
        if len(weights_df) >= 7
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="stat-card"><div class="label">현재 체중</div>'
            f'<div class="value">{latest_w:.1f} kg</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="stat-card"><div class="label">목표까지</div>'
            f'<div class="value">{delta_to_goal:+.1f} kg</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="stat-card"><div class="label">최근 7일</div>'
            f'<div class="value">{week_delta:+.1f} kg</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        h = hours_since_last_meal()
        h_text = f"{h} 시간" if h is not None else "기록 없음"
        st.markdown(
            f'<div class="stat-card"><div class="label">마지막 식사 후</div>'
            f'<div class="value">{h_text}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### 📈 최근 14일 체중 변화")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=weights_df["date"],
            y=weights_df["weight"],
            mode="lines+markers",
            line=dict(color=WARM_ORANGE, width=3, shape="spline"),
            marker=dict(size=9, color=WARM_ORANGE, line=dict(color="white", width=2)),
            fill="tozeroy",
            fillcolor="rgba(255,140,66,0.12)",
            name="체중",
            hovertemplate="%{x|%m월 %d일}<br>%{y:.1f} kg<extra></extra>",
        )
    )
    fig.add_hline(
        y=p["goal_kg"],
        line=dict(color=CALM_BLUE, dash="dash", width=2),
        annotation_text=f"목표 {p['goal_kg']:.1f}kg",
        annotation_position="top right",
        annotation_font_color=CALM_BLUE,
    )
    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        yaxis=dict(
            range=[
                min(weights_df["weight"].min(), p["goal_kg"]) - 0.8,
                weights_df["weight"].max() + 0.8,
            ],
            gridcolor="#F0F0F0",
        ),
        xaxis=dict(gridcolor="#F8F8F8"),
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### 🍱 오늘의 탄단지")
        macros = today_macros()
        if macros["count"] == 0:
            st.info("오늘 식사 기록이 아직 없어요. 식단 분석 탭에서 추가해보세요!")
        else:
            donut = go.Figure(
                data=[
                    go.Pie(
                        labels=["탄수화물", "단백질", "지방"],
                        values=[macros["carbs_g"], macros["protein_g"], macros["fat_g"]],
                        hole=0.62,
                        marker=dict(
                            colors=[WARM_ORANGE, CALM_BLUE, "#F4C430"],
                            line=dict(color="white", width=3),
                        ),
                        textinfo="label+percent",
                        textfont=dict(size=13),
                    )
                ]
            )
            donut.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=10),
                annotations=[
                    dict(
                        text=f"<b>{macros['calories']}</b><br>kcal",
                        font=dict(size=18, color=INK),
                        showarrow=False,
                    )
                ],
                showlegend=False,
            )
            st.plotly_chart(donut, width="stretch")
            st.caption(
                f"단백질 {macros['protein_g']}g · 탄수 {macros['carbs_g']}g · 지방 {macros['fat_g']}g · "
                f"식사 {macros['count']}회"
            )

    with col_right:
        st.markdown("### 💡 지금 이 순간 추천")
        h = hours_since_last_meal()
        macros = today_macros()
        title, body = snack_recommendation(h, macros)
        st.markdown(f"**{title}**")
        louis_says(body)

        # 단백질 게이지
        target = 70
        progress = min(macros["protein_g"] / target, 1.0)
        st.markdown(f"**오늘의 단백질 목표** ({macros['protein_g']} / {target}g)")
        st.progress(progress)
        if progress < 0.5:
            st.caption("💪 근손실 방지 — 단백질 더 챙겨주세요!")
        elif progress < 0.9:
            st.caption("👍 좋아요, 한 끼만 더 단백질 위주로!")
        else:
            st.caption("🎉 오늘 단백질 합격!")


# ── 탭 2: 식단 분석 ─────────────────────────────────────────
with tab2:
    st.markdown("### 📷 식단 사진 분석")
    if DEMO_MODE:
        st.warning(
            "🧪 **데모 모드** — 실제 API 호출 없이 예시 결과를 보여드려요. "
            "`ANTHROPIC_API_KEY` 환경변수를 설정하면 진짜 분석이 켜져요."
        )

    uploaded = st.file_uploader(
        "한 끼 식사 사진을 올려주세요 (jpg/png)",
        type=["jpg", "jpeg", "png"],
    )

    col_a, col_b = st.columns([1, 1])

    if uploaded is not None:
        image_bytes = uploaded.read()
        with col_a:
            img = Image.open(io.BytesIO(image_bytes))
            st.image(img, caption="업로드한 식단", width="stretch")

        with col_b:
            with st.spinner("루이가 분석 중... 🐾"):
                result = analyze_food_image(image_bytes)

            if "error" in result:
                st.error(result["error"])
            else:
                if result.get("demo"):
                    st.info("🧪 데모 응답")
                st.markdown(f"#### 🍽️ {result['dish']}")
                st.write("**구성:** " + ", ".join(result["items"]))

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("칼로리", f"{result['calories']} kcal")
                m2.metric("단백질", f"{result['protein_g']} g")
                m3.metric("탄수화물", f"{result['carbs_g']} g")
                m4.metric("지방", f"{result['fat_g']} g")

                louis_says(result["comment"], cool=True)

                if st.button("💾 오늘 식사로 기록", type="primary"):
                    new_meal = {
                        "datetime": datetime.now(),
                        "name": result["dish"],
                        "calories": result["calories"],
                        "protein_g": result["protein_g"],
                        "carbs_g": result["carbs_g"],
                        "fat_g": result["fat_g"],
                        "note": "사진 분석",
                    }
                    st.session_state.meals.append(new_meal)
                    try_persist("식단", sheets.append_meal, new_meal)
                    st.success("기록했어요! 대시보드에서 확인해보세요.")
                    st.rerun()
    else:
        with col_a:
            st.markdown(
                f"""
                <div style="border:2px dashed {WARM_ORANGE}; border-radius:14px;
                            padding:48px 20px; text-align:center; color:#888;">
                    📸<br><br>여기에 식단 사진을 끌어다 놓거나<br>위에서 파일을 골라주세요
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_b:
            louis_says(
                "사진만 올려주시면 한식 위주로 칼로리/단백질/탄수/지방을 추정해드릴게요. "
                "불규칙한 식사라도 기록만 쌓이면 패턴이 보여요. 부담없이 한 끼씩!",
                cool=True,
            )

    st.divider()
    st.markdown("### 📜 최근 식사 기록")
    if st.session_state.meals:
        meals_df = pd.DataFrame(st.session_state.meals)
        meals_df = meals_df.sort_values("datetime", ascending=False).copy()
        meals_df["시각"] = meals_df["datetime"].dt.strftime("%m/%d %H:%M")
        show = meals_df[["시각", "name", "calories", "protein_g", "carbs_g", "fat_g", "note"]]
        show.columns = ["시각", "메뉴", "kcal", "단백질g", "탄수g", "지방g", "메모"]
        st.dataframe(show, width="stretch", hide_index=True)
    else:
        st.caption("아직 기록이 없어요.")


# ── 탭 3: 체중 기록 ─────────────────────────────────────────
with tab3:
    st.markdown("### ⚖️ 오늘의 체중 입력")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_date = st.date_input("날짜", value=date.today(), key="w_date")
    with col2:
        new_weight = st.number_input(
            "체중 (kg)",
            35.0,
            120.0,
            float(st.session_state.weights[-1]["weight"]),
            0.1,
            key="w_value",
        )
    with col3:
        st.write("")
        st.write("")
        if st.button("기록", type="primary", width="stretch"):
            # 같은 날짜면 덮어쓰기
            existing = next(
                (i for i, w in enumerate(st.session_state.weights) if w["date"] == new_date),
                None,
            )
            if existing is not None:
                st.session_state.weights[existing]["weight"] = new_weight
            else:
                st.session_state.weights.append({"date": new_date, "weight": new_weight})
            p = st.session_state.profile
            p["current_kg"] = new_weight
            try_persist("체중", sheets.upsert_weight, new_date, new_weight)
            st.success(f"{new_date.strftime('%m월 %d일')} · {new_weight}kg 저장!")
            st.rerun()

    p = st.session_state.profile
    if new_weight - p["goal_kg"] < 0.5:
        louis_says(
            f"우와 {p['goal_kg']}kg 코앞이에요! 🎉 이대로만 가면 곧 목표 달성! "
            "단, 체중계 숫자보다 컨디션이 더 중요해요.",
            cool=True,
        )

    st.divider()
    st.markdown("### 📋 전체 체중 기록")

    weights_df = pd.DataFrame(st.session_state.weights).sort_values("date", ascending=False).copy()
    weights_df["변화"] = weights_df["weight"].diff(-1).round(2)
    weights_df["날짜"] = pd.to_datetime(weights_df["date"]).dt.strftime("%Y-%m-%d (%a)")
    show = weights_df[["날짜", "weight", "변화"]]
    show.columns = ["날짜", "체중(kg)", "전일比(kg)"]
    st.dataframe(show, width="stretch", hide_index=True, height=380)


# ── 탭 4: 운동 기록 ─────────────────────────────────────────
with tab4:
    st.markdown("### 🏃 산책/운동 기록")

    col1, col2, col3, col4, col5 = st.columns([1.2, 1.5, 1, 1, 1])
    with col1:
        ex_date = st.date_input("날짜", value=date.today(), key="ex_date")
    with col2:
        ex_course = st.selectbox("코스", COURSES, key="ex_course")
    with col3:
        ex_dist = st.number_input("거리(km)", 0.0, 30.0, 3.0, 0.1, key="ex_dist")
    with col4:
        ex_min = st.number_input("시간(분)", 0, 240, 35, 1, key="ex_min")
    with col5:
        st.write("")
        st.write("")
        if st.button("기록", type="primary", width="stretch", key="ex_save"):
            new_ex = {
                "date": ex_date,
                "course": ex_course,
                "distance_km": ex_dist,
                "minutes": ex_min,
            }
            st.session_state.exercises.append(new_ex)
            try_persist("운동", sheets.append_exercise, new_ex)
            st.success(f"{ex_course} · {ex_dist}km · {ex_min}분 기록 완료!")
            st.rerun()

    louis_says(
        f"오늘 어디 갈까요? 낙조길은 노을, 월성사는 조용한 산책, 보라매 공원은 사람 구경! 🐕",
        cool=False,
    )

    st.divider()
    st.markdown("### 📊 일자별 운동량")

    if st.session_state.exercises:
        ex_df = pd.DataFrame(st.session_state.exercises)
        ex_df["date"] = pd.to_datetime(ex_df["date"])
        # 일자×코스 합계 (스택 막대)
        agg = ex_df.groupby(["date", "course"], as_index=False)["distance_km"].sum()

        bar = px.bar(
            agg,
            x="date",
            y="distance_km",
            color="course",
            color_discrete_map={
                "낙조길": WARM_ORANGE,
                "월성사": "#7BAFD4",
                "보라매 공원": CALM_BLUE,
            },
            labels={"date": "날짜", "distance_km": "거리 (km)", "course": "코스"},
        )
        bar.update_layout(
            height=340,
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(gridcolor="#F0F0F0"),
            xaxis=dict(gridcolor="#F8F8F8"),
            legend=dict(orientation="h", y=-0.2),
            barmode="stack",
        )
        st.plotly_chart(bar, width="stretch")

        # 통계
        total_km = ex_df["distance_km"].sum()
        total_min = ex_df["minutes"].sum()
        favorite = ex_df["course"].mode().iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("총 거리", f"{total_km:.1f} km")
        c2.metric("총 시간", f"{total_min} 분")
        c3.metric("최애 코스", favorite)

        st.markdown("#### 📋 운동 기록")
        show = ex_df.sort_values("date", ascending=False).copy()
        show["날짜"] = show["date"].dt.strftime("%Y-%m-%d (%a)")
        show = show[["날짜", "course", "distance_km", "minutes"]]
        show.columns = ["날짜", "코스", "거리(km)", "시간(분)"]
        st.dataframe(show, width="stretch", hide_index=True)
    else:
        st.caption("아직 운동 기록이 없어요. 루이가 기다리고 있어요! 🐾")


# 푸터
st.markdown(
    f"""
    <div style="text-align:center; color:#aaa; font-size:0.82rem; margin-top:32px; padding:16px;">
        🌅 제주 한경면 낙조길 · {p['dog']}와 함께
    </div>
    """,
    unsafe_allow_html=True,
)
