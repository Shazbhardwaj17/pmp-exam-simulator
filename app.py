import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import datetime
import time
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="2026 PMP® Exam Simulator", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR PREMIUM UI ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stRadio > label {font-size: 18px; font-weight: bold; margin-bottom: 10px;}
    .stRadio div[role="radiogroup"] > label {
        padding: 15px; background-color: #f8f9fa; border: 1px solid #dee2e6; 
        border-radius: 8px; margin-bottom: 8px; transition: 0.3s;
    }
    .stRadio div[role="radiogroup"] > label:hover {background-color: #e2e6ea;}
    .timer-text {font-size: 26px; font-weight: 800; color: #D32F2F; text-align: center; padding: 10px; background: #FFEBEE; border-radius: 5px; border: 2px solid #D32F2F;}
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
    st.error("Error: flexiquiz-pmp-import.xlsx not found. Please ensure it is in the same folder as app.py")
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
        st.title("🎯 PMP® Exam Portal")
        st.caption("PearsonVUE-Style CBT Simulation | 2026 PMI Standards")
        st.divider()
        with st.form("login_form"):
            st.markdown("### 🔑 Student Access")
            name = st.text_input("Full Name", placeholder="e.g. Sagar Sharma")
            email = st.text_input("Registered Email", placeholder="e.g. sagar@example.com")
            if st.form_submit_button("Log In to Dashboard", type="primary", use_container_width=True):
                if name.strip() and email.strip():
                    st.session_state.student_name = name.strip()
                    st.session_state.student_email = email.strip()
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Name and Email are required.")

# -------------------------------------------------------------
# PAGE 2: DASHBOARD & TREND ANALYTICS
# -------------------------------------------------------------
elif st.session_state.page == "dashboard":
    st.sidebar.success(f"👤 **{st.session_state.student_name}**")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.title(f"👋 Dashboard & Analytics")
    st.divider()

    st.markdown("### 📝 Launch Simulator")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("### ⚡ Diagnostic Mock\n**25 Qs | 35 Mins**\n\nCross-domain baseline.")
        if st.button("Launch 25Q Exam", type="primary", use_container_width=True):
            st.session_state.active_df = df_full.head(25).copy()
            st.session_state.exam_title = "25Q Diagnostic Mock"
            st.session_state.end_time = time.time() + (35 * 60)
            st.session_state.user_answers = {}
            st.session_state.flagged = set()
            st.session_state.current_q = 0
            st.session_state.saved_attempt = False
            st.session_state.page = "exam"
            st.rerun()

    with c2:
        st.success("### 🏃 Domain Sprint\n**60 Qs | 75 Mins**\n\nTargeted domain practice.")
        st.button("Launch Sprint (Pro)", disabled=True, use_container_width=True)

    with c3:
        st.warning("### 🏆 Full PMP Mock\n**180 Qs | 230 Mins**\n\nFull length CBT replication.")
        st.button("Launch 180Q (Pro)", disabled=True, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📈 Your Readiness Trend")
    history_df = get_student_history(st.session_state.student_email)
    
    if len(history_df) > 0:
        # Plotly Trend Line
        chart_df = history_df.sort_values("id") # Chronological order
        fig = px.line(chart_df, x="date_taken", y="percentage", markers=True, 
                      title="Exam Scores Over Time",
                      labels={"date_taken": "Date", "percentage": "Score (%)"})
        
        # Add 70% passing benchmark line
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Passing Score (70%)", annotation_position="bottom right")
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(fig, use_container_width=True)

        # Historical Data Table
        st.markdown("#### Detailed History")
        display_df = history_df.copy()
        display_df["Result"] = display_df["passed"].apply(lambda x: "PASSED 🎉" if x == 1 else "FAIL ⚠️")
        display_df["Score"] = display_df["score"].astype(str) + " / " + display_df["total_questions"].astype(str)
        display_df["Percentage"] = display_df["percentage"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_df[["date_taken", "exam_title", "Score", "Percentage", "Result"]].rename(columns={"date_taken": "Date"}), use_container_width=True, hide_index=True)
    else:
        st.caption("No past attempts recorded. Take an exam to generate your readiness analytics.")

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
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    st_autorefresh(interval=10000, limit=None, key="timer_refresh")

    if st.sidebar.button("🔍 Review & Submit", type="primary", use_container_width=True):
        st.session_state.page = "pre_submit_review"
        st.rerun()

    st.markdown(f"### Question {cq + 1} of {total_q}")
    st.markdown(f"<p style='font-size: 18px;'>{row['Question Text']}</p>", unsafe_allow_html=True)
    
    options = [f"A) {row['Option 1 Text']}", f"B) {row['Option 2 Text']}", f"C) {row['Option 3 Text']}", f"D) {row['Option 4 Text']}"]
    current_val = st.session_state.user_answers.get(cq, None)

    selected = st.radio("Select choice:", options, index=options.index(current_val) if current_val in options else None, label_visibility="collapsed", key=f"radio_{cq}")
    if selected:
        st.session_state.user_answers[cq] = selected

    st.divider()

    c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
    with c1:
        if st.button("⬅️ Previous", disabled=(cq == 0), use_container_width=True):
            st.session_state.current_q -= 1
            st.rerun()
    with c2:
        is_flagged = st.checkbox("🚩 Flag for Review", value=(cq in st.session_state.flagged))
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

    st.title("📋 Pre-Submission Exam Review")
    st.divider()

    if unanswered_count > 0:
        st.warning(f"⚠️ **Attention:** You have **{unanswered_count} unanswered question(s)** and **{flagged_count} marked for review**.")
    else:
        st.success(f"✅ All **{total_q} questions** have been answered. You have **{flagged_count} marked for review**.")

    hc1, hc2, hc3, hc4 = st.columns([1, 2, 2, 2])
    hc1.markdown("**Question**")
    hc2.markdown("**Status**")
    hc3.markdown("**Flag**")
    hc4.markdown("**Action**")
    st.markdown("---")

    for idx in range(total_q):
        q_num = idx + 1
        is_ans = idx in st.session_state.user_answers
        is_flag = idx in st.session_state.flagged
        
        c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
        c1.write(f"**Q{q_num}**")
        c2.write("✅ Answered" if is_ans else "❌ **UNANSWERED**")
        c3.write("🚩 Flagged" if is_flag else "—")
        if c4.button(f"Return to Q{q_num}", key=f"jump_{idx}"):
            st.session_state.current_q = idx
            st.session_state.page = "exam"
            st.rerun()
        st.markdown("<hr style='margin: 0px; padding: 5px 0px;'>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        if st.button("🚀 Confirm & Final Submit for Grading", type="primary", use_container_width=True):
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
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': corr_opt = f"A) {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': corr_opt = f"B) {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': corr_opt = f"C) {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': corr_opt = f"D) {row['Option 4 Text']}"

        if ans == corr_opt: correct_count += 1

    percentage = (correct_count / total_q) * 100
    is_passed = percentage >= 70

    if not st.session_state.saved_attempt:
        save_attempt(st.session_state.student_name, st.session_state.student_email, st.session_state.exam_title, correct_count, total_q, percentage, is_passed)
        st.session_state.saved_attempt = True

    st.title("📊 PMP® Exam Score Report")
    st.caption(f"Candidate: {st.session_state.student_name} | {st.session_state.exam_title}")
    st.divider()

    col_chart, col_metrics = st.columns([1, 1])
    
    with col_chart:
        # Plotly Gauge Chart for Score
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = percentage,
            title = {'text': "Final Score (%)"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "#2E86C1"},
                'steps' : [
                    {'range': [0, 69.9], 'color': "#FFEBEE"},
                    {'range': [70, 100], 'color': "#E8F5E9"}],
                'threshold' : {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 70}
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_metrics:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric("Raw Score", f"{correct_count} / {total_q}")
        if is_passed:
            st.success("### 🎉 PASSED\nTarget Achieved (>=70%)")
        else:
            st.error("### ⚠️ NEEDS WORK\nBelow Target (<70%)")

    st.markdown("---")
    st.subheader("💡 Question Review & Mindset Explanations")

    for idx, row in df.iterrows():
        user_ans = st.session_state.user_answers.get(idx, "Unanswered")
        corr_opt = ""
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': corr_opt = f"A) {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': corr_opt = f"B) {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': corr_opt = f"C) {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': corr_opt = f"D) {row['Option 4 Text']}"

        is_corr = (user_ans == corr_opt)
        icon = "✅" if is_corr else "❌"

        with st.expander(f"{icon} Q{idx+1}: {'Correct' if is_corr else 'Incorrect'}"):
            st.markdown(f"**{row['Question Text']}**")
            st.markdown(f"**Your Answer:** `{user_ans}`")
            st.markdown(f"**Correct Answer:** `{corr_opt}`")
            st.info(f"**PMP Rationale:**\n\n{row['Question feedback']}")

    st.divider()
    if st.button("⬅️ Back to Dashboard", type="primary", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()