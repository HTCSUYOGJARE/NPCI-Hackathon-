# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from simulation_manager import HospitalSystem

st.set_page_config(page_title="Pravega AI", layout="wide")

if 'system' not in st.session_state:
    st.session_state['system'] = HospitalSystem()
    st.session_state['schedule'] = None

st.title("🏥 Smart OR Command Center")

# SIDEBAR
st.sidebar.subheader("1. Setup")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=['csv'])
if uploaded_file and st.sidebar.button("Generate Schedule"):
    st.session_state['schedule'] = st.session_state['system'].start_day(uploaded_file)
    st.success("Schedule Ready!")

st.sidebar.divider()
st.sidebar.subheader("2. Live Ops")

if st.session_state['schedule'] is not None:
    tab1, tab2, tab3 = st.sidebar.tabs(["Delay Start", "Duration", "Emergency"])
    
    # 1. DELAY START
    with tab1:
        st.write("**Surgeon/Patient Late?**")
        p_list = st.session_state['schedule']['Patient ID'].tolist()
        p_id = st.selectbox("Select Patient", p_list, key="start")
        
        delay = st.number_input("Minutes to ADD to Scheduled Start:", 0, 180, 15) 
        cur_time = st.time_input("Current Time Check", value=None, key="time1")
        
        if st.button("Apply Start Delay"):
            if cur_time:
                t_str = f"{cur_time.hour}:{cur_time.minute}"
                try:
                    new_sched = st.session_state['system'].handle_start_delay(p_id, delay, t_str)
                    if new_sched is None:
                        st.error("❌ Impossible Move!")
                    else:
                        st.session_state['schedule'] = new_sched
                        st.success("✅ Start Time Updated!")
                        st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    # 2. DURATION CHANGE
    with tab2:
        st.write("**Surgery Ending Early/Late?**")
        p_id_dur = st.selectbox("Patient", p_list, key="dur")
        dur_change = st.slider("Adjust Duration (Mins)", -180, 180, 0, 15)
        cur_time_2 = st.time_input("Current Time Check", value=None, key="time2")
        
        if st.button("Update Duration"):
            if cur_time_2:
                t_str = f"{cur_time_2.hour}:{cur_time_2.minute}"
                new_sched = st.session_state['system'].handle_duration_change(p_id_dur, dur_change, t_str)
                if new_sched is not None:
                    st.session_state['schedule'] = new_sched
                    st.success("✅ Duration Updated!")
                    st.rerun()

    # 3. EMERGENCY
    with tab3:
        st.write("**Code Red Admission**")
        em_type = st.selectbox("Type", ["Neurological", "Cardiovascular", "Orthopedic", "General"])
        em_time = st.time_input("Arrival Time", value=None, key="time3")
        if st.button("Admit to OR-11"):
            if em_time:
                t_str = f"{em_time.hour}:{em_time.minute}"
                new_sched = st.session_state['system'].handle_emergency_admission(em_type, t_str)
                st.session_state['schedule'] = new_sched
                st.rerun()

# CHART
if st.session_state['schedule'] is not None:
    df = st.session_state['schedule']
    df['Start'] = pd.to_datetime('2024-01-01 ' + df['Start Time'])
    df['Finish'] = pd.to_datetime('2024-01-01 ' + df['End Time'])
    
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Room", color="Surgeon", text="Patient ID")
    fig.update_yaxes(categoryorder="category ascending")
    st.plotly_chart(fig, use_container_width=True)
