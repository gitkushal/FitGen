# streamlit_app.py
import streamlit as st
import requests, json
from io import BytesIO

API_BASE = "http://127.0.0.1:5000/api"

st.set_page_config(page_title="FitGenesis AI", layout="wide")
st.title("💪 FitGenesis")

# Sidebar: user
st.sidebar.header("User / Gamification")
user_email = st.sidebar.text_input("User id (email)", value="user1@example.com")
user_name = st.sidebar.text_input("Name", value="Kushal")
if st.sidebar.button("Create / Load user"):
    r = requests.post(f"{API_BASE}/user/create", json={"user_id": user_email, "name": user_name})
    st.sidebar.json(r.json())

if st.sidebar.button("Refresh progress"):
    r = requests.get(f"{API_BASE}/user/{user_email}")
    if r.status_code == 200:
        user = r.json()
        st.sidebar.metric("🔥 Streak", user.get("streak", 0))
        st.sidebar.metric("⭐ XP", user.get("xp", 0))
        st.sidebar.write("🏅 Badges:", user.get("badges", []))
    else:
        st.sidebar.warning("User not found")

st.sidebar.write("---")
if st.sidebar.button("Mark Today Complete (+10 XP)"):
    r = requests.post(f"{API_BASE}/user/{user_email}/complete", json={"note":"Completed AI plan"})
    st.sidebar.write(r.json())

if st.sidebar.button("Mark Upload (+20 XP)"):
    r = requests.post(f"{API_BASE}/user/{user_email}/upload", json={"note":"Uploaded MRI"})
    st.sidebar.write(r.json())

if st.sidebar.button("Leaderboard"):
    r = requests.get(f"{API_BASE}/leaderboard?top=10")
    st.sidebar.dataframe(r.json())

# Main area: upload
st.header("Upload MRI / Medical Report")
with st.form("upload_form"):
    uploaded_file = st.file_uploader("Choose PDF / Image / TXT", type=["pdf", "jpg", "jpeg", "png", "txt"])
    age = st.number_input("Age", min_value=8, max_value=120, value=30)
    bmi = st.number_input("BMI", min_value=10.0, max_value=60.0, value=24.0)
    condition = st.text_input("Known condition (optional)", value="")
    exp_level = st.selectbox("Experience level", ["Beginner", "Intermediate", "Advanced"])
    pain_level = st.slider("Pain level (0-10)", min_value=0, max_value=10, value=0)
    submit = st.form_submit_button("Analyze & Generate Plan")

if submit:
    if not uploaded_file:
        st.error("Upload a file first")
    else:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
        data = {
            "age": str(age),
            "bmi": str(bmi),
            "condition": condition,
            "experience_level": exp_level,
            "pain_level": str(pain_level),
            "user_id": user_email
        }
        with st.spinner("Analyzing with AI..."):
            r = requests.post(f"{API_BASE}/analyze", files=files, data=data)
        if r.status_code != 200:
            st.error("Server error: " + r.text)
        else:
            res = r.json()
            st.subheader("🧾 Extracted / AI Result")
            st.json(res)
            # show simple view of plan
            if "exercise_plan" in res:
                st.subheader("🏋️ Exercise Plan (summary)")
                for d in res["exercise_plan"]:
                    st.markdown(f"**Day {d.get('day')}**: {', '.join(d.get('exercises',[]))}")
            # button to download PDF
            if st.button("Download PDF Report"):
                rr = requests.post(f"{API_BASE}/report", json={"result": res})
                
                if rr.status_code == 200:
                    st.success("Report generated successfully.")
                    st.download_button(
                        label="📄 Click to save PDF",
                        data=rr.content,
                        file_name="FitGenesis_Report.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error("Unable to generate PDF.")


# Show history / demo leaderboard
st.markdown("---")
st.subheader("Demo Controls")
if st.button("Show last 5 users (leaderboard)"):
    r = requests.get(f"{API_BASE}/leaderboard?top=5")
    if r.status_code == 200:
        st.table(r.json())

st.markdown("---")
st.header("📊 Analytics Dashboard")
import pandas as pd
import plotly.express as px

st.markdown("### User Progress Analytics")

if st.button("Load Analytics"):
    # fetch user data
    r = requests.get(f"{API_BASE}/user/{user_email}")
    if r.status_code != 200:
        st.error("User not found. Create user first.")
    else:
        user = r.json()

        # ---------- SUMMARY PANEL ----------
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("⭐ XP", user.get("xp", 0))
        col2.metric("🔥 Streak", user.get("streak", 0))

        # level = xp // 100
        level = user.get("xp", 0) // 100
        col3.metric("🎮 Level", level)

        badges = ", ".join(user.get("badges", [])) or "None"
        col4.metric("🏅 Badges", badges)

        st.write("---")
        st.subheader("📅 Daily XP Trend")

        # ---------- DAILY XP TREND ----------
        hist = user.get("history", [])
        if len(hist) == 0:
            st.info("No history yet. Complete tasks to generate analytics.")
        else:
            df = pd.DataFrame(hist)
            # ensure date sorted
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            fig = px.line(df, x='date', y='xp', markers=True,
                          title="XP Earned Per Day",
                          labels={'xp': 'XP', 'date': 'Date'})
            st.plotly_chart(fig, use_container_width=True)

            # ---------- EVENT TYPE PIE CHART ----------
            st.subheader("🧠 Activity Distribution (uploads vs completions vs other)")
            pie = df['type'].value_counts().reset_index()
            pie.columns = ['activity_type', 'count']
            fig2 = px.pie(pie, names='activity_type', values='count',
                           title="Activity Breakdown")
            st.plotly_chart(fig2, use_container_width=True)

            # ---------- HISTORY TABLE ----------
            st.subheader("📜 Detailed History")
            st.dataframe(df[['date', 'type', 'xp', 'note']])

            st.write("---")
            st.subheader("🏆 Leaderboard Comparison")

            r2 = requests.get(f"{API_BASE}/leaderboard?top=20")
            if r2.status_code == 200:
                lb = pd.DataFrame(r2.json())

                if not lb.empty:
                    lb['rank'] = lb['xp'].rank(ascending=False, method='dense')
                    st.dataframe(lb[['name', 'user_id', 'xp', 'streak', 'rank']])

                    # find current user rank
                    match = lb[lb['user_id'] == user_email]
                    if not match.empty:
                        st.success(f"🏅 Your current rank: {int(match['rank'].values[0])}")
                    else:
                        st.info("User not found in leaderboard")
                else:
                    st.info("Leaderboard empty")
            else:
                st.error("Failed to load leaderboard")
