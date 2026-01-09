import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- [설정] 페이지 기본 설정 ---
st.set_page_config(page_title="hsjg Academy ERP", page_icon="☁️", layout="wide")
st.title("☁️ hsjg Academy 통합 관리 시스템 (Cloud Ver.)")

# --- [핵심] 구글 시트 연결 함수 (캐싱으로 속도 향상) ---
# 매번 로그인하면 느리니까, 한 번 로그인 정보를 기억해둡니다.
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
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
        return pd.DataFrame() # 에러나면 빈 껍데기 반환

def add_data(sheet_name, new_data_dict):
    client = init_connection()
    sheet = client.open("Academy_DB").worksheet(sheet_name)
    
    # 1. 만약 시트가 텅 비어있으면(첫 데이터면) 헤더부터 추가
    if len(sheet.get_all_values()) == 0:
        header = list(new_data_dict.keys())
        sheet.append_row(header)
        
    # 2. 데이터 추가 (값만 리스트로 변환해서 추가)
    row_values = list(new_data_dict.values())
    # 모든 값을 문자열로 변환 (오류 방지)
    row_values = [str(v) for v in row_values]
    sheet.append_row(row_values)

# --- 사이드바 메뉴 ---
menu = st.sidebar.radio("메뉴 선택", 
    ["1. 강사 등록", "2. 학생 등록", "3. 반 개설", "4. 수강 배정", "5. 출석 체크", "6. 데이터 통합 조회"]
)

# ==========================================
# 1. 강사 등록
# ==========================================
if menu == "1. 강사 등록":
    st.subheader("👨‍🏫 강사 등록 (Google Sheets)")
    with st.form("teacher_form"):
        name = st.text_input("이름")
        subject = st.text_input("담당 과목")
        phone = st.text_input("연락처")
        
        if st.form_submit_button("등록하기"):
            if name:
                new_data = {'이름': name, '과목': subject, '연락처': phone}
                add_data('teachers', new_data)
                st.success(f"✅ {name} 선생님이 구글 시트에 저장되었습니다!")
                st.balloons()

# ==========================================
# 2. 학생 등록
# ==========================================
elif menu == "2. 학생 등록":
    st.subheader("📝 학생 등록")
    with st.form("student_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("이름")
            phone = st.text_input("연락처")
        with col2:
            grade = st.selectbox("학년", ["초4", "초5", "초6", "중1", "중2", "중3", "고1", "고2", "고3"])
            school = st.text_input("학교")
        
        if st.form_submit_button("저장"):
            new_data = {'이름': name, '연락처': phone, '학년': grade, '학교': school}
            add_data('students', new_data)
            st.success(f"✅ {name} 학생 등록 완료!")

# ==========================================
# 3. 반 개설
# ==========================================
elif menu == "3. 반 개설":
    st.subheader("📚 반 개설")
    df_teachers = load_data('teachers')
    
    if df_teachers.empty:
        st.warning("등록된 선생님이 없습니다.")
    else:
        with st.form("class_form"):
            c_name = st.text_input("반 이름")
            # 선생님 선택 (이름과 과목 결합)
            t_list = df_teachers['이름'].astype(str) + " (" + df_teachers['과목'].astype(str) + ")"
            teacher = st.selectbox("담당 선생님", t_list)
            time = st.text_input("수업 시간")
            
            if st.form_submit_button("반 만들기"):
                new_data = {'반이름': c_name, '선생님': teacher, '시간': time}
                add_data('classes', new_data)
                st.success(f"✅ {c_name} 반이 개설되었습니다!")

# ==========================================
# 4. 수강 배정
# ==========================================
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정")
    df_stu = load_data('students')
    df_cls = load_data('classes')
    
    if df_stu.empty or df_cls.empty:
        st.warning("학생이나 반 데이터가 부족합니다.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            s_list = df_stu['이름'].astype(str) + "(" + df_stu['학년'].astype(str) + ")"
            s_sel = st.selectbox("학생", s_list)
        with c2:
            c_list = df_cls['반이름'].astype(str)
            c_sel = st.selectbox("반", c_list)
            
        if st.button("배정하기"):
            new_data = {'학생': s_sel, '반이름': c_sel, '날짜': str(datetime.today().date())}
            add_data('enrollments', new_data)
            st.success("배정 완료!")

# ==========================================
# 5. 출석 체크
# ==========================================
elif menu == "5. 출석 체크":
    st.subheader("✅ 출석 체크")
    df_enroll = load_data('enrollments')
    df_cls = load_data('classes')
    
    if df_enroll.empty:
        st.warning("수강 배정된 내역이 없습니다.")
    else:
        today = st.date_input("날짜", datetime.today())
        # 개설된 반 목록 가져오기
        if not df_cls.empty:
            cls_list = df_cls['반이름'].unique()
        else:
            cls_list = df_enroll['반이름'].unique() # 혹시 반 데이터가 없으면 배정 내역에서라도 가져옴
            
        selected_class = st.selectbox("반 선택", cls_list)
        
        # 해당 반 학생 찾기
        targets = df_enroll[df_enroll['반이름'] == selected_class]['학생'].tolist()
        
        if not targets:
            st.error("이 반에 배정된 학생이 없습니다.")
        else:
            with st.form("att_form"):
                st.write(f"**{selected_class}** 출석부")
                att_results = {}
                for stu in targets:
                    chk = st.checkbox(f"{stu}", value=True)
                    att_results[stu] = "출석" if chk else "결석"
                
                memo = st.text_input("특이사항")
                
                if st.form_submit_button("출석 저장"):
                    # 여러 명을 한꺼번에 저장해야 함 -> 반복문 사용
                    for stu, status in att_results.items():
                        row = {
                            '날짜': str(today),
                            '반이름': selected_class,
                            '학생': stu,
                            '상태': status,
                            '비고': memo
                        }
                        add_data('attendance', row)
                    st.success("출석이 구글 시트에 저장되었습니다!")

# ==========================================
# 6. 통합 조회
# ==========================================
elif menu == "6. 데이터 통합 조회":
    st.subheader("📊 구글 시트 실시간 조회")
    
    tabs = st.tabs(["강사", "학생", "반", "배정", "출석"])
    
    with tabs[0]: st.dataframe(load_data('teachers'))
    with tabs[1]: st.dataframe(load_data('students'))
    with tabs[2]: st.dataframe(load_data('classes'))
    with tabs[3]: st.dataframe(load_data('enrollments'))
    with tabs[4]: st.dataframe(load_data('attendance'))