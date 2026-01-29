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
        try:
            self.artifacts = joblib.load("surgery_model_artifacts.pkl")
            self.model = self.artifacts['model']
        except: self.model = None

    def predict_duration(self, patient_row):
        return 120 # Fallback 

    def start_day(self, csv_file):
        df = pd.read_csv(csv_file)
        self.active_patients = []
        for _, row in df.iterrows():
            self.active_patients.append({
                'id': row['PatientID'], 'type': row['SurgeryType'],
                'surgeon': row['Surgeon'], 'duration': 120,
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
            # FIX: Base new time on SCHEDULED time, not current time
            scheduled_start = 480 
            if self.current_schedule is not None:
                row = self.current_schedule[self.current_schedule['Patient ID'] == patient_id]
                if not row.empty:
                    scheduled_start = row.iloc[0]['start_mins']
            
            # New Ready Time = Scheduled Start + Delay
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
        
        # Simple Map
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
                
                # CRITICAL: UNPIN Logic
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
