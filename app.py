import streamlit as st
import pandas as pd
import plotly.express as px
from simulation_manager import HospitalSystem

st.set_page_config(page_title="Pravega AI: OR Command Center", layout="wide", page_icon="🏥")

if 'system' not in st.session_state:
    st.session_state['system'] = HospitalSystem()
    st.session_state['schedule'] = None

# --- SIDEBAR ---
st.sidebar.title("🏥 Ops Control")

# 1. SETUP
st.sidebar.subheader("1. Setup Phase")
uploaded_file = st.sidebar.file_uploader("Upload Daily Manifest (CSV)", type=['csv'])
if uploaded_file and st.sidebar.button("☀️ Generate 8:00 AM Schedule"):
    with st.spinner("Optimizing... (Including 30min Surgeon Breaks)"):
        schedule = st.session_state['system'].start_day(uploaded_file)
        st.session_state['schedule'] = schedule
    st.sidebar.success("Schedule Ready!")

st.sidebar.divider()

# 2. LIVE OPS
st.sidebar.subheader("2. Live Operations")

if st.session_state['schedule'] is not None:
    # Use Tabs for cleaner UI
    tab1, tab2, tab3 = st.sidebar.tabs(["⏱️ Delay Start", "⏳ Duration", "🚨 Emergency"])
    
    # TAB 1: Start Delay (Surgeon/Patient Late)
    with tab1:
        st.write("**Scenario:** Surgeon stuck in traffic / Patient late.")
        p_list = st.session_state['schedule']['Patient ID'].tolist()
        p_id_start = st.selectbox("Select Patient", p_list, key="start_p")
        late_mins = st.number_input("Late Arrival (Minutes)", 0, 240, 60, step=15)
        cur_time_1 = st.time_input("Current Time", value=None, key="t1")
        
        if st.button("Update Start Time"):
            if cur_time_1:
                t_str = f"{cur_time_1.hour}:{cur_time_1.minute}"
                new_sched = st.session_state['system'].handle_start_delay(p_id_start, late_mins, t_str)
                st.session_state['schedule'] = new_sched
                st.rerun()

    # TAB 2: Duration Change (Surgery Early/Late)
    with tab2:
        st.write("**Scenario:** Surgery finished early or complication occurred.")
        p_id_dur = st.selectbox("Select Patient", p_list, key="dur_p")
        # Range -180 to +180 as requested
        dur_change = st.slider("Adjust Duration (Mins)", -180, 180, 0, 15)
        cur_time_2 = st.time_input("Current Time", value=None, key="t2")
        
        if st.button("Update Duration"):
            if cur_time_2:
                t_str = f"{cur_time_2.hour}:{cur_time_2.minute}"
                new_sched = st.session_state['system'].handle_duration_change(p_id_dur, dur_change, t_str)
                st.session_state['schedule'] = new_sched
                st.rerun()

    # TAB 3: Emergency
    with tab3:
        st.write("**Scenario:** Code Red Admission.")
        em_type = st.selectbox("Type", ["Neurological", "Cardiovascular", "Orthopedic", "General"])
        em_time = st.time_input("Arrival Time", value=None, key="t3")
        
        if st.button("🚑 Admit to OR-11"):
            if em_time:
                t_str = f"{em_time.hour}:{em_time.minute}"
                with st.spinner("Calling Visiting Surgeons if needed..."):
                    new_sched = st.session_state['system'].handle_emergency_admission(em_type, t_str)
                    st.session_state['schedule'] = new_sched
                st.rerun()

# --- MAIN DASHBOARD ---
st.title("🏥 Pravega: Smart OR Command Center")

if st.session_state['schedule'] is not None:
    df = st.session_state['schedule']
    
    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", len(df))
    c2.metric("Day Ends At", df['End Time'].max())
    
    # Check Visiting Surgeon Usage
    visiting = df['Surgeon'].str.contains("Visiting").sum()
    c3.metric("Visiting Surgeons", visiting)
    
    c4.metric("Emergency OT", "Active" if "OR-11 (Emerg)" in df['Room'].values else "Standby")

    # GANTT CHART
    df['Start'] = pd.to_datetime('2024-01-01 ' + df['Start Time'])
    df['Finish'] = pd.to_datetime('2024-01-01 ' + df['End Time'])
    
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Room", color="Surgeon", text="Patient ID",
        hover_data=["Type", "Duration", "Risk (ASA)"], height=700,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig.update_yaxes(categoryorder="category ascending")
    fig.layout.xaxis.type = 'date'
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Detailed Schedule"):
        st.dataframe(df)
else:
    st.info("👈 Upload 'patients_today.csv' to initialize the 8:00 AM Plan.")
