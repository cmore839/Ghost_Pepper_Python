# models/motor.py
class Motor:
    def __init__(self, id):
        self.id = id
        self.angle = 0.0
        self.velocity = 0.0
        self.current_q = 0.0
        self.is_enabled = False
        
        # Attributes for real-time status feedback
        self.status_angle = 0.0
        self.status_velocity = 0.0
        self.state = 0 # 0: INITIALIZING, 1: READY, 2: OPERATIONAL, 3: FAULT

        # Existing parameter storage
        self.phase_resistance = 0.0
        self.phase_inductance = 0.0
        self.parameters = {}