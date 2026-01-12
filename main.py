import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# --- [설정] 페이지 기본 설정 ---
st.set_page_config(page_title="hsjg Academy ERP", page_icon="☁️", layout="wide")
st.title("☁️ hsjg Academy 통합 관리 시스템 (Ver 2.0)")

# --- [핵심] 구글 시트 연결 함수 (로컬/클라우드 호환) ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # 1. 클라우드 비밀보관소(Secrets) 시도
        if "gcp_json" in st.secrets:
            key_dict = json.loads(st.secrets["gcp_json"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    except:
        # 2. 내 컴퓨터(로컬) 파일 사용
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
    # 헤더가 없으면 추가
    if len(sheet.get_all_values()) == 0:
        header = list(new_data_dict.keys())
        sheet.append_row(header)
    row_values = [str(v) for v in new_data_dict.values()]
    sheet.append_row(row_values)

# --- 사이드바 메뉴 ---
menu = st.sidebar.radio("메뉴 선택", 
    ["1. 강사 등록", "2. 학생 등록", "3. 반 개설", "4. 수강 배정", "5. 출석 체크", "6. 데이터 통합 조회", "7. 시간표 보기"]
)

# ==========================================
# 1. 강사 등록
# ==========================================
if menu == "1. 강사 등록":
    st.subheader("👨‍🏫 강사 등록")
    with st.form("teacher_form"):
        name = st.text_input("이름")
        subject = st.text_input("담당 과목")
        phone = st.text_input("연락처")
        if st.form_submit_button("등록하기"):
            add_data('teachers', {'이름': name, '과목': subject, '연락처': phone})
            st.success(f"✅ {name} 선생님 등록 완료!")

# ==========================================
# 2. 학생 등록
# ==========================================
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

# ==========================================
# 3. 반 개설 (업그레이드: 선택형)
# ==========================================
elif menu == "3. 반 개설":
    st.subheader("📚 반 개설")
    df_t = load_data('teachers')
    
    if df_t.empty:
        st.warning("선생님을 먼저 등록해주세요.")
    else:
        with st.form("class_form"):
            st.write("📝 **기본 정보 입력**")
            c_name = st.text_input("반 이름 (예: 중2 수학 A반)")
            
            # 선생님 목록
            if '이름' in df_t.columns and '과목' in df_t.columns:
                t_list = df_t['이름'].astype(str) + " (" + df_t['과목'].astype(str) + ")"
            else:
                t_list = df_t.iloc[:, 0].astype(str)
            
            t_name = st.selectbox("담당 선생님", t_list)
            
            st.divider()
            st.write("🕒 **수업 시간 설정**")
            
            # 요일 선택
            days_options = ["월", "화", "수", "목", "금", "토", "일"]
            selected_days = st.multiselect("수업 요일", days_options)
            
            # 시간 선택
            c1, c2 = st.columns(2)
            with c1:
                hour_options = [f"{i}시" for i in range(9, 24)] 
                selected_hour = st.selectbox("시작 시간 (시)", hour_options)
            with c2:
                minute_options = ["00분", "10분", "20분", "30분", "40분", "50분"]
                selected_minute = st.selectbox("시작 시간 (분)", minute_options)
            
            if st.form_submit_button("반 만들기"):
                if not c_name or not selected_days:
                    st.error("반 이름과 요일을 확인해주세요.")
                else:
                    # 요일 정렬
                    day_order = {"월":0, "화":1, "수":2, "목":3, "금":4, "토":5, "일":6}
                    selected_days.sort(key=lambda x: day_order[x])
                    
                    # 시간 문자열 생성
                    days_str = "".join(selected_days)
                    time_str = f"{days_str} {selected_hour} {selected_minute}"
                    
                    add_data('classes', {'반이름': c_name, '선생님': t_name, '시간': time_str})
                    st.success(f"✅ {c_name} ({time_str}) 개설 완료!")

# ==========================================
# 4. 수강 배정
# ==========================================
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정")
    df_s = load_data('students')
    df_c = load_data('classes')
    if df_s.empty or df_c.empty:
        st.warning("학생과 반 데이터가 필요합니다.")
    else:
        c1, c2 = st.columns(2)
        
        # 이름/반이름 컬럼 찾기 (없으면 첫번째 컬럼)
        s_col = '이름' if '이름' in df_s.columns else df_s.columns[0]
        c_col = '반이름' if '반이름' in df_c.columns else df_c.columns[0]

        s_sel = c1.selectbox("학생", df_s[s_col])
        c_sel = c2.selectbox("반", df_c[c_col])
        
        if st.button("배정하기"):
            add_data('enrollments', {'학생': s_sel, '반이름': c_sel, '날짜': str(datetime.today().date())})
            st.success("배정 완료!")

# ==========================================
# 5. 출석 체크
# ==========================================
elif menu == "5. 출석 체크":
    st.subheader("✅ 출석 체크")
    df_e = load_data('enrollments')
    if df_e.empty:
        st.warning("배정된 학생이 없습니다.")
    else:
        today = st.date_input("날짜", datetime.today())
        
        if '반이름' in df_e.columns:
            cls_list = df_e['반이름'].unique()
            cls = st.selectbox("반 선택", cls_list)
            targets = df_e[df_e['반이름'] == cls]['학생'].tolist()
            
            with st.form("att"):
                res = {}
                for t in targets:
                    res[t] = "출석" if st.checkbox(t, value=True) else "결석"
                memo = st.text_input("특이사항")
                if st.form_submit_button("저장"):
                    for t, s in res.items():
                        add_data('attendance', {'날짜': str(today), '반이름': cls, '학생': t, '상태': s, '비고': memo})
                    st.success("출석 저장 완료!")
        else:
            st.error("데이터 형식 오류: 반이름 컬럼을 찾을 수 없습니다.")

# ==========================================
# 6. 데이터 통합 조회
# ==========================================
elif menu == "6. 데이터 통합 조회":
    st.subheader("📊 데이터 조회")
    tabs = st.tabs(["강사", "학생", "반", "배정", "출석"])
    tabs[0].dataframe(load_data('teachers'))
    tabs[1].dataframe(load_data('students'))
    tabs[2].dataframe(load_data('classes'))
    tabs[3].dataframe(load_data('enrollments'))
    tabs[4].dataframe(load_data('attendance'))

# ==========================================
# 7. 시간표 보기 (업그레이드: 매트릭스형)
# ==========================================
elif menu == "7. 시간표 보기":
    st.subheader("📅 강사별 주간 시간표")
    st.info("💡 가로축은 요일, 세로축은 선생님입니다.")
    
    df_classes = load_data('classes')
    df_teachers = load_data('teachers')
    
    if df_classes.empty or df_teachers.empty:
        st.warning("데이터가 부족합니다. 강사와 반을 먼저 등록해주세요.")
    else:
        days = ["월", "화", "수", "목", "금", "토", "일"]
        cols = st.columns([2] + [1]*7) 
        cols[0].markdown("**구분**")
        for i, day in enumerate(days):
            cols[i+1].markdown(f"<div style='text-align:center; font-weight:bold; background-color:#eee; border-radius:5px;'>{day}</div>", unsafe_allow_html=True)
        st.divider()
        
        for _, t_row in df_teachers.iterrows():
            # 강사 이름 (컬럼명 유연하게 처리)
            t_name = t_row['이름'] if '이름' in df_teachers.columns else str(t_row.iloc[0])
            
            row_cols = st.columns([2] + [1]*7)
            row_cols[0].markdown(f"**👨‍🏫 {t_name}**")
            
            for i, day in enumerate(days):
                # 반 정보 찾기 (컬럼명 유연하게 처리)
                c_col = '선생님' if '선생님' in df_classes.columns else df_classes.columns[1]
                t_col = '시간' if '시간' in df_classes.columns else df_classes.columns[2]
                
                my_classes = df_classes[
                    (df_classes[c_col].astype(str).str.contains(t_name)) & 
                    (df_classes[t_col].astype(str).str.contains(day))
                ]
                
                with row_cols[i+1]:
                    if not my_classes.empty:
                        for _, c_row in my_classes.iterrows():
                            cn = c_row['반이름'] if '반이름' in df_classes.columns else c_row.iloc[0]
                            tm = c_row[t_col]
                            st.markdown(f"<div style='background-color:#e3f2fd; padding:5px; border-radius:5px; font-size:12px; margin-bottom:2px;'><b>{cn}</b><br>{tm}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='height:40px; border:1px dashed #ddd; border-radius:5px;'></div>", unsafe_allow_html=True)
            st.divider()
