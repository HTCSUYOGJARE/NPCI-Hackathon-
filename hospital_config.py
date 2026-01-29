# hospital_config.py

# 1. OPERATING THEATRES (12 Rooms)
ROOMS = [
    # Specialized Rooms (Strict Access)
    {'id': 1, 'name': 'OR-1 (Neuro)', 'type': 'Neuro', 'supported': ['Neurological', 'Spinal']},
    {'id': 2, 'name': 'OR-2 (Neuro)', 'type': 'Neuro', 'supported': ['Neurological', 'Spinal']},
    {'id': 3, 'name': 'OR-3 (Cardio)', 'type': 'Cardiac', 'supported': ['Cardiovascular', 'Thoracic']},
    {'id': 4, 'name': 'OR-4 (Cardio)', 'type': 'Cardiac', 'supported': ['Cardiovascular', 'Thoracic']},
    
    # General Rooms (Flexible)
    {'id': 5, 'name': 'OR-5 (General)', 'type': 'General', 'supported': ['General', 'Orthopedic', 'Cosmetic']},
    {'id': 6, 'name': 'OR-6 (General)', 'type': 'General', 'supported': ['General', 'Orthopedic', 'Cosmetic']},
    {'id': 7, 'name': 'OR-7 (Ortho)', 'type': 'General', 'supported': ['Orthopedic', 'General']},
    {'id': 8, 'name': 'OR-8 (Ortho)', 'type': 'General', 'supported': ['Orthopedic', 'General']},
    {'id': 9, 'name': 'OR-9 (Hybrid)', 'type': 'General', 'supported': ['General', 'Urology', 'Cosmetic']},
    {'id': 10, 'name': 'OR-10 (Robot)', 'type': 'General', 'supported': ['General', 'Urology']}, 
    
    # Emergency Room
    {'id': 11, 'name': 'OR-11 (Emerg)', 'type': 'General', 'supported': ['General', 'Orthopedic', 'Cardiovascular', 'Neurological', 'Cosmetic']},
    
    {'id': 12, 'name': 'OR-12 (Day)', 'type': 'General', 'supported': ['Cosmetic', 'General']}
]

# 2. SURGEONS (Full Roster)
SURGEONS = {
    # Main Staff
    'Dr. Strange': ['Neurological'],
    'Dr. Shepherd': ['Neurological'],
    'Dr. Yang': ['Cardiovascular'],
    'Dr. Burke': ['Cardiovascular'],
    'Dr. House': ['General', 'Orthopedic'],
    'Dr. Grey': ['General'],
    'Dr. Torres': ['Orthopedic'],
    'Dr. Lincoln': ['Orthopedic'],
    'Dr. Avery': ['Cosmetic', 'General'],
    'Dr. Bailey': ['General'],
    
    # Visiting Consultants (Backup)
    'Visiting Neuro': ['Neurological'],
    'Visiting Cardio': ['Cardiovascular'],
    'Visiting Ortho': ['Orthopedic'],
    'Visiting General': ['General', 'Cosmetic']
}

# 3. RESOURCES
EQUIPMENT = {
    'C-Arm': 4,
    'Robot': 1
}

# 4. RULES
CONSTANTS = {
    'DAY_START': 8 * 60,    # 08:00 AM
    'DAY_END': 23 * 60,     # 11:00 PM (Extended)
    'TURNOVER': 30,         # Room cleaning time
    'SURGEON_BREAK': 30     # Mandatory Surgeon Break
}
