import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import time
import qrcode
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont # 폰트 관련 모듈 추가
import io
import os

# ==========================================
# [기본 설정] 페이지 및 스타일
# ==========================================
st.set_page_config(page_title="형설지공 학원 ERP", page_icon="🏫", layout="wide")

st.markdown("""
<style>
    /* 1. 중앙 토스트 메시지 */
    .custom-alert {
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        background-color: rgba(46, 125, 50, 0.95); color: white; padding: 25px 50px;
        border-radius: 15px; font-size: 22px; font-weight: bold;
        z-index: 99999; box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        text-align: center; animation: fadeInOut 2s forwards;
        border: 2px solid #fff;
    }
    @keyframes fadeInOut { 0% { opacity: 0; transform: translate(-50%, -40%); } 15% { opacity: 1; transform: translate(-50%, -50%); } 85% { opacity: 1; transform: translate(-50%, -50%); } 100% { opacity: 0; transform: translate(-50%, -60%); } }
    
    /* 2. 수업 카드 스타일 */
    .class-card {
        background-color: #E3F2FD;
        border-left: 5px solid #1565C0;
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: transform 0.2s;
    }
    .class-card:hover { transform: scale(1.02); }
    
    .cc-subject { font-size: 0.8rem; color: #555; font-weight: bold; margin-bottom: 2px; }
    .cc-name { font-size: 1.05rem; color: #000; font-weight: 800; margin-bottom: 4px; line-height: 1.2; }
    .cc-info { font-size: 0.85rem; color: #333; margin-bottom: 2px; }
    .cc-time { font-size: 0.9rem; color: #1565C0; font-weight: 700; margin-top: 4px; }
    .cc-duration { font-size: 0.8rem; color: #E65100; font-weight: 600; margin-top: 2px; }

    /* 3. 빈 카드 (공강) 스타일 */
    .empty-card {
        background-color: #FAFAFA;
        border: 2px dashed #E0E0E0;
        border-radius: 8px;
        min-height: 140px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #BDBDBD;
        font-size: 0.9rem;
        margin-bottom: 5px;
    }

    /* 4. 좌측 시간축 카드 스타일 */
    .time-axis-card {
        background-color: #263238;
        color: white;
        border-radius: 8px;
        min-height: 140px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin-bottom: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        padding: 5px;
    }
    .tac-start { font-size: 1.1rem; font-weight: 800; color: #FFD54F; }
    .tac-tilde { font-size: 0.8rem; margin: 2px 0; color: #aaa; }
    .tac-end { font-size: 1.0rem; font-weight: 600; color: #fff; }

    /* 5. 요일 헤더 스타일 */
    .day-header {
        text-align: center;
        font-weight: 800;
        font-size: 1.1rem;
        padding: 10px 0;
        background-color: #f1f3f5;
        border-bottom: 2px solid #ddd;
        margin-bottom: 10px;
        border-radius: 5px;
        color: #333;
    }
    
    /* 6. 공통 UI 보정 */
    button[data-baseweb="tab"] > div { font-size: 1.1rem; font-weight: 600; }
    .day-badge-single {
        padding: 8px 0; border-radius: 8px; color: #444; font-weight: 800;
        text-align: center; display: block; width: 100%;
        border: 1px solid rgba(0,0,0,0.05); font-size: 0.9rem;
    }
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
            if "429" in str(e):
                time.sleep(2 ** i)
                continue
            else:
                raise e
    return func(*args, **kwargs)

@st.cache_data(ttl=0)
def load_data(sheet_name):
    try:
        client = init_connection()
        sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
        data = safe_api_call(sheet.get_all_records)
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def clear_cache():
    st.cache_data.clear()

def show_center_message(message, icon="✅"):
    placeholder = st.empty()
    placeholder.markdown(f'<div class="custom-alert"><span>{icon}</span> {message}</div>', unsafe_allow_html=True)
    time.sleep(1.2)
    placeholder.empty()

def calc_duration_min(start_time, end_time):
    try:
        t1 = datetime.strptime(start_time, "%H:%M")
        t2 = datetime.strptime(end_time, "%H:%M")
        diff = t2 - t1
        minutes = diff.seconds // 60
        return minutes
    except: return 0

def sort_time_strings(time_list):
    try:
        return sorted(list(set(time_list)), key=lambda x: datetime.strptime(x, "%H:%M"))
    except:
        return sorted(list(set(time_list)))

# [NEW] 디자인된 QR코드 생성 함수
def generate_styled_qr(data, student_name):
    # 1. QR 생성
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    
    # 2. 배경 캔버스 만들기 (QR보다 위아래 여백을 줌)
    top_padding = 60
    bottom_padding = 60
    canvas_w = qr_img.width + 40
    canvas_h = qr_img.height + top_padding + bottom_padding
    
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    
    # 3. QR 붙여넣기 (가운데 정렬)
    offset = ((canvas_w - qr_img.width) // 2, top_padding)
    canvas.paste(qr_img, offset)
    
    # 4. 텍스트 그리기
    draw = ImageDraw.Draw(canvas)
    
    # 폰트 로드 시도
    font_size_header = 30
    font_size_name = 35
    font_path = None
    
    # (1) 같은 폴더에 'font.ttf'가 있으면 최우선 사용 (GitHub 배포 시 유용)
    if os.path.exists("font.ttf"):
        font_path = "font.ttf"
    # (2) 맥OS 기본 한글 폰트
    elif os.path.exists("/System/Library/Fonts/Supplemental/AppleGothic.ttf"):
        font_path = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    # (3) 윈도우 기본 한글 폰트
    elif os.path.exists("C:/Windows/Fonts/malgun.ttf"):
        font_path = "C:/Windows/Fonts/malgun.ttf"
        
    try:
        if font_path:
            font_header = ImageFont.truetype(font_path, font_size_header)
            font_name = ImageFont.truetype(font_path, font_size_name)
        else:
            font_header = ImageFont.load_default()
            font_name = ImageFont.load_default()
    except:
        font_header = ImageFont.load_default()
        font_name = ImageFont.load_default()

    # 상단: 형설지공 학원
    text_header = "형설지공 학원"
    # 글자 크기 계산 (PIL 버전에 따라 다름, 최신버전 기준)
    try:
        bbox = draw.textbbox((0, 0), text_header, font=font_header)
        w_header = bbox[2] - bbox[0]
    except:
        w_header = draw.textlength(text_header, font=font_header)
        
    draw.text(((canvas_w - w_header) / 2, 15), text_header, fill="black", font=font_header)

    # 하단: 학생 이름
    text_name = student_name
    try:
        bbox = draw.textbbox((0, 0), text_name, font=font_name)
        w_name = bbox[2] - bbox[0]
    except:
        w_name = draw.textlength(text_name, font=font_name)
        
    draw.text(((canvas_w - w_name) / 2, canvas_h - 50), text_name, fill="black", font=font_name)
    
    return canvas

# [NEW] QR코드 디코딩 함수
def decode_qr(image_input):
    try:
        if image_input is None: return None
        bytes_data = image_input.getvalue()
        img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        if data: return data
    except Exception as e:
        pass
    return None

# --- CRUD 함수 ---
def add_data(sheet_name, new_data_dict):
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    if len(safe_api_call(sheet.get_all_values)) == 0:
        header = list(new_data_dict.keys())
        safe_api_call(sheet.append_row, header)
    row_values = [str(v) for v in new_data_dict.values()]
    safe_api_call(sheet.append_row, row_values)
    clear_cache()

def add_data_bulk(sheet_name, new_data_list):
    if not new_data_list: return
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    
    if len(safe_api_call(sheet.get_all_values)) == 0:
        header = list(new_data_list[0].keys())
        safe_api_call(sheet.append_row, header)
        
    rows_to_append = [list(d.values()) for d in new_data_list]
    if rows_to_append:
        safe_api_call(sheet.append_rows, rows_to_append)
        clear_cache()

def delete_data_all(sheet_name, target_dict):
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    data = safe_api_call(sheet.get_all_records)
    
    rows_to_delete = []
    for i, row in enumerate(data):
        match = True
        for key, value in target_dict.items():
            if str(row.get(key)) != str(value):
                match = False; break
        if match:
            rows_to_delete.append(i + 2)
    
    if rows_to_delete:
        for row_num in sorted(rows_to_delete, reverse=True):
            safe_api_call(sheet.delete_rows, row_num)
        clear_cache()
        return True
    return False

def update_data(sheet_name, target_col_name, target_val, new_data_dict):
    client = init_connection()
    sheet = safe_api_call(client.open("Academy_DB").worksheet, sheet_name)
    data = safe_api_call(sheet.get_all_records)
    for i, row in enumerate(data):
        if str(row.get(target_col_name)) == str(target_val):
            row_num = i + 2
            header = safe_api_call(sheet.row_values, 1)
            update_values = []
            for col_title in header:
                update_values.append(new_data_dict.get(col_title, row.get(col_title)))
            safe_api_call(sheet.update, f"A{row_num}", [update_values])
            clear_cache()
            return True
    return False

def get_col_data(df, col_name, fallback_index):
    if col_name in df.columns: return df[col_name]
    elif len(df.columns) > fallback_index: return df.iloc[:, fallback_index]
    else: return pd.Series([])

# ==========================================
# [메뉴] 사이드바 구성
# ==========================================
menu = st.sidebar.radio("메뉴 선택", 
    [
        "1. 강사 관리", 
        "2. 학생 관리", 
        "3. 반 관리", 
        "4. 수강 배정", 
        "5. 출석 체크", 
        "6. 데이터 통합 조회", 
        "7. 강사별 시간표", 
        "8. 강의실별 시간표", 
        "9. 학생 상세 분석",
        "10. QR 키오스크(출석)"
    ]
)

if menu != "10. QR 키오스크(출석)":
    st.title("🏫 형설지공 학원 통합 관리 시스템")

# ==========================================
# 1. 강사 관리
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
                with st.form("t_edit_form"):
                    n_name = st.text_input("이름", value=row.iloc[0])
                    n_sub = st.text_input("과목", value=row.iloc[1] if len(row)>1 else "")
                    n_ph = st.text_input("연락처", value=row.iloc[2] if len(row)>2 else "")
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("수정 저장"):
                        update_data('teachers', '이름', selected_t, {'이름': n_name, '과목': n_sub, '연락처': n_ph})
                        try: st.session_state['t_modify_idx'] = t_options.index(n_name)
                        except: st.session_state['t_modify_idx'] = 0
                        show_center_message("수정 완료!")
                        st.rerun()
                    if c2.form_submit_button("삭제하기"):
                        delete_data_all('teachers', {'이름': selected_t})
                        st.session_state['t_modify_idx'] = 0
                        show_center_message("삭제 완료!", icon="🗑️")
                        st.rerun()

# ==========================================
# 2. 학생 관리 (QR 발급 포함)
# ==========================================
elif menu == "2. 학생 관리":
    st.subheader("📝 학생 관리")
    tab1, tab2, tab3, tab4 = st.tabs(["📋 전체 학생 조회", "➕ 신규 등록", "🔧 수정/삭제", "📱 QR 발급"])
    
    df_c = load_data('classes')
    df_t = load_data('teachers')
    df_s = load_data('students')
    df_e = load_data('enrollments')

    all_subjects = sorted(get_col_data(df_t, '과목', 1).unique().tolist()) if not df_t.empty else []

    # [Tab 1] 전체 학생 리스트
    with tab1:
        if df_s.empty:
            st.info("등록된 학생이 없습니다.")
        else:
            try:
                display_cols = ['이름', '학년', '학교', '담당강사', '수강과목', '연락처', '학부모연락처']
                view_df = df_s[display_cols].copy()
                view_df.columns = ["이름", "학년", "학교", "담당 선생님", "수강 과목", "학생 연락처", "학부모 연락처"]
                view_df = view_df.reset_index(drop=True)

                def zebra_stripe(row):
                    if row.name % 2 == 0: color = '#E3F2FD'
                    else: color = '#F9F9F9'
                    return [f'background-color: {color}; color: black;'] * len(row)

                st.dataframe(view_df.style.apply(zebra_stripe, axis=1), use_container_width=True, hide_index=True, height=600)
            except KeyError:
                st.dataframe(df_s)

    # [Tab 2] 신규 등록
    with tab2:
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
        final_subjects = set()
        final_teachers = set()

        if not all_subjects: st.warning("등록된 과목이 없습니다.")

        for subj in all_subjects:
            is_taking = st.checkbox(f"📘 {subj} 수강", key=f"new_chk_{subj}")
            
            if is_taking:
                final_subjects.add(subj)
                sub_teachers = df_t[df_t.iloc[:, 1] == subj].iloc[:, 0].tolist()
                
                c_tea, c_cls = st.columns([1, 2])
                with c_tea:
                    sel_teas = st.multiselect(f"담당 선생님 ({subj})", sub_teachers, key=f"new_tea_{subj}")
                    for t in sel_teas: final_teachers.add(t)
                
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
                            final_enroll_list.append({
                                '학생': name,
                                '반이름': info['반이름'],
                                '담당강사': info['담당강사'],
                                '날짜': str(datetime.today().date())
                            })
                else:
                    with c_cls: st.write("👈 선생님을 먼저 선택하세요.")
                st.markdown("---")

        if st.button("💾 학생 저장 및 수강 등록", type="primary"):
            if not name:
                st.error("이름을 입력해주세요.")
            else:
                nd = {
                    '이름': name, 
                    '연락처': phone, 
                    '학부모연락처': p_phone, 
                    '학년': grade, 
                    '학교': school, 
                    '수강과목': ", ".join(sorted(list(final_subjects))), 
                    '담당강사': ", ".join(sorted(list(final_teachers)))
                }
                add_data('students', nd)
                if final_enroll_list: add_data_bulk('enrollments', final_enroll_list)
                show_center_message(f"✅ {name} 등록 완료!")
                time.sleep(1.5)
                st.rerun()

    # [Tab 3] 수정 및 삭제
    with tab3:
        if not df_s.empty:
            st.markdown("### 🔍 학생 검색 및 선택")
            search_k = st.text_input("이름 검색", key='s_search_edit', placeholder="이름 입력")
            
            # 동명이인 식별용 라벨
            df_s['display_label'] = df_s.apply(lambda x: f"{x['이름']} ({x['학년']})", axis=1)
            
            filtered_df = df_s[df_s['이름'].str.contains(search_k)] if search_k else df_s
            
            if filtered_df.empty:
                st.warning("검색 결과가 없습니다.")
            else:
                s_options = filtered_df['display_label'].tolist()
                idx = st.session_state.get('s_mod_idx', 0)
                if idx >= len(s_options): idx = 0
                
                target_display = st.selectbox("수정할 학생 선택", s_options, index=idx)
                if target_display in s_options:
                    st.session_state['s_mod_idx'] = s_options.index(target_display)
                
                target_real_name = target_display.split(' (')[0]
                row = filtered_df[filtered_df['display_label'] == target_display].iloc[0]
                
                def gv(i): return row.iloc[i] if len(row) > i else ""
                
                st.divider()
                st.markdown(f"##### 🔧 '{target_display}' 정보 수정")
                base_key = f"{target_display}" 
                
                c1, c2 = st.columns(2)
                nn = c1.text_input("이름", value=gv(0), key=f"edit_name_{base_key}")
                np = c1.text_input("학생 폰", value=gv(1), key=f"edit_phone_{base_key}")
                npp = c1.text_input("부모 폰", value=gv(2), key=f"edit_pphone_{base_key}")
                
                grs = ["초4","초5","초6","중1","중2","중3","고1","고2","고3"]
                cur_g = gv(3)
                ngr = c2.selectbox("학년", grs, index=grs.index(cur_g) if cur_g in grs else 0, key=f"edit_grade_{base_key}")
                ns = c2.text_input("학교", value=gv(4), key=f"edit_school_{base_key}")

                my_enrolls = df_e[df_e.iloc[:, 0] == target_real_name] if not df_e.empty else pd.DataFrame()
                
                active_subjects = set()
                active_teachers_map = {}
                active_classes_map = {}
                
                if not my_enrolls.empty:
                    current_class_names = my_enrolls.iloc[:, 1].tolist()
                    for cn in current_class_names:
                        c_row = df_c[df_c.iloc[:, 0] == cn]
                        if not c_row.empty:
                            r = c_row.iloc[0]
                            full_tea = r.iloc[1]
                            if "(" in full_tea:
                                t_real = full_tea.split('(')[0].strip()
                                sub_real = full_tea.split('(')[1].replace(')', '').strip()
                            else:
                                t_real = full_tea
                                sub_real = "기타"
                            
                            active_subjects.add(sub_real)
                            if sub_real not in active_teachers_map: active_teachers_map[sub_real] = set()
                            active_teachers_map[sub_real].add(t_real)
                            if sub_real not in active_classes_map: active_classes_map[sub_real] = []
                            active_classes_map[sub_real].append(f"{cn} ({r.iloc[2]})")

                st.markdown("##### 📚 수강 과목 및 반 수정")
                
                edit_final_enroll_list = []
                edit_final_subjects = set()
                edit_final_teachers = set()

                for subj in all_subjects:
                    is_active = subj in active_subjects
                    is_checked = st.checkbox(f"📘 {subj}", value=is_active, key=f"edit_chk_{subj}_{base_key}")
                    
                    if is_checked:
                        edit_final_subjects.add(subj)
                        sub_teachers = df_t[df_t.iloc[:, 1] == subj].iloc[:, 0].tolist()
                        
                        def_teas = list(active_teachers_map.get(subj, set()))
                        def_teas = [t for t in def_teas if t in sub_teachers]
                        
                        c_tea, c_cls = st.columns([1, 2])
                        with c_tea:
                            sel_teas = st.multiselect(f"담당 선생님 ({subj})", sub_teachers, default=def_teas, key=f"edit_tea_{subj}_{base_key}")
                            for t in sel_teas: edit_final_teachers.add(t)

                        if sel_teas:
                            cls_options = []
                            cls_map = {}
                            for tea in sel_teas:
                                t_classes = df_c[df_c.iloc[:, 1].str.contains(tea)]
                                for _, r in t_classes.iterrows():
                                    lbl = f"{r.iloc[0]} ({r.iloc[2]})"
                                    cls_options.append(lbl)
                                    cls_map[lbl] = {'반이름': r.iloc[0], '담당강사': r.iloc[1]}
                            
                            def_cls = active_classes_map.get(subj, [])
                            def_cls = [c for c in def_cls if c in cls_options]

                            with c_cls:
                                sel_cls_labels = st.multiselect(f"배정할 반 ({subj})", cls_options, default=def_cls, key=f"edit_cls_{subj}_{base_key}")
                                for lbl in sel_cls_labels:
                                    info = cls_map[lbl]
                                    edit_final_enroll_list.append({
                                        '학생': nn,
                                        '반이름': info['반이름'],
                                        '담당강사': info['담당강사'],
                                        '날짜': str(datetime.today().date())
                                    })

                st.divider()
                c_btn1, c_btn2 = st.columns(2)
                
                if c_btn1.button("💾 수정사항 저장"):
                    st.session_state['confirm_action'] = 'update'
                    st.session_state['confirm_target'] = target_display
                
                if c_btn2.button("🗑️ 학생 삭제", type="primary"):
                    st.session_state['confirm_action'] = 'delete'
                    st.session_state['confirm_target'] = target_display

                if st.session_state.get('confirm_action') and st.session_state.get('confirm_target') == target_display:
                    action = st.session_state['confirm_action']
                    
                    if action == 'update':
                        st.warning(f"⚠️ 정말로 '{target_display}' 학생 정보를 수정하시겠습니까?")
                        if st.button("✅ 네, 수정합니다 (최종)"):
                            nd = {
                                '이름': nn, '연락처': np, '학부모연락처': npp, 
                                '학년': ngr, '학교': ns, 
                                '수강과목': ", ".join(sorted(list(edit_final_subjects))), 
                                '담당강사': ", ".join(sorted(list(edit_final_teachers)))
                            }
                            update_data('students', '이름', target_real_name, nd)
                            delete_data_all('enrollments', {'학생': target_real_name})
                            if edit_final_enroll_list: add_data_bulk('enrollments', edit_final_enroll_list)
                            
                            st.session_state['confirm_action'] = None
                            show_center_message("수정 완료!")
                            time.sleep(1.5)
                            st.rerun()

                    elif action == 'delete':
                        st.error(f"⚠️ 경고: 정말로 '{target_display}' 학생을 삭제하시겠습니까? (수강 기록도 모두 삭제됨)")
                        if st.button("🟥 네, 삭제합니다 (최종)"):
                            delete_data_all('students', {'이름': target_real_name})
                            delete_data_all('enrollments', {'학생': target_real_name})
                            st.session_state['confirm_action'] = None
                            st.session_state['s_mod_idx'] = 0
                            show_center_message("삭제 완료!", icon="🗑️")
                            time.sleep(1.5)
                            st.rerun()

    # [Tab 4] QR 발급
    with tab4:
        st.markdown("### 📱 학생 QR 코드 발급")
        if df_s.empty:
            st.warning("등록된 학생이 없습니다.")
        else:
            search_qr = st.text_input("학생 검색 (이름)", key="qr_k")
            df_s['L'] = df_s['이름'] + " (" + df_s['학년'] + ")"
            filtered_qr = df_s[df_s['이름'].str.contains(search_qr)] if search_qr else df_s
            
            sel_qr_std = st.selectbox("QR 발급할 학생 선택", filtered_qr['L'].tolist(), key="qr_sel")
            
            if sel_qr_std:
                real_name = sel_qr_std.split(' (')[0]
                row = df_s[df_s['이름'] == real_name].iloc[0]
                
                # QR 데이터: 이름/전화번호뒷자리
                phone_last4 = str(row['연락처'])[-4:] if str(row['연락처']) else "0000"
                qr_data = f"{real_name}/{phone_last4}"
                
                st.info(f"데이터: {qr_data}")
                
                # [수정] 디자인된 QR 생성 함수 호출
                img = generate_styled_qr(qr_data, real_name)
                
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(img, caption=f"{real_name} 학생 출석 QR", width=200)
                with c2:
                    st.success("✅ '형설지공 학원' 전용 QR이 생성되었습니다.")
                    st.write("이 이미지를 캡처해서 학생이나 학부모님께 보내주세요.")

# ==========================================
# 3. 반 관리
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
        if df_t.empty: st.warning("선생님 등록 필요")
        else:
            t_opts = (get_col_data(df_t, '이름', 0) + " (" + get_col_data(df_t, '과목', 1) + ")").tolist()
            
            st.info("📝 **반 정보 입력**")
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

            st.divider()
            if st.button("반 만들기 (저장)", type="primary"):
                if not c_name: st.error("반 이름을 입력해주세요.")
                elif not schedule_data: st.error("요일을 최소 하나 이상 선택해주세요.")
                else:
                    final_sche = [f"{d} {t}" for d, t in schedule_data.items()]
                    add_data('classes', {'반이름': c_name, '선생님': t_name, '시간': ", ".join(final_sche), '강의실': c_room})
                    show_center_message(f"'{c_name}' 개설 완료!")
                    time.sleep(1)
                    st.rerun()

    with tab2:
        df_c = load_data('classes')
        df_t = load_data('teachers')
        if df_c.empty: st.info("개설된 반 없음")
        else:
            t_opts = (get_col_data(df_t, '이름', 0) + " (" + get_col_data(df_t, '과목', 1) + ")").tolist()
            if 'edit_t_idx' not in st.session_state: st.session_state['edit_t_idx'] = 0
            
            f_t = st.selectbox("1️⃣ 선생님 선택", t_opts, index=st.session_state['edit_t_idx'])
            if f_t in t_opts: st.session_state['edit_t_idx'] = t_opts.index(f_t)

            if f_t:
                ct = get_col_data(df_c, '선생님', 1).astype(str)
                f_c = df_c[ct == f_t]
                if f_c.empty: st.warning("담당 반이 없습니다.")
                else:
                    c_opts = (get_col_data(f_c, '반이름', 0) + " (" + get_col_data(f_c, '강의실', 3).astype(str) + ")").tolist()
                    if 'edit_c_idx' not in st.session_state: st.session_state['edit_c_idx'] = 0
                    
                    sel_c_label = st.selectbox("2️⃣ 반 선택", c_opts, index=st.session_state['edit_c_idx'])
                    if sel_c_label in c_opts: st.session_state['edit_c_idx'] = c_opts.index(sel_c_label)
                    
                    if sel_c_label:
                        curr = f_c.iloc[st.session_state['edit_c_idx']]
                        real_c_name = curr.iloc[0]
                        def_room = str(curr.iloc[3]) if len(curr)>3 else "기타"
                        if def_room not in rooms: def_room = "기타"
                        curr_sche_map = {}
                        for p in str(curr.iloc[2]).split(','):
                            kp = p.strip().split()
                            if len(kp)==2: curr_sche_map[kp[0]] = kp[1]

                        st.divider()
                        st.markdown(f"#### 🔧 '{real_c_name}' 수정")
                        
                        uc1, uc2, uc3 = st.columns([2, 1, 2])
                        u_c_name = uc1.text_input("반 이름", value=real_c_name, key=f"edit_n_{real_c_name}")
                        u_room = uc2.selectbox("강의실", rooms, index=rooms.index(def_room), key=f"edit_r_{real_c_name}")
                        u_t_name = uc3.selectbox("선생님", t_opts, index=t_opts.index(f_t), key=f"edit_t_{real_c_name}")
                        
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
                                with chk_col: u_chk = st.checkbox("", value=has_d, key=f"u_chk_{day}_{real_c_name}", label_visibility="collapsed")
                                with badge_col: st.markdown(f'<div class="day-badge-single" style="background-color:{day_colors[day]};">{day}</div>', unsafe_allow_html=True)
                            
                            with ud2: u_sh = st.selectbox("시", hours, index=sh_i, key=f"u_sh_{day}_{real_c_name}", label_visibility="collapsed", disabled=not u_chk)
                            with ud3: u_sm = st.selectbox("분", mins, index=sm_i, key=f"u_sm_{day}_{real_c_name}", label_visibility="collapsed", disabled=not u_chk)
                            with ud4: st.write("~")
                            with ud5: u_eh = st.selectbox("시", hours, index=eh_i, key=f"u_eh_{day}_{real_c_name}", label_visibility="collapsed", disabled=not u_chk)
                            with ud6: u_em = st.selectbox("분", mins, index=em_i, key=f"u_em_{day}_{real_c_name}", label_visibility="collapsed", disabled=not u_chk)
                            
                            if u_chk:
                                st_t = f"{u_sh.replace('시',':')}{u_sm.replace('분','')}"
                                en_t = f"{u_eh.replace('시',':')}{u_em.replace('분','')}"
                                u_updated_sche.append(f"{day} {st_t}-{en_t}")
                        
                        st.divider()
                        ub1, ub2 = st.columns(2)
                        if ub1.button("수정 저장", type="primary"):
                            nd = {'반이름': u_c_name, '선생님': u_t_name, '시간': ", ".join(u_updated_sche), '강의실': u_room}
                            update_data('classes', '반이름', real_c_name, nd)
                            show_center_message("수정 완료!")
                            time.sleep(1)
                            st.rerun()
                        if ub2.button("삭제하기"):
                            delete_data_all('classes', {'반이름': real_c_name})
                            delete_data_all('enrollments', {'반이름': real_c_name})
                            st.session_state['edit_c_idx'] = 0
                            show_center_message("삭제 완료!", icon="🗑️")
                            time.sleep(1)
                            st.rerun()

# ==========================================
# 4. 수강 배정
# ==========================================
elif menu == "4. 수강 배정":
    st.subheader("🔗 수강 배정 현황")
    tab1, tab2 = st.tabs(["📋 전체 수강 현황", "➕ 개별 관리"])
    
    df_s = load_data('students')
    df_c = load_data('classes')
    df_e = load_data('enrollments')

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
    st.subheader("✅ 출석 체크 (수동)")
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
# 7. 강사별 시간표
# ==========================================
elif menu == "7. 강사별 시간표":
    st.subheader("📅 강사별 주간 시간표")
    df_c, df_t, df_e = load_data('classes'), load_data('teachers'), load_data('enrollments')
    
    if not df_t.empty and not df_c.empty:
        t_names = get_col_data(df_t, '이름', 0)
        t_subs = get_col_data(df_t, '과목', 1)
        teachers_raw = t_names.tolist()
        days_ko = ["월", "화", "수", "목", "금", "토", "일"]
        
        tabs = st.tabs([f"{n} ({s})" for n, s in zip(t_names, t_subs)])
        
        for idx, teacher_raw in enumerate(teachers_raw):
            with tabs[idx]:
                my_classes = df_c[df_c.iloc[:,1].str.contains(teacher_raw)]
                local_times = set()
                if not my_classes.empty:
                    for _, row in my_classes.iterrows():
                        for tp in str(row.iloc[2]).split(','):
                            try: local_times.add(tp.split()[1].split('-')[0])
                            except: pass
                sorted_timeline = sort_time_strings(list(local_times))
                
                if not sorted_timeline:
                    st.info("등록된 수업이 없습니다.")
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
# 8. 강의실별 시간표
# ==========================================
elif menu == "8. 강의실별 시간표":
    st.subheader("🏫 강의실 배정 현황")
    df_c, df_e = load_data('classes'), load_data('enrollments')
    
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

# ==========================================
# 10. QR 키오스크 (출석)
# ==========================================
elif menu == "10. QR 키오스크(출석)":
    st.empty() # 상단 여백 제거
    st.markdown("""<style>.block-container{padding-top:2rem;} h1{text-align:center;color:#1565C0;}</style>""", unsafe_allow_html=True)
    
    st.title("📷 형설지공 학원 출석 키오스크")
    st.write("카메라에 QR코드를 비춰주세요.")
    
    img_file_buffer = st.camera_input("QR 스캔", label_visibility="hidden")
    
    if img_file_buffer:
        decoded_text = decode_qr(img_file_buffer)
        if decoded_text:
            try:
                s_name, s_phone4 = decoded_text.split('/')
                
                df_s = load_data('students')
                df_e = load_data('enrollments')
                df_c = load_data('classes')
                
                student_row = df_s[df_s['이름'] == s_name]
                if student_row.empty: st.error("등록되지 않은 학생입니다.")
                else:
                    now = datetime.now()
                    today_weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
                    current_time_str = now.strftime("%H:%M")
                    
                    my_classes = df_e[df_e.iloc[:,0] == s_name]
                    found_class_today = False
                    
                    if not my_classes.empty:
                        for _, row in my_classes.iterrows():
                            c_name = row.iloc[1]
                            c_info = df_c[df_c.iloc[:,0] == c_name]
                            if not c_info.empty:
                                schedule_str = str(c_info.iloc[0, 2])
                                if today_weekday in schedule_str:
                                    for part in schedule_str.split(','):
                                        if part.strip().startswith(today_weekday):
                                            t_range = part.strip().split()[1]
                                            start_time_str = t_range.split('-')[0]
                                            
                                            s_time = datetime.strptime(start_time_str, "%H:%M")
                                            s_time = now.replace(hour=s_time.hour, minute=s_time.minute, second=0)
                                            
                                            status = "출석"
                                            msg = f"{s_name} 학생, 환영합니다! (수업: {c_name})"
                                            limit_time = s_time + timedelta(minutes=10)
                                            
                                            if now > limit_time:
                                                status = "지각"
                                                msg = f"🚨 {s_name} 학생, 지각입니다! (수업: {c_name})"
                                            elif now < (s_time - timedelta(minutes=60)):
                                                 status = "보강/자습"
                                                 msg = f"{s_name} 학생, 일찍 왔네요! 자습하세요."
                                            
                                            add_data('attendance', {'날짜': str(now.date()), '반이름': c_name, '학생': s_name, '상태': status, '비고': f"QR체크({current_time_str})"})
                                            
                                            if status == "지각": st.error(msg)
                                            else: st.success(msg)
                                            found_class_today = True; break
                    
                    if not found_class_today:
                        st.info(f"{s_name} 학생, 오늘은 정규 수업이 없습니다.")
                        if st.button("보강 출석 확인"):
                            add_data('attendance', {'날짜': str(now.date()), '반이름': "보강/자습", '학생': s_name, '상태': "보강", '비고': f"QR체크({current_time_str})"})
                            st.success("보강 출석 처리되었습니다.")

            except Exception as e: st.error(f"QR 코드 오류 ({e})")
        else:
            st.warning("QR 코드가 인식되지 않았습니다.")