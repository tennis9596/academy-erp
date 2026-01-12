import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import time

# --- [설정] 페이지 기본 설정 ---
st.set_page_config(page_title="학원 통합 관리 시스템", page_icon="🏫", layout="wide")
st.title("🏫 학원 통합 관리 시스템 (ERP Ver 3.4 - 안정성 강화)")

# --- [핵심] 구글 시트 연결 (연결 객체는 리소스 캐싱) ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_json" in st.secrets:
            key_dict = json.loads(st.secrets["gcp_json"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    except:
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    client = gspread.authorize(creds)
    return client

# --- [수정됨] 데이터 불러오기 (캐싱 적용: ttl=10초) ---
# 10초 동안은 다시 구글을 부르지 않고 기억한 데이터를 씀 -> 에러 방지!
@st.cache_data(ttl=10)
def load_data(sheet_name):
    try:
        client = init_connection()
        sheet = client.open("Academy_DB").worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# --- [수정됨] 데이터 추가/삭제/수정 시 캐시 초기화 ---
# 데이터를 바꿨을 때는 기억을 지우고 다시 가져와야 함
def clear_cache():
    st.cache_data.clear()

def add_data(sheet_name, new_data_dict):
    client = init_connection()
    sheet = client.open("Academy_DB").worksheet(sheet_name)
    if len(sheet.get_all_values()) == 0:
        header = list(new_data_dict.keys())
        sheet.append_row(header)
    row_values = [str(v) for v in new_data_dict.values()]
    sheet.append_row(row_values)
    clear_cache() # [중요] 저장 후 캐시 삭제

def delete_data(sheet_name, target_dict):
    client = init_connection()
    sheet = client.open("Academy_DB").worksheet(sheet_name)
    data = sheet.get_all_records()
    for i, row in enumerate(data):
        match = True
        for key, value in target_dict.items():
            if str(row.get(key)) != str(value):
                match = False
                break
        if match:
            sheet.delete_rows(i + 2)
            clear_cache() # [중요] 삭제 후 캐시 삭제
            return True
    return False

def update_data(sheet_name, target_col_name, target_val, new_data_dict):
    client = init_connection()
    sheet = client.open("Academy_DB").worksheet(sheet_name)
    data = sheet.get_all_records()
    for i, row in enumerate(data):
        if str(row.get(target_col_name)) == str(target_val):
            row_num = i + 2
            header = sheet.row_values(1)
            update_values = []
            for col_title in header:
                update_values.append(new_data_dict.get(col_title, row.get(col_title)))
            sheet.update(f"A{row_num}", [update_values])
            clear_cache() # [중요] 수정 후 캐시 삭제
            return True
    return False

def get_col_data(df, col_name, fallback_index):
    if col_name in df.columns: return df[col_name]
    elif len(df.columns) > fallback_index: return df.iloc[:, fallback_index]
    else: return pd.Series([])

# --- 사이드바 메뉴 ---
menu = st.sidebar.radio("메뉴 선택", 
    ["1. 강사 관리", "2. 학생 등록", "3. 반 관리", "4. 수강 배정", "5. 출석 체크", "6. 데이터 통합 조회", "7. 시간표 보기", "8. 학생 상세 분석"]
)

# ==========================================
# 1. 강사 관리
# ==========================================
if menu == "1. 강사 관리":
    st.subheader("👨‍🏫 강사 관리")
    tab1, tab2 = st.tabs(["➕ 신규 등록", "🔧 수정 및 삭제"])
    
    with tab1:
        with st.form("teacher_form"):
            name = st.text_input("이름")
            subject = st.text_input("담당 과목")
            phone = st.text_input("연락처")
            if st.form_submit_button("등록하기"):
                if not name:
                    st.error("이름을 입력하세요.")
                else:
                    new_data = {'이름': name, '과목': subject, '연락처': phone}
                    add_data('teachers', new_data)
                    st.toast(f"✅ {name} 선생님 등록 완료!", icon="🎉")
                    st.success(f"✅ {name} 선생님 등록 완료!")
                    st.dataframe(pd.DataFrame([new_data]))

    with tab2:
        df_t = load_data('teachers')
        if not df_t.empty:
            t_names = get_col_data(df_t, '이름', 0)
            selected_t = st.selectbox("선생님 선택", t_names.tolist())
            
            if selected_t:
                col0 = df_t.columns[0]
                row = df_t[df_t[col0] == selected_t].iloc[0]
                
                with st.form("edit_t"):
                    n_name = st.text_input("이름", value=row.iloc[0])
                    n_sub = st.text_input("과목", value=row.iloc[1] if len(row)>1 else "") 
                    n_ph = st.text_input("연락처", value=row.iloc[2] if len(row)>2 else "")
                    
                    c1, c2 = st.columns(2)
                    with c1: upd = st.form_submit_button("수정 저장")
                    with c2: 
                        del_chk = st.checkbox("삭제 확인")
                        dele = st.form_submit_button("삭제하기")
                    
                    if upd:
                        new_data = {'이름': n_name, '과목': n_sub, '연락처': n_ph}
                        update_data('teachers', '이름', selected_t, new_data)
                        st.toast("✅ 정보가 수정되었습니다!", icon="🔧")
                        st.success("수정 완료!")
                        st.dataframe(pd.DataFrame([new_data]))
                        
                    if dele and del_chk:
                        delete_data('teachers', {'이름': selected_t})
                        st.toast(f"🗑️ {selected_t} 선생님 삭제 완료", icon="🗑️")
                        time.sleep(1)
                        st.rerun()

# ==========================================
# 2. 학생 등록
# ==========================================
elif menu == "2. 학생 등록":
    st.subheader("📝 학생 등록")
    df_t = load_data('teachers')
    with st.form("student_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("이름")
            phone = st.text_input("학생 폰")
            p_phone = st.text_input("부모님 폰")
        with c2:
            grade = st.selectbox("학년", ["초4","초5","초6","중1","중2","중3","고1","고2","고3"])
            school = st.text_input("학교")
        
        st.divider()
        subs = st.multiselect("과목", ["수학","영어","국어","과학","사회","기타"])
        
        if not df_t.empty:
            tn = get_col_data(df_t, '이름', 0).astype(str)
            ts = get_col_data(df_t, '과목', 1).astype(str)
            t_opts = (tn + " (" + ts + ")").tolist()
        else:
            t_opts = []
        sel_t = st.multiselect("담당 선생님", t_opts)
        
        if st.form_submit_button("저장하기"):
            new_data = {
                '이름': name, '연락처': phone, '학부모연락처': p_phone,
                '학년': grade, '학교': school,
                '수강과목': ", ".join(subs), '담당강사': ", ".join(sel_t)
            }
            add_data('students', new_data)
            st.toast(f"✅ {name} 학생 등록 성공!", icon="🎓")
            st.success("등록 완료")
            st.dataframe(pd.DataFrame([new_data]))

# ==========================================
# 3. 반 관리
# ==========================================
elif menu == "3. 반 관리":
    st.subheader("📚 반 관리")
    tab1, tab2 = st.tabs(["➕ 반 개설", "🔧 반 정보 수정/삭제"])
    
    with tab1:
        df_t = load_data('teachers')
        if df_t.empty:
            st.warning("선생님을 먼저 등록해주세요.")
        else:
            st.info("📝 **반 정보를 입력하세요** (요일 체크 -> 시간 입력)")
            c_name = st.text_input("반 이름")
            
            tn = get_col_data(df_t, '이름', 0).astype(str)
            ts = get_col_data(df_t, '과목', 1).astype(str)
            t_name = st.selectbox("담당 선생님", (tn + " (" + ts + ")").tolist())
            
            st.divider()
            days = ["월", "화", "수", "목", "금", "토", "일"]
            hours = [f"{i}시" for i in range(9, 23)]
            mins = ["00분", "10분", "20분", "30분", "40분", "50분"]
            
            schedule_data = {}
            for day in days:
                c1, c2, c3 = st.columns([1, 2, 2])
                with c1: is_chk = st.checkbox(f"{day}요일", key=f"c_{day}")
                if is_chk:
                    with c2: h = st.selectbox("시", hours, key=f"h_{day}", label_visibility="collapsed")
                    with c3: m = st.selectbox("분", mins, key=f"m_{day}", label_visibility="collapsed")
                    schedule_data[day] = f"{h.replace('시',':')}{m.replace('분','')}"
                else:
                    with c2: st.empty()
                    with c3: st.empty()

            st.divider()
            if st.button("반 만들기 (저장)"):
                if not c_name or not schedule_data:
                    st.error("이름과 시간을 확인하세요.")
                else:
                    ftime = ", ".join([f"{d} {t}" for d, t in schedule_data.items()])
                    new_data = {'반이름': c_name, '선생님': t_name, '시간': ftime}
                    add_data('classes', new_data)
                    st.toast(f"✅ {c_name} 개설 완료!", icon="🏫")
                    st.success("개설 완료")
                    st.dataframe(pd.DataFrame([new_data]))

    with tab2:
        df_c = load_data('classes')
        df_e = load_data('enrollments')
        df_t = load_data('teachers')
        
        if df_c.empty:
            st.info("개설된 반이 없습니다.")
        else:
            if not df_t.empty:
                tn = get_col_data(df_t, '이름', 0).astype(str)
                ts = get_col_data(df_t, '과목', 1).astype(str)
                f_t = st.selectbox("1️⃣ 선생님 선택", (tn + " (" + ts + ")").tolist())
            else: f_t = None
            
            if f_t:
                ct = get_col_data(df_c, '선생님', 1).astype(str)
                f_c = df_c[ct == f_t]
                if f_c.empty:
                    st.warning("담당하는 반이 없습니다.")
                    sel_c = None
                else:
                    cn = get_col_data(f_c, '반이름', 0)
                    sel_c = st.selectbox("2️⃣ 반 선택", cn.tolist())
            else: sel_c = None
            
            if sel_c:
                curr = df_c[df_c[df_c.columns[0]] == sel_c].iloc[0]
                st.divider()
                with st.form("edit_c"):
                    nn = st.text_input("반 이름", value=curr.iloc[0])
                    # 선생님 목록
                    tl = (tn + " (" + ts + ")").tolist() if not df_t.empty else []
                    try: ti = tl.index(curr.iloc[1])
                    except: ti = 0
                    nt = st.selectbox("선생님", tl, index=ti)
                    ntm = st.text_input("시간", value=curr.iloc[2] if len(curr)>2 else "")
                    
                    c1, c2 = st.columns(2)
                    with c1: upd = st.form_submit_button("수정 저장")
                    with c2: 
                        dchk = st.checkbox("삭제 확인")
                        dele = st.form_submit_button("삭제하기")
                    
                    if upd:
                        nd = {'반이름': nn, '선생님': nt, '시간': ntm}
                        update_data('classes', '반이름', sel_c, nd)
                        st.toast("✅ 수정되었습니다!", icon="🔧")
                        st.success("수정 완료")
                        st.dataframe(pd.DataFrame([nd]))
                    
                    if dele and dchk:
                        ecn = get_col_data(df_e, '반이름', 1)
                        if not df_e.empty and len(df_e[ecn == sel_c]) > 0:
                            st.error("⛔ 학생이 있어 삭제 불가")
                        else:
                            delete_data('classes', {'반이름': sel_c})
                            st.toast("🗑️ 삭제되었습니다.", icon="🗑️")
                            time.sleep(1)
                            st.rerun()

# ==========================================
# 4. 수강 배정
# ==========================================
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정")
    df_s = load_data('students')
    df_c = load_data('classes')
    df_t = load_data('teachers')
    df_e = load_data('enrollments')
    
    if df_s.empty: st.warning("학생 데이터 없음")
    else:
        k = st.text_input("학생 검색", placeholder="이름/번호")
        ssn = None
        if k:
            sn = get_col_data(df_s, '이름', 0).astype(str)
            sp = get_col_data(df_s, '연락처', 1).astype(str)
            res = df_s[sn.str.contains(k) | sp.str.contains(k)]
            if not res.empty:
                sl = st.selectbox("학생 선택", (get_col_data(res, '이름', 0) + " (" + get_col_data(res, '학교', 3) + ")").unique())
                ssn = res[res.iloc[:,0] == sl.split(" (")[0]].iloc[0].iloc[0]

        st.divider()
        if ssn:
            st.markdown(f"#### 👤 {ssn} 수강 목록")
            if not df_e.empty:
                esn = get_col_data(df_e, '학생', 0)
                myc = df_e[esn == ssn]
                for i, row in myc.iterrows():
                    c1, c2 = st.columns([4,1])
                    c1.write(f"📘 **{row.iloc[1]}** ({row.iloc[2] if len(row)>2 else ''})")
                    if c2.button("취소", key=f"d_{i}"):
                        delete_data('enrollments', {'학생': row.iloc[0], '반이름': row.iloc[1]})
                        st.toast("수강이 취소되었습니다.", icon="👋")
                        time.sleep(0.5)
                        st.rerun()
            
            st.markdown("#### ➕ 신규 배정")
            if not df_t.empty:
                s_sub = st.selectbox("과목", get_col_data(df_t, '과목', 1).unique())
                # 강사 필터링
                tsc = get_col_data(df_t, '과목', 1)
                tnc = get_col_data(df_t, '이름', 0)
                s_tea = st.selectbox("강사", df_t[tsc == s_sub].iloc[:,0].tolist())
                
                if s_tea:
                    ctc = get_col_data(df_c, '선생님', 1).astype(str)
                    cs = df_c[ctc.str.contains(s_tea)]
                    if not cs.empty:
                        cnc = get_col_data(cs, '반이름', 0)
                        ctm = get_col_data(cs, '시간', 2)
                        s_cls = st.selectbox("반", (cnc + " (" + ctm + ")").tolist())
                    else: s_cls = None
                else: s_cls = None
                
                if s_cls and st.button("배정 확정"):
                    rcn = cs[(cnc + " (" + ctm + ")") == s_cls].iloc[0].iloc[0]
                    dup = False
                    if not df_e.empty:
                        if not df_e[(get_col_data(df_e,'학생',0)==ssn) & (get_col_data(df_e,'반이름',1)==rcn)].empty:
                            dup = True
                    if dup: st.error("이미 수강중")
                    else:
                        nd = {'학생': ssn, '반이름': rcn, '담당강사': s_tea, '날짜': str(datetime.today().date())}
                        add_data('enrollments', nd)
                        st.toast(f"✅ {ssn} 학생 배정 완료!", icon="🔗")
                        st.success("배정 완료")
                        time.sleep(1)
                        st.rerun()

# ==========================================
# 5 ~ 8. 기타 메뉴
# ==========================================
elif menu == "5. 출석 체크":
    st.subheader("✅ 출석 체크")
    df_e = load_data('enrollments')
    if not df_e.empty:
        td = st.date_input("날짜")
        cn = get_col_data(df_e, '반이름', 1)
        cls = st.selectbox("반 선택", cn.unique())
        sn = get_col_data(df_e, '학생', 0)
        stds = df_e[cn == cls].iloc[:,0].tolist()
        
        with st.form("att"):
            r = {s: ("출석" if st.checkbox(s, True) else "결석") for s in stds}
            memo = st.text_input("특이사항")
            if st.form_submit_button("저장"):
                for s, stt in r.items():
                    add_data('attendance', {'날짜': str(td), '반이름': cls, '학생': s, '상태': sst if 'sst' in locals() else stt, '비고': memo})
                st.toast("✅ 출석 정보가 저장되었습니다!", icon="📝")
                st.success("저장 완료")

elif menu == "6. 데이터 통합 조회":
    st.subheader("📊 데이터 조회")
    tabs = st.tabs(["강사", "학생", "반", "배정", "출석"])
    tabs[0].dataframe(load_data('teachers'))
    tabs[1].dataframe(load_data('students'))
    tabs[2].dataframe(load_data('classes'))
    tabs[3].dataframe(load_data('enrollments'))
    tabs[4].dataframe(load_data('attendance'))

elif menu == "7. 시간표 보기":
    st.subheader("📅 시간표")
    df_c = load_data('classes')
    df_t = load_data('teachers')
    if not df_c.empty:
        days = ["월", "화", "수", "목", "금", "토", "일"]
        cols = st.columns([2] + [1]*7)
        cols[0].write("구분")
        for i, d in enumerate(days): cols[i+1].write(d)
        st.divider()
        for _, t in df_t.iterrows():
            tn = t.iloc[0]
            rc = st.columns([2] + [1]*7)
            rc[0].write(f"**{tn}**")
            for i, d in enumerate(days):
                ct = get_col_data(df_c, '선생님', 1).astype(str)
                ctm = get_col_data(df_c, '시간', 2).astype(str)
                mc = df_c[(ct.str.contains(tn)) & (ctm.str.contains(d))]
                with rc[i+1]:
                    for _, r in mc.iterrows():
                        st.caption(f"{r.iloc[0]}\n{r.iloc[2]}")

elif menu == "8. 학생 상세 분석":
    st.subheader("📊 학생 분석")
    df_s = load_data('students')
    df_a = load_data('attendance')
    if not df_s.empty:
        k = st.text_input("검색 (이름/번호)")
        if k:
            sn = get_col_data(df_s, '이름', 0).astype(str)
            sp = get_col_data(df_s, '연락처', 1).astype(str)
            res = df_s[sn.str.contains(k) | sp.str.contains(k)]
            if not res.empty:
                ln = get_col_data(res, '이름', 0)
                ls = get_col_data(res, '학교', 3)
                lbl = ln + " (" + ls + ")"
                sl = st.selectbox("선택", lbl.unique())
                sr = res[lbl == sl].iloc[0]
                
                st.divider()
                st.write(f"### {sr.iloc[0]}")
                c1,c2 = st.columns(2)
                c1.info(f"학생: {sr.iloc[1]}") 
                c2.error(f"부모: {sr.iloc[2]}")
                
                if not df_a.empty:
                    an = get_col_data(df_a, '학생', 2)
                    ma = df_a[an == sr.iloc[0]]
                    if not ma.empty:
                        ast = get_col_data(ma, '상태', 3)
                        rt = len(ma[ast=='출석']) / len(ma) * 100
                        st.metric("출석률", f"{rt:.1f}%")
                        st.dataframe(ma)