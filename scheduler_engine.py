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
        horizon = 24 * 60 
        
        starts = {}
        ends = {}
        room_intervals = {} 
        room_vars = {}      
        
        surgeon_intervals = {doc: [] for doc in self.surgeons}
        equipment_intervals = {eq: [] for eq in self.equipment_caps}
        
        for p in patients:
            pid = p['id']
            dur = int(p['duration'])
            
            # 1. Start Time Variables
            start_var = self.model.NewIntVar(CONSTANTS['DAY_START'], horizon, f'start_{pid}')
            end_var = self.model.NewIntVar(CONSTANTS['DAY_START'], horizon, f'end_{pid}')
            
            # --- LOGIC: START TIME CONSTRAINTS ---
            # Base constraint: Cannot start before Day Start
            # Dynamic constraint: 'ready_time' (Added via UI for delayed arrival)
            min_start = p.get('ready_time', CONSTANTS['DAY_START'])
            
            # Emergency Pinning (If surgery is fixed in past)
            if 'fixed_start' in p:
                self.model.Add(start_var == p['fixed_start'])
            elif 'min_start_time' in p:
                # Must be after current time AND after ready time
                actual_min = max(min_start, p['min_start_time'])
                self.model.Add(start_var >= actual_min)
            else:
                self.model.Add(start_var >= min_start)
            
            starts[pid] = start_var
            ends[pid] = end_var

            # 2. SURGEON BREAK CONSTRAINT (Crucial Update)
            # Logic: Surgeon is occupied for Duration + 30 mins Break
            doc = p.get('surgeon')
            if doc and doc in surgeon_intervals:
                # The 'surgeon_interval' blocks the doctor for (Surgery + Break)
                # Note: This doesn't block the ROOM, just the DOCTOR.
                total_doc_time = dur + 30 # 30 min mandatory break
                
                surgeon_interval = self.model.NewIntervalVar(
                    start_var, total_doc_time, self.model.NewIntVar(0, horizon, ''), f'doc_task_{pid}'
                )
                surgeon_intervals[doc].append(surgeon_interval)

            # 3. ROOM ASSIGNMENT
            valid_rooms = []
            for r in self.rooms:
                rid = r['id']
                if p['type'] not in r['supported']: continue 

                x_pr = self.model.NewBoolVar(f'{pid}_in_{rid}')
                room_vars[(pid, rid)] = x_pr
                
                if 'fixed_room' in p:
                    if p['fixed_room'] == r['name']: self.model.Add(x_pr == 1)
                    else: self.model.Add(x_pr == 0)
                
                valid_rooms.append(x_pr)
                
                # Room Occupancy = Duration + Turnover (Cleaning)
                dur_clean = dur + CONSTANTS['TURNOVER']
                opt_int = self.model.NewOptionalIntervalVar(
                    start_var, dur_clean, self.model.NewIntVar(0, horizon, ''), 
                    x_pr, f'room_int_{pid}_{rid}'
                )
                if rid not in room_intervals: room_intervals[rid] = []
                room_intervals[rid].append(opt_int)

            if valid_rooms:
                self.model.Add(sum(valid_rooms) == 1)

            # 4. EQUIPMENT
            master_interval = self.model.NewIntervalVar(start_var, dur, end_var, f'task_{pid}')
            if p.get('needs_c_arm'): equipment_intervals['C-Arm'].append(master_interval)
            if p.get('needs_robot'): equipment_intervals['Robot'].append(master_interval)

        # APPLY NO-OVERLAP
        for rid, intervals in room_intervals.items(): self.model.AddNoOverlap(intervals)
        for doc, intervals in surgeon_intervals.items(): self.model.AddNoOverlap(intervals)
        for eq_name, intervals in equipment_intervals.items():
            if intervals: self.model.AddCumulative(intervals, [1]*len(intervals), self.equipment_caps.get(eq_name, 100))

        # OBJECTIVE
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
