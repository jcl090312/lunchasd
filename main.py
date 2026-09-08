import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date, timedelta


# ==========================================
# 페이지 설정
# ==========================================

st.set_page_config(
    page_title="우리 학교 급식",
    page_icon="🍚",
    layout="wide"
)


# ==========================================
# CSS
# ==========================================

st.markdown("""
<style>

.main-title {
    font-size: 40px;
    font-weight: 700;
}

.subtitle {
    color: #666;
    font-size: 17px;
}

.meal-card {
    padding: 20px;
    border-radius: 15px;
    background-color: #f7f7f7;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 학교 데이터
# ==========================================

@st.cache_data
def load_schools():

    # GitHub Raw 주소로 변경
    url = "YOUR_GITHUB_RAW_CSV_URL"

    return pd.read_csv(url)


schools = load_schools()


# ==========================================
# NEIS 급식 API
# ==========================================

def get_meal(office_code, school_code, target_date):

    api_key = st.secrets["NEIS_API_KEY"]

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"

    params = {
        "KEY": api_key,
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_YMD": target_date.strftime("%Y%m%d")
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    if response.status_code != 200:
        return None

    data = response.json()

    try:
        rows = data["mealServiceDietInfo"][1]["row"]

        return rows

    except (KeyError, IndexError):
        return None


# ==========================================
# 제목
# ==========================================

st.markdown(
    '<div class="main-title">🍚 우리 학교 급식</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">전국 학교의 급식을 한눈에 확인하고 비교해보세요.</div>',
    unsafe_allow_html=True
)

st.divider()


# ==========================================
# 학교 선택
# ==========================================

st.subheader("🏫 학교 선택")

school_names = schools["학교명"].dropna().unique().tolist()

default_school = "당곡고등학교"

default_index = (
    school_names.index(default_school)
    if default_school in school_names
    else 0
)

selected_schools = st.multiselect(
    "비교할 학교를 선택하세요.",
    school_names,
    default=[default_school] if default_school in school_names else [],
    help="2개 이상의 학교를 선택하면 학교별 비교가 가능합니다."
)


# ==========================================
# 날짜 선택
# ==========================================

selected_date = st.date_input(
    "📅 급식 날짜",
    value=date.today()
)


# ==========================================
# 선택 학교 확인
# ==========================================

if not selected_schools:

    st.info("학교를 하나 이상 선택해주세요.")

    st.stop()


# ==========================================
# 학교 급식 데이터 수집
# ==========================================

meal_results = []

for school_name in selected_schools:

    school_info = schools[
        schools["학교명"] == school_name
    ]

    if school_info.empty:
        continue

    school = school_info.iloc[0]

    meals = get_meal(
        school["교육청코드"],
        school["학교코드"],
        selected_date
    )

    if meals:

        for meal in meals:

            meal_results.append({
                "학교명": school_name,
                "식사": meal.get("MMEAL_SC_NM", ""),
                "메뉴": meal.get("DDISH_NM", ""),
                "칼로리": meal.get("CAL_INFO", ""),
                "탄수화물": meal.get("CAR_INFO", ""),
                "단백질": meal.get("PRO_INFO", ""),
                "지방": meal.get("FAT_INFO", ""),
                "알레르기": meal.get("ORPLC_INFO", "")
            })


meal_df = pd.DataFrame(meal_results)


# ==========================================
# 급식 표시
# ==========================================

st.divider()

st.subheader(
    f"🍱 {selected_date.strftime('%Y년 %m월 %d일')} 급식"
)


if meal_df.empty:

    st.warning("해당 날짜의 급식 정보가 없습니다.")

else:

    for school in selected_schools:

        school_meal = meal_df[
            meal_df["학교명"] == school
        ]

        if school_meal.empty:

            st.warning(
                f"{school}: 급식 정보가 없습니다."
            )

            continue

        st.markdown(
            f"### 🏫 {school}"
        )

        for _, meal in school_meal.iterrows():

            st.markdown(
                f"""
                <div class="meal-card">

                <b>{meal["식사"]}</b>

                <br><br>

                {meal["메뉴"]}

                <br><br>

                🔥 {meal["칼로리"]}

                </div>
                """,
                unsafe_allow_html=True
            )


# ==========================================
# 학교 비교
# ==========================================

if len(selected_schools) >= 2 and not meal_df.empty:

    st.divider()

    st.subheader("📊 학교별 영양 비교")

    # 숫자 변환
    meal_df["열량"] = (
        meal_df["칼로리"]
        .str.extract(r"([\d.]+)")
        .astype(float)
    )

    comparison = (
        meal_df
        .groupby("학교명")["열량"]
        .mean()
        .reset_index()
    )

    fig = px.bar(
        comparison,
        x="학교명",
        y="열량",
        title="학교별 평균 급식 열량",
        labels={
            "학교명": "학교",
            "열량": "열량 (kcal)"
        },
        text_auto=".0f"
    )

    fig.update_layout(
        template="plotly_white",
        height=450
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# ==========================================
# 급식 상세 정보
# ==========================================

if not meal_df.empty:

    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "🥗 영양 정보",
        "⚠️ 알레르기",
        "📋 원산지"
    ])

    with tab1:

        st.dataframe(
            meal_df[
                [
                    "학교명",
                    "식사",
                    "칼로리",
                    "탄수화물",
                    "단백질",
                    "지방"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    with tab2:

        st.dataframe(
            meal_df[
                [
                    "학교명",
                    "식사",
                    "알레르기"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    with tab3:

        st.info(
            "NEIS API에서 제공하는 원산지 정보를 "
            "이 영역에 표시할 수 있습니다."
        )
