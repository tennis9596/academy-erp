import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import time
import qrcode
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import io
import os
import calendar

# ==========================================
# [기본 설정] 페이지 및 스타일
# ==========================================
st.set_page_config(page_title="형설지공 학원 ERP", page_icon="🏫", layout="wide")

st.markdown("""
<style>
    /* 1. 인쇄 모드 설정 (Ctrl+P, 생활기록부용) */
    @media print {
        [data-testid="stSidebar"], header, footer, .stButton, .no-print { display: none !important; }
        .block-container { padding: 0 !important; max-width: 100% !important; }
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        .report-card { break-inside: avoid; }
    }

    /* 2. 카드형 시간표 스타일 (강사/강의실 시간표용) */
    .class-card {
        background-color: #E3F2FD; border-left: 5px solid #1565C0; border-radius: 8px;
        padding: 8px; margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        min-height: 100px; display: flex; flex-direction: column; justify-content: center;
    }
    .cc-subject { font-size: 0.8rem; color: #555; font-weight: bold; }
    .cc-name { font-size: 1.05rem; color: #000; font-weight: 800; margin-bottom: 3px; }
    .cc-info { font-size: 0.85rem; color: #333; }
    .cc-time { font-size: 0.9rem; color: #1565C0; font-weight: 700; margin-top: 3px; }
    .cc-duration { font-size: 0.8rem; color: #E65100; font-weight: 600; }
    
    .empty-card { background-color: #FAFAFA; border: 2px dashed #E0E0E0; border-radius: 8px; min-height: 100px; }
    
    .time-axis-card {
        background-color: #263238; color: white; border-radius: 8px;
        min-height: 100px; display: flex; flex-direction: column; align-items: center; justify-content: center;
        padding: 5px; margin-bottom: 5px;
    }
    .tac-start { font-size: 1.1rem; font-weight: 800; color: #FFD54F; }
    .tac-tilde { font-size: 0.8rem; margin: 2px 0; color: #aaa; }
    .tac-end { font-size: 1.0rem; font-weight: 600; color: #fff; }

    .day-header { text-align: center; font-weight: 800; background-color: #f1f3f5; padding: 10px 0; border-radius: 5px; margin-bottom: 10px; }
    
    /* 3. 생활기록부 리포트용 스타일 */
    .report-title { font-size: 2.2rem; font-weight: 900; color: #1565C0; text-align: center; margin-bottom: 10px; border-bottom: 3px solid #1565C0; padding-bottom: 10px; }
    .report-section { font-size: 1.3rem; font-weight: 800; color: #333; margin-top: 25px; margin-bottom: 10px; border-left: 5px solid #1565C0; padding-left: 10px; }
    .info-box { background-color: #f8f9fa; border: 1px solid #ddd; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
    .info-label { font-weight: bold; color: #555; }
    .info-value { font-weight: bold; color: #000; font-size: 1.1rem; }
    
    /* 4. 달력 스타일 */
    .cal-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .cal-th { background-color: #eee; padding: 5px; text-align: center; font-weight: bold; border: 1px solid #ddd; }
    .cal-td { height: 80px; vertical-align: top; border: 1px solid #ddd; padding: 5px; font-size: 0.9rem; position: relative; }
    .cal-day-num { font-weight: bold; margin-bottom: 3px; display: block; color: #333; }
    .cal-badge { display: block; padding: 4px; border-radius: 4px; font-size: 0.8rem; margin-bottom: 2px; color: white; text-align: center; font-weight: bold; }
    .bg-green { background-color: #4CAF50; } 
    .bg-red { background-color: #F44336; }   
    .bg-gray { background-color: #9E9E9E; }  
    .bg-blue { background-color: #2196F3; }

    /* 5. 알림 메시지 */
    .custom-alert { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background-color: rgba(46, 125, 50, 0.95); color: white; padding: 25px 50px; border-radius: 15px; font-size: 22px; font-weight: bold; z-index: 99999; animation: fadeInOut 2s forwards; border: 2px solid #fff; }
    @keyframes fadeInOut { 0% { opacity: 0; transform: translate(-50%, -40%); } 15% { opacity: 1; transform: translate(-50%, -50%); } 85% { opacity: 1; transform: translate(-50%, -50%); } 100% { opacity: 0; transform: translate(-50%, -60%); } }
    
    /* 6. 요일 뱃지 (반 개설용) */
    .day-badge-single { padding: 8px 0; border-radius: 8px; color: #444; font-weight: 800; text-align: center; display: block; width: 100%; border: 1px solid rgba(0,0,0,0.05); font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# [함수] 구글 시트 및 유틸리티 (이 부분만 수정)
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
    # [수정] 429 에러(요청 과다) 방지를 위한 재시도 로직 강화
    max_retries = 7
    for i in range(max_retries):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if "429" in str(e): 
                time.sleep((1.5 ** i) + 1) # 대기 시간을 점차 늘림 (2초, 3초, 5초...)
                continue
            else: raise e
        except Exception as e:
            time.sleep(1)
            continue
    return func(*args, **kwargs)

# [수정] ttl=3 적용 (3초간 캐시 유지 -> 연속 클릭 시 API 호출 방지)
@st.cache_data(ttl=3)
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

def calc_duration_min(s, e):
    try:
        t1 = datetime.strptime(s, "%H:%M")
        t2 = datetime.strptime(e, "%H:%M")
        return (t2 - t1).seconds // 60
    except: return 0

def sort_time_strings(time_list):
    try: return sorted(list(set(time_list)), key=lambda x: datetime.strptime(x, "%H:%M"))
    except: return sorted(list(set(time_list)))

# HTML 달력 렌더링
def render_html_calendar(year, month, attendance_records):
    cal = calendar.Calendar(firstweekday=6) # 일요일 시작
    month_days = cal.monthdayscalendar(year, month)
    
    html = f"<div style='font-weight:bold; text-align:center; font-size:1.4rem; margin-bottom:15px; color:#333;'>📅 {year}년 {month}월 출석 현황</div>"
    html += "<table class='cal-table'><thead><tr>"
    for d in ["일", "월", "화", "수", "목", "금", "토"]:
        html += f"<th class='cal-th'>{d}</th>"
    html += "</tr></thead><tbody>"
    
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='background-color:#fafafa;'></td>"
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                content = f"<span class='cal-day-num'>{day}</span>"
                if date_str in attendance_records:
                    recs = attendance_records[date_str]
                    if not isinstance(recs, list): recs = [recs]
                    for rec in recs:
                        status = rec['status']
                        color = "bg-green"
                        if "지각" in status: color = "bg-red"
                        elif "결석" in status: color = "bg-gray"
                        elif "보강" in status: color = "bg-blue"
                        short_cls = rec['class_name'][:4] + ".." if len(rec['class_name']) > 4 else rec['class_name']
                        content += f"<span class='cal-badge {color}'>{status} ({short_cls})</span>"
                html += f"<td class='cal-td'>{content}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# QR 생성
def generate_styled_qr(data, student_name):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data); qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    top_p, bot_p = 60, 60
    canvas_w, canvas_h = qr_img.width + 40, qr_img.height + top_p + bot_p
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    canvas.paste(qr_img, ((canvas_w - qr_img.width) // 2, top_p))
    draw = ImageDraw.Draw(canvas)
    
    font_path = "font.ttf" if os.path.exists("font.ttf") else "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    try:
        fh = ImageFont.truetype(font_path, 30); fn = ImageFont.truetype(font_path, 35)
    except:
        fh = ImageFont.load_default(); fn = ImageFont.load_default()
        
    draw.text(((canvas_w - draw.textlength("형설지공 학원", font=fh)) / 2, 15), "형설지공 학원", fill="black", font=fh)
    draw.text(((canvas_w - draw.textlength(student_name, font=fn)) / 2, canvas_h - 50), student_name, fill="black", font=fn)
    return canvas

def decode_qr(image_input):
    try:
        if image_input is None: return None
        bytes_data = image_input.getvalue()
        img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        return data if data else None
    except: return None

# --- CRUD Functions ---
def add_data(sheet, data_dict):
    client = init_connection()
    ws = safe_api_call(client.open("Academy_DB").worksheet, sheet)
    if len(safe_api_call(ws.get_all_values)) == 0: safe_api_call(ws.append_row, list(data_dict.keys()))
    safe_api_call(ws.append_row, [str(v) for v in data_dict.values()]); clear_cache()

def add_data_bulk(sheet, data_list):
    if not data_list: return
    client = init_connection()
    ws = safe_api_call(client.open("Academy_DB").worksheet, sheet)
    if len(safe_api_call(ws.get_all_values)) == 0: safe_api_call(ws.append_row, list(data_list[0].keys()))
    safe_api_call(ws.append_rows, [list(d.values()) for d in data_list]); clear_cache()

def delete_data_all(sheet, target_dict):
    client = init_connection()
    ws = safe_api_call(client.open("Academy_DB").worksheet, sheet)
    data = safe_api_call(ws.get_all_records)
    rows = []
    for i, r in enumerate(data):
        if all(str(r.get(k)) == str(v) for k, v in target_dict.items()): rows.append(i+2)
    if rows:
        for r in sorted(rows, reverse=True): safe_api_call(ws.delete_rows, r)
        clear_cache(); return True
    return False

def update_data(sheet, t_col, t_val, new_dict):
    client = init_connection()
    ws = safe_api_call(client.open("Academy_DB").worksheet, sheet)
    data = safe_api_call(ws.get_all_records)
    for i, r in enumerate(data):
        if str(r.get(t_col)) == str(t_val):
            rn = i+2; head = safe_api_call(ws.row_values, 1)
            uv = [new_dict.get(c, r.get(c)) for c in head]
            safe_api_call(ws.update, f"A{rn}", [uv]); clear_cache(); return True
    return False

def get_col_data(df, col, idx):
    if col in df.columns: return df[col]
    elif len(df.columns) > idx: return df.iloc[:, idx]
    else: return pd.Series([])

# ==========================================
# [메뉴] 사이드바 구성
# ==========================================
with st.sidebar:
    # [수정] 학원 이름과 시스템 명칭을 상단에 배치
    st.title("🏫 형설지공 학원")
    st.markdown("# 🎓 통합 ERP 시스템")
    st.markdown("---")
    
    # 메뉴 스타일 유지 (줄바꿈 방지 등)
    menu = option_menu("메뉴 선택", 
        ["1. 강사 관리", "2. 학생 관리", "3. 반 관리", "4. 수강 배정", 
         "5. 출석 관리", "6. 상담 관리", "7. 강사별 시간표", "8. 강의실별 시간표", 
         "9. 학생 개인별 종합"], 
        icons=['person-video3', 'backpack', 'easel', 'journal-check', 
               'calendar-check', 'chat-dots', 'clock', 'building', 'card-checklist'],
        menu_icon="cast", default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#f0f2f6"},
            "icon": {"color": "orange", "font-size": "18px"}, 
            "nav-link": {
                "font-size": "15px", 
                "text-align": "left", 
                "margin":"0px", 
                "white-space": "nowrap", 
                "--hover-color": "#eee"
            },
            "nav-link-selected": {"background-color": "#02ab21"},
        }
    )
    st.markdown("---")
    st.caption("Developed by 형설지공 2026")

# ==========================================
# 1. 강사 관리 (안전장치 추가됨)
# ==========================================
if menu == "1. 강사 관리":
    st.subheader("👨‍🏫 강사 관리")
    tab1, tab2 = st.tabs(["➕ 신규 등록", "🔧 수정 및 삭제"])
    
    with tab1:
        with st.form("teacher_create_form"):
            name = st.text_input("이름")
            subject = st.text_input("담당 과목")
            phone = st.text_input("연락처")
            if st.form_submit_button("등록하기"):
                if not name: st.error("이름을 입력하세요.")
                else:
                    add_data('teachers', {'이름': name, '과목': subject, '연락처': phone})
                    show_center_message(f"{name} 선생님 등록 완료!")
                    st.rerun()

    with tab2:
        df_t = load_data('teachers')
        if not df_t.empty:
            t_names = get_col_data(df_t, '이름', 0).astype(str)
            t_options = t_names.tolist()
            idx = st.session_state.get('t_modify_idx', 0)
            if idx >= len(t_options): idx = 0
            
            selected_t = st.selectbox("수정할 선생님 선택", t_options, index=idx)
            if selected_t in t_options: st.session_state['t_modify_idx'] = t_options.index(selected_t)
            
            if selected_t:
                row = df_t[df_t[df_t.columns[0]] == selected_t].iloc[0]
                st.divider()
                st.markdown(f"##### 🔧 '{selected_t}' 선생님 정보 수정")
                
                # 안전장치를 위해 form 대신 직접 입력 사용
                n_name = st.text_input("이름", value=row.iloc[0], key="edit_t_n")
                n_sub = st.text_input("과목", value=row.iloc[1] if len(row)>1 else "", key="edit_t_s")
                n_ph = st.text_input("연락처", value=row.iloc[2] if len(row)>2 else "", key="edit_t_p")
                
                c1, c2 = st.columns(2)
                
                # [수정 안전장치]
                if c1.button("💾 수정 저장"):
                    st.session_state['confirm_action'] = 'update_teacher'
                
                if st.session_state.get('confirm_action') == 'update_teacher':
                    st.warning(f"⚠️ 정말로 '{selected_t}' 선생님 정보를 수정하시겠습니까?")
                    col_y, col_n = st.columns([1,1])
                    if col_y.button("네, 수정합니다", type="primary"):
                        update_data('teachers', '이름', selected_t, {'이름': n_name, '과목': n_sub, '연락처': n_ph})
                        st.session_state['confirm_action'] = None
                        show_center_message("수정 완료!")
                        time.sleep(1)
                        st.rerun()
                    if col_n.button("취소"):
                        st.session_state['confirm_action'] = None
                        st.rerun()

                # [삭제 안전장치]
                if c2.button("🗑️ 삭제하기"):
                    st.session_state['confirm_action'] = 'delete_teacher'
                
                if st.session_state.get('confirm_action') == 'delete_teacher':
                    st.error(f"⚠️ 경고: '{selected_t}' 선생님을 삭제하시겠습니까? (복구 불가)")
                    col_y, col_n = st.columns([1,1])
                    if col_y.button("네, 삭제합니다", type="primary"):
                        delete_data_all('teachers', {'이름': selected_t})
                        st.session_state['confirm_action'] = None
                        st.session_state['t_modify_idx'] = 0
                        show_center_message("삭제 완료!", icon="🗑️")
                        time.sleep(1)
                        st.rerun()
                    if col_n.button("취소"):
                        st.session_state['confirm_action'] = None
                        st.rerun()

# ==========================================
# 2. 학생 관리 (신규 등록 시 5칸 데이터 저장 & 정보 자동 갱신)
# ==========================================
elif menu == "2. 학생 관리":
    st.subheader("📝 학생 관리")
    t1, t2, t3, t4 = st.tabs(["📋 전체 학생 조회", "➕ 신규 등록", "🔧 수정/삭제", "📱 QR 발급/인쇄"])
    
    # 데이터 로드
    df_c, df_t, df_s = load_data('classes'), load_data('teachers'), load_data('students')
    all_subjects = sorted(get_col_data(df_t, '과목', 1).unique().tolist()) if not df_t.empty else []

    # [Tab 1] 전체 조회
    with t1:
        st.dataframe(df_s, use_container_width=True)

    # [Tab 2] 신규 등록
    with t2:
        if df_c.empty: st.warning("⚠️ 개설된 반이 없습니다.")
        st.markdown("##### 1️⃣ 기본 정보 입력")
        c1, c2 = st.columns(2)
        name = c1.text_input("이름", key="create_name")
        phone = c1.text_input("학생 폰", key="create_phone")
        p_phone = c1.text_input("부모님 폰", key="create_p_phone")
        grade = c2.selectbox("학년", ["초4","초5","초6","중1","중2","중3","고1","고2","고3"], key="create_grade")
        school = c2.text_input("학교", key="create_school")
        
        st.divider()
        st.markdown("##### 2️⃣ 수강 과목 및 반 선택")
        final_enroll_list = []
        for subj in all_subjects:
            if st.checkbox(f"📘 {subj} 수강", key=f"new_chk_{subj}"):
                sub_teachers = df_t[df_t.iloc[:, 1] == subj].iloc[:, 0].tolist()
                c_tea, c_cls = st.columns([1, 2])
                with c_tea:
                    sel_teas = st.multiselect(f"담당 선생님 ({subj})", sub_teachers, key=f"new_tea_{subj}")
                if sel_teas:
                    cls_options = []
                    cls_map = {}
                    for tea in sel_teas:
                        t_classes = df_c[df_c.iloc[:, 1].str.contains(tea)]
                        for _, r in t_classes.iterrows():
                            lbl = f"{r.iloc[0]} ({r.iloc[2]})"
                            cls_options.append(lbl)
                            cls_map[lbl] = {'반이름': r.iloc[0], '담당강사': r.iloc[1]}
                    with c_cls:
                        sel_cls_labels = st.multiselect(f"배정할 반 ({subj})", cls_options, key=f"new_cls_{subj}")
                        for lbl in sel_cls_labels:
                            info = cls_map[lbl]
                            # [핵심 수정] 5칸 구조에 맞춰서 '과목' 정보를 추가함
                            final_enroll_list.append({
                                '학생': name,
                                '과목': subj,
                                '반이름': info['반이름'],
                                '담당강사': info['담당강사'],
                                '날짜': str(datetime.today().date())
                            })
        
        if st.button("💾 학생 저장 및 수강 등록", type="primary"):
            if not name:
                st.error("이름을 입력해주세요.")
            else:
                nd = {'이름': name, '연락처': phone, '학부모연락처': p_phone, '학년': grade, '학교': school}
                add_data('students', nd)
                if final_enroll_list: add_data_bulk('enrollments', final_enroll_list)
                show_center_message(f"✅ {name} 등록 완료!")
                time.sleep(1.5); st.rerun()

    # [Tab 3] 수정/삭제
    with t3:
        if not df_s.empty:
            st.markdown("### 🔍 학생 검색 및 수정")
            k = st.text_input("이름 검색", key='s_search_edit')
            df_s['L'] = df_s.iloc[:,0] + " (" + df_s.iloc[:,3] + ")"
            f = df_s[df_s.iloc[:,0].str.contains(k)] if k else df_s
            
            s_ops = f['L'].tolist()
            s_sel = st.selectbox("학생 선택", s_ops)
            
            if s_sel:
                real_n = s_sel.split(' (')[0]
                row = df_s[df_s.iloc[:,0] == real_n].iloc[0]
                
                st.divider()
                st.markdown(f"##### 🔧 '{real_n}' 학생 정보 수정")
                
                sc1, sc2 = st.columns(2)
                u_nm = sc1.text_input("이름", value=row.iloc[0], key=f"u_sn_{real_n}")
                u_hp = sc1.text_input("학생 폰", value=row.iloc[1], key=f"u_sp_{real_n}")
                u_pp = sc1.text_input("부모 폰", value=row.iloc[2], key=f"u_spp_{real_n}")
                
                grs = ["초4","초5","초6","중1","중2","중3","고1","고2","고3"]
                cur_g = row.iloc[3]
                u_gr = sc2.selectbox("학년", grs, index=grs.index(cur_g) if cur_g in grs else 0, key=f"u_sg_{real_n}")
                u_sc = sc2.text_input("학교", value=row.iloc[4], key=f"u_ssc_{real_n}")

                bc1, bc2 = st.columns(2)
                
                if bc1.button("💾 수정 내용 저장"):
                    st.session_state['confirm_action'] = 'update_student'
                
                if st.session_state.get('confirm_action') == 'update_student':
                    st.warning(f"⚠️ '{real_n}' 학생의 정보를 수정하시겠습니까?")
                    col_y, col_n = st.columns([1,1])
                    if col_y.button("네, 수정합니다", type="primary"):
                        nd = {'이름': u_nm, '연락처': u_hp, '학부모연락처': u_pp, '학년': u_gr, '학교': u_sc}
                        update_data('students', '이름', real_n, nd)
                        st.session_state['confirm_action'] = None
                        show_center_message("수정 완료!")
                        time.sleep(1); st.rerun()
                    if col_n.button("취소"):
                        st.session_state['confirm_action'] = None
                        st.rerun()

                if bc2.button("🗑️ 학생 삭제 (복구 불가)", type="primary"):
                    st.session_state['confirm_action'] = 'delete_student'

                if st.session_state.get('confirm_action') == 'delete_student':
                    st.error(f"⚠️ 경고: '{real_n}' 학생을 삭제하면 수강 기록까지 모두 사라집니다.")
                    col_y, col_n = st.columns([1,1])
                    if col_y.button("네, 모두 삭제합니다", type="primary"):
                        delete_data_all('students', {'이름': real_n})
                        delete_data_all('enrollments', {'학생': real_n})
                        st.session_state['confirm_action'] = None
                        show_center_message("삭제 완료", icon="🗑️")
                        time.sleep(1); st.rerun()
                    if col_n.button("취소"):
                        st.session_state['confirm_action'] = None
                        st.rerun()

    # [Tab 4] QR 발급 및 인쇄
    with t4:
        st.markdown("### 📱 QR 코드 발급 및 인쇄")
        df = load_data('students')
        if not df.empty:
            s = st.selectbox("학생 선택", df.iloc[:,0], key='qr_sel_main')
            if s:
                row = df[df.iloc[:,0]==s].iloc[0]
                ph = str(row.iloc[1])[-4:] if len(row)>1 else "0000"
                img = generate_styled_qr(f"{s}/{ph}", s)
                c_qr1, c_qr2 = st.columns([1, 1.5])
                with c_qr1: st.image(img, caption=f"{s} 학생 QR", width=300)
                with c_qr2:
                    st.success(f"✅ **{s}** 학생의 QR코드가 생성되었습니다.")
                    st.markdown("**🖨️ 인쇄:** `Ctrl + P`를 눌러 인쇄하세요.")
                    st.divider()
                    buf = io.BytesIO(); img.save(buf, format="PNG"); byte_im = buf.getvalue()
                    st.download_button("💾 이미지 다운로드", data=byte_im, file_name=f"형설지공_{s}_QR.png", mime="image/png", type="primary")

# ==========================================
# 3. 반 관리 (안전장치 추가됨)
# ==========================================
elif menu == "3. 반 관리":
    st.subheader("📚 반 관리")
    tab1, tab2 = st.tabs(["➕ 반 개설", "🔧 반 정보 수정/삭제"])
    
    days = ["월", "화", "수", "목", "금", "토", "일"]
    day_colors = {"월":"#FFEBEE", "화":"#FFF3E0", "수":"#E8F5E9", "목":"#E3F2FD", "금":"#F3E5F5", "토":"#FAFAFA", "일":"#FFEBEE"}
    hours = [f"{i}시" for i in range(9, 23)]
    mins = ["00분", "10분", "20분", "30분", "40분", "50분"]
    rooms = ["기타", "101호", "102호", "103호", "104호"]

    with tab1:
        df_t = load_data('teachers')
        if df_t.empty: st.warning("선생님을 먼저 등록해주세요.")
        else:
            t_opts = (get_col_data(df_t, '이름', 0) + " (" + get_col_data(df_t, '과목', 1) + ")").tolist()
            c1, c2, c3 = st.columns([2, 1, 2])
            c_name = c1.text_input("반 이름", key="new_c_name")
            c_room = c2.selectbox("강의실", rooms, key="new_c_room")
            t_name = c3.selectbox("담당 선생님", t_opts, key="new_t_name")
            
            st.write("🕒 **요일 및 시간 설정**")
            schedule_data = {}
            for day in days:
                d_c1, d_c2, d_c3, d_c4, d_c5, d_c6 = st.columns([1, 2, 2, 0.5, 2, 2])
                with d_c1:
                    chk_col, badge_col = st.columns([0.3, 0.7])
                    with chk_col: is_chk = st.checkbox("", key=f"new_chk_{day}", label_visibility="collapsed")
                    with badge_col: st.markdown(f'<div class="day-badge-single" style="background-color:{day_colors[day]};">{day}</div>', unsafe_allow_html=True)
                with d_c2: sh = st.selectbox("시", hours, key=f"new_sh_{day}", label_visibility="collapsed", disabled=not is_chk)
                with d_c3: sm = st.selectbox("분", mins, key=f"new_sm_{day}", label_visibility="collapsed", disabled=not is_chk)
                with d_c4: st.write("~")
                with d_c5: eh = st.selectbox("시", hours, index=1, key=f"new_eh_{day}", label_visibility="collapsed", disabled=not is_chk)
                with d_c6: em = st.selectbox("분", mins, key=f"new_em_{day}", label_visibility="collapsed", disabled=not is_chk)
                if is_chk:
                    schedule_data[day] = f"{sh.replace('시',':')}{sm.replace('분','')}-{eh.replace('시',':')}{em.replace('분','')}"

            if st.button("반 만들기 (저장)", type="primary"):
                if not c_name: st.error("반 이름을 입력해주세요.")
                elif not schedule_data: st.error("요일을 최소 하나 이상 선택해주세요.")
                else:
                    final_sche = [f"{d} {t}" for d, t in schedule_data.items()]
                    add_data('classes', {'반이름': c_name, '선생님': t_name, '시간': ", ".join(final_sche), '강의실': c_room})
                    show_center_message(f"'{c_name}' 개설 완료!")
                    time.sleep(1); st.rerun()

    with tab2:
        df_c = load_data('classes')
        df_t = load_data('teachers')
        if df_c.empty: st.info("개설된 반이 없습니다.")
        else:
            t_opts = (get_col_data(df_t, '이름', 0) + " (" + get_col_data(df_t, '과목', 1) + ")").tolist() if not df_t.empty else []
            c_opts = df_c.iloc[:, 0].tolist()
            sel_c_name = st.selectbox("수정할 반 선택", c_opts)
            
            if sel_c_name:
                curr_row = df_c[df_c.iloc[:, 0] == sel_c_name].iloc[0]
                curr_teacher = str(curr_row.iloc[1])
                curr_schedule_str = str(curr_row.iloc[2])
                curr_room = str(curr_row.iloc[3]) if len(curr_row) > 3 else "기타"
                if curr_room not in rooms: curr_room = "기타"
                curr_sche_map = {}
                for p in curr_schedule_str.split(','):
                    kp = p.strip().split()
                    if len(kp)==2: curr_sche_map[kp[0]] = kp[1]

                st.divider()
                st.markdown(f"#### 🔧 '{sel_c_name}' 정보 수정")
                uc1, uc2, uc3 = st.columns([2, 1, 2])
                u_c_name = uc1.text_input("반 이름", value=sel_c_name, key=f"edit_n_{sel_c_name}")
                u_room = uc2.selectbox("강의실", rooms, index=rooms.index(curr_room), key=f"edit_r_{sel_c_name}")
                t_idx = t_opts.index(curr_teacher) if curr_teacher in t_opts else 0
                u_t_name = uc3.selectbox("담당 선생님", t_opts, index=t_idx, key=f"edit_t_{sel_c_name}")
                
                st.write("🕒 **시간 수정**")
                u_updated_sche = []
                for day in days:
                    has_d = day in curr_sche_map
                    sh_i, sm_i, eh_i, em_i = 0, 0, 0, 0
                    if has_d:
                        try:
                            s, e = curr_sche_map[day].split('-')
                            sh_i = hours.index(s.split(':')[0]+"시")
                            sm_i = mins.index(s.split(':')[1]+"분" if len(s.split(':')[1])==2 else "0"+s.split(':')[1]+"분")
                            eh_i = hours.index(e.split(':')[0]+"시")
                            em_i = mins.index(e.split(':')[1]+"분" if len(e.split(':')[1])==2 else "0"+e.split(':')[1]+"분")
                        except: pass
                    ud1, ud2, ud3, ud4, ud5, ud6 = st.columns([1, 2, 2, 0.5, 2, 2])
                    with ud1:
                        chk_col, badge_col = st.columns([0.3, 0.7])
                        with chk_col: u_chk = st.checkbox("", value=has_d, key=f"u_chk_{day}_{sel_c_name}", label_visibility="collapsed")
                        with badge_col: st.markdown(f'<div class="day-badge-single" style="background-color:{day_colors[day]};">{day}</div>', unsafe_allow_html=True)
                    with ud2: u_sh = st.selectbox("시", hours, index=sh_i, key=f"u_sh_{day}_{sel_c_name}", label_visibility="collapsed", disabled=not u_chk)
                    with ud3: u_sm = st.selectbox("분", mins, index=sm_i, key=f"u_sm_{day}_{sel_c_name}", label_visibility="collapsed", disabled=not u_chk)
                    with ud4: st.write("~")
                    with ud5: u_eh = st.selectbox("시", hours, index=eh_i, key=f"u_eh_{day}_{sel_c_name}", label_visibility="collapsed", disabled=not u_chk)
                    with ud6: u_em = st.selectbox("분", mins, index=em_i, key=f"u_em_{day}_{sel_c_name}", label_visibility="collapsed", disabled=not u_chk)
                    if u_chk:
                        st_t = f"{u_sh.replace('시',':')}{u_sm.replace('분','')}"
                        en_t = f"{u_eh.replace('시',':')}{u_em.replace('분','')}"
                        u_updated_sche.append(f"{day} {st_t}-{en_t}")
                
                st.divider()
                ub1, ub2 = st.columns(2)
                
                # [수정 안전장치]
                if ub1.button("💾 수정사항 저장", type="primary"):
                    st.session_state['confirm_action'] = 'update_class'
                
                if st.session_state.get('confirm_action') == 'update_class':
                    st.warning(f"⚠️ '{sel_c_name}' 반 정보를 수정하시겠습니까?")
                    col_y, col_n = st.columns([1,1])
                    if col_y.button("네, 수정합니다", type="primary"):
                        nd = {'반이름': u_c_name, '선생님': u_t_name, '시간': ", ".join(u_updated_sche), '강의실': u_room}
                        update_data('classes', '반이름', sel_c_name, nd)
                        st.session_state['confirm_action'] = None
                        show_center_message("수정 완료!")
                        time.sleep(1); st.rerun()
                    if col_n.button("취소"):
                        st.session_state['confirm_action'] = None
                        st.rerun()
                
                # [삭제 안전장치]
                if ub2.button("🗑️ 반 삭제"):
                    st.session_state['confirm_action'] = 'delete_class'
                
                if st.session_state.get('confirm_action') == 'delete_class':
                    st.error(f"⚠️ 경고: '{sel_c_name}' 반을 삭제하면 소속된 학생들의 수강 기록도 모두 삭제됩니다.")
                    col_y, col_n = st.columns([1,1])
                    if col_y.button("네, 삭제합니다", type="primary"):
                        delete_data_all('classes', {'반이름': sel_c_name})
                        delete_data_all('enrollments', {'반이름': sel_c_name})
                        st.session_state['confirm_action'] = None
                        show_center_message("삭제 완료!", icon="🗑️")
                        time.sleep(1); st.rerun()
                    if col_n.button("취소"):
                        st.session_state['confirm_action'] = None
                        st.rerun()

# ==========================================
# 4. 수강 배정 (5개 항목: 학생/과목/반이름/강사/날짜 저장 Ver)
# ==========================================
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정 관리")
    
    # 데이터 실시간 로드
    df_e = load_data('enrollments')
    df_s = load_data('students')
    df_t = load_data('teachers')
    df_c = load_data('classes')

    # 세션 상태 초기화
    if 'draft_enrolls' not in st.session_state:
        st.session_state.draft_enrolls = []
    if 'confirm_save_cart' not in st.session_state:
        st.session_state.confirm_save_cart = False
    if 'confirm_cancel_target' not in st.session_state:
        st.session_state.confirm_cancel_target = None

    tab1, tab2 = st.tabs(["📋 전체 수강 현황", "➕ 수강 신청 (장바구니)"])

    # [Tab 1] 전체 현황
    with tab1:
        if df_e.empty:
            st.info("현재 배정된 수강 내역이 없습니다.")
        else:
            # 5개 컬럼을 모두 보여줍니다.
            try:
                st.dataframe(df_e[['학생', '과목', '반이름', '담당강사', '날짜']], use_container_width=True)
            except:
                st.warning("구글 시트 헤더가 [학생, 과목, 반이름, 담당강사, 날짜] 순서인지 확인해주세요.")

    # [Tab 2] 장바구니 방식 배정
    with tab2:
        if df_s.empty or df_t.empty or df_c.empty:
            st.warning("학생, 강사, 반 데이터가 모두 있어야 배정이 가능합니다.")
        else:
            c_left, c_right = st.columns([1, 1.2])
            
            # --- [왼쪽] 학생 선택 및 수업 담기 ---
            with c_left:
                st.markdown("### 1️⃣ 학생 선택")
                df_s['L'] = df_s.iloc[:,0] + " (" + df_s.iloc[:,4] + ")" 
                s_list = df_s['L'].tolist()
                sel_student_label = st.selectbox("학생을 선택하세요", s_list, key="assign_sel_std")

                if sel_student_label:
                    real_name = sel_student_label.split(' (')[0]
                    s_info = df_s[df_s.iloc[:,0] == real_name].iloc[0]
                    st.success(f"👤 **{s_info.iloc[0]}** ({s_info.iloc[3]})")
                    
                    st.divider()
                    st.markdown("### 2️⃣ 수업 담기")
                    
                    all_subjects = sorted(get_col_data(df_t, '과목', 1).unique().tolist())
                    sel_subj = st.selectbox("과목 선택", ["(선택하세요)"] + all_subjects)
                    
                    if sel_subj != "(선택하세요)":
                        sub_teachers = df_t[df_t.iloc[:, 1] == sel_subj].iloc[:, 0].tolist()
                        if not sub_teachers:
                            st.error("해당 과목의 강사가 없습니다.")
                            sel_tea = None
                        else:
                            sel_tea = st.selectbox("강사 선택", ["(선택하세요)"] + sub_teachers)
                        
                        if sel_tea and sel_tea != "(선택하세요)":
                            t_classes = df_c[df_c.iloc[:, 1].str.contains(sel_tea)]
                            if t_classes.empty:
                                st.error("해당 강사의 개설된 반이 없습니다.")
                                sel_cls_full = None
                            else:
                                cls_opts = [f"{r.iloc[0]} ({r.iloc[2]})" for _, r in t_classes.iterrows()]
                                sel_cls_full = st.selectbox("반 선택", ["(선택하세요)"] + cls_opts)
                                
                                if sel_cls_full and sel_cls_full != "(선택하세요)":
                                    real_cls_name = sel_cls_full.split(' (')[0]
                                    if st.button("⬇️ 장바구니에 담기", type="primary"):
                                        # 중복 체크
                                        is_exist = False
                                        for item in st.session_state.draft_enrolls:
                                            # 과목까지 같아야 완전 중복으로 처리
                                            if item['학생'] == real_name and item['반이름'] == real_cls_name and item['과목'] == sel_subj:
                                                is_exist = True
                                        
                                        if not df_e.empty:
                                            try:
                                                # DB 중복 체크 (학생, 과목, 반이름 일치 여부)
                                                already = df_e[
                                                    (df_e.iloc[:,0]==real_name) & 
                                                    (df_e.iloc[:,1]==sel_subj) & 
                                                    (df_e.iloc[:,2]==real_cls_name)
                                                ]
                                                if not already.empty: is_exist = True
                                            except: pass

                                        if is_exist:
                                            st.warning("이미 담겼거나 수강 중인 수업입니다.")
                                        else:
                                            st.session_state.draft_enrolls.append({
                                                '학생': real_name,
                                                '과목': sel_subj, 
                                                '반이름': real_cls_name,
                                                '담당강사': sel_tea,
                                                '날짜': str(datetime.today().date())
                                            })
                                            st.rerun()

            # --- [오른쪽] 장바구니 확인 및 저장 ---
            with c_right:
                st.markdown(f"### 🛒 수강 신청 목록 ({len(st.session_state.draft_enrolls)}건)")
                
                if st.session_state.draft_enrolls:
                    for i, item in enumerate(st.session_state.draft_enrolls):
                        with st.container():
                            cc1, cc2 = st.columns([4, 1])
                            # 화면 표시: [과목] 반이름
                            cc1.markdown(f"**{item['학생']}** - :blue[[{item['과목']}]] {item['반이름']} ({item['담당강사']})")
                            if cc2.button("삭제", key=f"draft_del_{i}"):
                                del st.session_state.draft_enrolls[i]
                                st.rerun()
                    
                    st.divider()
                    
                    if not st.session_state.confirm_save_cart:
                        if st.button("💾 전체 저장하기 (배정 확정)", type="primary", use_container_width=True):
                            st.session_state.confirm_save_cart = True
                            st.rerun()
                    else:
                        st.warning(f"⚠️ 총 {len(st.session_state.draft_enrolls)}건의 수업을 배정하시겠습니까?")
                        col_y, col_n = st.columns([1, 1])
                        
                        if col_y.button("네, 저장합니다", type="primary", use_container_width=True):
                            # [핵심] 이제 '과목'을 포함해서 5개 항목을 저장합니다.
                            # 순서: 학생, 과목, 반이름, 담당강사, 날짜
                            add_data_bulk('enrollments', st.session_state.draft_enrolls)
                            st.session_state.draft_enrolls = []
                            st.session_state.confirm_save_cart = False
                            show_center_message("✅ 배정 완료!")
                            time.sleep(1.5); st.rerun()
                            
                        if col_n.button("취소", use_container_width=True):
                            st.session_state.confirm_save_cart = False
                            st.rerun()
                else:
                    st.info("왼쪽에서 수업을 선택하고 '담기'를 눌러주세요.")

                # [참고] 기존 수강 내역
                if sel_student_label:
                    st.markdown("---")
                    st.markdown("#### 📋 현재 수강 중인 수업")
                    real_name_curr = sel_student_label.split(' (')[0]
                    
                    if not df_e.empty:
                        try:
                            # 학생 이름 필터링 (0번 컬럼)
                            curr_list = df_e[df_e.iloc[:,0] == real_name_curr]
                            if not curr_list.empty:
                                for idx, row in curr_list.iterrows():
                                    # [중요] 컬럼 인덱스 변경됨
                                    # 0:학생, 1:과목, 2:반이름, 3:담당강사, 4:날짜
                                    subj_val = row.iloc[1]
                                    cls_val = row.iloc[2]
                                    tea_val = row.iloc[3]
                                    
                                    unique_key = f"{real_name_curr}_{cls_val}_{subj_val}"
                                    c1, c2 = st.columns([4, 1])
                                    c1.markdown(f"• :blue[[{subj_val}]] {cls_val} (담당: {tea_val})")
                                    
                                    if st.session_state.confirm_cancel_target != unique_key:
                                        if c2.button("취소", key=f"btn_cancel_{unique_key}"):
                                            st.session_state.confirm_cancel_target = unique_key
                                            st.rerun()
                                    else:
                                        with c2:
                                            st.markdown("**:red[삭제?]**")
                                            y_col, n_col = st.columns(2)
                                            if y_col.button("네", key=f"yes_{unique_key}"):
                                                # 삭제 시에도 반이름과 학생 이름으로 매칭
                                                delete_data_all('enrollments', {'학생': real_name_curr, '반이름': cls_val})
                                                st.session_state.confirm_cancel_target = None
                                                show_center_message("수강 취소 완료!")
                                                time.sleep(1); st.rerun()
                                            if n_col.button("아니오", key=f"no_{unique_key}"):
                                                st.session_state.confirm_cancel_target = None
                                                st.rerun()
                            else:
                                st.caption("현재 수강 중인 수업이 없습니다.")
                        except: st.caption("데이터 로드 중... (헤더를 확인해주세요)")
                    else:
                        st.caption("현재 수강 중인 수업이 없습니다.")

# ==========================================
# 5. 출석 체크 (Full Code 유지)
# ==========================================
elif menu == "5. 출석 체크":
    st.subheader("✅ 수동 출석 체크")
    df_e = load_data('enrollments')
    if not df_e.empty:
        td = st.date_input("날짜")
        cls = st.selectbox("반 선택", df_e.iloc[:,1].unique())
        stds = sorted(list(set(df_e[df_e.iloc[:,1] == cls].iloc[:,0].tolist())))
        with st.form("att_form"):
            st.write(f"**{cls}** 수강생 ({len(stds)}명)")
            res = {}; cols = st.columns(4)
            for i, s in enumerate(stds):
                with cols[i%4]: res[s] = "출석" if st.checkbox(s, value=True) else "결석"
            memo = st.text_input("특이사항")
            if st.form_submit_button("출석 저장"):
                for s, v in res.items():
                    add_data('attendance', {'날짜': str(td), '반이름': cls, '학생': s, '상태': v, '비고': memo})
                show_center_message("출석 저장 완료!")

# ==========================================
# 6. 데이터 통합 조회 (Full Code 유지)
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
# 7. 강사별 시간표 (5칸 데이터 구조 반영 수정)
# ==========================================
elif menu == "7. 강사별 시간표":
    st.subheader("📅 강사별 주간 시간표")
    df_c, df_t, df_e, df_s = load_data('classes'), load_data('teachers'), load_data('enrollments'), load_data('students')
    
    if not df_t.empty and not df_c.empty:
        t_names = get_col_data(df_t, '이름', 0); t_subs = get_col_data(df_t, '과목', 1)
        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        
        tabs = st.tabs([f"{n} ({s})" for n, s in zip(t_names, t_subs)])
        
        for idx, teacher_raw in enumerate(t_names):
            with tabs[idx]:
                my_classes = df_c[df_c.iloc[:,1].str.contains(teacher_raw)]
                local_times = set()
                if not my_classes.empty:
                    for _, row in my_classes.iterrows():
                        for tp in str(row.iloc[2]).split(','):
                            try: local_times.add(tp.split()[1].split('-')[0])
                            except: pass
                sorted_timeline = sort_time_strings(list(local_times))
                
                if not sorted_timeline: st.info("수업 없음")
                else:
                    cols = st.columns([0.5] + [1]*7)
                    cols[0].write("")
                    for i, d in enumerate(days_ko): cols[i+1].markdown(f"<div class='day-header'>{d}</div>", unsafe_allow_html=True)
                    
                    for start_t in sorted_timeline:
                        cols = st.columns([0.5] + [1]*7)
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
                            found_list = []
                            for _, row in my_classes.iterrows():
                                for tp in str(row.iloc[2]).split(','):
                                    if tp.strip().startswith(d):
                                        try:
                                            s, e = tp.split()[1].split('-')
                                            if s == start_t:
                                                found_list.append({
                                                    'sub': t_subs.iloc[idx], 
                                                    'name': row.iloc[0], 
                                                    'room': row.iloc[3], 
                                                    'time': tp.split()[1], 
                                                    'dur': calc_duration_min(s, e)
                                                })
                                        except: pass
                            
                            with cols[i+1]:
                                if found_list:
                                    sub_cols = st.columns(len(found_list))
                                    for si, found in enumerate(found_list):
                                        with sub_cols[si]:
                                            detail_info = []
                                            if not df_e.empty and not df_s.empty:
                                                # [수정] iloc[:,2]가 '반이름' 입니다. (0:학생, 1:과목, 2:반이름...)
                                                try:
                                                    target_col_idx = 2
                                                    std_names = df_e[df_e.iloc[:, target_col_idx] == found['name']].iloc[:,0].tolist()
                                                    matched_std = df_s[df_s.iloc[:,0].isin(std_names)]
                                                    for _, r in matched_std.iterrows():
                                                        detail_info.append(f"• {r.iloc[0]} ({r.iloc[3]}, {r.iloc[4]})")
                                                except: pass # 인덱스 에러 방지
                                            
                                            std_count = len(detail_info)
                                            
                                            st.markdown(f"""<div class='class-card'><div class='cc-subject'>{found['sub']}</div><div class='cc-name'>{found['name']}</div><div class='cc-info'>🏫 {found['room']}</div><div class='cc-time'>⏰ {found['time']}</div><div class='cc-duration'>⏳ {found['dur']}분</div></div>""", unsafe_allow_html=True)
                                            
                                            with st.popover(f"👥 {std_count}명", use_container_width=True):
                                                st.markdown(f"**{found['name']} 수강생 ({std_count}명)**")
                                                if detail_info:
                                                    for info in sorted(detail_info): st.markdown(info)
                                                else:
                                                    st.caption("수강생이 없습니다.")
                                else:
                                    st.markdown("<div class='empty-card'></div>", unsafe_allow_html=True)

# ==========================================
# 8. 강의실별 시간표 (5칸 데이터 구조 반영 수정)
# ==========================================
elif menu == "8. 강의실별 시간표":
    st.subheader("🏫 강의실 배정 현황")
    df_c, df_e, df_s = load_data('classes'), load_data('enrollments'), load_data('students')
    
    if not df_c.empty:
        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        d_tabs = st.tabs(days_ko)
        rooms = ["기타", "101호", "102호", "103호", "104호"]
        
        for idx, day in enumerate(days_ko):
            with d_tabs[idx]:
                day_times = set()
                day_classes = []
                for _, row in df_c.iterrows():
                    for tp in str(row.iloc[2]).split(','):
                        if tp.strip().startswith(day):
                            try:
                                t_range = tp.split()[1]
                                day_times.add(t_range.split('-')[0])
                                day_classes.append((row, t_range))
                            except: pass
                sorted_timeline = sort_time_strings(list(day_times))
                
                if not sorted_timeline: st.info("수업 없음")
                else:
                    cols = st.columns([0.3] + [1]*len(rooms))
                    cols[0].write("")
                    for i, r in enumerate(rooms): cols[i+1].markdown(f"<div class='day-header'>{r}</div>", unsafe_allow_html=True)
                    
                    for start_t in sorted_timeline:
                        cols = st.columns([0.3] + [1]*len(rooms))
                        max_end = start_t
                        for r_data, t_str in day_classes:
                            try:
                                s, e = t_str.split('-')
                                if s == start_t and e > max_end: max_end = e
                            except: pass
                        with cols[0]:
                            st.markdown(f"<div class='time-axis-card'><span class='tac-start'>{start_t}</span><span class='tac-tilde'>~</span><span class='tac-end'>{max_end}</span></div>", unsafe_allow_html=True)
                        
                        for i, r in enumerate(rooms):
                            found_list = []
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
                                            found_list.append({
                                                'sub': sub, 
                                                'name': r_data.iloc[0], 
                                                'tea': tn, 
                                                'time': t_str, 
                                                'dur': calc_duration_min(s, e)
                                            })
                                    except: pass
                            
                            with cols[i+1]:
                                if found_list:
                                    sub_cols = st.columns(len(found_list))
                                    for si, found in enumerate(found_list):
                                        with sub_cols[si]:
                                            detail_info = []
                                            if not df_e.empty and not df_s.empty:
                                                # [수정] iloc[:,2]가 '반이름' 입니다.
                                                try:
                                                    target_col_idx = 2
                                                    std_names = df_e[df_e.iloc[:, target_col_idx] == found['name']].iloc[:,0].tolist()
                                                    matched_std = df_s[df_s.iloc[:,0].isin(std_names)]
                                                    for _, r in matched_std.iterrows():
                                                        detail_info.append(f"• {r.iloc[0]} ({r.iloc[3]}, {r.iloc[4]})")
                                                except: pass

                                            std_count = len(detail_info)

                                            st.markdown(f"""<div class='class-card' style='border-left-color:#43A047;background-color:#E8F5E9;'><div class='cc-subject'>{found['sub']}</div><div class='cc-name'>{found['name']}</div><div class='cc-info'>👨‍🏫 {found['tea']}</div><div class='cc-time'>⏰ {found['time']}</div><div class='cc-duration'>⏳ {found['dur']}분</div></div>""", unsafe_allow_html=True)
                                            
                                            with st.popover(f"👥 {std_count}명", use_container_width=True):
                                                st.markdown(f"**{found['name']} 수강생 ({std_count}명)**")
                                                for info in sorted(detail_info): st.markdown(info)
                                else:
                                    st.markdown("<div class='empty-card'></div>", unsafe_allow_html=True)

# ==========================================
# 9. 학생 개인별 종합 (한 페이지 통합 & 리얼 달력 뷰)
# ==========================================
elif menu == "9. 학생 개인별 종합":
    import calendar  # 달력 기능을 위해 추가
    
    st.subheader("📊 학생 개인별 종합 기록부")
    
    # 데이터 로드
    df_s = load_data('students')
    df_e = load_data('enrollments')
    df_a = load_data('attendance')

    if df_s.empty:
        st.warning("등록된 학생이 없습니다.")
    else:
        # 1. 학생 선택
        df_s['L'] = df_s.iloc[:,0] + " (" + df_s.iloc[:,4] + ")"
        s_list = df_s['L'].tolist()
        s_sel = st.selectbox("학생을 선택하세요", s_list)
        
        if s_sel:
            real_name = s_sel.split(' (')[0]
            s_info = df_s[df_s.iloc[:,0] == real_name].iloc[0]
            
            st.divider()
            
            # 2. 프로필 섹션
            col_p1, col_p2 = st.columns([1, 4])
            with col_p1:
                qr_img = generate_styled_qr(f"{real_name}", real_name)
                st.image(qr_img, width=130)
            with col_p2:
                st.markdown(f"### **{s_info.iloc[0]}**")
                st.caption(f"🏫 {s_info.iloc[4]} ({s_info.iloc[3]}) | 📞 {s_info.iloc[1]}")
                st.caption(f"👪 학부모: {s_info.iloc[2]}")

            st.markdown("---")

            # 3. [구역 1] 수강 및 배정 현황
            st.markdown("##### 📘 수강 및 배정 현황")
            if not df_e.empty:
                try:
                    my_classes = df_e[df_e.iloc[:,0] == real_name]
                    if my_classes.empty:
                        st.info("현재 수강 중인 수업이 없습니다.")
                    else:
                        # 5칸 구조(학생, 과목, 반이름, 강사, 날짜) -> 필요한 3개만 추출
                        display_df = my_classes.iloc[:, [1, 2, 3]]
                        display_df.columns = ["수강 과목", "수강 반", "담당 선생님"]
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                except:
                    st.error("데이터 구조를 불러오는 중입니다.")
            else:
                st.info("수강 기록이 없습니다.")

            st.divider()

            # 4. [구역 2] 월별 출석 현황 (달력 뷰)
            
            # (1) 년/월 선택 네비게이션
            if 'view_year' not in st.session_state:
                st.session_state.view_year = datetime.today().year
                st.session_state.view_month = datetime.today().month

            c_nav1, c_nav2, c_nav3 = st.columns([1, 2, 1])
            with c_nav1:
                if st.button("◀ 이전 달", use_container_width=True):
                    st.session_state.view_month -= 1
                    if st.session_state.view_month == 0:
                        st.session_state.view_month = 12
                        st.session_state.view_year -= 1
                    st.rerun()
            with c_nav2:
                st.markdown(f"<h4 style='text-align: center; margin-top:5px;'>📅 {st.session_state.view_year}년 {st.session_state.view_month}월</h4>", unsafe_allow_html=True)
            with c_nav3:
                if st.button("다음 달 ▶", use_container_width=True):
                    st.session_state.view_month += 1
                    if st.session_state.view_month == 13:
                        st.session_state.view_month = 1
                        st.session_state.view_year += 1
                    st.rerun()

            # (2) 출석 데이터 매핑
            att_map = {} # { 날짜(int) : [상태리스트] }
            if not df_a.empty:
                try:
                    target_ym = f"{st.session_state.view_year}-{st.session_state.view_month:02d}"
                    # 학생 필터링
                    my_att = df_a[df_a.iloc[:,2] == real_name]
                    # 해당 월 필터링
                    month_data = my_att[my_att.iloc[:,0].astype(str).str.contains(target_ym)]
                    
                    for _, row in month_data.iterrows():
                        # 날짜에서 '일(day)'만 추출 (예: 2026-01-19 -> 19)
                        d_str = str(row.iloc[0])
                        day_int = int(d_str.split('-')[2])
                        status = row.iloc[3]
                        
                        if day_int not in att_map: att_map[day_int] = []
                        att_map[day_int].append(status)
                except: pass

            # (3) 달력 그리기
            # 요일 헤더
            d_cols = st.columns(7)
            days_ko = ["월", "화", "수", "목", "금", "토", "일"]
            for i, d in enumerate(days_ko):
                d_cols[i].markdown(f"<div style='text-align:center; color:gray; font-size:0.8rem;'>{d}</div>", unsafe_allow_html=True)
            
            # 날짜 채우기
            month_cal = calendar.monthcalendar(st.session_state.view_year, st.session_state.view_month)
            
            for week in month_cal:
                w_cols = st.columns(7)
                for i, day in enumerate(week):
                    with w_cols[i]:
                        if day == 0:
                            st.write("") # 빈 날짜
                        else:
                            # 날짜 표시
                            st.markdown(f"**{day}**")
                            
                            # 출석 상태 표시 (도장)
                            if day in att_map:
                                statuses = att_map[day]
                                for s in statuses:
                                    if s == '출석':
                                        st.markdown(f"<span style='color:green; font-size:0.8rem;'>🟢 출석</span>", unsafe_allow_html=True)
                                    elif s == '지각':
                                        st.markdown(f"<span style='color:orange; font-size:0.8rem;'>🟠 지각</span>", unsafe_allow_html=True)
                                    elif s == '결석':
                                        st.markdown(f"<span style='color:red; font-size:0.8rem;'>🔴 결석</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<br>", unsafe_allow_html=True) # 줄맞춤용 빈칸
            
            # (4) 간단 통계 (달력 아래)
            if att_map:
                st.markdown("---")
                # 전체 상태 리스트 평탄화
                all_statuses = [s for sublist in att_map.values() for s in sublist]
                c1, c2, c3 = st.columns(3)
                c1.metric("이달의 출석", f"{all_statuses.count('출석')}회")
                c2.metric("지각", f"{all_statuses.count('지각')}회")
                c3.metric("결석", f"{all_statuses.count('결석')}회")

# ==========================================
# 10. QR 키오스크
# ==========================================
elif menu == "10. QR 키오스크(출석)":
    st.empty(); st.markdown("""<style>.block-container{padding-top:2rem;} h1{text-align:center;color:#1565C0;}</style>""", unsafe_allow_html=True)
    st.title("📷 형설지공 학원 출석 키오스크"); st.write("카메라에 QR코드를 비춰주세요.")
    img_file_buffer = st.camera_input("QR 스캔", label_visibility="hidden")
    if img_file_buffer:
        decoded_text = decode_qr(img_file_buffer)
        if decoded_text:
            try:
                s_name, s_phone4 = decoded_text.split('/')
                df_s, df_e, df_c = load_data('students'), load_data('enrollments'), load_data('classes')
                student_row = df_s[df_s['이름'] == s_name]
                if student_row.empty: st.error("등록되지 않은 학생입니다.")
                else:
                    now = datetime.now(); today_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]; current_time_str = now.strftime("%H:%M")
                    my_classes = df_e[df_e.iloc[:,0] == s_name]; found_class_today = False
                    if not my_classes.empty:
                        for _, row in my_classes.iterrows():
                            c_name = row.iloc[1]; c_info = df_c[df_c.iloc[:,0] == c_name]
                            if not c_info.empty:
                                schedule_str = str(c_info.iloc[0, 2])
                                if today_weekday in schedule_str:
                                    for part in schedule_str.split(','):
                                        if part.strip().startswith(today_weekday):
                                            t_range = part.strip().split()[1]; start_time_str = t_range.split('-')[0]
                                            s_time = datetime.strptime(start_time_str, "%H:%M"); s_time = now.replace(hour=s_time.hour, minute=s_time.minute, second=0)
                                            status = "출석"; msg = f"{s_name} 학생, 환영합니다! (수업: {c_name})"; limit_time = s_time + timedelta(minutes=10)
                                            if now > limit_time: status = "지각"; msg = f"🚨 {s_name} 학생, 지각입니다! (수업: {c_name})"
                                            elif now < (s_time - timedelta(minutes=60)): status = "보강/자습"; msg = f"{s_name} 학생, 일찍 왔네요! 자습하세요."
                                            add_data('attendance', {'날짜': str(now.date()), '반이름': c_name, '학생': s_name, '상태': status, '비고': f"QR체크({current_time_str})"})
                                            if status == "지각": st.error(msg)
                                            else: st.success(msg)
                                            found_class_today = True; break
                    if not found_class_today:
                        st.info(f"{s_name} 학생, 오늘은 정규 수업이 없습니다."); 
                        if st.button("보강 출석 확인"): add_data('attendance', {'날짜': str(now.date()), '반이름': "보강/자습", '학생': s_name, '상태': "보강", '비고': f"QR체크({current_time_str})"}); st.success("보강 출석 처리되었습니다.")
            except: st.error("QR 오류")
        else: st.warning("QR 인식 실패")