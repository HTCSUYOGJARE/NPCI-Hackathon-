import pandas as pd
import joblib
from scheduler_engine import EnterpriseScheduler
from hospital_config import ROOMS, SURGEONS, EQUIPMENT

class HospitalSystem:
    def __init__(self):
        self.scheduler = EnterpriseScheduler(ROOMS, SURGEONS, EQUIPMENT)
        self.current_schedule = None
        self.active_patients = []
        
        try:
            self.artifacts = joblib.load("surgery_model_artifacts.pkl")
            self.model = self.artifacts['model']
        except:
            self.model = None

    def predict_duration(self, patient_row):
        if not self.model: return 120
        try:
            # Simple fallback encoding for demo
            return 120 
        except:
            return 120

    def start_day(self, csv_file):
        df = pd.read_csv(csv_file)
        patients_payload = []
        for _, row in df.iterrows():
            pred_duration = self.predict_duration(row)
            p_obj = {
                'id': row['PatientID'],
                'type': row['SurgeryType'],
                'surgeon': row['Surgeon'],
                'duration': pred_duration,
                'asa_score': row['ASA_Score'],
                'needs_c_arm': row.get('Needs_CArm', False),
                'needs_robot': row.get('Needs_Robot', False),
                'ready_time': 480 # Default: Everyone ready at 8:00 AM
            }
            patients_payload.append(p_obj)
            
        self.active_patients = patients_payload
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule

    def handle_emergency_admission(self, p_type, current_time_str):
        # 1. Logic to swap surgeon if busy (Visiting Team)
        h, m = map(int, current_time_str.split(':'))
        now_mins = h * 60 + m
        
        surgeon_map = {'Neurological': 'Dr. Strange', 'Cardiovascular': 'Dr. Yang', 'Orthopedic': 'Dr. Torres', 'General': 'Dr. Grey', 'Cosmetic': 'Dr. Avery'}
        main_surgeon = surgeon_map.get(p_type, 'Dr. House')
        visiting_surgeon = f"Visiting {p_type.split()[0]}"
        
        # Check if main surgeon is busy
        is_busy = False
        if self.current_schedule is not None:
            doc_sched = self.current_schedule[self.current_schedule['Surgeon'] == main_surgeon]
            for _, row in doc_sched.iterrows():
                if row['start_mins'] <= now_mins <= row['end_mins']:
                    is_busy = True
                    break
        
        final_surgeon = visiting_surgeon if is_busy else main_surgeon
        
        # 2. Add Emergency Patient
        new_p = {
            'id': f'EMERG-{len(self.active_patients)+1}',
            'type': p_type,
            'surgeon': final_surgeon,
            'duration': 120,
            'asa_score': 4,
            'fixed_room': 'OR-11 (Emerg)', # FORCE OR-11
            'min_start_time': now_mins
        }
        self.active_patients.append(new_p)
        return self.recalculate_schedule(now_mins)

    # --- NEW: Handles "Surgeon Late" or "Patient Late" ---
    def handle_start_delay(self, patient_id, delay_mins, current_time_str):
        h, m = map(int, current_time_str.split(':'))
        now_mins = h * 60 + m
        
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        if target_p:
            # Set their new Ready Time (e.g., 8:00 AM + 120 mins = 10:00 AM)
            # Or Current Time + Delay
            target_p['ready_time'] = now_mins + delay_mins
            
        return self.recalculate_schedule(now_mins)

    # --- NEW: Handles "Surgery Finished Early/Late" ---
    def handle_duration_change(self, patient_id, change_mins, current_time_str):
        h, m = map(int, current_time_str.split(':'))
        now_mins = h * 60 + m
        
        target_p = next((p for p in self.active_patients if p['id'] == patient_id), None)
        if target_p:
            # Duration cannot be less than 30 mins
            target_p['duration'] = max(30, target_p['duration'] + change_mins)
            
        return self.recalculate_schedule(now_mins)

    def recalculate_schedule(self, current_mins):
        # Pinning Logic: Lock past events
        if self.current_schedule is not None:
            for p in self.active_patients:
                if 'EMERG' in p['id']: continue 
                
                sched_row = self.current_schedule[self.current_schedule['Patient ID'] == p['id']]
                if sched_row.empty: continue
                
                start_mins = sched_row.iloc[0]['start_mins']
                assigned_room = sched_row.iloc[0]['Room']
                
                # If surgery started in the past, LOCK IT
                if start_mins < current_mins:
                    p['fixed_start'] = start_mins
                    p['fixed_room'] = assigned_room
                else:
                    p.pop('fixed_start', None)
                    p.pop('fixed_room', None)
                    p['min_start_time'] = current_mins
        
        self.current_schedule = self.scheduler.solve(self.active_patients)
        return self.current_schedule
