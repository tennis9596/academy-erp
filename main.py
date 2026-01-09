import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# --- [설정] 페이지 기본 설정 ---
st.set_page_config(page_title="hsjg Academy ERP", page_icon="☁️", layout="wide")
st.title("☁️ hsjg Academy 통합 관리 시스템 (Cloud Ver.)")

# --- [핵심] 구글 시트 연결 함수 (하이브리드 버전) ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. 클라우드 비밀보관소(Secrets)에 키가 있는지 확인
    if "gcp_json" in st.secrets:
        key_dict = json.loads(st.secrets["gcp_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    # 2. 없으면 내 컴퓨터(로컬) 파일 찾기
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
        
    client = gspread.authorize(creds)
    return client

# --- [함수] 데이터 불러오기/저장하기 ---
def load_data(sheet_name):
    try:
        client = init_connection()
        sheet = client.open("Academy_DB").worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def add_data(sheet_name, new_data_dict):
    client = init_connection()
    sheet = client.open("Academy_DB").worksheet(sheet_name)
    if len(sheet.get_all_values()) == 0:
        header = list(new_data_dict.keys())
        sheet.append_row(header)
    row_values = [str(v) for v in new_data_dict.values()]
    sheet.append_row(row_values)

# --- 사이드바 메뉴 ---
menu = st.sidebar.radio("메뉴 선택", 
    ["1. 강사 등록", "2. 학생 등록", "3. 반 개설", "4. 수강 배정", "5. 출석 체크", "6. 데이터 통합 조회", "7. 시간표 보기"]
)

# 1. 강사 등록
if menu == "1. 강사 등록":
    st.subheader("👨‍🏫 강사 등록")
    with st.form("teacher_form"):
        name = st.text_input("이름")
        subject = st.text_input("담당 과목")
        phone = st.text_input("연락처")
        if st.form_submit_button("등록하기"):
            add_data('teachers', {'이름': name, '과목': subject, '연락처': phone})
            st.success(f"✅ {name} 선생님 등록 완료!")

# 2. 학생 등록
elif menu == "2. 학생 등록":
    st.subheader("📝 학생 등록")
    with st.form("student_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("이름")
            phone = st.text_input("연락처")
        with c2:
            grade = st.selectbox("학년", ["초4", "초5", "초6", "중1", "중2", "중3", "고1", "고2", "고3"])
            school = st.text_input("학교")
        if st.form_submit_button("저장"):
            add_data('students', {'이름': name, '연락처': phone, '학년': grade, '학교': school})
            st.success(f"✅ {name} 학생 등록 완료!")

# 3. 반 개설
elif menu == "3. 반 개설":
    st.subheader("📚 반 개설")
    df_t = load_data('teachers')
    if df_t.empty:
        st.warning("선생님을 먼저 등록해주세요.")
    else:
        with st.form("class_form"):
            c_name = st.text_input("반 이름")
            t_name = st.selectbox("담당 선생님", df_t['이름'] + " (" + df_t['과목'] + ")")
            time = st.text_input("수업 시간")
            if st.form_submit_button("반 만들기"):
                add_data('classes', {'반이름': c_name, '선생님': t_name, '시간': time})
                st.success(f"✅ {c_name} 개설 완료!")

# 4. 수강 배정
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정")
    df_s = load_data('students')
    df_c = load_data('classes')
    if df_s.empty or df_c.empty:
        st.warning("학생과 반 데이터가 필요합니다.")
    else:
        c1, c2 = st.columns(2)
        s_sel = c1.selectbox("학생", df_s['이름'] + "(" + df_s['학년'] + ")")
        c_sel = c2.selectbox("반", df_c['반이름'])
        if st.button("배정하기"):
            add_data('enrollments', {'학생': s_sel, '반이름': c_sel, '날짜': str(datetime.today().date())})
            st.success("배정 완료!")

# 5. 출석 체크
elif menu == "5. 출석 체크":
    st.subheader("✅ 출석 체크")
    df_e = load_data('enrollments')
    if df_e.empty:
        st.warning("배정된 학생이 없습니다.")
    else:
        today = st.date_input("날짜", datetime.today())
        cls = st.selectbox("반 선택", df_e['반이름'].unique())
        targets = df_e[df_e['반이름'] == cls]['학생'].tolist()
        
        with st.form("att"):
            res = {}
            for t in targets:
                res[t] = "출석" if st.checkbox(t, value=True) else "결석"
            if st.form_submit_button("저장"):
                for t, s in res.items():
                    add_data('attendance', {'날짜': str(today), '반이름': cls, '학생': t, '상태': s})
                st.success("출석 저장 완료!")

# 6. 조회
elif menu == "6. 데이터 통합 조회":
    st.subheader("📊 데이터 조회")
    tabs = st.tabs(["강사", "학생", "반", "배정", "출석"])
    tabs[0].dataframe(load_data('teachers'))
    tabs[1].dataframe(load_data('students'))
    tabs[2].dataframe(load_data('classes'))
    tabs[3].dataframe(load_data('enrollments'))
    tabs[4].dataframe(load_data('attendance'))
# ==========================================
# 7. 시간표 보기 (New!)
# ==========================================
elif menu == "7. 시간표 보기":
    st.subheader("📅 주간 수업 시간표")
    st.info("💡 '반 개설' 메뉴에서 시간에 '월', '화' 같은 요일이 포함되어야 표에 나타납니다.")
    
    # 데이터 가져오기
    df_classes = load_data('classes')
    
    if df_classes.empty:
        st.warning("아직 개설된 반이 없습니다.")
    else:
        # 1. 월~토 6개 기둥 만들기
        days = ["월", "화", "수", "목", "금", "토"]
        cols = st.columns(len(days)) # 화면을 6등분 함
        
        # 2. 각 요일별로 수업 분류해서 보여주기
        for i, day in enumerate(days):
            with cols[i]:
                # 요일 제목 꾸미기
                st.markdown(f"<div style='text-align: center; font-weight: bold; background-color: #f0f2f6; padding: 5px; border-radius: 5px;'>{day}요일</div>", unsafe_allow_html=True)
                st.write("") # 한 줄 띄우기
                
                # 데이터에서 해당 요일 글자가 들어간 수업만 찾기
                # (예: '월수금 7시' 데이터는 '월', '수', '금' 칸에 모두 나타남)
                # 에러 방지를 위해 문자열로 변환(astype) 후 검색
                daily_schedule = df_classes[df_classes['시간'].astype(str).str.contains(day)]
                
                if not daily_schedule.empty:
                    for _, row in daily_schedule.iterrows():
                        # 카드 형태로 예쁘게 보여주기
                        with st.container(border=True):
                            st.markdown(f"**📘 {row['반이름']}**")
                            st.caption(f"⏰ {row['시간']}")
                            st.caption(f"쌤: {row['선생님']}")
                else:
                    # 수업 없으면 흐린 글씨로 표시
                    st.caption("수업 없음")
