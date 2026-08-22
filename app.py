import streamlit as st
import pandas as pd
import sqlite3
import datetime
import time
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# Configure page without emojis
st.set_page_config(page_title="PMP Certification Portal", layout="wide", initial_sidebar_state="expanded")

# --- ENTERPRISE CSS THEME ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
        background-color: #F8F9FA !important; 
    }
    
    h1, h2, h3 {
        color: #202124 !important; 
        font-weight: 600 !important;
        letter-spacing: -0.5px;
    }
    h4, h5, h6, p { color: #3C4043 !important; }
    
    /* Primary Buttons (Tech Blue) */
    button[data-testid="baseButton-primary"] {
        background-color: #1A73E8 !important; 
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        box-shadow: none !important;
        transition: background-color 0.2s ease !important;
    }
    button[data-testid="baseButton-primary"]:hover {
        background-color: #1557B0 !important;
    }
    
    /* Secondary Buttons (White with Grey Border) */
    button[data-testid="baseButton-secondary"] {
        background-color: #FFFFFF !important;
        color: #5F6368 !important;
        border: 1px solid #DADCE0 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        box-shadow: none !important;
        transition: background-color 0.2s ease !important;
    }
    button[data-testid="baseButton-secondary"]:hover {
        background-color: #F1F3F4 !important;
        color: #202124 !important;
    }

    /* Form Cards (Login Box) */
    [data-testid="stForm"] {
        background-color: #FFFFFF !important;
        border: 1px solid #DADCE0 !important;
        border-radius: 8px !important;
        padding: 32px !important;
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.1) !important;
    }

    /* Interactive Radio Cards */
    .stRadio > label { 
        font-size: 16px !important; 
        font-weight: 600 !important; 
        color: #202124 !important; 
        margin-bottom: 12px !important; 
    }
    .stRadio div[role="radiogroup"] > label {
        padding: 16px 20px !important; 
        background-color: #FFFFFF !important; 
        border: 1px solid #DADCE0 !important; 
        border-radius: 8px !important; 
        margin-bottom: 12px !important; 
        transition: all 0.2s ease-in-out !important;
        color: #3C4043 !important;
        font-weight: 500 !important;
        cursor: pointer !important;
    }
    .stRadio div[role="radiogroup"] > label:hover {
        background-color: #F8F9FA !important;
        border-color: #1A73E8 !important;
    }
    
    /* Timer Display */
    .timer-text {
        font-size: 20px; 
        font-weight: 600; 
        color: #1A73E8; 
        text-align: center; 
        padding: 16px; 
        background: #E8F0FE; 
        border-radius: 8px; 
        border: 1px solid #D2E3FC;
        margin-bottom: 20px;
    }
    
    /* Clean Text Inputs */
    .stTextInput input {
        border-radius: 6px !important;
        border: 1px solid #DADCE0 !important;
        padding: 12px !important;
        font-weight: 500 !important;
        color: #202124 !important;
    }
    .stTextInput input:focus {
        border-color: #1A73E8 !important;
        box-shadow: 0 0 0 1px #1A73E8 !important;
    }
    
    hr { border-top: 1px solid #E8EAED !important; }
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
        st.title("PMP Certification Portal")
        st.caption("Computer-Based Testing Environment | 2026 Standards")
        st.divider()
        with st.form("login_form"):
            st.markdown("### Candidate Authentication")
            name = st.text_input("Full Legal Name", placeholder="e.g. Sagar Sharma")
            email = st.text_input("Registered Email Address", placeholder="e.g. sagar@example.com")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Access Dashboard", type="primary", use_container_width=True):
                if name.strip() and email.strip():
                    st.session_state.student_name = name.strip()
                    st.session_state.student_email = email.strip()
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Authentication Error: Name and Email are required.")

# -------------------------------------------------------------
# PAGE 2: DASHBOARD & TREND ANALYTICS
# -------------------------------------------------------------
elif st.session_state.page == "dashboard":
    st.sidebar.markdown(f"**Candidate:** {st.session_state.student_name}")
    st.sidebar.markdown(f"**ID:** {st.session_state.student_email}")
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if st.sidebar.button("Secure Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.title("Performance Dashboard")
    st.divider()

    st.markdown("### Authorized Assessments")
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
        st.button("Launch Specialization", disabled=True, use_container_width=True)

    with c3:
        st.warning("**Full Certification Mock**\n\n180 Questions | 230 Minutes\n\nComplete CBT replication.")
        st.button("Launch Full Mock", disabled=True, use_container_width=True)

    st.markdown("---")
    st.markdown("### Readiness Analytics")
    history_df = get_student_history(st.session_state.student_email)
    
    if len(history_df) > 0:
        chart_df = history_df.sort_values("id")
        fig = px.line(chart_df, x="date_taken", y="percentage", markers=True, 
                      title="Cumulative Performance Trend",
                      labels={"date_taken": "Date", "percentage": "Score (%)"},
                      color_discrete_sequence=["#1A73E8"]) 
        
        fig.add_hline(y=70, line_dash="dash", line_color="#C5221F", annotation_text="Target Score (70%)", annotation_position="bottom right")
        fig.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#F8F9FA", yaxis=dict(range=[0, 105], gridcolor="#F1F3F4"), xaxis=dict(gridcolor="#F1F3F4"))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Assessment History")
        display_df = history_df.copy()
        display_df["Result"] = display_df["passed"].apply(lambda x: "PASS" if x == 1 else "REVIEW")
        display_df["Score"] = display_df["score"].astype(str) + " / " + display_df["total_questions"].astype(str)
        display_df["Percentage"] = display_df["percentage"].apply(lambda x: f"{x:.1f}%")
        st.dataframe(display_df[["date_taken", "exam_title", "Score", "Percentage", "Result"]].rename(columns={"date_taken": "Date"}), use_container_width=True, hide_index=True)
    else:
        st.caption("Complete an assessment above to generate your predictive analytics.")

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
    st_autorefresh(interval=10000, limit=None, key="timer_refresh")

    if st.sidebar.button("Review Progress", use_container_width=True):
        st.session_state.page = "pre_submit_review"
        st.rerun()

    st.markdown(f"#### Item {cq + 1} of {total_q}")
    st.markdown(f"<p style='font-size: 18px; font-weight: 600; margin-bottom: 24px; color: #202124;'>{row['Question Text']}</p>", unsafe_allow_html=True)
    
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
    st.sidebar.markdown(f"<div class='timer-text'>Time Remaining<br>{mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)
    st_autorefresh(interval=10000, limit=None, key="timer_refresh_review")

    st.title("Pre-Submission Review")
    st.divider()

    if unanswered_count > 0:
        st.warning(f"Notice: You have {unanswered_count} unanswered items.")
    else:
        st.success("All items answered.")

    hc1, hc2, hc3, hc4 = st.columns([1, 2, 2, 2])
    hc1.markdown("**Item**")
    hc2.markdown("**Status**")
    hc3.markdown("**Flagged**")
    hc4.markdown("**Action**")
    st.markdown("---")

    for idx in range(total_q):
        q_num = idx + 1
        is_ans = idx in st.session_state.user_answers
        is_flag = idx in st.session_state.flagged
        
        c1, c2, c3, c4 = st.columns([1, 2, 2, 2])
        c1.write(f"Item {q_num}")
        c2.write("Answered" if is_ans else "Incomplete")
        c3.write("Yes" if is_flag else "—")
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
# PAGE 5: SCORE & EXPLANATIONS
# -------------------------------------------------------------
elif st.session_state.page == "results":
    df = st.session_state.active_df
    total_q = len(df)
    correct_count = 0
    
    # Robust comparison logic (strips prefixes and compares text only)
    for idx, row in df.iterrows():
        raw_ans = st.session_state.user_answers.get(idx, "Unanswered")
        raw_corr_opt = ""
        
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': raw_corr_opt = f"A. {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': raw_corr_opt = f"B. {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': raw_corr_opt = f"C. {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': raw_corr_opt = f"D. {row['Option 4 Text']}"

        clean_user = raw_ans[3:].strip() if raw_ans != "Unanswered" else "Unanswered"
        clean_corr = raw_corr_opt[3:].strip()

        if clean_user == clean_corr: 
            correct_count += 1

    percentage = (correct_count / total_q) * 100
    is_passed = percentage >= 70

    if not st.session_state.saved_attempt:
        save_attempt(st.session_state.student_name, st.session_state.student_email, st.session_state.exam_title, correct_count, total_q, percentage, is_passed)
        st.session_state.saved_attempt = True

    st.title("Official Score Report")
    st.divider()

    col_chart, col_metrics = st.columns([1, 1])
    
    with col_chart:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = percentage,
            title = {'text': "Final Score (%)", 'font': {'size': 20, 'color': '#202124'}},
            number = {'font': {'color': '#1A73E8', 'weight': 'bold'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#DADCE0"},
                'bar': {'color': "#4285F4"}, 
                'steps' : [
                    {'range': [0, 69.9], 'color': "#FCE8E6"}, 
                    {'range': [70, 100], 'color': "#E6F4EA"}], 
                'threshold' : {'line': {'color': "#EA4335", 'width': 4}, 'thickness': 0.75, 'value': 70} 
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_metrics:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.metric("Items Correct", f"{correct_count} / {total_q}")
        if is_passed:
            st.success("Target Proficiency Achieved: PASS")
        else:
            st.error("Target Proficiency Not Met: REVIEW REQUIRED")

    st.markdown("---")
    st.subheader("Item Analysis & Rationales")

    for idx, row in df.iterrows():
        user_ans = st.session_state.user_answers.get(idx, "Unanswered")
        corr_opt = ""
        if str(row.get('Option 1 Correct', '')).strip().lower() == 'yes': corr_opt = f"A. {row['Option 1 Text']}"
        elif str(row.get('Option 2 Correct', '')).strip().lower() == 'yes': corr_opt = f"B. {row['Option 2 Text']}"
        elif str(row.get('Option 3 Correct', '')).strip().lower() == 'yes': corr_opt = f"C. {row['Option 3 Text']}"
        elif str(row.get('Option 4 Correct', '')).strip().lower() == 'yes': corr_opt = f"D. {row['Option 4 Text']}"

        clean_user = user_ans[3:].strip() if user_ans != "Unanswered" else "Unanswered"
        clean_corr = corr_opt[3:].strip()
        is_corr = (clean_user == clean_corr)

        # HTML Rendering for Exact Pastel Colors
        if is_corr:
            bg_color = "#E6F4EA"
            border_color = "#CEEAD6"
            text_color = "#137333"
            status_text = "Correct"
            
            html_card = f'''
            <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <h4 style="color: {text_color}; margin-top: 0; margin-bottom: 12px; font-size: 16px; font-weight: 700;">Item {idx+1}: {status_text}</h4>
                <p style="font-weight: 600; color: #202124; font-size: 16px; margin-bottom: 16px;">{row['Question Text']}</p>
                <p style="margin-bottom: 6px; color: {text_color}; font-size: 15px;"><b>Candidate Selection:</b> {user_ans}</p>
                <p style="margin-bottom: 16px; color: {text_color}; font-size: 15px;"><b>Correct Selection:</b> {corr_opt}</p>
                <div style="background-color: rgba(255,255,255,0.7); padding: 14px; border-radius: 6px; color: #3C4043; font-size: 15px; border-left: 4px solid {text_color};">
                    <b>Rationale:</b> {row['Question feedback']}
                </div>
            </div>
            '''
        else:
            bg_color = "#FCE8E6"
            border_color = "#FAD2CF"
            wrong_color = "#C5221F"
            right_color = "#137333"
            status_text = "Review"
            
            html_card = f'''
            <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <h4 style="color: {wrong_color}; margin-top: 0; margin-bottom: 12px; font-size: 16px; font-weight: 700;">Item {idx+1}: {status_text}</h4>
                <p style="font-weight: 600; color: #202124; font-size: 16px; margin-bottom: 16px;">{row['Question Text']}</p>
                <p style="margin-bottom: 6px; color: {wrong_color}; font-size: 15px;"><b>Candidate Selection:</b> {user_ans}</p>
                <p style="margin-bottom: 16px; color: {right_color}; font-size: 15px;"><b>Correct Selection:</b> {corr_opt}</p>
                <div style="background-color: rgba(255,255,255,0.7); padding: 14px; border-radius: 6px; color: #3C4043; font-size: 15px; border-left: 4px solid {right_color};">
                    <b>Rationale:</b> {row['Question feedback']}
                </div>
            </div>
            '''
            
        st.markdown(html_card, unsafe_allow_html=True)

    st.divider()
    if st.button("Return to Dashboard", type="primary", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()
