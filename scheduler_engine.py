# scheduler_engine.py
from ortools.sat.python import cp_model
import pandas as pd
from hospital_config import CONSTANTS

class EnterpriseScheduler:
    def __init__(self, rooms, surgeons_dict, equipment_caps):
        self.rooms = rooms
        self.surgeons = surgeons_dict
        self.equipment_caps = equipment_caps
        self.model = None
        self.solver = cp_model.CpSolver()

    def solve(self, patients):
        self.model = cp_model.CpModel()
        # Horizon: 48 Hours to prevent midnight crashes
        horizon = 48 * 60 
        
        starts = {}
        ends = {}
        room_intervals = {} 
        room_vars = {}      
        
        surgeon_intervals = {doc: [] for doc in self.surgeons}
        equipment_intervals = {eq: [] for eq in self.equipment_caps}
        
        for p in patients:
            pid = p['id']
            dur = int(p['duration'])
            
            # Variables
            start_var = self.model.NewIntVar(0, horizon, f'start_{pid}')
            end_var = self.model.NewIntVar(0, horizon, f'end_{pid}')
            
            # --- START TIME CONSTRAINTS ---
            min_start = max(CONSTANTS['DAY_START'], p.get('ready_time', 0))
            self.model.Add(start_var >= min_start)
            
            # Pinning Logic
            if 'fixed_start' in p:
                self.model.Add(start_var == p['fixed_start'])
            elif 'min_start_time' in p:
                self.model.Add(start_var >= p['min_start_time'])

            starts[pid] = start_var
            ends[pid] = end_var

            # --- SURGEON BREAK LOGIC ---
            doc = p.get('surgeon')
            if doc and doc in surgeon_intervals:
                # Surgeon blocked for Duration + Break
                break_time = CONSTANTS.get('SURGEON_BREAK', 30)
                total_doc_time = dur + break_time
                s_int = self.model.NewIntervalVar(
                    start_var, total_doc_time, self.model.NewIntVar(0, horizon, ''), f'doc_task_{pid}'
                )
                surgeon_intervals[doc].append(s_int)

            # --- ROOM LOGIC ---
            valid_rooms = []
            for r in self.rooms:
                if p['type'] not in r['supported']: continue
                rid = r['id']
                x_pr = self.model.NewBoolVar(f'{pid}_in_{rid}')
                room_vars[(pid, rid)] = x_pr
                
                if 'fixed_room' in p:
                    if p['fixed_room'] == r['name']: self.model.Add(x_pr == 1)
                    else: self.model.Add(x_pr == 0)

                valid_rooms.append(x_pr)
                
                # Room blocked for Duration + Turnover
                dur_clean = dur + CONSTANTS['TURNOVER']
                r_int = self.model.NewOptionalIntervalVar(
                    start_var, dur_clean, self.model.NewIntVar(0, horizon, ''), 
                    x_pr, f'room_int_{pid}_{rid}'
                )
                if rid not in room_intervals: room_intervals[rid] = []
                room_intervals[rid].append(r_int)
            
            if valid_rooms: self.model.Add(sum(valid_rooms) == 1)

            # --- EQUIPMENT ---
            m_int = self.model.NewIntervalVar(start_var, dur, end_var, f'task_{pid}')
            if p.get('needs_c_arm'): equipment_intervals['C-Arm'].append(m_int)
            if p.get('needs_robot'): equipment_intervals['Robot'].append(m_int)

        # Constraints
        for intervals in room_intervals.values(): self.model.AddNoOverlap(intervals)
        for intervals in surgeon_intervals.values(): self.model.AddNoOverlap(intervals)
        for eq, intervals in equipment_intervals.items():
            if intervals: self.model.AddCumulative(intervals, [1]*len(intervals), self.equipment_caps.get(eq, 100))

        # Objective
        makespan = self.model.NewIntVar(0, horizon, 'makespan')
        self.model.AddMaxEquality(makespan, list(ends.values()))
        obj_terms = [makespan]
        for p in patients:
            weight = p.get('asa_score', 1) * 2
            obj_terms.append(starts[p['id']] * weight)
        self.model.Minimize(sum(obj_terms))
        
        status = self.solver.Solve(self.model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            results = []
            for p in patients:
                pid = p['id']
                start = self.solver.Value(starts[pid])
                end = self.solver.Value(ends[pid])
                
                # Find Assigned Room
                assigned_room = "Waitlist"
                for r in self.rooms:
                    rid = r['id']
                    if (pid, rid) in room_vars and self.solver.Value(room_vars[(pid, rid)]) == 1:
                        assigned_room = r['name']
                        break
                
                results.append({
                    "Patient ID": pid,
                    "Type": p['type'],
                    "Surgeon": p.get('surgeon'),
                    "Room": assigned_room,
                    "Start Time": f"{start//60:02d}:{start%60:02d}",
                    "End Time": f"{end//60:02d}:{end%60:02d}",
                    "Duration": p['duration'],
                    "start_mins": start,
                    "end_mins": end,
                    "Risk (ASA)": p.get('asa_score', 1)
                })
            return pd.DataFrame(results).sort_values('start_mins')
        else:
            return None
