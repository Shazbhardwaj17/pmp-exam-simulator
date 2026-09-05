import streamlit as st
import pandas as pd
import psycopg2
import re
import hashlib
import time
import json
import streamlit.components.v1 as components
from supabase import create_client, Client # NEW IMPORT

# --- 1. PAGE CONFIG & CORE CSS ---
st.set_page_config(page_title="PMP Simulator Elite", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif !important; 
        background-color: #F9FAFB !important; 
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    div[data-testid="stButton"] button, a[data-testid="stLinkButton"] { border-radius: 6px !important; font-weight: 600 !important; transition: all 0.2s; text-decoration: none !important; }
    div[data-testid="stButton"] button[kind="primary"], a[data-testid="stLinkButton"] { background-color: #2563EB !important; color: white !important; border: none !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover, a[data-testid="stLinkButton"]:hover { background-color: #1D4ED8 !important; }
    
    .course-card { background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 24px; height: 100%; transition: transform 0.2s; margin-bottom: 15px; }
    .course-card:hover { transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    
    div[role="radiogroup"] > label, div[data-testid="stCheckbox"] {
        border: 1px solid #D1D5DB !important;
        border-radius: 8px !important;
        padding: 14px 16px !important;
        margin-bottom: 12px !important;
        background-color: #FFFFFF !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    
    div[role="radiogroup"] > label:hover, div[data-testid="stCheckbox"]:hover {
        border-color: #9CA3AF !important;
        background-color: #F9FAFB !important;
    }
    
    .stRadio label p, .stCheckbox label p, .stRadio span, .stCheckbox span { 
        font-size: 15px !important; 
        font-weight: 400 !important; 
        color: #111827 !important; 
        line-height: 1.5 !important;
    }
    
    .pass-rule { font-size: 13px; margin-bottom: 4px; }
    .rule-pass { color: #10B981; font-weight: 600; }
    .rule-fail { color: #6B7280; }
    .pmp-report { background: white; padding: 30px; border-radius: 8px; border: 1px solid #E5E7EB; margin-top: 20px; }
    .pmp-grade { font-size: 24px; font-weight: 700; }
    .grade-pass { color: #10B981; }
    .grade-fail { color: #EF4444; }
    .domain-row { display: flex; align-items: center; margin-bottom: 15px; }
    .domain-name { width: 200px; font-weight: 600; color: #374151; }
    .domain-bar-bg { flex-grow: 1; background: #F3F4F6; height: 24px; border-radius: 12px; overflow: hidden; display: flex; position: relative; }
    .domain-marker { position: absolute; height: 100%; border-right: 2px solid white; }
    .block-container { padding-top: 2rem !important; }
@media (max-width: 768px) {
        .block-container { padding-top: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
        .course-card { padding: 16px; margin-bottom: 12px; }
        h1 { font-size: 24px !important; margin-bottom: 20px !important; }
        h3 { font-size: 18px !important; }
        h4 { font-size: 16px !important; }
        .pmp-report { padding: 15px; }
        .domain-row { flex-direction: column; align-items: flex-start; margin-bottom: 25px; }
        .domain-name { width: 100%; margin-bottom: 8px; font-size: 14px; }
        .domain-bar-bg { width: 100%; }
        div[role="radiogroup"] > label, div[data-testid="stCheckbox"] { padding: 10px 12px !important; }
    }</style>
""", unsafe_allow_html=True)

# --- 2. SUPABASE POSTGRESQL SETUP ---
@st.cache_resource
def init_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

conn = init_connection()
supabase = init_supabase()

# --- 3. DATA SANITIZATION & PIPELINE ---
def clean_pmp_text(text):
    if not isinstance(text, str): return text
    text = re.sub(r'\s*(?:[A-E]-\d(?:,\s*)?){2,}$', '', text)
    text = re.sub(r'^(?:[A-E]-\d|[A-E])[\.\:\)]\s*', '', text)
    text = re.sub(r'\s+(?:[A-E]-\d|[A-E])[\.\:\)]\s*', ' | ', text)
    return text.strip()

@st.cache_data
def load_question_bank():
    try:
        all_tabs = pd.read_excel("pmp_question_bank_v6.xlsx", sheet_name=None)
        df_list = []
        for sheet_name, sheet_df in all_tabs.items():
            col_map = {}
            for c in sheet_df.columns:
                c_clean = str(c).strip()
                c_lower = c_clean.lower()
                if c_lower.startswith('option') and c_lower.endswith('correct'): col_map[c] = c_clean.title()
                elif c_lower.startswith('option') and c_lower.endswith('text'): col_map[c] = c_clean.title()
                elif c_lower == 'question text': col_map[c] = 'Question Text'
                elif 'feedback' in c_lower or 'explanation' in c_lower or 'rationale' in c_lower: col_map[c] = 'Explanation'
                elif c_lower == 'domain': col_map[c] = 'Domain'
                else: col_map[c] = c_clean
            
            sheet_df.rename(columns=col_map, inplace=True)
            
            for col in ['Question Text', 'Option 1 Text', 'Option 2 Text', 'Option 3 Text', 'Option 4 Text']:
                if col in sheet_df.columns:
                    sheet_df[col] = sheet_df[col].apply(clean_pmp_text)
                    
            sheet_df['Source_Sheet'] = sheet_name
            sheet_df = sheet_df.sample(frac=1, random_state=42).reset_index(drop=True)
            df_list.append(sheet_df)
            
        return pd.concat(df_list, ignore_index=True).dropna(subset=['Question Text'])
    except Exception: return None

df_full = load_question_bank()

def get_sheet_from_title(title):
    if title == "Bonus Mock Test": return "Free_Mock_Test"
    if title == "Sample Test": return "Bonus_Questions"
    return title.replace(' ', '_')

# --- 4. JS TIMER ---
def inject_js_timer(minutes, exam_name):
    safe_name = exam_name.replace(" ", "_")
    timer_html = f"""
    <div style="font-size:16px; font-weight:700; color:#111827; padding: 10px 0;">Time Remaining: <span id="time" style="color:#2563EB;">Loading...</span></div>
    <script>
        var examKey = 'pmp_timer_v2_{safe_name}';
        var endTime = sessionStorage.getItem(examKey);
        if (!endTime) {{ endTime = new Date().getTime() + ({minutes} * 60000); sessionStorage.setItem(examKey, endTime); }}
        var x = setInterval(function() {{
            var now = new Date().getTime(), distance = endTime - now;
            var h = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)), m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)), s = Math.floor((distance % (1000 * 60)) / 1000);
            document.getElementById("time").innerHTML = (h<10?"0"+h:h) + ":" + (m<10?"0"+m:m) + ":" + (s<10?"0"+s:s);
            if (distance < 0) {{ clearInterval(x); document.getElementById("time").innerHTML = "00:00:00"; document.getElementById("time").style.color = "#DC2626"; }}
        }}, 1000);
    </script>
    """
    components.html(timer_html, height=40)

# --- 5. ROBUST STATE INITIALIZATION ---
default_states = {
    "page": "auth",
    "auth_mode": "login",
    "current_q": 0,
    "review_q_idx": 0,
    "is_premium": False,
    "exam_title": "",
    "active_exam": None,
    "exam_start_time": time.time(),
    "flagged": set(),
    "answers": {},
    "review_answers": {},
    "student_email": "",
    "student_name": ""
}

for key, value in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 6. PAGE: AUTHENTICATION ---
if st.session_state.page == "auth":
    st.markdown("<h1 style='text-align: center; color: #111827; margin-bottom: 40px;'>PMP Elite Simulator</h1>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        if st.session_state.auth_mode == "register":
            st.markdown("<h3 style='text-align: center;'>Create Account</h3>", unsafe_allow_html=True)
            name = st.text_input("Full Name *", placeholder="Alex Carter")
            email = st.text_input("E-mail *", placeholder="alex.carter@example.com")
            password = st.text_input("Create Password *", type="password")
            
            has_len, has_upper, has_lower = len(password) >= 8, bool(re.search(r'[A-Z]', password)), bool(re.search(r'[a-z]', password))
            has_num, has_spec = bool(re.search(r'\d', password)), bool(re.search(r'[@$!%*?&_]', password))
            
            st.markdown(f"""
            <div style="background:#F3F4F6; padding:10px; border-radius:6px; margin-bottom:15px;">
                <div class="pass-rule {'rule-pass' if has_len else 'rule-fail'}">{'✅' if has_len else '○'} 8+ characters</div>
                <div class="pass-rule {'rule-pass' if has_upper else 'rule-fail'}">{'✅' if has_upper else '○'} One uppercase</div>
                <div class="pass-rule {'rule-pass' if has_lower else 'rule-fail'}">{'✅' if has_lower else '○'} One lowercase</div>
                <div class="pass-rule {'rule-pass' if has_num else 'rule-fail'}">{'✅' if has_num else '○'} One number</div>
                <div class="pass-rule {'rule-pass' if has_spec else 'rule-fail'}">{'✅' if has_spec else '○'} One special char</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Start your learning journey", type="primary", use_container_width=True):
                if not (has_len and has_upper and has_lower and has_num and has_spec): 
                    st.error("Please meet all password requirements.")
                else:
                    try:
                        # 1. Create secure user in Supabase Native Auth
                        supabase.auth.sign_up({"email": email.lower(), "password": password})
                        
                        # 2. Add profile to custom table so Razorpay Webhooks still work
                        c = conn.cursor()
                        c.execute("INSERT INTO users (email, first_name, last_name, password_hash, is_premium) VALUES (%s, %s, %s, 'supabase_auth', 0)", 
                                  (email.lower(), name.split()[0], name.split()[-1] if len(name.split())>1 else ""))
                        conn.commit()
                        
                        st.session_state.auth_mode = "login"
                        st.success("Registered successfully! Please log in.")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Registration failed. Email may already be in use.")
            if st.button("Already have an account? Sign in", use_container_width=True): st.session_state.auth_mode = "login"; st.rerun()

        elif st.session_state.auth_mode == "login":
            st.markdown("<h3 style='text-align: center;'>Sign In</h3>", unsafe_allow_html=True)
            email = st.text_input("E-mail *")
            password = st.text_input("Password *", type="password")
            
            if st.button("Sign in", type="primary", use_container_width=True):
                try:
                    # 1. Authenticate via Supabase Native Auth API
                    supabase.auth.sign_in_with_password({"email": email.lower(), "password": password})
                    
                    # 2. Fetch premium status & name from your custom table
                    c = conn.cursor()
                    c.execute("SELECT first_name, last_name, is_premium FROM users WHERE email=%s", (email.lower(),))
                    user = c.fetchone()
                    
                    if user:
                        st.session_state.student_name, st.session_state.student_email = f"{user[0]} {user[1]}", email.lower()
                        st.session_state.is_premium = bool(user[2] or 0)
                        st.session_state.page = "dashboard"
                        st.rerun()
                    else:
                        st.error("Profile sync error. Contact support.")
                except Exception as e:
                    st.error("Invalid email or password.")
            
            if st.button("Forgot Password?", use_container_width=True): st.session_state.auth_mode = "forgot"; st.rerun()
            if st.button("Need an account? Sign up", use_container_width=True): st.session_state.auth_mode = "register"; st.rerun()

        elif st.session_state.auth_mode == "forgot":
            st.markdown("<h3 style='text-align: center;'>Reset Password</h3>", unsafe_allow_html=True)
            st.info("Enter your registered email address to receive instructions on how to reset your password.")
            reset_email = st.text_input("E-mail *")
            
            if st.button("Send Reset Link", type="primary", use_container_width=True):
                if reset_email:
                    try:
                        # Built-in Supabase Reset API
                        supabase.auth.reset_password_email(reset_email.lower())
                        st.success("If this email is registered, a password reset link has been sent to your inbox.")
                    except Exception as e:
                        st.error("Error sending request. Please try again.")
                else:
                    st.error("Please enter an email address.")
                    
            if st.button("← Back to Sign In", use_container_width=True): st.session_state.auth_mode = "login"; st.rerun()

# --- 7. PAGE: LMS DASHBOARD ---
elif st.session_state.page == "dashboard":
    h_col1, h_col2 = st.columns([4, 1])
    with h_col1: 
        st.markdown(f"<h1>Hi, {st.session_state.student_name.split()[0]}</h1>", unsafe_allow_html=True)
    with h_col2: 
        if st.button("Log Out", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

    if df_full is None: 
        st.error("Question bank not found.")
        st.stop()
        
    available_sheets = df_full['Source_Sheet'].dropna().unique().tolist()
    razorpay_url = f"https://pages.razorpay.com/pl_TXusukBRHuPCo4/view?email={st.session_state.student_email}"

    def render_card(sheet_id, title, desc, is_locked=False):
        if is_locked:
            st.markdown(f'''
            <div class="course-card" style="border: 1px solid #E5E7EB; background: #F9FAFB; opacity: 0.9;">
                <h4 style="color: #4B5563;">🔒 {title}</h4>
                <p style="font-size:13px; color:#6B7280; margin-bottom: 15px;">{desc}</p>
                <div style="background:#E5E7EB; color:#4B5563; font-size:13px; font-weight:600; padding:8px; border-radius:6px; text-align:center;">
                    Premium Access Required
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="course-card"><h4>{title}</h4><p style="font-size:13px; color:#6B7280;">{desc}</p></div>', unsafe_allow_html=True)
            if st.button("Launch", key=f"btn_{sheet_id}", type="primary", use_container_width=True):
                st.session_state.active_exam = df_full[df_full['Source_Sheet'] == sheet_id].copy()
                st.session_state.exam_title, st.session_state.page = title, "live_exam"
                st.session_state.current_q, st.session_state.flagged, st.session_state.answers = 0, set(), {}
                st.session_state.exam_start_time = time.time()
                st.rerun()

    def paywall_block(title):
        st.markdown(f"""
        <div style="background:white; border:1px solid #E5E7EB; border-radius:8px; padding:40px 20px; text-align:center; margin-bottom:25px;">
            <h3 style="color:#374151; margin-bottom:8px;">🔒 Premium Access Required</h3>
            <p style="color:#6B7280; font-size:15px; margin-bottom:20px;">Unlock all 6 Full-Length Mocks, Domain Sprints, and In-depth Analytics to accelerate your PMP preparation.</p>
        </div>
        """, unsafe_allow_html=True)
        _, c1, c2, _ = st.columns([1, 1.5, 1.5, 1])
        with c1:
            st.link_button("Secure Premium Access (₹699)", razorpay_url, type="primary", use_container_width=True)
        with c2:
            if st.button("Confirm Premium Activation", key=f"verify_btn_{title.replace(' ', '_')}", use_container_width=True):
                c = conn.cursor()
                c.execute("SELECT is_premium FROM users WHERE email=%s", (st.session_state.student_email,))
                user_status = c.fetchone()
                if user_status and user_status[0] == 1:
                    st.session_state.is_premium = True
                    st.success("Payment verified! Premium features unlocked.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Payment not registered yet. Please wait a moment and try again.")

    t1, t2, t3, t4 = st.tabs(["My Analytics", "Sample Tests", "Domain Sprints", "Full Mocks"])
    
    with t1:
        st.markdown("### Recent Exam Performance")
        if not st.session_state.is_premium: 
            paywall_block("Advanced Analytics")
        else:
            c = conn.cursor()
            c.execute("SELECT id, exam_name, score_percent, time_taken_sec, timestamp, answers_json FROM exam_results WHERE email=%s ORDER BY timestamp DESC", (st.session_state.student_email,))
            history = c.fetchall()
            if history:
                for row in history:
                    score, mins, ans_json = row[2], row[3] // 60, row[5]
                    color = "#10B981" if score >= 70 else "#EF4444"
                    hc1, hc2 = st.columns([4, 1])
                    with hc1:
                        st.markdown(f"""<div style="background:white; padding:15px; border-radius:8px; border:1px solid #E5E7EB; display:flex; justify-content:space-between; align-items:center;">
                            <div><strong>{row[1]}</strong><br><span style="font-size:12px; color:#6B7280;">Time: {mins} minutes | Date: {str(row[4])[:10]}</span></div>
                            <div style="font-size:20px; font-weight:700; color:{color};">{score:.1f}%</div></div>""", unsafe_allow_html=True)
                    with hc2:
                        st.markdown("<div style='padding-top:15px;'></div>", unsafe_allow_html=True)
                        if st.button("Review", key=f"rev_{row[0]}", use_container_width=True):
                            st.session_state.review_exam_name = row[1]
                            st.session_state.review_answers = json.loads(ans_json) if ans_json else {}
                            st.session_state.review_q_idx = 0
                            st.session_state.page = "review_exam"
                            st.rerun()
            else: 
                st.info("You haven't completed any exams yet.")
            
    with t2:
        st.markdown("### Sample Tests (Free Access)")
        if "Bonus_Questions" in available_sheets: 
            render_card("Bonus_Questions", "Sample Test", "Establish your baseline.", is_locked=False)
                
    with t3:
        st.markdown("### Domain Sprints")
        if not st.session_state.is_premium:
            paywall_block("Targeted Domain Sprints")
        sprint_sheets = sorted([s for s in available_sheets if "Sprint" in s])
        c1, c2, c3 = st.columns(3)
        for i, sheet in enumerate(sprint_sheets):
            with [c1, c2, c3][i % 3]: 
                render_card(sheet, sheet.replace('_', ' '), "60 Questions | 75 Mins", is_locked=(not st.session_state.is_premium))
                
    with t4:
        st.markdown("### Full-Length Mocks")
        if not st.session_state.is_premium:
            paywall_block("Full-Length Mock Exams")
        full_mocks = sorted([s for s in available_sheets if "Full_Mock" in s])
        if "Free_Mock_Test" in available_sheets: 
            full_mocks.append("Free_Mock_Test")
        c1, c2, c3 = st.columns(3)
        for i, sheet in enumerate(full_mocks):
            with [c1, c2, c3][i % 3]: 
                title = "Bonus Mock Test" if sheet == "Free_Mock_Test" else sheet.replace('_', ' ')
                render_card(sheet, title, "180 Questions | 230 Mins", is_locked=(not st.session_state.is_premium))

# --- 8. PAGE: LIVE EXAM ---
elif st.session_state.page == "live_exam":
    if st.session_state.active_exam is None:
        st.session_state.page = "dashboard"
        st.rerun()
        
    df_exam = st.session_state.active_exam
    total_q = len(df_exam)
    idx = st.session_state.current_q
    
    st.markdown(f"**{st.session_state.exam_title}**")
    
    # Custom Timer Logic
    if st.session_state.exam_title == "Sample Test":
        time_limit = 15
    elif "Mock" in st.session_state.exam_title:
        time_limit = 230
    else:
        time_limit = 75

    # --- MAIN SCREEN TOP BAR (visible on mobile, since the sidebar is hidden) ---
    top1, top2, top3 = st.columns([2, 2, 1])
    with top1:
        inject_js_timer(time_limit, st.session_state.exam_title)
    with top2:
        st.progress((idx) / total_q if total_q > 0 else 0)
        st.markdown(f"<div style='text-align:center; font-size:13px; color:#6B7280; margin-top:5px;'>Question {idx + 1} of {total_q}</div>", unsafe_allow_html=True)
    with top3:
        if st.button("Exit Exam", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()
    # -------------------------------------------------------------------------

    row = df_exam.iloc[idx]
    
    st.markdown(f"<div style='background:white; padding:32px; border-radius:12px; border:1px solid #E5E7EB; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom:24px;'><p style='color:#111827; font-size:21px; font-weight:600; line-height:1.6; margin-bottom:0;'>{row['Question Text']}</p></div>", unsafe_allow_html=True)
    
    opts = [str(row['Option 1 Text']), str(row['Option 2 Text']), str(row['Option 3 Text']), str(row['Option 4 Text'])]
    correct_cols = [str(row.get(f'Option {i} Correct', '')).strip().lower() for i in range(1, 5)]
    num_correct = sum(1 for x in correct_cols if x in ['yes', 'true', '1', 'correct'])
    
    q_text_lower = str(row['Question Text']).lower()
    has_bundled_options = any(' | ' in opt for opt in opts)
    
    multi_match = re.search(r'\b(choose|select|which)\s+(two|three|2|3)\b', q_text_lower)
    
    if has_bundled_options:
        is_multiple = False
        limit = 1
    elif num_correct > 1:
        is_multiple = True
        limit = num_correct
    elif multi_match:
        is_multiple = True
        num_str = multi_match.group(2)
        limit = 3 if num_str in ['three', '3'] else 2
    else:
        is_multiple = False
        limit = 1
        
    if is_multiple:
        st.markdown(f"<p style='color:#6B7280; font-size:14px; font-weight:600;'>Select {limit} options:</p>", unsafe_allow_html=True)
        current_selections = st.session_state.answers.get(idx, [])
        new_selections = []
        for i, opt in enumerate(opts):
            if st.checkbox(opt, value=(opt in current_selections), key=f"q_{idx}_opt_{i}"): new_selections.append(opt)
        st.session_state.answers[idx] = new_selections
        if len(new_selections) > limit: 
            st.warning(f"⚠️ You should only select {limit} options.")
    else:
        current_selection = st.session_state.answers.get(idx, None)
        default_idx = opts.index(current_selection) if current_selection in opts else None
        st.session_state.answers[idx] = st.radio("Options", opts, index=default_idx, label_visibility="collapsed", key=f"q_{idx}")
    
    st.markdown("<hr style='margin: 40px 0 20px 0; border-top: 1px solid #E5E7EB;'>", unsafe_allow_html=True)
    
    n1, n2, n3, n4 = st.columns([1, 1.5, 1, 1.2])
    with n1:
        if idx > 0 and st.button("← Previous", use_container_width=True): st.session_state.current_q -= 1; st.rerun()
    with n2:
        is_flagged = idx in st.session_state.flagged
        if st.checkbox("⚑ Flag for Review", value=is_flagged, key=f"flag_{idx}"): st.session_state.flagged.add(idx)
        else: st.session_state.flagged.discard(idx)
        st.markdown(f"<div style='text-align:center; font-size:13px; color:#6B7280;'>{idx + 1} / {total_q}</div>", unsafe_allow_html=True)
    with n3:
        if idx < total_q - 1:
            if st.button("Next →", type="primary", use_container_width=True): st.session_state.current_q += 1; st.rerun()
    with n4:
        if st.button("Review Board", use_container_width=True): 
            st.session_state.page = "pre_submit_review"; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# --- 8.5 PAGE: PRE-SUBMIT REVIEW ---
elif st.session_state.page == "pre_submit_review":
    df_exam = st.session_state.active_exam
    total_q = len(df_exam)
    st.markdown("<h2>Exam Review</h2>", unsafe_allow_html=True)
    st.info("Please review your flagged and unanswered questions before final submission.")
    
    unanswered_count = sum(1 for i in range(total_q) if st.session_state.answers.get(i) is None or (isinstance(st.session_state.answers.get(i), list) and len(st.session_state.answers.get(i)) == 0))
    st.markdown(f"**Unanswered:** <span style='color:#EF4444;'>{unanswered_count}</span> &nbsp;&nbsp;|&nbsp;&nbsp; **Flagged:** <span style='color:#F59E0B;'>{len(st.session_state.flagged)}</span>", unsafe_allow_html=True)
    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
    
    cols = st.columns(10)
    for i in range(total_q):
        marker = " ⚑" if i in st.session_state.flagged else " ❓" if st.session_state.answers.get(i) is None or (isinstance(st.session_state.answers.get(i), list) and len(st.session_state.answers.get(i)) == 0) else ""
        if cols[i % 10].button(f"Q{i+1}{marker}", key=f"jump_{i}", use_container_width=True):
            st.session_state.current_q, st.session_state.page = i, "live_exam"; st.rerun()
            
    st.markdown("<hr style='margin: 40px 0 20px 0; border-top: 1px solid #E5E7EB;'>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("← Return to Exam"): st.session_state.page = "live_exam"; st.rerun()
    with c2:
        if st.button("Finalize & Grade Exam", type="primary"):
            time_taken = int(time.time() - st.session_state.get('exam_start_time', time.time()))
            stats = {'People': {'tot':0, 'cor':0}, 'Process': {'tot':0, 'cor':0}, 'Business Environment': {'tot':0, 'cor':0}}
            total_correct = 0
            
            for i in range(total_q):
                q_row = df_exam.iloc[i]
                domain = str(q_row.get('Domain', 'Process'))
                d_key = 'Business Environment' if 'business' in domain.lower() else 'People' if 'people' in domain.lower() else 'Process'
                stats[d_key]['tot'] += 1
                correct_answers = [str(q_row[f'Option {j} Text']) for j in range(1, 5) if str(q_row.get(f'Option {j} Correct', '')).strip().lower() in ['yes', 'true', '1', 'correct']]
                user_ans = st.session_state.answers.get(i)
                is_correct = set(user_ans) == set(correct_answers) if isinstance(user_ans, list) else user_ans in correct_answers
                if is_correct:
                    total_correct += 1
                    stats[d_key]['cor'] += 1
            
            score_pct = (total_correct / total_q) * 100 if total_q > 0 else 0
            st.session_state.final_score, st.session_state.final_stats, st.session_state.time_taken = score_pct, stats, time_taken
            safe_answers = {str(k): v for k, v in st.session_state.answers.items()}
            
            c = conn.cursor()
            c.execute("INSERT INTO exam_results (email, exam_name, score_percent, time_taken_sec, domains_json, answers_json) VALUES (%s, %s, %s, %s, %s, %s)", 
                      (st.session_state.student_email, st.session_state.exam_title, score_pct, time_taken, json.dumps(stats), json.dumps(safe_answers)))
            conn.commit()
            
            st.session_state.review_exam_name, st.session_state.review_answers = st.session_state.exam_title, safe_answers
            st.session_state.page = "results"; st.rerun()

# --- 9. PAGE: EXAM RESULTS ---
elif st.session_state.page == "results":
    st.markdown("<h2>Exam Analysis | PMP®</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1: 
        if st.button("← Return to Dashboard"): st.session_state.page = "dashboard"; st.rerun()
    with c2:
        if st.button("Review Questions & Feedback →", type="primary"): st.session_state.review_q_idx, st.session_state.page = 0, "review_exam"; st.rerun()
    
    score, (mins, secs) = st.session_state.final_score, divmod(st.session_state.time_taken, 60)
    status, status_class = ("PASS", "grade-pass") if score >= 70 else ("FAIL", "grade-fail")
    
    st.markdown(f"""
    <div class="pmp-report">
        <p style="color:#6B7280; margin-bottom:5px;">Exam Name: <strong>{st.session_state.exam_title}</strong></p>
        <p style="color:#6B7280; margin-bottom:20px;">Time Taken: <strong>{mins}m {secs}s</strong> | Overall Score: <strong>{score:.1f}%</strong></p>
        <div style="padding:15px; background:#F9FAFB; border-left:4px solid {'#10B981' if score>=70 else '#EF4444'}; margin-bottom: 30px;">
            <span style="font-size:16px;">Overall Performance: </span><span class="pmp-grade {status_class}">{status}</span>
        </div>
        <h4 style="margin-bottom:20px;">Exam Breakdown</h4>
        <div style="display:flex; justify-content:space-between; padding-left:200px; margin-bottom:10px; font-size:12px; color:#6B7280; font-weight:600;">
            <div style="width:25%; text-align:center;">Needs Improvement</div><div style="width:25%; text-align:center;">Below Target</div>
            <div style="width:25%; text-align:center;">Target</div><div style="width:25%; text-align:center;">Above Target</div>
        </div>
    """, unsafe_allow_html=True)
    
    for domain, data in st.session_state.final_stats.items():
        if data['tot'] == 0: continue
        d_score = (data['cor'] / data['tot']) * 100
        if d_score < 60: color, pct = "#EF4444", max(5, (d_score/60)*25)
        elif d_score < 75: color, pct = "#F59E0B", 25 + ((d_score-60)/15)*25
        elif d_score < 85: color, pct = "#10B981", 50 + ((d_score-75)/10)*25
        else: color, pct = "#059669", 75 + ((d_score-85)/15)*25
        
        st.markdown(f"""
        <div class="domain-row"><div class="domain-name">{domain}</div>
            <div class="domain-bar-bg">
                <div class="domain-marker" style="left:25%;"></div><div class="domain-marker" style="left:50%;"></div><div class="domain-marker" style="left:75%;"></div>
                <div style="width:{min(100, pct)}%; background:{color}; height:100%; border-radius:12px;"></div>
            </div>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# --- 10. PAGE: EXAM REVIEW & FEEDBACK ---
elif st.session_state.page == "review_exam":
    sheet_name = get_sheet_from_title(st.session_state.review_exam_name)
    df_exam = df_full[df_full['Source_Sheet'] == sheet_name].copy()
    total_q = len(df_exam)
    idx = st.session_state.review_q_idx
    
    st.sidebar.markdown(f"**Reviewing: {st.session_state.review_exam_name}**")
    st.sidebar.progress((idx + 1) / total_q if total_q > 0 else 0)
    st.sidebar.markdown(f"Question {idx + 1} of {total_q}")
    if st.sidebar.button("Exit Review", use_container_width=True): st.session_state.page = "dashboard"; st.rerun()

    row = df_exam.iloc[idx]
    user_ans = st.session_state.review_answers.get(str(idx), "No Answer Selected")
    if user_ans is None or (isinstance(user_ans, list) and len(user_ans) == 0): user_ans = "No Answer Selected"
    
    correct_answers = [str(row[f'Option {j} Text']) for j in range(1, 5) if str(row.get(f'Option {j} Correct', '')).strip().lower() in ['yes', 'true', '1', 'correct']]
    is_correct = set(user_ans) == set(correct_answers) if isinstance(user_ans, list) else user_ans in correct_answers
    ans_color = "#10B981" if is_correct else "#EF4444"
    
    user_ans_str = " | ".join(user_ans) if isinstance(user_ans, list) else str(user_ans)
    corr_ans_str = " | ".join(correct_answers)
    
    st.markdown(f"<div style='background:white; padding:32px; border-radius:12px; border:1px solid #E5E7EB; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom:24px;'><p style='color:#111827; font-size:21px; font-weight:600; line-height:1.6; margin-bottom:0;'>{row['Question Text']}</p></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom: 10px;'><strong>Your Answer:</strong> <span style='color:{ans_color}; font-weight:600;'>{user_ans_str}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom: 20px;'><strong>Correct Answer:</strong> <span style='color:#10B981; font-weight:600;'>{corr_ans_str}</span></div>", unsafe_allow_html=True)
    
    # Safe retrieval of feedback data 
    explanation_text = row.get('Explanation', 'No explanation provided.')
    if pd.isna(explanation_text) or str(explanation_text).strip() == '': 
        explanation_text = "No explanation provided."
        
    st.info(f"**Explanation:**\n\n{explanation_text}")
    st.markdown("<hr style='margin: 40px 0 20px 0; border-top: 1px solid #E5E7EB;'>", unsafe_allow_html=True)
    
    n1, _, n3 = st.columns([1, 1.5, 1])
    with n1:
        if idx > 0 and st.button("← Previous", use_container_width=True): st.session_state.review_q_idx -= 1; st.rerun()
    with n3:
        if idx < total_q - 1:
            if st.button("Next →", type="primary", use_container_width=True): st.session_state.review_q_idx += 1; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
