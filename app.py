import streamlit as st
import pandas as pd
import sqlite3
import datetime
import time
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# Configure page
st.set_page_config(page_title="PMP® Certification Simulator", layout="wide", initial_sidebar_state="expanded")

# --- PREMIUM MODERN EDTECH CSS ---
# Note: The comments inside the style tags are standard CSS comments (/* ... */) and are correct here.
st.markdown("""
<style>
    /* Import Google Fonts for a happy, modern look */
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

    /* Hide Streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Apply Font Family globally */
    html, body, [class*="css"] {
        font-family: 'Nunito', sans-serif !important;
        background-color: #F4F7FE !important; /* Soft, happy light-blue/grey background */
    }
    
    /* Headings Styling */
    h1, h2, h3 {
        color: #1B2559 !important; /* Deep Indigo for strong contrast */
        font-weight: 800 !important;
        letter-spacing: -0.5px;
    }
    h4, h5, h6, p { color: #2B3674 !important; }
    
    /* 🚀 Vibrant Gradient Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #FF7F50 0%, #FF416C 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 12px 24px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(255, 65, 108, 0.25) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(255, 65, 108, 0.4) !important;
    }

    /* 📝 Modern Selectable Option Cards */
    .stRadio > label { 
        font-size: 18px !important; 
        font-weight: 700 !important; 
        color: #1B2559 !important; 
        margin-bottom: 12px !important; 
    }
    .stRadio div[role="radiogroup"] > label {
        padding: 18px 20px !important; 
        background-color: #FFFFFF !important; 
        border: 2px solid #E9EDF7 !important; 
        border-radius: 12px !important; 
        margin-bottom: 12px !important; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.02) !important;
        transition: all 0.2s ease-in-out !important;
        color: #2B3674 !important;
        font-weight: 600 !important;
        cursor: pointer !important;
    }
    .stRadio div[role="radiogroup"] > label:hover {
        border-color: #4318FF !important; /* Vibrant Indigo hover accent */
        background-color: #F8F9FF !important;
        transform: scale(1.01) !important;
    }
    
    /* ⏱️ Timer Styling - Tech Blue */
    .timer-text {
        font-size: 24px; 
        font-weight: 800; 
        color: #FFFFFF; 
        text-align: center; 
        padding: 16px; 
        background: linear-gradient(135deg, #4318FF 0%, #868CFF 100%); 
        border-radius: 12px; 
        box-shadow: 0 4px 15px rgba(67, 24, 255, 0.25);
        margin-bottom: 20px;
    }
    
    /* Text Inputs (Login Form) */
    .stTextInput input {
        border-radius: 10px !important;
        border: 2px solid #E9EDF7 !important;
        padding: 12px !important;
        font-weight: 600 !important;
        color: #1B2559 !important;
    }
    .stTextInput input:focus {
        border-color: #4318FF !important;
        box-shadow: 0 0 0 2px rgba(67, 24, 255, 0.2) !important;
    }
    
    /* Metric Cards (Results) */
    [data-testid="stMetricValue"] {
        color: #4318FF !important;
        font-weight: 800 !important;
    }
    
    hr { border-top: 2px solid #E9EDF7 !important; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# DATABASE SETUP
# -------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("pmp_portal.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT, student_email TEXT,
            exam_title TEXT, score INTEGER, total_questions INTEGER, percentage REAL, passed INTEGER, date_taken TEXT)""")
    conn.commit()
    conn.close()

def save_attempt(name, email, title, score, total, pct, passed):
    conn = sqlite3.connect("pmp_portal.db")
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO exam_attempts (student_name, student_email, exam_title, score, total_questions, percentage, passed, date_taken) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
              (name, email.strip().lower(), title, score, total, pct, 1 if passed else 0, now_str))
    conn.commit()
    conn.close()

def get_student_history(email):
    conn = sqlite3.connect("pmp_portal.db")
    df_hist = pd.read_sql_query("SELECT id, exam_title, score, total_questions, percentage, passed, date_taken FROM exam_attempts WHERE student_email = ? ORDER BY id DESC", conn, params=(email.strip().lower(),))
    conn.close()
    return df_hist

init_db()

# -------------------------------------------------------------
# LOAD QUESTIONS
# -------------------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_excel("flexiquiz-pmp-import.xlsx")

try:
    df_full = load_data()
except Exception:
    st.error("System Error: Question bank unavailable.")
    st.stop()

# -------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------
if "page" not in st.session_state: st.session_state.page = "landing"
if "student_name" not in st.session_state: st.session_state.student_name = ""
if "student_email" not in st.session_state: st.session_state.student_email = ""
if "user_answers" not in st.session_state: st.session_state.user_answers = {}
if "flagged" not in st.session_state: st.session_state.flagged = set()
if "current_q" not in st.session_state: st.session_state.current_q = 0
if "end_time" not in st.session_state: st.session_state.end_time = None
if "saved_attempt" not in st.session_state: st.session_state.saved_attempt = False

# -------------------------------------------------------------
# PAGE 1: LANDING & LOGIN
# -------------------------------------------------------------
if st.session_state.page == "landing":
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("PMP® Master Simulator")
        st.caption("Premium 2026 PMI Standards Experience")
        st.divider()
        with st.form("login_form"):
            st.markdown("### 👋 Welcome Back")
            name = st.text_input("Full Name", placeholder="e.g. Sagar Sharma")
            email = st.text_input("Email Address", placeholder="e.g. sagar@example.com")
            if st.form_submit_button("Enter Dashboard 🚀", type="primary", use_container_width=True):
                if name.strip() and email.strip():
                    st.session_state.student_name = name.strip()
                    st.session_state.student_email = email.strip()
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Please provide your name and email to continue.")

# -------------------------------------------------------------
# PAGE 2: DASHBOARD & TREND ANALYTICS
# -------------------------------------------------------------
elif st.session_state.page == "dashboard":
    st.sidebar.markdown(f"**👤 Candidate:** {st.session_state.student_name}")
    st.sidebar.markdown(f"**✉️ ID:** {st.session_state.student_email}")
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.title("My Performance Dashboard")
    st.divider()

    st.markdown("### 🎯 Launch Assessments")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("### Diagnostic\n\n**25 Questions | 35 Mins**\n\nCross-domain baseline.")
        if st.button("Start Diagnostic ⚡", type="primary", use_container_width=True):
            st.session_state.active_df = df_full.head(25).copy()
            st.session_state.exam_title = "Diagnostic Baseline Assessment"
            st.session_state.end_time = time.time() + (35 * 60)
            st.session_state.user_answers = {}
            st.session_state.flagged = set()
            st.session_state.current_q = 0
            st.session_state.saved_attempt = False
            st.session_state.page = "exam"
            st.rerun()

    with c2:
        st.success("### Domain Sprint\n\n**60 Questions | 75 Mins**\n\nTargeted domain focus.")
        st.button("Unlock Sprint 🔒", disabled=True, use_container_width=True)

    with c3:
        st.warning("### Full Mock\n\n**180 Questions | 230 Mins**\n\nUltimate exam replication.")
        st.button("Unlock Mock 🔒", disabled=True, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📈 Readiness Analytics")
    history_df = get_student_history(st.session_state.student_email)
    
    if len(history_df) > 0:
        chart_df = history_df.sort_values("id")
        fig = px.line(chart_df, x="date_taken", y="percentage", markers=True, 
                      title="Cumulative Performance Trend",
                      labels={"date_taken": "Date", "percentage": "Score (%)"},
                      color_discrete_sequence=["#4318FF"]) # Vibrant Indigo line
        
        # Coral threshold line
        fig.add_hline(y=70, line_dash="dash", line_color="#FF7F50", annotation_text="Target Score (70%)", annotation_position="bottom right")
        fig.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", yaxis=dict(range=[0, 105], gridcolor="#F4F7FE"), xaxis=dict(gridcolor="#F4F7FE"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Detailed History")
        display_df = history_df.copy()
        display_df["Result"] = display_df["passed"].apply(lambda x: "🟢 PASS" if x == 1 else "🟡 REVIEW")
        display_df["Score"] = display_df["score"].astype(str) + " / " + display_df["total_questions"].astype(str)
        display_df["Percentage"] = display_df["percentage"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_df[["date_taken", "exam_title", "Score", "Percentage", "Result"]].rename(columns={"date_taken": "Date"}), use_container_width=True, hide_index=True)
    else:
        st.caption("Start an assessment above to unlock your predictive analytics.")

# -------------------------------------------------------------
# PAGE 3: LIVE EXAM
# -------------------------------------------------------------
elif st.session_state.page == "exam":
    time_left = int(st.session_state.end_time - time.time())
    if time_left <= 0:
        st.session_state.page = "results"
        st.rerun()

    df = st.session_state.active_df
    total_q = len(df)
    cq = st.session_state.current_q
    row = df.iloc[cq]

    mins, secs = divmod(time_left, 60)
    st.sidebar.markdown(f"<div class='timer-text'>⏱️ {mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)
    st_autorefresh(interval=10000, limit=None, key="timer_refresh")

    if st.sidebar.button("Review Answers", use_container_width=True):
        st.session_state.page = "pre_submit_review"
        st.rerun()

    st.markdown(f"#### Question {cq + 1} of {total_q}")
    st.markdown(f"<p style='font-size: 20px; font-weight: 600; margin-bottom: 24px; color: #1B2559;'>{row['Question Text']}</p>", unsafe_allow_html=True)
    
    options = [f"A. {row['Option 1 Text']}", f"B. {row['Option 2 Text']}", f"C. {row['Option 3 Text']}", f"D. {row['Option 4 Text']}"]
    current_val = st.session_state.user_answers.get(cq, None)

    selected = st.radio("Choose your answer:", options, index=options.index(current_val) if current_val in options else None, label_visibility="collapsed", key=f"radio_{cq}")
    if selected:
        st.session_state.user_answers[cq] = selected

    st.divider()

    c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
    with c1:
        if st.button("⬅️ Back", disabled=(cq == 0), use_container_width=True):
            st.session_state.current_q -= 1
            st.rerun()
    with c2:
        is_flagged = st.checkbox("🚩 Flag for Later", value=(cq in st.session_state.flagged))
        if is_flagged: st.session_state.flagged.add(cq)
        else: st.session_state.flagged.discard(cq)
    with c4:
        if cq < total_q - 1:
            if st.button("Next ➡️", type="primary", use_container_width=True):
                st.session_state.current_q += 1
                st.rerun()
        else:
            if st.button("Review & Submit", type="primary", use_container_width=True):
                st.session_state.page = "pre_submit_review"
                st.rerun()

# -------------------------------------------------------------
# PAGE 4: PRE-SUBMISSION REVIEW 
# -------------------------------------------------------------
elif st.session_state.page == "pre_submit_review":
    df = st.session_state.active_df
    total_q = len(df)
    answered_count = len(st.session_state.user_answers)
    unanswered_count = total_q - answered_count
    flagged_count = len(st.session_state.flagged)

    time_left = int(st.session_state.end_time - time.time())
    if time_left <= 0:
        st.session_state.page = "results"
        st.rerun()
    mins, secs = divmod(time_left, 60)
    st.sidebar.markdown(f"<div class='timer-text'>⏱️ {mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)
    st_autorefresh(interval=10000, limit=None, key="timer_refresh_review")

    st.title("Review Your Work")
    st.divider()

    if unanswered_count > 0:
        st.warning(f"Heads up! You have {unanswered_count} unanswered questions.")
    else:
        st.success("Great job! All questions answered.")

    hc1, hc2, hc3, hc4 = st.columns([1, 2, 2, 2])
    hc1.markdown("**Q#**")
    hc2.markdown("**Status**")
    hc3.markdown("**Flagged**")
    hc4.markdown("**Action**")
    st.markdown("---")

    for idx in range(total_q):
        q_num = idx + 1
        is_ans = idx in st.session_state.user_answers
        is_flag = idx in st.session_state.flagged
        
        c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
        c1.write(f"{q_num}")
        c2.write("✅ Answered" if is_ans else "❌ Incomplete")
        c3.write("🚩 Yes" if is_flag else "—")
        if c4.button(f"Jump to Q{q_num}", key=f"jump_{idx}"):
            st.session_state.current_q = idx
            st.session_state.page = "exam"
            st.rerun()
        st.markdown("<hr style='margin: 0px; padding: 5px 0px;'>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        if st.button("Final Submit 🚀", type="primary", use_container_width=True):
            st.session_state.page = "results"
            st.rerun()

# -------------------------------------------------------------
# PAGE 5: SCORE & EXPLANATIONS
# -------------------------------------------------------------
elif st.session_state.page == "results":
    df = st.session_state.active_df
    total_q = len(df)
    correct_count = 0
    
    for idx, row in df.iterrows():
        ans = st.session_state.user_answers.get(idx)
        corr_opt = ""
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': corr_opt = f"A. {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': corr_opt = f"B. {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': corr_opt = f"C. {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': corr_opt = f"D. {row['Option 4 Text']}"

        if ans == corr_opt: correct_count += 1

    percentage = (correct_count / total_q) * 100
    is_passed = percentage >= 70

    if not st.session_state.saved_attempt:
        save_attempt(st.session_state.student_name, st.session_state.student_email, st.session_state.exam_title, correct_count, total_q, percentage, is_passed)
        st.session_state.saved_attempt = True

    st.title("Your Score Report 🎉")
    st.divider()

    col_chart, col_metrics = st.columns([1, 1])
    
    with col_chart:
        # Happy, Vibrant Gauge Chart (Using Python comments #)
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = percentage,
            title = {'text': "Final Score (%)", 'font': {'size': 20, 'color': '#1B2559', 'family': 'Nunito'}},
            number = {'font': {'color': '#4318FF', 'family': 'Nunito', 'weight': 'bold'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#E9EDF7"},
                'bar': {'color': "#4318FF"}, # Electric Indigo
                'steps' : [
                    {'range': [0, 69.9], 'color': "#FFF5F5"}, 
                    {'range': [70, 100], 'color': "#F0FFF4"}], # Soft Mint for pass
                'threshold' : {'line': {'color': "#FF7F50", 'width': 4}, 'thickness': 0.75, 'value': 70} 
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_metrics:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric("Questions Correct", f"{correct_count} / {total_q}")
        if is_passed:
            st.success("### 🎉 PASSED\nYou hit the target score!")
        else:
            st.warning("### 💡 REVIEW NEEDED\nKeep practicing, you'll get it next time!")

    st.markdown("---")
    st.subheader("Mindset Explanations 🧠")

    for idx, row in df.iterrows():
        user_ans = st.session_state.user_answers.get(idx, "Unanswered")
        corr_opt = ""
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': corr_opt = f"A. {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': corr_opt = f"B. {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': corr_opt = f"C. {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': corr_opt = f"D. {row['Option 4 Text']}"

        is_corr = (user_ans == corr_opt)
        status_mark = "🟢" if is_corr else "🔴"

        with st.expander(f"{status_mark} Q{idx+1}: {'Nailed it!' if is_corr else 'Review This'}"):
            st.markdown(f"**{row['Question Text']}**")
            st.markdown(f"**Your Choice:** `{user_ans}`")
            st.markdown(f"**Correct Answer:** `{corr_opt}`")
            st.info(f"**PMP Mindset Rationale:**\n\n{row['Question feedback']}")

    st.divider()
    if st.button("Return to Dashboard 🏠", type="primary", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()
