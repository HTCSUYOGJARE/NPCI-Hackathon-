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
        """
        patients: List of dicts including 'id', 'duration', 'fixed_start' (optional)
        """
        self.model = cp_model.CpModel()
        horizon = 24 * 60 # 24 Hours
        
        starts = {}
        ends = {}
        room_intervals = {} # For room conflict check
        room_vars = {}      # To track assignments
        
        # Maps for Resource Constraints
        surgeon_intervals = {doc: [] for doc in self.surgeons}
        equipment_intervals = {eq: [] for eq in self.equipment_caps}
        
        # --- 1. SETUP VARIABLES ---
        for p in patients:
            pid = p['id']
            dur = int(p['duration'])
            
            # Variables
            start_var = self.model.NewIntVar(CONSTANTS['DAY_START'], horizon, f'start_{pid}')
            end_var = self.model.NewIntVar(CONSTANTS['DAY_START'], horizon, f'end_{pid}')
            
            # Master Interval (Used for Surgeon/Equip)
            master_interval = self.model.NewIntervalVar(start_var, dur, end_var, f'task_{pid}')
            
            starts[pid] = start_var
            ends[pid] = end_var
            
            # --- PINNING LOGIC (THE SELF-HEALING CORE) ---
            # If this is a past event (Emergency Scenario), lock it.
            if 'fixed_start' in p:
                self.model.Add(start_var == p['fixed_start'])
            elif 'min_start_time' in p:
                self.model.Add(start_var >= p['min_start_time'])
            
            # --- ROOM ASSIGNMENT ---
            valid_rooms = []
            
            for r in self.rooms:
                rid = r['id']
                
                # Check Capability
                if p['type'] not in r['supported']:
                    continue # Skip incompatible rooms
                
                # Create Boolean: Is Patient P in Room R?
                x_pr = self.model.NewBoolVar(f'{pid}_in_{rid}')
                room_vars[(pid, rid)] = x_pr
                
                # Logic: If fixed_room is set (Emergency), force the boolean
                if 'fixed_room' in p:
                    if p['fixed_room'] == r['name']:
                        self.model.Add(x_pr == 1)
                    else:
                        self.model.Add(x_pr == 0)
                
                valid_rooms.append(x_pr)
                
                # Create Room Interval (Surgery + Cleaning Time)
                dur_clean = dur + CONSTANTS['TURNOVER']
                
                # Optional Interval: Only active if x_pr is True
                opt_int = self.model.NewOptionalIntervalVar(
                    start_var, dur_clean, self.model.NewIntVar(0, horizon, ''), 
                    x_pr, f'room_int_{pid}_{rid}'
                )
                
                if rid not in room_intervals: room_intervals[rid] = []
                room_intervals[rid].append(opt_int)

            # Constraint: Must be in exactly one room
            if not valid_rooms:
                print(f"⚠️ SKIPPING {pid}: No compatible room found for {p['type']}.")
                continue
            self.model.Add(sum(valid_rooms) == 1)

            # --- RESOURCE TRACKING ---
            # Surgeon
            doc = p.get('surgeon')
            if doc and doc in surgeon_intervals:
                surgeon_intervals[doc].append(master_interval)
            
            # Equipment (C-Arm, etc.)
            if p.get('needs_c_arm'):
                equipment_intervals['C-Arm'].append(master_interval)
            if p.get('needs_robot'):
                equipment_intervals['Robot'].append(master_interval)

        # --- 2. APPLY CONSTRAINTS ---
        
        # A. Room Non-Overlap
        for rid, intervals in room_intervals.items():
            self.model.AddNoOverlap(intervals)
            
        # B. Surgeon Non-Overlap
        for doc, intervals in surgeon_intervals.items():
            if len(intervals) > 1:
                self.model.AddNoOverlap(intervals)
                
        # C. Equipment Capacity (Cumulative)
        for eq_name, intervals in equipment_intervals.items():
            if intervals:
                cap = self.equipment_caps.get(eq_name, 100)
                # Each surgery consumes 1 unit
                demands = [1] * len(intervals)
                self.model.AddCumulative(intervals, demands, cap)

        # --- 3. OBJECTIVE FUNCTION ---
        # Min(Makespan) + Min(Wait Penalty)
        makespan = self.model.NewIntVar(0, horizon, 'makespan')
        self.model.AddMaxEquality(makespan, list(ends.values()))
        
        # Weighted Cost
        obj_terms = [makespan]
        
        # Priority Weighting: Push High ASA (Risk) earlier
        for p in patients:
            weight = p.get('asa_score', 1) * 2
            obj_terms.append(starts[p['id']] * weight)
            
        self.model.Minimize(sum(obj_terms))
        
        # --- 4. SOLVE ---
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
                    "Risk (ASA)": p.get('asa_score', 1) # <--- ADDED THIS LINE TO FIX CRASH
                })
            
            return pd.DataFrame(results).sort_values('start_mins')
        else:
            print("❌ No Solution Found")
            return None