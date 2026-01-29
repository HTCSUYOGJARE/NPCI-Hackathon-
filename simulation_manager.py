# simulation_manager.py
import pandas as pd
import joblib
from scheduler_engine import EnterpriseScheduler
from hospital_config import ROOMS, SURGEONS, EQUIPMENT

class HospitalSystem:
    def __init__(self):
        self.scheduler = EnterpriseScheduler(ROOMS, SURGEONS, EQUIPMENT)
        self.current_schedule = None
        self.active_patients = [] # Stores full dicts
        
        # Load AI Model
        try:
            self.artifacts = joblib.load("surgery_model_artifacts.pkl")
            self.model = self.artifacts['model']
            print("✅ AI Model Loaded Successfully")
        except:
            print("⚠️ Model not found. Using fallback durations.")
            self.model = None

    def predict_duration(self, patient_row):
        """Uses XGBoost to predict duration based on patient data"""
        if not self.model: return 120 # Fallback
        
        # Prepare input vector (Must match training columns exactly)
        # Input: Age, Gender(0/1), BMI, SurgeryType(0-3), Anesthesia(0/1), ASA, Comorb
        try:
            # We use the encoders saved in artifacts to transform text -> int
            # Inside simulation_manager.py -> predict_duration method
            # Inside simulation_manager.py -> predict_duration method
            input_df = pd.DataFrame([{
                'Age': patient_row['Age'],
                'Gender': self.artifacts['le_gender'].transform([patient_row['Gender']])[0],
                'BMI': patient_row['BMI'],
                'SurgeryType': self.artifacts['le_surgery'].transform([patient_row['SurgeryType']])[0],
                'AnesthesiaType': self.artifacts['le_anesthesia'].transform([patient_row['AnesthesiaType']])[0],
                'ASA_Score': patient_row['ASA_Score'],
                'Has_Comorbidity': patient_row['Has_Comorbidity'] # Direct mapping now!
            }])
            return int(self.model.predict(input_df)[0])
        except Exception as e:
            print(f"Prediction Error for {patient_row['PatientID']}: {e}")
            return 90 # Safe fallback

    def start_day(self, csv_file):
        """1. Load CSV -> 2. AI Predict -> 3. Optimize"""
        df = pd.read_csv(csv_file)
        
        patients_payload = []
        for _, row in df.iterrows():
            # 1. AI Prediction
            pred_duration = self.predict_duration(row)
            
            # 2. Build Patient Object
            p_obj = {
                'id': row['PatientID'],
                'type': row['SurgeryType'],
                'surgeon': row['Surgeon'],
                'duration': pred_duration,
                'asa_score': row['ASA_Score'],
                'needs_c_arm': row.get('Needs_CArm', False),
                'needs_robot': row.get('Needs_Robot', False)
            }
            patients_payload.append(p_obj)
            
        self.active_patients = patients_payload
        
        # 3. Optimize
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule

    def handle_emergency(self, patient_id, added_delay, current_time_hhmm):
        """Re-optimizes schedule while pinning past events"""
        print(f"🚨 Handling Delay: {patient_id} +{added_delay} mins")
        
        # Convert HH:MM to minutes
        h, m = map(int, current_time_hhmm.split(':'))
        current_mins = h * 60 + m
        
        # 1. Update Duration
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        if target_p:
            target_p['duration'] += added_delay
            
        # 2. Pin Logic
        if self.current_schedule is not None:
            for p in self.active_patients:
                # Find scheduled start time
                sched_row = self.current_schedule[self.current_schedule['Patient ID'] == p['id']]
                if sched_row.empty: continue
                
                start_mins = sched_row.iloc[0]['start_mins']
                assigned_room = sched_row.iloc[0]['Room']
                
                if start_mins < current_mins:
                    # STARTED IN PAST -> PIN IT
                    p['fixed_start'] = start_mins
                    p['fixed_room'] = assigned_room
                else:
                    # FUTURE -> FREE TO MOVE (But not before now)
                    p.pop('fixed_start', None)
                    p.pop('fixed_room', None)
                    p['min_start_time'] = current_mins

        # 3. Re-Solve
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule