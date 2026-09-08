import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
import calendar
from datetime import datetime

# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 데이터 분석",
    page_icon="🥗",
    layout="wide"
)

st.title("🥗 학교 급식 데이터 분석")
st.caption("NEIS 학교급식 데이터를 활용한 월간 급식 · 영양 · 채식 친화도 분석")

# =========================================================
# API 설정
# =========================================================

SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"

try:
    API_KEY = st.secrets["NEIS_API_KEY"]
except:
    st.error(
        "NEIS_API_KEY가 설정되지 않았습니다.\n\n"
        ".streamlit/secrets.toml에 API 키를 넣어주세요."
    )
    st.stop()


# =========================================================
# 학교 검색
# =========================================================

@st.cache_data(ttl=3600)
def search_school(school_name):

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 50,
        "SCHUL_NM": school_name
    }

    try:
        response = requests.get(
            SCHOOL_API,
            params=params,
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        if "schoolInfo" not in data:
            return pd.DataFrame()

        rows = data["schoolInfo"][1]["row"]

        df = pd.DataFrame(rows)

        return df

    except Exception:
        return pd.DataFrame()


# =========================================================
# 월간 급식 가져오기
# =========================================================

@st.cache_data(ttl=600)
def get_month_meals(atpt_code, school_code, year, month):

    start_date = f"{year}{month:02d}01"

    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}{month:02d}{last_day:02d}"

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": start_date,
        "MLSV_TO_YMD": end_date
    }

    try:
        response = requests.get(
            MEAL_API,
            params=params,
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        if "mealServiceDietInfo" not in data:
            return pd.DataFrame()

        rows = data["mealServiceDietInfo"][1]["row"]

        return pd.DataFrame(rows)

    except Exception:
        return pd.DataFrame()


# =========================================================
# 메뉴 정리
# =========================================================

def clean_menu(menu):

    if pd.isna(menu):
        return ""

    menu = str(menu)

    # HTML 태그 제거
    menu = re.sub(r"<br\s*/?>", "\n", menu, flags=re.I)
    menu = re.sub(r"<[^>]+>", "", menu)

    return menu.strip()


def split_menu(menu):

    menu = clean_menu(menu)

    if not menu:
        return []

    lines = menu.split("\n")

    result = []

    for line in lines:

        line = line.strip()

        if line:
            result.append(line)

    return result


# =========================================================
# 영양정보 파싱
# =========================================================

def parse_nutrition(text):

    if pd.isna(text):
        return {
            "탄수화물": None,
            "단백질": None,
            "지방": None
        }

    text = str(text)

    result = {
        "탄수화물": None,
        "단백질": None,
        "지방": None
    }

    patterns = {
        "탄수화물": r"탄수화물\s*\(g\)\s*[:：]?\s*([0-9.]+)",
        "단백질": r"단백질\s*\(g\)\s*[:：]?\s*([0-9.]+)",
        "지방": r"지방\s*\(g\)\s*[:：]?\s*([0-9.]+)"
    }

    for key, pattern in patterns.items():

        match = re.search(pattern, text)

        if match:
            result[key] = float(match.group(1))

    return result


def parse_calorie(text):

    if pd.isna(text):
        return None

    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)",
        str(text)
    )

    if match:
        return float(match.group(1))

    return None


# =========================================================
# 알레르기 정보
# =========================================================

ALLERGY = {
    "1": "난류",
    "2": "우유",
    "3": "메밀",
    "4": "땅콩",
    "5": "대두",
    "6": "밀",
    "7": "고등어",
    "8": "게",
    "9": "새우",
    "10": "돼지고기",
    "11": "복숭아",
    "12": "토마토",
    "13": "아황산류",
    "14": "호두",
    "15": "닭고기",
    "16": "쇠고기",
    "17": "오징어",
    "18": "조개류",
    "19": "잣"
}


def get_allergies(menu):

    if pd.isna(menu):
        return []

    text = str(menu)

    # 메뉴 뒤쪽의 괄호 안 숫자를 찾음
    numbers = re.findall(
        r"\(([0-9.\s]+)\)",
        text
    )

    found = set()

    for group in numbers:

        for number in re.findall(r"\d+", group):

            if number in ALLERGY:
                found.add(number)

    return sorted(
        found,
        key=lambda x: int(x)
    )


# =========================================================
# 채식 친화도 분석
# =========================================================

ANIMAL_KEYWORDS = [

    # 육류
    "돼지",
    "돼지고기",
    "돈육",
    "제육",
    "삼겹살",
    "소고기",
    "쇠고기",
    "불고기",
    "갈비",
    "닭",
    "닭고기",
    "치킨",
    "오리",

    # 가공육
    "햄",
    "소시지",
    "베이컨",
    "스팸",

    # 생선
    "고등어",
    "연어",
    "참치",
    "멸치",
    "꽁치",
    "갈치",
    "생선",

    # 해산물
    "새우",
    "오징어",
    "문어",
    "낙지",
    "게",
    "꽃게",
    "조개",
    "굴",
    "홍합",

    # 달걀 / 유제품
    "계란",
    "달걀",
    "메추리알",
    "우유",
    "치즈",
    "버터",
    "크림"
]


def is_animal_menu(menu):

    text = menu.lower()

    for keyword in ANIMAL_KEYWORDS:

        if keyword.lower() in text:
            return True

    return False


def daily_vegan_score(menu):

    menus = split_menu(menu)

    if not menus:
        return None

    vegan_possible = 0

    for item in menus:

        if not is_animal_menu(item):
            vegan_possible += 1

    score = vegan_possible / len(menus) * 100

    return round(score, 1)


def monthly_vegan_score(df):

    if df.empty:
        return None

    scores = []

    for _, row in df.iterrows():

        score = daily_vegan_score(
            row["급식메뉴"]
        )

        if score is not None:
            scores.append(score)

    if not scores:
        return None

    return round(sum(scores) / len(scores), 1)


def score_grade(score):

    if score is None:
        return "데이터 없음"

    if score >= 80:
        return "매우 높음"

    if score >= 60:
        return "높음"

    if score >= 40:
        return "보통"

    if score >= 20:
        return "낮음"

    return "매우 낮음"


# =========================================================
# 급식 데이터 전처리
# =========================================================

def prepare_meals(df):

    if df.empty:
        return df

    result = df.copy()

    result["급식일"] = pd.to_datetime(
        result["MLSV_YMD"],
        format="%Y%m%d"
    )

    result["급식메뉴"] = result["DDISH_NM"].apply(
        clean_menu
    )

    result["식사"] = result["MMEAL_SC_NM"]

    result["칼로리"] = result["CAL_INFO"].apply(
        parse_calorie
    )

    nutrition = result["NTR_INFO"].apply(
        parse_nutrition
    )

    result["탄수화물"] = nutrition.apply(
        lambda x: x["탄수화물"]
    )

    result["단백질"] = nutrition.apply(
        lambda x: x["단백질"]
    )

    result["지방"] = nutrition.apply(
        lambda x: x["지방"]
    )

    result["채식점수"] = result["급식메뉴"].apply(
        daily_vegan_score
    )

    result["알레르기"] = result["급식메뉴"].apply(
        get_allergies
    )

    return result


# =========================================================
# 날짜 선택
# =========================================================

now = datetime.now()

st.sidebar.header("📅 분석 기간")

year = st.sidebar.selectbox(
    "연도",
    range(now.year - 2, now.year + 1),
    index=2
)

month = st.sidebar.selectbox(
    "월",
    range(1, 13),
    index=now.month - 1
)


# =========================================================
# 학교 선택
# =========================================================

st.sidebar.header("🏫 학교 선택")

st.sidebar.caption(
    "최대 5개 학교를 비교할 수 있습니다."
)

school_names = []

for i in range(5):

    default = "당곡고등학교" if i == 0 else ""

    name = st.sidebar.text_input(
        f"학교 {i + 1}",
        value=default,
        key=f"school_{i}"
    )

    if name.strip():
        school_names.append(name.strip())


if len(school_names) == 0:

    st.info("학교를 한 곳 이상 입력해주세요.")
    st.stop()


# =========================================================
# 학교 데이터 가져오기
# =========================================================

school_data = {}

with st.spinner("학교와 급식 데이터를 불러오는 중입니다..."):

    for name in school_names:

        school_df = search_school(name)

        if school_df.empty:
            continue

        # 입력한 이름과 가장 비슷한 학교를 우선 선택
        exact = school_df[
            school_df["SCHUL_NM"] == name
        ]

        if not exact.empty:
            selected = exact.iloc[0]
        else:
            selected = school_df.iloc[0]

        atpt_code = selected["ATPT_OFCDC_SC_CODE"]
        school_code = selected["SD_SCHUL_CODE"]
        real_name = selected["SCHUL_NM"]

        meals = get_month_meals(
            atpt_code,
            school_code,
            year,
            month
        )

        meals = prepare_meals(meals)

        school_data[real_name] = meals


if not school_data:

    st.error(
        "학교 정보를 찾지 못했습니다. "
        "학교명을 다시 확인해주세요."
    )
    st.stop()


# =========================================================
# 학교별 월간 채식 점수
# =========================================================

st.header("🥗 이달의 채식 친화도")

score_data = []

for school, df in school_data.items():

    score = monthly_vegan_score(df)

    score_data.append({
        "학교": school,
        "채식 친화도": score if score is not None else 0,
        "평가": score_grade(score)
    })

score_df = pd.DataFrame(score_data)


# =========================================================
# 점수 카드
# =========================================================

cols = st.columns(len(score_df))

for col, (_, row) in zip(cols, score_df.iterrows()):

    with col:

        st.metric(
            label=row["학교"],
            value=f"{row['채식 친화도']:.1f}점"
        )

        st.caption(
            f"평가: {row['평가']}"
        )


# =========================================================
# 점수 계산 방법
# =========================================================

with st.expander("📖 채식 친화도 점수는 어떻게 계산하나요?"):

    st.markdown("""
### 채식 친화도 계산 방법

이 점수는 **급식 메뉴 이름을 분석해서 계산한 추정값**입니다.

#### ① 하루 점수

하루의 급식 메뉴 중에서 동물성 식재료가 포함된 것으로
확인되는 메뉴를 제외하고 계산합니다.

**하루 점수 = 채식 가능 메뉴 수 ÷ 전체 메뉴 수 × 100**

예를 들어,

- 전체 메뉴: 5개
- 동물성 식재료가 확인되는 메뉴: 2개
- 채식 가능 메뉴: 3개

라면

**3 ÷ 5 × 100 = 60점**

입니다.

#### ② 한 달 점수

해당 월의 급식일별 점수를 모두 계산한 뒤 평균을 냅니다.

**월간 채식 친화도 = 하루 점수들의 평균**

### 점수 해석

| 점수 | 의미 |
|---:|---|
| 80~100점 | 매우 높음 |
| 60~79점 | 높음 |
| 40~59점 | 보통 |
| 20~39점 | 낮음 |
| 0~19점 | 매우 낮음 |

⚠️ **중요:** 메뉴 이름만으로는 육수, 소스, 조리 과정 등에 들어간
동물성 재료나 교차 접촉 여부를 확인할 수 없습니다.
따라서 이 점수는 **비건 인증이나 안전성을 보장하는 점수가 아니라
월간 급식 메뉴를 비교하기 위한 참고용 지표**입니다.
""")


# =========================================================
# 학교별 점수 비교 그래프
# =========================================================

if len(score_df) >= 2:

    fig = px.bar(
        score_df,
        x="학교",
        y="채식 친화도",
        text="채식 친화도",
        title=f"{year}년 {month}월 학교별 채식 친화도"
    )

    fig.update_traces(
        texttemplate="%{text:.1f}점",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_title="채식 친화도 점수",
        xaxis_title="학교",
        yaxis_range=[0, 100]
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# =========================================================
# 영양 비교
# =========================================================

st.header("📊 월간 영양 데이터 비교")

nutrition_rows = []

for school, df in school_data.items():

    if df.empty:
        continue

    # 점심 데이터만 우선 사용
    lunch = df[df["식사"].astype(str).str.contains("중식")]

    if lunch.empty:
        lunch = df

    nutrition_rows.append({
        "학교": school,
        "탄수화물": lunch["탄수화물"].mean(),
        "단백질": lunch["단백질"].mean(),
        "지방": lunch["지방"].mean(),
        "한 달 평균 열량": lunch["칼로리"].mean()
    })

nutrition_df = pd.DataFrame(nutrition_rows)

if not nutrition_df.empty:

    c1, c2 = st.columns(2)

    with c1:

        fig = px.bar(
            nutrition_df,
            x="학교",
            y="탄수화물",
            text="탄수화물",
            title="📊 학교별 평균 탄수화물"
        )

        fig.update_traces(
            texttemplate="%{text:.1f}g",
            textposition="outside"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with c2:

        fig = px.bar(
            nutrition_df,
            x="학교",
            y="단백질",
            text="단백질",
            title="📊 학교별 평균 단백질"
        )

        fig.update_traces(
            texttemplate="%{text:.1f}g",
            textposition="outside"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    c3, c4 = st.columns(2)

    with c3:

        fig = px.bar(
            nutrition_df,
            x="학교",
            y="지방",
            text="지방",
            title="📊 학교별 평균 지방"
        )

        fig.update_traces(
            texttemplate="%{text:.1f}g",
            textposition="outside"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with c4:

        fig = px.bar(
            nutrition_df,
            x="학교",
            y="한 달 평균 열량",
            text="한 달 평균 열량",
            title="📊 한 달 평균 열량"
        )

        fig.update_traces(
            texttemplate="%{text:.1f} kcal",
            textposition="outside"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# =========================================================
# 월간 급식표
# =========================================================

st.header(f"📅 {year}년 {month}월 월간 급식표")

st.caption(
    "달력에서 날짜별 급식 메뉴와 채식 친화도 추정 점수를 한눈에 확인할 수 있습니다."
)


# 학교별 탭
tabs = st.tabs(
    list(school_data.keys())
)

for tab, (school, df) in zip(
    tabs,
    school_data.items()
):

    with tab:

        if df.empty:

            st.warning(
                "이 학교의 해당 월 급식 데이터가 없습니다."
            )

            continue

        # 중식 우선
        lunch = df[
            df["식사"].astype(str).str.contains("중식")
        ].copy()

        if lunch.empty:
            lunch = df.copy()

        # 날짜별 데이터
        day_data = {}

        for _, row in lunch.iterrows():

            day = row["급식일"].day

            day_data[day] = {
                "menu": row["급식메뉴"],
                "score": row["채식점수"],
                "allergy": row["알레르기"]
            }

        # 요일 헤더
        weekday_cols = st.columns(7)

        weekdays = [
            "월",
            "화",
            "수",
            "목",
            "금",
            "토",
            "일"
        ]

        for col, weekday in zip(
            weekday_cols,
            weekdays
        ):

            col.markdown(
                f"**{weekday}**"
            )

        # 달력
        month_calendar = calendar.monthcalendar(
            year,
            month
        )

        for week in month_calendar:

            cols = st.columns(7)

            for col, day in zip(cols, week):

                with col:

                    if day == 0:
                        st.write("")
                        continue

                    st.markdown(
                        f"### {day}일"
                    )

                    if day not in day_data:

                        st.caption(
                            "급식 없음"
                        )

                        continue

                    info = day_data[day]

                    score = info["score"]

                    if score is not None:

                        st.metric(
                            "채식 친화도",
                            f"{score:.0f}점"
                        )

                    menu_items = split_menu(
                        info["menu"]
                    )

                    for item in menu_items:

                        # 알레르기 번호는 별도 표시
                        clean_item = re.sub(
                            r"\([0-9.\s]+\)",
                            "",
                            item
                        ).strip()

                        if clean_item:

                            st.write(
                                f"• {clean_item}"
                            )

                    if info["allergy"]:

                        allergy_names = [
                            ALLERGY[x]
                            for x in info["allergy"]
                        ]

                        st.caption(
                            "⚠️ 알레르기: "
                            + ", ".join(allergy_names)
                        )

                    st.divider()


# =========================================================
# 일별 채식 점수 추이
# =========================================================

st.header("📈 한 달 동안의 채식 친화도 변화")

for school, df in school_data.items():

    if df.empty:
        continue

    lunch = df[
        df["식사"].astype(str).str.contains("중식")
    ].copy()

    if lunch.empty:
        lunch = df.copy()

    if lunch.empty:
        continue

    chart_df = lunch[
        ["급식일", "채식점수"]
    ].dropna()

    if chart_df.empty:
        continue

    fig = px.line(
        chart_df,
        x="급식일",
        y="채식점수",
        markers=True,
        title=f"{school} - 월간 채식 친화도 변화"
    )

    fig.update_layout(
        yaxis_title="채식 친화도",
        xaxis_title="날짜",
        yaxis_range=[0, 100]
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# =========================================================
# 알레르기 정보
# =========================================================

st.header("⚠️ 월간 알레르기 정보")

for school, df in school_data.items():

    if df.empty:
        continue

    st.subheader(f"🏫 {school}")

    allergy_count = {}

    for allergies in df["알레르기"]:

        for number in allergies:

            allergy_name = ALLERGY[number]

            allergy_count[allergy_name] = (
                allergy_count.get(allergy_name, 0) + 1
            )

    if allergy_count:

        allergy_df = pd.DataFrame(
            list(allergy_count.items()),
            columns=["알레르기 항목", "등장 횟수"]
        ).sort_values(
            "등장 횟수",
            ascending=False
        )

        st.dataframe(
            allergy_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "해당 월 급식 데이터에서 알레르기 번호가 확인되지 않았습니다."
        )


# =========================================================
# 원본 월간 데이터
# =========================================================

st.header("📋 월간 급식 데이터")

for school, df in school_data.items():

    with st.expander(f"🔎 {school} 전체 데이터 보기"):

        if df.empty:

            st.write("데이터가 없습니다.")

        else:

            display_df = df[
                [
                    "급식일",
                    "식사",
                    "급식메뉴",
                    "칼로리",
                    "탄수화물",
                    "단백질",
                    "지방",
                    "채식점수"
                ]
            ].copy()

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 안내
# =========================================================

st.divider()

st.caption(
    "※ 본 서비스는 NEIS 학교급식 데이터를 활용하여 메뉴·영양정보를 분석합니다."
)

st.caption(
    "※ 채식 친화도는 메뉴명에 나타난 식재료를 기준으로 계산한 참고용 추정치이며, "
    "실제 조리 과정이나 육수·소스의 성분을 보장하지 않습니다."
)

st.caption(
    "※ 알레르기 정보는 NEIS에서 제공하는 급식 알레르기 표시를 기준으로 합니다."
)
