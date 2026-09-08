import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
import calendar
from datetime import date


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="오늘 뭐 먹지?",
    page_icon="🥗",
    layout="wide"
)


# =========================================================
# 디자인
# =========================================================

st.markdown("""
<style>

.main-title {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 5px;
}

.sub-title {
    color: #777;
    font-size: 17px;
    margin-bottom: 25px;
}

.meal-card {
    padding: 20px;
    border-radius: 16px;
    background: #f8f9fa;
    border: 1px solid #eeeeee;
    margin-bottom: 15px;
}

.vegan-good {
    padding: 12px;
    border-radius: 10px;
    background: #eaf7ed;
}

.vegan-warning {
    padding: 12px;
    border-radius: 10px;
    background: #fff5e6;
}

.month-cell {
    min-height: 130px;
    padding: 10px;
    border: 1px solid #eeeeee;
    border-radius: 10px;
    background: #fafafa;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# API KEY
# =========================================================

if "NEIS_API_KEY" not in st.secrets:
    st.error(
        "NEIS API 키가 없습니다.\n\n"
        "Streamlit → Settings → Secrets에 "
        "NEIS_API_KEY를 등록해주세요."
    )
    st.stop()

API_KEY = st.secrets["NEIS_API_KEY"]


# =========================================================
# 상수
# =========================================================

SCHOOL_API = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_API = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# 알레르기 번호
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


# =========================================================
# 학교 검색
# =========================================================

@st.cache_data(ttl=3600)
def search_school(keyword):

    if not keyword:
        return pd.DataFrame()

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 50,
        "SCHUL_NM": keyword
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

        result = []

        for row in rows:

            result.append({
                "학교명": row.get("SCHUL_NM", ""),
                "교육청코드": row.get(
                    "ATPT_OFCDC_SC_CODE", ""
                ),
                "학교코드": row.get(
                    "SD_SCHUL_CODE", ""
                ),
                "학교종류": row.get(
                    "SCHUL_KND_SC_NM", ""
                ),
                "주소": row.get(
                    "ORG_RDNMA", ""
                )
            })

        return pd.DataFrame(result)

    except Exception:

        return pd.DataFrame()


# =========================================================
# 급식 조회
# =========================================================

@st.cache_data(ttl=600)
def get_meals(
    office_code,
    school_code,
    from_date,
    to_date
):

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_date.strftime("%Y%m%d"),
        "MLSV_TO_YMD": to_date.strftime("%Y%m%d")
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

        result = []

        for row in rows:

            nutrition = parse_nutrition(
                row.get("NTR_INFO", "")
            )

            result.append({

                "날짜": row.get(
                    "MLSV_YMD", ""
                ),

                "식사": row.get(
                    "MMEAL_SC_NM", ""
                ),

                "메뉴": clean_menu(
                    row.get("DDISH_NM", "")
                ),

                "원산지": row.get(
                    "ORPLC_INFO", ""
                ),

                "칼로리": parse_number(
                    row.get("CAL_INFO", "")
                ),

                "탄수화물": nutrition["탄수화물"],

                "단백질": nutrition["단백질"],

                "지방": nutrition["지방"],

                "알레르기번호": extract_allergy_numbers(
                    row.get("DDISH_NM", "")
                )
            })

        return pd.DataFrame(result)

    except Exception:

        return pd.DataFrame()


# =========================================================
# 메뉴 정리
# =========================================================

def clean_menu(menu):

    menu = menu.replace("<br/>", "\n")
    menu = menu.replace("<br>", "\n")

    return menu


# =========================================================
# 숫자 추출
# =========================================================

def parse_number(text):

    if not text:
        return None

    match = re.search(
        r"[-+]?\d*\.?\d+",
        str(text)
    )

    if match:
        return float(match.group())

    return None


# =========================================================
# 영양정보 파싱
# =========================================================

def parse_nutrition(text):

    result = {
        "탄수화물": None,
        "단백질": None,
        "지방": None
    }

    if not text:
        return result

    patterns = {

        "탄수화물": [
            r"탄수화물[^0-9]*([\d.]+)",
            r"탄수[^0-9]*([\d.]+)"
        ],

        "단백질": [
            r"단백질[^0-9]*([\d.]+)"
        ],

        "지방": [
            r"지방[^0-9]*([\d.]+)"
        ]
    }

    for key, pattern_list in patterns.items():

        for pattern in pattern_list:

            match = re.search(
                pattern,
                text
            )

            if match:

                result[key] = float(
                    match.group(1)
                )

                break

    return result


# =========================================================
# 알레르기 번호
# =========================================================

def extract_allergy_numbers(menu):

    numbers = re.findall(
        r"(?<!\d)(1[0-9]|[1-9])(?!\d)",
        menu
    )

    return sorted(
        set(numbers),
        key=lambda x: int(x)
    )


# =========================================================
# 채식 친화도 추정
# =========================================================

ANIMAL_KEYWORDS = [
    "돼지",
    "돈육",
    "제육",
    "삼겹",
    "닭",
    "치킨",
    "계란",
    "달걀",
    "난",
    "소고기",
    "쇠고기",
    "한우",
    "불고기",
    "갈비",
    "고등어",
    "연어",
    "참치",
    "오징어",
    "새우",
    "게",
    "조개",
    "멸치",
    "육수",
    "어묵",
    "햄",
    "소시지"
]


def vegan_score(menu):

    text = menu.lower()

    detected = []

    for keyword in ANIMAL_KEYWORDS:

        if keyword in text:
            detected.append(keyword)

    detected = list(dict.fromkeys(detected))

    if len(detected) == 0:
        return 100, []

    score = max(
        0,
        100 - len(detected) * 20
    )

    return score, detected


# =========================================================
# 알레르기 표시
# =========================================================

def allergy_names(numbers):

    result = []

    for number in numbers:

        if number in ALLERGY:

            result.append(
                f"{number}. {ALLERGY[number]}"
            )

    return result


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="main-title">🥗 오늘 뭐 먹지?</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    '학교 급식을 분석하고 나에게 맞는 급식을 찾아보세요.'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# 학교 선택
# =========================================================

st.subheader("🏫 학교 선택")

st.caption(
    "당곡고등학교가 기본으로 선택됩니다. "
    "여러 학교를 선택하면 영양 정보를 비교할 수 있습니다."
)


school_slots = []

default_names = [
    "당곡고등학교",
    "",
    "",
    "",
    ""
]


for i in range(5):

    with st.expander(
        f"학교 {i + 1}",
        expanded=(i < 3)
    ):

        keyword = st.text_input(
            f"학교 {i + 1} 검색",
            value=default_names[i],
            key=f"school_search_{i}",
            placeholder="예: 당곡고등학교"
        )

        if keyword:

            results = search_school(keyword)

            if not results.empty:

                options = []

                for _, row in results.iterrows():

                    options.append(
                        f'{row["학교명"]} | '
                        f'{row["학교종류"]} | '
                        f'{row["주소"]}'
                    )

                selected = st.selectbox(
                    f"학교 {i + 1} 선택",
                    options,
                    key=f"school_select_{i}"
                )

                selected_index = options.index(
                    selected
                )

                school_slots.append(
                    results.iloc[selected_index]
                )

            else:

                st.warning(
                    "검색된 학교가 없습니다."
                )


# 중복 제거
unique_schools = []

school_codes = set()

for school in school_slots:

    code = school["학교코드"]

    if code not in school_codes:

        unique_schools.append(school)
        school_codes.add(code)


# =========================================================
# 날짜
# =========================================================

st.divider()

selected_date = st.date_input(
    "📅 조회할 날짜",
    value=date.today()
)


# =========================================================
# 데이터 조회
# =========================================================

school_data = {}

for school in unique_schools:

    meals = get_meals(
        school["교육청코드"],
        school["학교코드"],
        selected_date,
        selected_date
    )

    school_data[
        school["학교명"]
    ] = meals


# =========================================================
# 오늘 급식
# =========================================================

st.divider()

st.header("🍚 오늘의 급식")


if not unique_schools:

    st.info(
        "학교를 선택해주세요."
    )

else:

    for school_name, meals in school_data.items():

        st.subheader(
            f"🏫 {school_name}"
        )

        if meals.empty:

            st.warning(
                "해당 날짜의 급식 정보가 없습니다."
            )

            continue

        for _, meal in meals.iterrows():

            score, detected = vegan_score(
                meal["메뉴"]
            )

            if score >= 80:

                status = "🥬 채식 친화적 메뉴로 추정"

                css_class = "vegan-good"

            else:

                status = "⚠️ 동물성 식재료 포함 가능성"

                css_class = "vegan-warning"

            st.markdown(
                f"""
                <div class="meal-card">

                <h3>
                🍴 {meal["식사"]}
                </h3>

                <p style="white-space:pre-line;">
                {meal["메뉴"]}
                </p>

                <div class="{css_class}">
                <b>{status}</b><br>
                채식 친화도 추정: {score}점
                </div>

                </div>
                """,
                unsafe_allow_html=True
            )

            if detected:

                st.caption(
                    "감지된 동물성 식재료 관련 키워드: "
                    + ", ".join(detected)
                )


# =========================================================
# 월간 데이터 가져오기
# =========================================================

st.divider()

st.header("📅 월간 급식표")

year = selected_date.year
month = selected_date.month

first_day = date(
    year,
    month,
    1
)

last_day = date(
    year,
    month,
    calendar.monthrange(
        year,
        month
    )[1]
)


monthly_data = {}

with st.spinner("이번 달 급식을 불러오는 중입니다..."):

    for school in unique_schools:

        monthly_data[
            school["학교명"]
        ] = get_meals(
            school["교육청코드"],
            school["학교코드"],
            first_day,
            last_day
        )


# =========================================================
# 월간 급식표
# =========================================================

for school_name, meals in monthly_data.items():

    st.subheader(
        f"🏫 {school_name}"
    )

    if meals.empty:

        st.info(
            "이번 달 급식 정보가 없습니다."
        )

        continue

    monthly = meals.copy()

    monthly["날짜"] = pd.to_datetime(
        monthly["날짜"]
    )

    monthly["일"] = monthly[
        "날짜"
    ].dt.day

    # 날짜별 메뉴 묶기
    table = []

    for day in sorted(
        monthly["일"].unique()
    ):

        day_data = monthly[
            monthly["일"] == day
        ]

        lunch = day_data[
            day_data["식사"].str.contains(
                "중식",
                na=False
            )
        ]

        if not lunch.empty:

            menu = lunch.iloc[0]["메뉴"]

        else:

            menu = "급식 정보 없음"

        table.append({

            "일": f"{int(day)}일",

            "요일": pd.to_datetime(
                f"{year}-{month:02d}-{int(day):02d}"
            ).strftime("%a"),

            "급식": menu
        })

    calendar_df = pd.DataFrame(table)

    st.dataframe(
        calendar_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 월간 통계
# =========================================================

st.divider()

st.header("📊 월간 영양 분석")


monthly_rows = []


for school_name, meals in monthly_data.items():

    if meals.empty:
        continue

    temp = meals.copy()

    temp["학교"] = school_name

    monthly_rows.append(temp)


if monthly_rows:

    all_monthly = pd.concat(
        monthly_rows,
        ignore_index=True
    )

    # 숫자 변환
    numeric_columns = [
        "칼로리",
        "탄수화물",
        "단백질",
        "지방"
    ]

    for column in numeric_columns:

        all_monthly[column] = pd.to_numeric(
            all_monthly[column],
            errors="coerce"
        )


    # =====================================================
    # 평균 수치
    # =====================================================

    stats = (
        all_monthly
        .groupby("학교")[numeric_columns]
        .mean()
        .reset_index()
    )


    # =====================================================
    # 학교별 평균 열량
    # =====================================================

    st.subheader("🔥 한 달 평균 열량")

    fig_calorie = px.bar(
        stats,
        x="학교",
        y="칼로리",
        text="칼로리",
        title="학교별 한 달 평균 급식 열량",
        labels={
            "학교": "학교",
            "칼로리": "평균 열량 (kcal)"
        }
    )

    fig_calorie.update_traces(
        texttemplate="%{text:.0f} kcal",
        textposition="outside"
    )

    fig_calorie.update_layout(
        template="plotly_white",
        height=450
    )

    st.plotly_chart(
        fig_calorie,
        use_container_width=True
    )


    # =====================================================
    # 탄수화물
    # =====================================================

    st.subheader("📊 탄수화물 비교")

    fig_carbs = px.bar(
        stats,
        x="학교",
        y="탄수화물",
        text="탄수화물",
        title="학교별 평균 탄수화물",
        labels={
            "학교": "학교",
            "탄수화물": "탄수화물 (g)"
        }
    )

    fig_carbs.update_traces(
        texttemplate="%{text:.1f} g",
        textposition="outside"
    )

    fig_carbs.update_layout(
        template="plotly_white",
        height=450
    )

    st.plotly_chart(
        fig_carbs,
        use_container_width=True
    )


    # =====================================================
    # 단백질
    # =====================================================

    st.subheader("📊 단백질 비교")

    fig_protein = px.bar(
        stats,
        x="학교",
        y="단백질",
        text="단백질",
        title="학교별 평균 단백질",
        labels={
            "학교": "학교",
            "단백질": "단백질 (g)"
        }
    )

    fig_protein.update_traces(
        texttemplate="%{text:.1f} g",
        textposition="outside"
    )

    fig_protein.update_layout(
        template="plotly_white",
        height=450
    )

    st.plotly_chart(
        fig_protein,
        use_container_width=True
    )


    # =====================================================
    # 지방
    # =====================================================

    st.subheader("📊 지방 비교")

    fig_fat = px.bar(
        stats,
        x="학교",
        y="지방",
        text="지방",
        title="학교별 평균 지방",
        labels={
            "학교": "학교",
            "지방": "지방 (g)"
        }
    )

    fig_fat.update_traces(
        texttemplate="%{text:.1f} g",
        textposition="outside"
    )

    fig_fat.update_layout(
        template="plotly_white",
        height=450
    )

    st.plotly_chart(
        fig_fat,
        use_container_width=True
    )


# =========================================================
# 알레르기 정보
# =========================================================

st.divider()

st.header("⚠️ 알레르기 정보")

st.caption(
    "NEIS 급식 데이터에 표시된 알레르기 번호를 "
    "식재료 이름으로 변환하여 보여줍니다."
)

for school_name, meals in school_data.items():

    if meals.empty:
        continue

    st.subheader(
        f"🏫 {school_name}"
    )

    for _, meal in meals.iterrows():

        allergy = allergy_names(
            meal["알레르기번호"]
        )

        if allergy:

            st.write(
                f"**{meal['식사']}**"
            )

            st.write(
                " · ".join(allergy)
            )

        else:

            st.write(
                f"**{meal['식사']}**: "
                "표시된 알레르기 정보 없음"
            )


# =========================================================
# 원산지 정보
# =========================================================

st.divider()

st.header("🌾 원산지 정보")

for school_name, meals in school_data.items():

    if meals.empty:
        continue

    st.subheader(
        f"🏫 {school_name}"
    )

    for _, meal in meals.iterrows():

        if meal["원산지"]:

            with st.expander(
                f"{meal['식사']} 원산지"
            ):

                st.text(
                    meal["원산지"]
                )


# =========================================================
# 안내
# =========================================================

st.divider()

st.caption(
    "※ 본 서비스는 NEIS 공개 급식 데이터를 활용합니다. "
    "급식 메뉴명만으로 실제 조리 과정이나 소스에 포함된 "
    "모든 원재료를 확인할 수 없으므로, "
    "채식 친화도는 참고용 추정치입니다."
)

st.caption(
    "데이터 출처: 교육부·시도교육청 나이스 교육정보 개방 포털"
)
