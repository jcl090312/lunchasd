import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date, timedelta


# ==================================================
# 기본 설정
# ==================================================

st.set_page_config(
    page_title="오늘 뭐 먹지?",
    page_icon="🍚",
    layout="wide"
)


# ==================================================
# CSS
# ==================================================

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

.school-card {
    padding: 20px;
    border-radius: 15px;
    background-color: #f7f7f7;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# API KEY
# ==================================================

try:
    API_KEY = st.secrets["NEIS_API_KEY"]
except Exception:
    st.error(
        "NEIS API 키가 설정되지 않았습니다. "
        "Streamlit Secrets에 NEIS_API_KEY를 등록해주세요."
    )
    st.stop()


# ==================================================
# 학교 검색 API
# ==================================================

@st.cache_data(ttl=3600)
def search_schools(keyword):

    url = "https://open.neis.go.kr/hub/schoolInfo"

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": keyword
    }

    try:

        response = requests.get(
            url,
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
                "교육청코드": row.get("ATPT_OFCDC_SC_CODE", ""),
                "학교코드": row.get("SD_SCHUL_CODE", ""),
                "학교종류": row.get("SCHUL_KND_SC_NM", ""),
                "주소": row.get("ORG_RDNMA", "")
            })

        return pd.DataFrame(result)

    except Exception as e:

        st.error(f"학교 검색 중 오류가 발생했습니다: {e}")

        return pd.DataFrame()


# ==================================================
# 급식 API
# ==================================================

@st.cache_data(ttl=600)
def get_meal(
    office_code,
    school_code,
    target_date
):

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"

    params = {
        "KEY": API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_YMD": target_date.strftime("%Y%m%d")
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "mealServiceDietInfo" not in data:
            return pd.DataFrame()

        rows = data["mealServiceDietInfo"][1]["row"]

        result = []

        for row in rows:

            result.append({

                "식사": row.get(
                    "MMEAL_SC_NM",
                    ""
                ),

                "메뉴": row.get(
                    "DDISH_NM",
                    ""
                ),

                "칼로리": row.get(
                    "CAL_INFO",
                    ""
                ),

                "탄수화물": row.get(
                    "CAR_INFO",
                    ""
                ),

                "단백질": row.get(
                    "PRO_INFO",
                    ""
                ),

                "지방": row.get(
                    "FAT_INFO",
                    ""
                ),

                "원산지": row.get(
                    "ORPLC_INFO",
                    ""
                )
            })

        return pd.DataFrame(result)

    except Exception:

        return pd.DataFrame()


# ==================================================
# 제목
# ==================================================

st.markdown(
    '<div class="main-title">🍚 오늘 뭐 먹지?</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    '전국 학교 급식을 검색하고 비교해보세요.'
    '</div>',
    unsafe_allow_html=True
)


# ==================================================
# 학교 검색
# ==================================================

st.subheader("🏫 학교 선택")

keyword = st.text_input(
    "학교 이름을 검색하세요",
    value="당곡고등학교",
    placeholder="예: 당곡고등학교"
)


# ==================================================
# 검색 실행
# ==================================================

if keyword:

    schools = search_schools(keyword)

else:

    schools = pd.DataFrame()


if schools.empty:

    st.warning(
        "검색된 학교가 없습니다."
    )

    st.stop()


# ==================================================
# 학교 선택
# ==================================================

school_labels = []

for _, school in schools.iterrows():

    label = (
        f'{school["학교명"]} '
        f'({school["학교종류"]}) - '
        f'{school["주소"]}'
    )

    school_labels.append(label)


selected_labels = st.multiselect(
    "비교할 학교를 선택하세요.",
    school_labels,
    default=school_labels[:1]
)


# ==================================================
# 선택된 학교 정보
# ==================================================

selected_schools = []

for label in selected_labels:

    index = school_labels.index(label)

    selected_schools.append(
        schools.iloc[index]
    )


# ==================================================
# 날짜 선택
# ==================================================

st.subheader("📅 급식 날짜")

selected_date = st.date_input(
    "날짜를 선택하세요.",
    value=date.today()
)


# ==================================================
# 급식 조회
# ==================================================

if selected_schools:

    st.divider()

    st.subheader(
        f"🍱 {selected_date.strftime('%Y년 %m월 %d일')} 급식"
    )

    all_meals = []

    for school in selected_schools:

        meals = get_meal(
            school["교육청코드"],
            school["학교코드"],
            selected_date
        )

        if meals.empty:

            st.info(
                f'{school["학교명"]}: '
                "해당 날짜의 급식 정보가 없습니다."
            )

            continue


        # ------------------------------------------
        # 학교 제목
        # ------------------------------------------

        st.markdown(
            f"### 🏫 {school['학교명']}"
        )

        # ------------------------------------------
        # 급식 표시
        # ------------------------------------------

        for _, meal in meals.iterrows():

            st.markdown(
                f"""
                <div class="school-card">

                <h4>🍴 {meal['식사']}</h4>

                <p>
                {meal['메뉴']}
                </p>

                <p>
                🔥 {meal['칼로리']}
                </p>

                </div>
                """,
                unsafe_allow_html=True
            )


        # ------------------------------------------
        # 그래프용 데이터
        # ------------------------------------------

        for _, meal in meals.iterrows():

            calorie_text = str(
                meal["칼로리"]
            )

            try:

                calorie = float(
                    calorie_text
                    .replace("kcal", "")
                    .strip()
                )

            except:

                calorie = None


            if calorie is not None:

                all_meals.append({

                    "학교": school["학교명"],

                    "식사": meal["식사"],

                    "열량": calorie

                })


# ==================================================
# 학교 비교 그래프
# ==================================================

if len(selected_schools) >= 2:

    st.divider()

    st.subheader(
        "📊 학교별 급식 열량 비교"
    )

    chart_df = pd.DataFrame(
        all_meals
    )

    if not chart_df.empty:

        comparison = (
            chart_df
            .groupby("학교")["열량"]
            .mean()
            .reset_index()
        )

        fig = px.bar(

            comparison,

            x="학교",

            y="열량",

            text="열량",

            title="학교별 평균 급식 열량",

            labels={
                "학교": "학교",
                "열량": "열량 (kcal)"
            }

        )

        fig.update_traces(
            texttemplate="%{text:.0f} kcal",
            textposition="outside"
        )

        fig.update_layout(
            height=500,
            template="plotly_white"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:

        st.info(
            "비교할 영양 정보가 없습니다."
        )


# ==================================================
# 안내
# ==================================================

else:

    st.info(
        "학교를 2개 이상 선택하면 "
        "학교 비교 그래프가 나타납니다."
    )
