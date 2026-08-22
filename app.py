import streamlit as st
import pandas as pd
import sqlite3
import datetime
import time
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# Configure page with a professional title
st.set_page_config(page_title="PMP® Certification Simulator", layout="wide", initial_sidebar_state="expanded")

# --- ENTERPRISE CSS THEME (Pastels & Slate) ---
st.markdown("""
<style>
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Clean, soft background */
    .stApp { background-color: #F8FAFC; }
    
    /* Elegant Typography */
    h1, h2, h3, h4 { color: #1E293B; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    p { color: #334155; }
    
    /* Professional Radio Buttons (Options) */
    .stRadio > label { font-size: 16px; font-weight: 600; color: #475569; margin-bottom: 12px; }
    .stRadio div[role="radiogroup"] > label {
        padding: 16px; 
        background-color: #FFFFFF; 
        border: 1px solid #E2E8F0; 
        border-radius: 6px; 
        margin-bottom: 10px; 
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
        transition: all 0.2s ease-in-out;
        color: #334155;
    }
    .stRadio div[role="radiogroup"] > label:hover {
        border-color: #94A3B8;
        background-color: #F1F5F9;
    }
    
    /* Muted Corporate Timer */
    .timer-text {
        font-size: 22px; 
        font-weight: 500; 
        color: #334155; 
        text-align: center; 
        padding: 12px; 
        background: #FFFFFF; 
        border-radius: 6px; 
        border: 1px solid #CBD5E1;
        letter-spacing: 1px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Clean Divider */
    hr { border-top: 1px solid #E2E8F0; }
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
    st.error("System Error: Question bank securely locked or unavailable.")
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
        st.title("PMP® Certification Portal")
        st.caption("PearsonVUE-Aligned Computer-Based Testing Environment | 2026 Standards")
        st.divider()
        with st.form("login_form"):
            st.markdown("#### Candidate Authentication")
            name = st.text_input("Full Legal Name", placeholder="e.g. Sagar Sharma")
            email = st.text_input("Registered Email Address", placeholder="e.g. sagar@example.com")
            if st.form_submit_button("Access Candidate Dashboard", type="primary", use_container_width=True):
                if name.strip() and email.strip():
                    st.session_state.student_name = name.strip()
                    st.session_state.student_email = email.strip()
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Authentication failed: Name and Email are required.")

# -------------------------------------------------------------
# PAGE 2: DASHBOARD & TREND ANALYTICS
# -------------------------------------------------------------
elif st.session_state.page == "dashboard":
    st.sidebar.markdown(f"**Candidate:** {st.session_state.student_name}")
    st.sidebar.markdown(f"**ID:** {st.session_state.student_email}")
    if st.sidebar.button("Secure Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.title("Performance Dashboard")
    st.divider()

    st.markdown("#### Authorized Assessments")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**Diagnostic Baseline**\n\n25 Questions | 35 Minutes\n\nCross-domain assessment.")
        if st.button("Launch Diagnostic", type="primary", use_container_width=True):
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
        st.success("**Domain Specialization**\n\n60 Questions | 75 Minutes\n\nTargeted domain analysis.")
        st.button("Launch Specialization (Pro)", disabled=True, use_container_width=True)

    with c3:
        st.warning("**Full Certification Mock**\n\n180 Questions | 230 Minutes\n\nComplete CBT replication.")
        st.button("Launch Full Mock (Pro)", disabled=True, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Readiness Analytics")
    history_df = get_student_history(st.session_state.student_email)
    
    if len(history_df) > 0:
        chart_df = history_df.sort_values("id")
        fig = px.line(chart_df, x="date_taken", y="percentage", markers=True, 
                      title="Cumulative Performance Trend",
                      labels={"date_taken": "Assessment Date", "percentage": "Score (%)"},
                      color_discrete_sequence=["#3D5A80"]) # Slate blue line
        
        # Muted red line for threshold
        fig.add_hline(y=70, line_dash="dash", line_color="#E07A5F", annotation_text="Passing Threshold (70%)", annotation_position="bottom right")
        fig.update_layout(plot_bgcolor="white", yaxis=dict(range=[0, 105], gridcolor="#F1F5F9"), xaxis=dict(gridcolor="#F1F5F9"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### Assessment History")
        display_df = history_df.copy()
        display_df["Result"] = display_df["passed"].apply(lambda x: "PASS" if x == 1 else "REVIEW REQUIRED")
        display_df["Score"] = display_df["score"].astype(str) + " / " + display_df["total_questions"].astype(str)
        display_df["Percentage"] = display_df["percentage"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_df[["date_taken", "exam_title", "Score", "Percentage", "Result"]].rename(columns={"date_taken": "Date"}), use_container_width=True, hide_index=True)
    else:
        st.caption("Insufficient data. Complete an assessment to generate predictive analytics.")

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
    st.sidebar.markdown(f"<div class='timer-text'>Time Remaining<br>{mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    st_autorefresh(interval=10000, limit=None, key="timer_refresh")

    if st.sidebar.button("Review & Submit", use_container_width=True):
        st.session_state.page = "pre_submit_review"
        st.rerun()

    st.markdown(f"#### Item {cq + 1} of {total_q}")
    st.markdown(f"<p style='font-size: 18px; margin-bottom: 20px;'>{row['Question Text']}</p>", unsafe_allow_html=True)
    
    options = [f"A. {row['Option 1 Text']}", f"B. {row['Option 2 Text']}", f"C. {row['Option 3 Text']}", f"D. {row['Option 4 Text']}"]
    current_val = st.session_state.user_answers.get(cq, None)

    selected = st.radio("Select an option:", options, index=options.index(current_val) if current_val in options else None, label_visibility="collapsed", key=f"radio_{cq}")
    if selected:
        st.session_state.user_answers[cq] = selected

    st.divider()

    c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
    with c1:
        if st.button("Previous", disabled=(cq == 0), use_container_width=True):
            st.session_state.current_q -= 1
            st.rerun()
    with c2:
        is_flagged = st.checkbox("Flag for Review", value=(cq in st.session_state.flagged))
        if is_flagged: st.session_state.flagged.add(cq)
        else: st.session_state.flagged.discard(cq)
    with c4:
        if cq < total_q - 1:
            if st.button("Next", type="primary", use_container_width=True):
                st.session_state.current_q += 1
                st.rerun()
        else:
            if st.button("Review Responses", type="primary", use_container_width=True):
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
    st.sidebar.markdown(f"<div class='timer-text'>Time Remaining<br>{mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)
    st_autorefresh(interval=10000, limit=None, key="timer_refresh_review")

    st.title("Pre-Submission Review")
    st.divider()

    if unanswered_count > 0:
        st.warning(f"Notice: {unanswered_count} unanswered item(s) and {flagged_count} item(s) flagged for review.")
    else:
        st.success(f"All {total_q} items answered. {flagged_count} item(s) flagged for review.")

    hc1, hc2, hc3, hc4 = st.columns([1, 2, 2, 2])
    hc1.markdown("**Item**")
    hc2.markdown("**Status**")
    hc3.markdown("**Flag**")
    hc4.markdown("**Action**")
    st.markdown("---")

    for idx in range(total_q):
        q_num = idx + 1
        is_ans = idx in st.session_state.user_answers
        is_flag = idx in st.session_state.flagged
        
        c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
        c1.write(f"Item {q_num}")
        c2.write("Answered" if is_ans else "**Incomplete**")
        c3.write("Flagged" if is_flag else "—")
        if c4.button(f"Review Item {q_num}", key=f"jump_{idx}"):
            st.session_state.current_q = idx
            st.session_state.page = "exam"
            st.rerun()
        st.markdown("<hr style='margin: 0px; padding: 5px 0px;'>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        if st.button("Confirm & Submit Assessment", type="primary", use_container_width=True):
            st.session_state.page = "results"
            st.rerun()

# -------------------------------------------------------------
# PAGE 5: GAUGE CHART RESULTS & EXPLANATIONS
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

    st.title("Official Score Report")
    st.caption(f"Candidate: {st.session_state.student_name} | {st.session_state.exam_title}")
    st.divider()

    col_chart, col_metrics = st.columns([1, 1])
    
    with col_chart:
        # Professional Pastel Gauge Chart
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = percentage,
            title = {'text': "Final Score (%)", 'font': {'size': 20, 'color': '#334155'}},
            number = {'font': {'color': '#1E293B'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#CBD5E1"},
                'bar': {'color': "#3D5A80"}, # Slate Blue progress bar
                'steps' : [
                    {'range': [0, 69.9], 'color': "#FDF2F8"}, # Soft pink/rose bg
                    {'range': [70, 100], 'color': "#F0FDF4"}], # Soft sage/mint bg
                'threshold' : {'line': {'color': "#E07A5F", 'width': 4}, 'thickness': 0.75, 'value': 70} # Muted coral threshold
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="#F8FAFC")
        st.plotly_chart(fig, use_container_width=True)

    with col_metrics:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric("Raw Score", f"{correct_count} / {total_q}")
        if is_passed:
            st.success("### PASS\nTarget Proficiency Achieved")
        else:
            st.error("### REVIEW REQUIRED\nTarget Proficiency Not Met")

    st.markdown("---")
    st.subheader("Item Analysis & Rationales")

    for idx, row in df.iterrows():
        user_ans = st.session_state.user_answers.get(idx, "Unanswered")
        corr_opt = ""
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': corr_opt = f"A. {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': corr_opt = f"B. {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': corr_opt = f"C. {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': corr_opt = f"D. {row['Option 4 Text']}"

        is_corr = (user_ans == corr_opt)
        status_mark = "✓" if is_corr else "✗"

        with st.expander(f"{status_mark} Item {idx+1}: {'Correct' if is_corr else 'Incorrect'}"):
            st.markdown(f"**{row['Question Text']}**")
            st.markdown(f"**Candidate Selection:** `{user_ans}`")
            st.markdown(f"**Correct Selection:** `{corr_opt}`")
            st.info(f"**Rationale:**\n\n{row['Question feedback']}")

    st.divider()
    if st.button("Return to Dashboard", type="primary", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()
