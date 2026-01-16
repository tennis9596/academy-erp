import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import time

# ==========================================
# [기본 설정] 페이지 및 스타일
# ==========================================
st.set_page_config(page_title="학원 통합 관리 시스템", page_icon="🏫", layout="wide")
st.title("🏫 학원 통합 관리 시스템 (ERP Ver 9.2 - 독립적 유동 시간표)")

st.markdown("""
<style>
    .custom-alert {
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        background-color: rgba(46, 125, 50, 0.95); color: white; padding: 25px 50px;
        border-radius: 15px; font-size: 22px; font-weight: bold;
        z-index: 99999; box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        text-align: center; animation: fadeInOut 2s forwards; border: 2px solid #fff;
    }
    @keyframes fadeInOut { 0% { opacity: 0; transform: translate(-50%, -40%); } 15% { opacity: 1; transform: translate(-50%, -50%); } 85% { opacity: 1; transform: translate(-50%, -50%); } 100% { opacity: 0; transform: translate(-50%, -60%); } }
    
    .class-card {
        background-color: #E3F2FD; border-left: 5px solid #1565C0; border-radius: 8px;
        padding: 8px; margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        min-height: 140px; display: flex; flex-direction: column; justify-content: center;
        transition: transform 0.2s;
    }
    .class-card:hover { transform: scale(1.02); }
    .cc-subject { font-size: 0.8rem; color: #555; font-weight: bold; margin-bottom: 2px; }
    .cc-name { font-size: 1.05rem; color: #000; font-weight: 800; margin-bottom: 4px; line-height: 1.2; }
    .cc-info { font-size: 0.85rem; color: #333; margin-bottom: 2px; }
    .cc-time { font-size: 0.9rem; color: #1565C0; font-weight: 700; margin-top: 4px; }
    .cc-duration { font-size: 0.8rem; color: #E65100; font-weight: 600; margin-top: 2px; }

    .empty-card {
        background-color: #FAFAFA; border: 2px dashed #E0E0E0; border-radius: 8px;
        min-height: 140px; display: flex; align-items: center; justify-content: center;
        color: #BDBDBD; font-size: 0.9rem; margin-bottom: 5px;
    }

    .time-axis-card {
        background-color: #263238; color: white; border-radius: 8px;
        min-height: 140px; display: flex; flex-direction: column; align-items: center;
        justify-content: center; margin-bottom: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); padding: 5px;
    }
    .tac-start { font-size: 1.1rem; font-weight: 800; color: #FFD54F; }
    .tac-tilde { font-size: 0.8rem; margin: 2px 0; color: #aaa; }
    .tac-end { font-size: 1.0rem; font-weight: 600; color: #fff; }

    .day-header {
        text-align: center; font-weight: 800; font-size: 1.1rem; padding: 10px 0;
        background-color: #f1f3f5; border-bottom: 2px solid #ddd; margin-bottom: 10px;
        border-radius: 5px; color: #333;
    }
    button[data-baseweb="tab"] > div { font-size: 1.1rem; font-weight: 600; }
    .day-badge-single { padding: 8px 0; border-radius: 8px; color: #444; font-weight: 800; text-align: center; display: block; width: 100%; border: 1px solid rgba(0,0,0,0.05); font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# [함수] 구글 시트 및 유틸리티
# ==========================================
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

def safe_api_call(func, *args, **kwargs):
    max_retries = 5
    for i in range(max_retries):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if "429" in str(e): time.sleep(2 ** i); continue
            else: raise e
    return func(*args, **kwargs)

@st.cache_data(ttl=0)
def load_data(sheet_name):
    try:
        client = init_connection()
        sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
        data = safe_api_call(sheet.get_all_records)
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def clear_cache(): st.cache_data.clear()

def show_center_message(message, icon="✅"):
    placeholder = st.empty()
    placeholder.markdown(f'<div class="custom-alert"><span>{icon}</span> {message}</div>', unsafe_allow_html=True)
    time.sleep(1.2); placeholder.empty()

def calc_duration_min(start_time, end_time):
    try:
        t1 = datetime.strptime(start_time, "%H:%M")
        t2 = datetime.strptime(end_time, "%H:%M")
        return (t2 - t1).seconds // 60
    except: return 0

def sort_time_strings(time_list):
    try: return sorted(list(set(time_list)), key=lambda x: datetime.strptime(x, "%H:%M"))
    except: return sorted(list(set(time_list)))

# --- CRUD ---
def add_data(sheet_name, new_data_dict):
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    if len(safe_api_call(sheet.get_all_values)) == 0: safe_api_call(sheet.append_row, list(new_data_dict.keys()))
    safe_api_call(sheet.append_row, [str(v) for v in new_data_dict.values()])
    clear_cache()

def add_data_bulk(sheet_name, new_data_list):
    if not new_data_list: return
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    if len(safe_api_call(sheet.get_all_values)) == 0: safe_api_call(sheet.append_row, list(new_data_list[0].keys()))
    safe_api_call(sheet.append_rows, [list(d.values()) for d in new_data_list])
    clear_cache()

def delete_data_all(sheet_name, target_dict):
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    data = safe_api_call(sheet.get_all_records)
    rows_to_delete = []
    for i, row in enumerate(data):
        match = True
        for key, value in target_dict.items():
            if str(row.get(key)) != str(value): match = False; break
        if match: rows_to_delete.append(i + 2)
    if rows_to_delete:
        for row_num in sorted(rows_to_delete, reverse=True): safe_api_call(sheet.delete_rows, row_num)
        clear_cache(); return True
    return False

def update_data(sheet_name, target_col_name, target_val, new_data_dict):
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    data = safe_api_call(sheet.get_all_records)
    for i, row in enumerate(data):
        if str(row.get(target_col_name)) == str(target_val):
            row_num = i + 2
            header = safe_api_call(sheet.row_values, 1)
            uv = [new_data_dict.get(col, row.get(col)) for col in header]
            safe_api_call(sheet.update, f"A{row_num}", [uv])
            clear_cache(); return True
    return False

def get_col_data(df, col_name, fallback_index):
    if col_name in df.columns: return df[col_name]
    elif len(df.columns) > fallback_index: return df.iloc[:, fallback_index]
    else: return pd.Series([])

# ==========================================
# 사이드바
# ==========================================
menu = st.sidebar.radio("메뉴 선택", ["1. 강사 관리", "2. 학생 관리", "3. 반 관리", "4. 수강 배정", "5. 출석 체크", "6. 데이터 통합 조회", "7. 강사별 시간표", "8. 강의실별 시간표", "9. 학생 상세 분석"])

# ==========================================
# 1. 강사 관리
# ==========================================
if menu == "1. 강사 관리":
    st.subheader("👨‍🏫 강사 관리")
    tab1, tab2 = st.tabs(["➕ 신규 등록", "🔧 수정 및 삭제"])
    with tab1:
        with st.form("t_create"):
            name = st.text_input("이름")
            subject = st.text_input("과목")
            phone = st.text_input("연락처")
            if st.form_submit_button("등록"):
                if name: add_data('teachers', {'이름': name, '과목': subject, '연락처': phone}); show_center_message(f"{name} 등록 완료!"); st.rerun()
                else: st.error("이름 필수")
    with tab2:
        df_t = load_data('teachers')
        if not df_t.empty:
            t_list = get_col_data(df_t, '이름', 0).tolist()
            sel_t = st.selectbox("강사 선택", t_list, index=st.session_state.get('t_mod_idx', 0))
            if sel_t in t_list: st.session_state['t_mod_idx'] = t_list.index(sel_t)
            
            if sel_t:
                row = df_t[df_t[df_t.columns[0]] == sel_t].iloc[0]
                with st.form("t_edit"):
                    nn = st.text_input("이름", row.iloc[0])
                    ns = st.text_input("과목", row.iloc[1])
                    np = st.text_input("연락처", row.iloc[2])
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("수정"):
                        update_data('teachers', '이름', sel_t, {'이름': nn, '과목': ns, '연락처': np})
                        show_center_message("수정 완료"); st.rerun()
                    if c2.form_submit_button("삭제"):
                        delete_data_all('teachers', {'이름': sel_t})
                        st.session_state['t_mod_idx']=0
                        show_center_message("삭제 완료"); st.rerun()

# ==========================================
# 2. 학생 관리
# ==========================================
elif menu == "2. 학생 관리":
    st.subheader("📝 학생 관리")
    tab1, tab2, tab3 = st.tabs(["📋 전체 학생", "➕ 신규 등록", "🔧 수정/삭제"])
    df_c, df_t, df_s, df_e = load_data('classes'), load_data('teachers'), load_data('students'), load_data('enrollments')
    all_subjects = sorted(get_col_data(df_t, '과목', 1).unique().tolist()) if not df_t.empty else []

    with tab1:
        if not df_s.empty:
            v_df = df_s[['이름','학년','학교','담당강사','수강과목','연락처','학부모연락처']].copy()
            st.dataframe(v_df.style.apply(lambda r: [f'background-color: {"#E3F2FD" if r.name%2==0 else "#F9F9F9"}; color: black']*len(r), axis=1), use_container_width=True, hide_index=True, height=600)
        else: st.info("데이터 없음")

    with tab2:
        if df_c.empty: st.warning("반 데이터 없음")
        c1, c2 = st.columns(2)
        nm = c1.text_input("이름", key="n_nm")
        ph = c1.text_input("학생 폰", key="n_ph")
        pp = c1.text_input("부모 폰", key="n_pp")
        gr = c2.selectbox("학년", ["초4","초5","초6","중1","중2","중3","고1","고2","고3"], key="n_gr")
        sc = c2.text_input("학교", key="n_sc")
        
        st.divider(); st.markdown("##### 2️⃣ 수강 과목 및 반 선택")
        fin_enroll, fin_subs, fin_teas = [], set(), set()
        
        for sub in all_subjects:
            if st.checkbox(f"📘 {sub}", key=f"n_chk_{sub}"):
                fin_subs.add(sub)
                teas = df_t[df_t.iloc[:,1]==sub].iloc[:,0].tolist()
                c_t, c_c = st.columns([1,2])
                sel_ts = c_t.multiselect(f"선생님 ({sub})", teas, key=f"n_t_{sub}")
                for t in sel_ts: fin_teas.add(t)
                
                if sel_ts:
                    cls_opts, cls_map = [], {}
                    for t in sel_ts:
                        t_cs = df_c[df_c.iloc[:,1].str.contains(t)]
                        for _, r in t_cs.iterrows():
                            lbl = f"{r.iloc[0]} ({r.iloc[2]})"
                            cls_opts.append(lbl); cls_map[lbl] = {'n': r.iloc[0], 't': r.iloc[1]}
                    sel_cs = c_c.multiselect(f"반 ({sub})", cls_opts, key=f"n_c_{sub}")
                    for lbl in sel_cs: fin_enroll.append({'학생': nm, '반이름': cls_map[lbl]['n'], '담당강사': cls_map[lbl]['t'], '날짜': str(datetime.today().date())})
        
        if st.button("저장", type="primary"):
            if not nm: st.error("이름 입력")
            else:
                add_data('students', {'이름': nm, '연락처': ph, '학부모연락처': pp, '학년': gr, '학교': sc, '수강과목': ", ".join(sorted(list(fin_subs))), '담당강사': ", ".join(sorted(list(fin_teas)))})
                if fin_enroll: add_data_bulk('enrollments', fin_enroll)
                show_center_message("등록 완료!"); st.rerun()

    with tab3:
        if not df_s.empty:
            k = st.text_input("이름 검색", key="s_k")
            df_s['dsp'] = df_s.apply(lambda x: f"{x['이름']} ({x['학년']})", axis=1)
            f_df = df_s[df_s['이름'].str.contains(k)] if k else df_s
            
            if not f_df.empty:
                opts = f_df['dsp'].tolist()
                sel = st.selectbox("학생 선택", opts, index=st.session_state.get('s_idx', 0))
                if sel in opts: st.session_state['s_idx'] = opts.index(sel)
                
                real_n = sel.split(' (')[0]
                row = f_df[f_df['dsp']==sel].iloc[0]
                
                st.divider()
                c1, c2 = st.columns(2)
                un = c1.text_input("이름", row['이름'], key="u_nm")
                up = c1.text_input("학생 폰", row['연락처'], key="u_ph")
                upp = c1.text_input("부모 폰", row['학부모연락처'], key="u_pp")
                ug = c2.selectbox("학년", ["초4","초5","초6","중1","중2","중3","고1","고2","고3"], index=["초4","초5","초6","중1","중2","중3","고1","고2","고3"].index(row['학년']), key="u_gr")
                us = c2.text_input("학교", row['학교'], key="u_sc")
                
                my_en = df_e[df_e.iloc[:,0]==real_n] if not df_e.empty else pd.DataFrame()
                act_subs, act_teas_map, act_cls_map = set(), {}, {}
                if not my_en.empty:
                    for cn in my_en.iloc[:,1]:
                        cr = df_c[df_c.iloc[:,0]==cn]
                        if not cr.empty:
                            r = cr.iloc[0]
                            tr = r.iloc[1].split('(')[0].strip() if "(" in r.iloc[1] else r.iloc[1]
                            sr = r.iloc[1].split('(')[1].replace(')','').strip() if "(" in r.iloc[1] else "기타"
                            act_subs.add(sr)
                            act_teas_map.setdefault(sr, set()).add(tr)
                            act_cls_map.setdefault(sr, []).append(f"{cn} ({r.iloc[2]})")
                
                st.markdown("##### 📚 수강 수정")
                u_enroll, u_subs, u_teas = [], set(), set()
                for sub in all_subjects:
                    if st.checkbox(f"📘 {sub}", value=(sub in act_subs), key=f"u_chk_{sub}_{real_n}"):
                        u_subs.add(sub)
                        ts = df_t[df_t.iloc[:,1]==sub].iloc[:,0].tolist()
                        defs = [t for t in list(act_teas_map.get(sub, set())) if t in ts]
                        c_t, c_c = st.columns([1,2])
                        s_ts = c_t.multiselect(f"강사 ({sub})", ts, default=defs, key=f"u_t_{sub}_{real_n}")
                        for t in s_ts: u_teas.add(t)
                        if s_ts:
                            c_ops, c_map = [], {}
                            for t in s_ts:
                                t_cs = df_c[df_c.iloc[:,1].str.contains(t)]
                                for _, r in t_cs.iterrows():
                                    lbl = f"{r.iloc[0]} ({r.iloc[2]})"; c_ops.append(lbl)
                                    c_map[lbl] = {'n': r.iloc[0], 't': r.iloc[1]}
                            d_cls = [c for c in act_cls_map.get(sub, []) if c in c_ops]
                            s_cs = c_c.multiselect(f"반 ({sub})", c_ops, default=d_cls, key=f"u_c_{sub}_{real_n}")
                            for lbl in s_cs: u_enroll.append({'학생': un, '반이름': c_map[lbl]['n'], '담당강사': c_map[lbl]['t'], '날짜': str(datetime.today().date())})
                
                b1, b2 = st.columns(2)
                if b1.button("수정 저장"):
                    st.session_state['act'] = 'upd'; st.session_state['tgt'] = sel
                if b2.button("삭제", type="primary"):
                    st.session_state['act'] = 'del'; st.session_state['tgt'] = sel
                
                if st.session_state.get('act') and st.session_state.get('tgt') == sel:
                    if st.session_state['act'] == 'upd':
                        st.warning("정말 수정하시겠습니까?")
                        if st.button("확인 (수정)"):
                            nd = {'이름': un, '연락처': up, '학부모연락처': upp, '학년': ug, '학교': us, '수강과목': ", ".join(sorted(list(u_subs))), '담당강사': ", ".join(sorted(list(u_teas)))}
                            update_data('students', '이름', real_n, nd)
                            delete_data_all('enrollments', {'학생': real_n})
                            if u_enroll: add_data_bulk('enrollments', u_enroll)
                            st.session_state['act'] = None; show_center_message("수정 완료"); st.rerun()
                    elif st.session_state['act'] == 'del':
                        st.error("정말 삭제하시겠습니까? (복구 불가)")
                        if st.button("확인 (삭제)"):
                            delete_data_all('students', {'이름': real_n})
                            delete_data_all('enrollments', {'학생': real_n})
                            st.session_state['act'] = None; st.session_state['s_idx'] = 0
                            show_center_message("삭제 완료"); st.rerun()

# ==========================================
# 3. 반 관리
# ==========================================
elif menu == "3. 반 관리":
    st.subheader("📚 반 관리")
    tab1, tab2 = st.tabs(["➕ 반 개설", "🔧 수정/삭제"])
    days, hours, mins = ["월","화","수","목","금","토","일"], [f"{i}시" for i in range(9,23)], ["00분","10분","20분","30분","40분","50분"]
    day_cols = {"월":"#FFEBEE","화":"#FFF3E0","수":"#E8F5E9","목":"#E3F2FD","금":"#F3E5F5","토":"#FAFAFA","일":"#FFEBEE"}

    with tab1:
        df_t = load_data('teachers')
        if df_t.empty: st.warning("교사 없음")
        else:
            ts = (get_col_data(df_t,'이름',0)+" ("+get_col_data(df_t,'과목',1)+")").tolist()
            c1, c2, c3 = st.columns([2,1,2])
            cn = c1.text_input("반 이름", key="nc_n")
            cr = c2.selectbox("강의실", ["기타","101호","102호","103호","104호"], key="nc_r")
            ct = c3.selectbox("담당 강사", ts, key="nc_t")
            
            sch = []
            for d in days:
                dc1, dc2, dc3, dc4, dc5, dc6 = st.columns([1,2,2,0.5,2,2])
                with dc1:
                    chk = st.checkbox("", key=f"chk_{d}")
                    st.markdown(f"<div class='day-badge-single' style='background-color:{day_cols[d]}'>{d}</div>", unsafe_allow_html=True)
                with dc2: s_h = st.selectbox("시", hours, key=f"s_h_{d}", disabled=not chk, label_visibility="collapsed")
                with dc3: s_m = st.selectbox("분", mins, key=f"s_m_{d}", disabled=not chk, label_visibility="collapsed")
                with dc4: st.write("~")
                with dc5: e_h = st.selectbox("시", hours, index=1, key=f"e_h_{d}", disabled=not chk, label_visibility="collapsed")
                with dc6: e_m = st.selectbox("분", mins, key=f"e_m_{d}", disabled=not chk, label_visibility="collapsed")
                if chk: sch.append(f"{d} {s_h.replace('시',':')}{s_m.replace('분','')}-{e_h.replace('시',':')}{e_m.replace('분','')}")
            
            if st.button("반 생성", type="primary"):
                if not cn: st.error("이름 입력")
                else: add_data('classes', {'반이름': cn, '선생님': ct, '시간': ", ".join(sch), '강의실': cr}); show_center_message("생성 완료"); st.rerun()

    with tab2:
        df_c = load_data('classes')
        if df_c.empty: st.info("반 없음")
        else:
            df_t = load_data('teachers')
            ts = (get_col_data(df_t,'이름',0)+" ("+get_col_data(df_t,'과목',1)+")").tolist()
            sel_t = st.selectbox("강사 필터", ts, index=st.session_state.get('ct_idx', 0))
            if sel_t in ts: st.session_state['ct_idx'] = ts.index(sel_t)
            
            if sel_t:
                f_cs = df_c[df_c.iloc[:,1]==sel_t]
                if f_cs.empty: st.warning("담당 반 없음")
                else:
                    c_opts = (f_cs.iloc[:,0]+" ("+f_cs.iloc[:,3].astype(str)+")").tolist()
                    sel_c = st.selectbox("반 선택", c_opts, index=st.session_state.get('cc_idx', 0))
                    if sel_c in c_opts: st.session_state['cc_idx'] = c_opts.index(sel_c)
                    
                    real_cn = sel_c.split(' (')[0]
                    curr = f_cs[f_cs.iloc[:,0]==real_cn].iloc[0]
                    cur_sch = {}
                    for p in str(curr.iloc[2]).split(','):
                        kp = p.strip().split()
                        if len(kp)==2: cur_sch[kp[0]] = kp[1]
                    
                    st.divider()
                    st.markdown(f"#### 🔧 {real_cn} 수정")
                    un = st.text_input("반 이름", real_cn, key=f"un_{real_cn}")
                    ur = st.selectbox("강의실", ["기타","101호","102호","103호","104호"], index=["기타","101호","102호","103호","104호"].index(curr.iloc[3]), key=f"ur_{real_cn}")
                    ut = st.selectbox("강사", ts, index=ts.index(sel_t), key=f"ut_{real_cn}")
                    
                    usch = []
                    for d in days:
                        has = d in cur_sch
                        s_i, sm_i, e_i, em_i = 0, 0, 0, 0
                        if has:
                            try:
                                s, e = cur_sch[d].split('-')
                                s_i, sm_i = hours.index(s.split(':')[0]+"시"), mins.index(s.split(':')[1]+"분" if len(s.split(':')[1])==2 else "0"+s.split(':')[1]+"분")
                                e_i, em_i = hours.index(e.split(':')[0]+"시"), mins.index(e.split(':')[1]+"분" if len(e.split(':')[1])==2 else "0"+e.split(':')[1]+"분")
                            except: pass
                        dc1, dc2, dc3, dc4, dc5, dc6 = st.columns([1,2,2,0.5,2,2])
                        with dc1:
                            uchk = st.checkbox("", value=has, key=f"uchk_{d}_{real_cn}")
                            st.markdown(f"<div class='day-badge-single' style='background-color:{day_cols[d]}'>{d}</div>", unsafe_allow_html=True)
                        with dc2: ush = st.selectbox("시", hours, index=s_i, key=f"ush_{d}_{real_cn}", disabled=not uchk, label_visibility="collapsed")
                        with dc3: usm = st.selectbox("분", mins, index=sm_i, key=f"usm_{d}_{real_cn}", disabled=not uchk, label_visibility="collapsed")
                        with dc4: st.write("~")
                        with dc5: ueh = st.selectbox("시", hours, index=e_i, key=f"ueh_{d}_{real_cn}", disabled=not uchk, label_visibility="collapsed")
                        with dc6: uem = st.selectbox("분", mins, index=em_i, key=f"uem_{d}_{real_cn}", disabled=not uchk, label_visibility="collapsed")
                        if uchk: usch.append(f"{d} {ush.replace('시',':')}{usm.replace('분','')}-{ueh.replace('시',':')}{uem.replace('분','')}")
                    
                    b1, b2 = st.columns(2)
                    if b1.button("수정 저장"):
                        update_data('classes', '반이름', real_cn, {'반이름': un, '선생님': ut, '시간': ", ".join(usch), '강의실': ur})
                        show_center_message("수정 완료"); st.rerun()
                    if b2.button("삭제"):
                        delete_data_all('classes', {'반이름': real_cn})
                        delete_data_all('enrollments', {'반이름': real_cn})
                        st.session_state['cc_idx']=0
                        show_center_message("삭제 완료"); st.rerun()

# ==========================================
# 4. 수강 배정
# ==========================================
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정 현황")
    tab1, tab2 = st.tabs(["📋 전체 수강 현황", "➕ 개별 관리"])
    df_s, df_c, df_t, df_e = load_data('students'), load_data('classes'), load_data('teachers'), load_data('enrollments')

    with tab1:
        if df_e.empty: st.info("내역 없음")
        else:
            view_df = df_e.copy()
            view_df.columns = ["학생", "반", "선생님", "등록일"]
            st.dataframe(view_df, use_container_width=True, hide_index=True)

    with tab2:
        st.info("학생 관리 메뉴를 이용하세요.")
        if not df_s.empty:
            k = st.text_input("학생 검색", key="assign_k")
            s_list = get_col_data(df_s, '이름', 0)
            if k: s_list = s_list[s_list.str.contains(k)]
            sel = st.selectbox("학생 선택", s_list.unique()) if not s_list.empty else None
            
            if sel:
                st.divider()
                st.write(f"**{sel}**의 반 목록")
                if not df_e.empty:
                    my = df_e[df_e.iloc[:,0]==sel]
                    for i, r in my.iterrows():
                        c1, c2 = st.columns([3,1])
                        c1.success(r.iloc[1])
                        if c2.button("취소", key=f"del_{i}"):
                            delete_data_all('enrollments', {'학생': sel, '반이름': r.iloc[1]})
                            st.rerun()
                
                with c2:
                    st.markdown("**➕ 반 추가 배정**")
                    if not df_c.empty:
                        cls_opts = []
                        for _, row in df_c.iterrows():
                            cls_opts.append(f"{row.iloc[0]} ({row.iloc[1]})")
                        
                        target_cls_full = st.selectbox("추가할 반 선택", cls_opts)
                        if st.button("추가 배정"):
                            real_cls = target_cls_full.split(' (')[0]
                            real_teacher = target_cls_full.split(' (')[1].replace(')', '')
                            add_data('enrollments', {'학생': sel, '반이름': real_cls, '담당강사': real_teacher, '날짜': str(datetime.today().date())})
                            show_center_message("추가 배정 완료")
                            time.sleep(1); st.rerun()

# ==========================================
# 5. 출석 체크
# ==========================================
elif menu == "5. 출석 체크":
    st.subheader("✅ 출석 체크")
    df_e = load_data('enrollments')
    if not df_e.empty:
        td = st.date_input("날짜")
        cls = st.selectbox("반 선택", df_e.iloc[:,1].unique())
        stds = sorted(list(set(df_e[df_e.iloc[:,1] == cls].iloc[:,0].tolist())))
        with st.form("att_form"):
            st.write(f"**{cls}** 수강생 ({len(stds)}명)")
            res = {}
            cols = st.columns(4)
            for i, s in enumerate(stds):
                with cols[i%4]: res[s] = "출석" if st.checkbox(s, value=True) else "결석"
            memo = st.text_input("특이사항")
            if st.form_submit_button("출석 저장"):
                for s, v in res.items():
                    add_data('attendance', {'날짜': str(td), '반이름': cls, '학생': s, '상태': v, '비고': memo})
                show_center_message("출석 저장 완료!")

# ==========================================
# 6. 데이터 통합 조회
# ==========================================
elif menu == "6. 데이터 통합 조회":
    st.subheader("📊 데이터 통합 조회")
    tabs = st.tabs(["강사", "학생", "반", "배정", "출석"])
    tabs[0].dataframe(load_data('teachers'))
    tabs[1].dataframe(load_data('students'))
    tabs[2].dataframe(load_data('classes'))
    tabs[3].dataframe(load_data('enrollments'))
    tabs[4].dataframe(load_data('attendance'))

# ==========================================
# 7. 강사별 시간표 (독립적 유동 시간표)
# ==========================================
elif menu == "7. 강사별 시간표":
    st.subheader("📅 강사별 주간 시간표 (맞춤형 시간대)")
    df_c, df_t, df_e = load_data('classes'), load_data('teachers'), load_data('enrollments')
    
    if not df_t.empty and not df_c.empty:
        t_names = get_col_data(df_t, '이름', 0)
        t_subs = get_col_data(df_t, '과목', 1)
        teachers_raw = t_names.tolist()
        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        
        tabs = st.tabs([f"{n} ({s})" for n, s in zip(t_names, t_subs)])
        
        for idx, teacher_raw in enumerate(teachers_raw):
            with tabs[idx]:
                # [핵심] 현재 탭(선생님)에 해당하는 수업만 필터링하여 타임라인 생성
                my_classes = df_c[df_c.iloc[:,1].str.contains(teacher_raw)]
                
                local_times = set()
                if not my_classes.empty:
                    for _, row in my_classes.iterrows():
                        for tp in str(row.iloc[2]).split(','):
                            try: local_times.add(tp.split()[1].split('-')[0])
                            except: pass
                
                sorted_local_timeline = sort_time_strings(list(local_times))
                
                if not sorted_local_timeline:
                    st.info("등록된 수업이 없습니다.")
                else:
                    cols = st.columns([0.5] + [1]*7)
                    cols[0].write("")
                    for i, d in enumerate(days_ko): cols[i+1].markdown(f"<div class='day-header'>{d}</div>", unsafe_allow_html=True)
                    
                    for start_t in sorted_local_timeline:
                        cols = st.columns([0.5] + [1]*7)
                        
                        # 이 시간대(start_t)의 최대 종료 시간 계산 (타임라인 표시용)
                        max_end = start_t
                        for _, row in my_classes.iterrows():
                             for tp in str(row.iloc[2]).split(','):
                                try:
                                    s, e = tp.split()[1].split('-')
                                    if s == start_t and e > max_end: max_end = e
                                except: pass
                        
                        with cols[0]:
                            st.markdown(f"<div class='time-axis-card'><span class='tac-start'>{start_t}</span><span class='tac-tilde'>~</span><span class='tac-end'>{max_end}</span></div>", unsafe_allow_html=True)
                        
                        for i, d in enumerate(days_ko):
                            found = None
                            for _, row in my_classes.iterrows():
                                for tp in str(row.iloc[2]).split(','):
                                    if tp.strip().startswith(d):
                                        try:
                                            s, e = tp.split()[1].split('-')
                                            if s == start_t:
                                                found = {'sub': t_subs.iloc[idx], 'name': row.iloc[0], 'room': row.iloc[3], 'time': tp.split()[1], 'dur': calc_duration_min(s, e)}
                                        except: pass
                            with cols[i+1]:
                                if found:
                                    st.markdown(f"""<div class='class-card'><div class='cc-subject'>{found['sub']}</div><div class='cc-name'>{found['name']}</div><div class='cc-info'>🏫 {found['room']}</div><div class='cc-time'>⏰ {found['time']}</div><div class='cc-duration'>⏳ {found['dur']}분</div></div>""", unsafe_allow_html=True)
                                    students = []
                                    if not df_e.empty:
                                        raw = df_e[df_e.iloc[:,1]==found['name']].iloc[:,0].tolist()
                                        students = sorted(list(set(raw)))
                                    with st.popover(f"👥 명단 ({len(students)}명)", use_container_width=True):
                                        for s in students: st.text(f"• {s}")
                                else:
                                    st.markdown("<div class='empty-card'></div>", unsafe_allow_html=True)

# ==========================================
# 8. 강의실별 시간표 (독립적 유동 시간표)
# ==========================================
elif menu == "8. 강의실별 시간표":
    st.subheader("🏫 강의실 배정 현황 (맞춤형 시간대)")
    df_c, df_e = load_data('classes'), load_data('enrollments')
    
    if not df_c.empty:
        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        d_tabs = st.tabs(days_ko)
        rooms = ["기타", "101호", "102호", "103호", "104호"]
        
        for idx, day in enumerate(days_ko):
            with d_tabs[idx]:
                # [핵심] 현재 탭(요일)에 해당하는 수업만 필터링하여 타임라인 생성
                day_times = set()
                day_classes = [] # (row, time_str)
                
                for _, row in df_c.iterrows():
                    for tp in str(row.iloc[2]).split(','):
                        if tp.strip().startswith(day):
                            try:
                                t_range = tp.split()[1]
                                day_times.add(t_range.split('-')[0])
                                day_classes.append((row, t_range))
                            except: pass
                
                sorted_day_timeline = sort_time_strings(list(day_times))
                
                if not sorted_day_timeline:
                    st.info("이 요일에는 수업이 없습니다.")
                else:
                    cols = st.columns([0.3] + [1]*len(rooms))
                    cols[0].write("")
                    for i, r in enumerate(rooms): cols[i+1].markdown(f"<div class='day-header'>{r}</div>", unsafe_allow_html=True)
                    
                    for start_t in sorted_day_timeline:
                        cols = st.columns([0.3] + [1]*len(rooms))
                        max_end = start_t
                        # 이 시간대(start_t)의 최대 종료 시간 계산
                        for r_data, t_str in day_classes:
                            try:
                                s, e = t_str.split('-')
                                if s == start_t and e > max_end: max_end = e
                            except: pass
                        
                        with cols[0]:
                            st.markdown(f"<div class='time-axis-card'><span class='tac-start'>{start_t}</span><span class='tac-tilde'>~</span><span class='tac-end'>{max_end}</span></div>", unsafe_allow_html=True)
                        
                        for i, r in enumerate(rooms):
                            found = None
                            for r_data, t_str in day_classes:
                                curr_r = str(r_data.iloc[3])
                                if curr_r not in rooms: curr_r = "기타"
                                if curr_r == r:
                                    try:
                                        s, e = t_str.split('-')
                                        if s == start_t:
                                            full_tea = str(r_data.iloc[1])
                                            tn = full_tea.split('(')[0] if "(" in full_tea else full_tea
                                            sub = full_tea.split('(')[1].replace(')', '') if "(" in full_tea else "과목"
                                            found = {'sub': sub, 'name': r_data.iloc[0], 'tea': tn, 'time': t_str, 'dur': calc_duration_min(s, e)}
                                    except: pass
                            with cols[i+1]:
                                if found:
                                    st.markdown(f"""<div class='class-card' style='border-left-color:#43A047;background-color:#E8F5E9;'><div class='cc-subject'>{found['sub']}</div><div class='cc-name'>{found['name']}</div><div class='cc-info'>👨‍🏫 {found['tea']}</div><div class='cc-time'>⏰ {found['time']}</div><div class='cc-duration'>⏳ {found['dur']}분</div></div>""", unsafe_allow_html=True)
                                    students = []
                                    if not df_e.empty:
                                        raw = df_e[df_e.iloc[:,1]==found['name']].iloc[:,0].tolist()
                                        students = sorted(list(set(raw)))
                                    with st.popover(f"👥 명단 ({len(students)}명)", use_container_width=True):
                                        for s in students: st.text(f"• {s}")
                                else:
                                    st.markdown("<div class='empty-card'></div>", unsafe_allow_html=True)

# ==========================================
# 9. 학생 상세 분석
# ==========================================
elif menu == "9. 학생 상세 분석":
    st.subheader("📊 학생 상세 분석")
    df_s, df_a = load_data('students'), load_data('attendance')
    if not df_s.empty:
        k = st.text_input("검색 (이름)", key='detail_search')
        if k:
            res = df_s[df_s.iloc[:,0].str.contains(k)]
            if not res.empty:
                sl = st.selectbox("학생 선택", res.iloc[:,0].unique())
                row = res[res.iloc[:,0]==sl].iloc[0]
                st.divider()
                st.markdown(f"### 🧑‍🎓 {row.iloc[0]} ({row.iloc[3]} / {row.iloc[4]})")
                c1, c2 = st.columns(2)
                c1.info(f"📞 학생: {row.iloc[1]}")
                c2.error(f"📞 부모님: {row.iloc[2]}")
                if not df_a.empty:
                    ma = df_a[df_a.iloc[:,2] == sl]
                    if not ma.empty:
                        total = len(ma)
                        att = len(ma[ma.iloc[:,3] == "출석"])
                        rate = (att/total)*100
                        st.metric("출석률", f"{rate:.1f}%", f"{att}/{total}회")
                        st.dataframe(ma)
                    else: st.info("출석 기록이 없습니다.")