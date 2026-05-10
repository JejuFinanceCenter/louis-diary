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

## Google Sheets 영구 저장 연동 (선택)

기본 상태에서는 데이터가 `st.session_state`에만 저장돼서 새로고침하면 시드값으로 리셋됩니다. 체중·식단·운동 로그를 영구 저장하려면 Google Sheets를 백엔드로 연결할 수 있어요. **연결이 안 되면 자동으로 session_state 폴백**이라 앱은 항상 동작합니다.

### 1단계: Google Cloud 프로젝트 만들기

1. https://console.cloud.google.com 접속 → Google 계정 로그인
2. 상단 헤더의 **프로젝트 선택** 드롭다운 클릭 → 우상단 **새 프로젝트**
3. 프로젝트 이름: `louis-diary` (또는 원하는 이름) 입력 → **만들기**
4. 알림창의 **프로젝트 선택** 으로 방금 만든 프로젝트로 전환 (헤더 드롭다운에 표시되는지 확인)

### 2단계: 필요한 API 두 개 활성화

1. 좌측 햄버거 메뉴 ☰ → **API 및 서비스 → 라이브러리**
2. 검색창에 `Google Sheets API` 입력 → 결과 클릭 → **사용** 버튼
3. 다시 ☰ → **API 및 서비스 → 라이브러리**
4. 검색창에 `Google Drive API` 입력 → 결과 클릭 → **사용** 버튼
   - Sheets API만으로는 시트를 못 찾는 경우가 있어 Drive API도 필수입니다

### 3단계: 서비스 계정 만들기

1. ☰ → **IAM 및 관리자 → 서비스 계정**
2. 상단 **+ 서비스 계정 만들기**
3. 이름: `louis-diary-bot` (영문/하이픈만, 한글 X) → **만들기 및 계속하기**
4. **이 서비스 계정에 프로젝트 액세스 권한 부여** 단계는 **건너뛰기 가능** → 그냥 **계속**
5. **사용자에게 이 서비스 계정에 액세스 권한 부여** 단계도 비워두고 → **완료**

### 4단계: JSON 키 발급

1. 방금 만든 서비스 계정 이메일을 클릭 (예: `louis-diary-bot@louis-diary.iam.gserviceaccount.com`)
2. 상단 탭에서 **키** 클릭 → **키 추가 → 새 키 만들기**
3. **JSON** 선택 → **만들기**
4. JSON 파일이 자동으로 다운로드됩니다. **이 파일은 비밀번호급으로 보관하세요** (절대 git에 커밋 X)
5. 서비스 계정 이메일 주소를 어딘가 복사해두세요 (다음 단계에서 씀)

### 5단계: Google Sheet 만들고 서비스 계정에 공유

1. https://sheets.google.com 접속 → **빈 스프레드시트** 만들기
2. 시트 이름: `louis-diary-data` (원하는 이름)
3. 우상단 **공유** 버튼 클릭
4. **사용자 및 그룹 추가** 입력란에 4단계에서 복사한 **서비스 계정 이메일** 붙여넣기
5. 권한을 **편집자** 로 설정, "이메일 알림 보내기" 체크 해제 → **공유**
6. URL에서 시트 ID 복사:
   ```
   https://docs.google.com/spreadsheets/d/【여기가_시트_ID】/edit
   ```

### 6단계: Streamlit secrets에 등록

**로컬 (`.streamlit/secrets.toml`):**

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
spreadsheet_id = "여기에_5단계의_시트_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "louis-diary-bot@...iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

→ 4단계에서 받은 JSON 파일을 열어서 키-값을 그대로 옮겨 적으면 됩니다. `private_key` 의 줄바꿈은 `\n` 문자로 유지하세요.

**Streamlit Cloud:** App settings → Secrets 에 위 내용 그대로 붙여넣기.

### 7단계: 워크시트는 자동 생성

앱이 처음 시트에 접속하면 다음 3개 워크시트를 자동으로 만듭니다:
- `weight_log` — date, weight
- `meal_log` — timestamp, food_name, calories, protein, carbs, fat
- `exercise_log` — timestamp, course, distance, duration, calories

수동으로 미리 만들 필요 없습니다.

## 스택

- Streamlit · pandas · plotly · Pillow · anthropic
- gspread · google-auth (영구 저장)
- Python 3.12 권장
