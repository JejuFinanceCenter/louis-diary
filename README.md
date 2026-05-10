# 🌅 루이와 함께하는 다이어트 다이어리

제주 한경면 낙조길에서 반려견 루이와 함께 걷는 아내를 위한 Streamlit 다이어트 관리 앱.

- 14일 체중 추이 · 오늘의 탄단지 · 공복 시간 기반 단백질 위주 간식 추천
- 한식 사진 업로드 → Anthropic Claude Vision으로 영양 분석
- 체중/운동 코스(낙조길/월성사/보라매 공원) 기록

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

`ANTHROPIC_API_KEY` 환경변수가 없으면 식단 분석은 자동으로 데모 모드로 동작합니다.

## Streamlit Cloud 배포

1. https://share.streamlit.io 접속 → GitHub 로그인
2. **New app** → 이 저장소 선택, branch `main`, file `app.py`
3. **Advanced settings → Secrets** 에 아래 한 줄 입력:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-본인키"
   ```
4. **Deploy** 클릭

`secrets.toml.example` 의 형식대로 입력하면 됩니다. 실제 키는 절대 커밋하지 마세요.

## 스택

- Streamlit · pandas · plotly · Pillow · anthropic
- Python 3.12 권장
