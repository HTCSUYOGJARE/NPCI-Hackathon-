# simulation_manager.py
import pandas as pd
import joblib
from scheduler_engine import EnterpriseScheduler
from hospital_config import ROOMS, SURGEONS, EQUIPMENT

class HospitalSystem:
    def __init__(self):
        self.scheduler = EnterpriseScheduler(ROOMS, SURGEONS, EQUIPMENT)
        self.current_schedule = None
        self.active_patients = []
        
        # Load AI Model
        try:
            self.artifacts = joblib.load("surgery_model_artifacts.pkl")
            self.model = self.artifacts['model']
            print("✅ AI Model Loaded Successfully")
        except:
            print("⚠️ Model not found. Using fallback durations.")
            self.model = None

    def predict_duration(self, patient_row):
        """
        Restored AI Logic: Uses the XGBoost model to predict duration.
        """
        if not self.model: 
            return 120 # Fallback if model missing
        
        try:
            # Helper to handle "Unseen Labels" without crashing
            # If the model has never seen "RobotAssisted", it maps it to a default
            def safe_transform(encoder, value):
                try:
                    return encoder.transform([value])[0]
                except:
                    return encoder.transform([encoder.classes_[0]])[0]

            # 1. Prepare Input Vector (Exact columns from training)
            input_df = pd.DataFrame([{
                'Age': patient_row['Age'],
                'Gender': safe_transform(self.artifacts['le_gender'], patient_row['Gender']),
                'BMI': patient_row['BMI'],
                'SurgeryType': safe_transform(self.artifacts['le_surgery'], patient_row['SurgeryType']),
                'AnesthesiaType': safe_transform(self.artifacts['le_anesthesia'], patient_row['AnesthesiaType']),
                'ASA_Score': patient_row['ASA_Score'],
                'Has_Comorbidity': int(patient_row.get('Has_Comorbidity', 0))
            }])
            
            # 2. Predict
            pred = self.model.predict(input_df)[0]
            return int(max(30, pred)) # Minimum 30 mins
            
        except Exception as e:
            print(f"⚠️ Prediction Error for {patient_row.get('PatientID', '?')}: {e}")
            return 120 # Safe Fallback

    def start_day(self, csv_file):
        df = pd.read_csv(csv_file)
        self.active_patients = []
        for _, row in df.iterrows():
            # CALL THE AI HERE
            pred_dur = self.predict_duration(row)
            
            self.active_patients.append({
                'id': row['PatientID'], 'type': row['SurgeryType'],
                'surgeon': row['Surgeon'], 
                'duration': pred_dur, # <--- AI PREDICTION IS USED HERE
                'asa_score': row['ASA_Score'], 
                'needs_c_arm': row.get('Needs_CArm', False),
                'needs_robot': row.get('Needs_Robot', False),
                'ready_time': 480 # 8:00 AM Default
            })
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule

    def handle_start_delay(self, patient_id, delay_mins, current_time_str):
        h, m = map(int, current_time_str.split(':'))
        now_mins = h * 60 + m
        
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        
        if target_p:
            # Logic: New Ready Time = Scheduled + Delay
            scheduled_start = 480 
            if self.current_schedule is not None:
                row = self.current_schedule[self.current_schedule['Patient ID'] == patient_id]
                if not row.empty:
                    scheduled_start = row.iloc[0]['start_mins']
            
            target_p['ready_time'] = max(scheduled_start + delay_mins, now_mins)
            
        # Unpin this specific patient
        return self.recalculate_schedule(now_mins, ignore_pinning_for=patient_id)

    def handle_duration_change(self, patient_id, change_mins, current_time_str):
        h, m = map(int, current_time_str.split(':'))
        now_mins = h * 60 + m
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        if target_p:
            target_p['duration'] = max(30, target_p['duration'] + change_mins)
        return self.recalculate_schedule(now_mins)

    def handle_emergency_admission(self, p_type, current_time_str):
        h, m = map(int, current_time_str.split(':'))
        now_mins = h * 60 + m
        
        main_surgeon = {'Neurological': 'Dr. Strange', 'Cardiovascular': 'Dr. Yang'}.get(p_type, 'Dr. House')
        
        self.active_patients.append({
            'id': f'EMERG-{len(self.active_patients)+1}',
            'type': p_type, 'surgeon': main_surgeon,
            'duration': 120, 'asa_score': 4,
            'fixed_room': 'OR-11 (Emerg)', 'min_start_time': now_mins
        })
        return self.recalculate_schedule(now_mins)

    def recalculate_schedule(self, current_mins, ignore_pinning_for=None):
        if self.current_schedule is not None:
            for p in self.active_patients:
                if 'EMERG' in p['id']: continue
                
                # UNPIN Logic
                if p['id'] == ignore_pinning_for:
                    p.pop('fixed_start', None)
                    p.pop('fixed_room', None)
                    p['min_start_time'] = current_mins
                    continue
                
                # Standard Pinning
                sched_row = self.current_schedule[self.current_schedule['Patient ID'] == p['id']]
                if not sched_row.empty:
                    start_mins = sched_row.iloc[0]['start_mins']
                    if start_mins < current_mins:
                        p['fixed_start'] = start_mins
                        p['fixed_room'] = sched_row.iloc[0]['Room']
                    else:
                        p.pop('fixed_start', None)
                        p.pop('fixed_room', None)
                        p['min_start_time'] = current_mins
        
        return self.scheduler.solve(self.active_patients)
