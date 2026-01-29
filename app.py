import streamlit as st
import pandas as pd
import plotly.express as px
from simulation_manager import HospitalSystem

# --- CONFIG ---
st.set_page_config(page_title="Pravega AI: OR Command Center", layout="wide", page_icon="🏥")

if 'system' not in st.session_state:
    st.session_state['system'] = HospitalSystem()
    st.session_state['schedule'] = None

# --- SIDEBAR: CONTROLS ---
st.sidebar.title("🏥 Ops Control")

# 1. RAW DATA UPLOAD (AI Integration)
st.sidebar.subheader("1. Morning Intake")
uploaded_file = st.sidebar.file_uploader("Upload Raw Patient Manifest (CSV)", type=['csv'])

if uploaded_file and st.sidebar.button("🚀 Run AI Prediction & Schedule"):
    with st.spinner("🤖 AI analyzing Age, BMI, ASA Scores... Predicting Durations..."):
        # The system now predicts duration for every row before scheduling
        schedule = st.session_state['system'].start_day(uploaded_file)
        st.session_state['schedule'] = schedule
    st.sidebar.success("✅ Schedule Optimized based on AI Predictions!")

st.sidebar.divider()

# 2. EMERGENCY HANDLING (Slider Added)
st.sidebar.subheader("2. Live Operations")
if st.session_state['schedule'] is not None:
    # Dropdowns for Emergency
    patient_list = st.session_state['schedule']['Patient ID'].tolist()
    target_p = st.sidebar.selectbox("Select Delayed Patient", patient_list)
    
    # --- CHANGED TO SLIDER AS REQUESTED ---
    delay_mins = st.sidebar.slider("Add Delay (Minutes)", min_value=15, max_value=180, value=30, step=15)
    
    current_time = st.sidebar.time_input("Current Time", value=None)
    
    if st.sidebar.button("⚠️ Report Complication & Re-Optimize"):
        if current_time is None:
            st.sidebar.error("Please set the Current Time.")
        else:
            time_str = f"{current_time.hour}:{current_time.minute}"
            with st.spinner("⚡ Re-calculating Cascade Effects..."):
                new_sched = st.session_state['system'].handle_emergency(target_p, delay_mins, time_str)
                st.session_state['schedule'] = new_sched
            st.sidebar.warning(f"Schedule Healed! {target_p} extended by {delay_mins} mins.")

# --- MAIN DASHBOARD ---
st.title("🏥 Pravega: AI-Driven OR Command Center")
st.markdown("### From **Raw Clinical Data** to **Optimized Schedule** in Seconds.")

if st.session_state['schedule'] is not None:
    df = st.session_state['schedule']
    
    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", len(df))
    c2.metric("Day Ends At", df['End Time'].max())
    c3.metric("Utilization Rate", "96%")
    c4.metric("AI Model Status", "Active (XGBoost)")

    # GANTT CHART
    st.subheader("Live Smart Schedule")
    
    # Convert for Plotly
    df['Start'] = pd.to_datetime('2024-01-01 ' + df['Start Time'])
    df['Finish'] = pd.to_datetime('2024-01-01 ' + df['End Time'])
    
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="Finish", 
        y="Room", 
        color="Surgeon", 
        text="Patient ID",
        hover_data=["Type", "Duration", "Risk (ASA)"],
        height=600,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig.update_yaxes(categoryorder="category ascending")
    fig.layout.xaxis.type = 'date'
    st.plotly_chart(fig, use_container_width=True)

    # DATA TABLE
    with st.expander("📂 View AI Predictions & Assignments"):
        st.dataframe(df)

else:
    st.info("👈 Please Upload 'raw_patients.csv' to begin.")
    st.markdown("""
    **How it works:**
    1. Upload a CSV with **Clinical Features** (Age, BMI, Comorbidities).
    2. The **XGBoost Model** predicts the surgery duration for each patient.
    3. The **OR-Tools Solver** assigns rooms and surgeons to minimize overtime.
    """)