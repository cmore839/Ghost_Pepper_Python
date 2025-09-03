# services/gearing_service.py
import time
import math
import threading
import numpy as np
from utils import ramp_value

class GearingService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self.is_active = False
        self.mode = "position" 
        self.target_position = 0.0
        self.max_velocity = 50.0
        self.acceleration = 200.0
        self._current_pos = 0.0
        self._current_vel = 0.0
        self._previous_gui_target = 0.0 # Track previous target for clean plotting

    def start(self, leader_id, follower_id, follower_ratio, mode="position"):
        if self.is_active:
            return

        self.leader_id = leader_id
        self.follower_id = follower_id
        self.follower_ratio = follower_ratio
        self.mode = mode
        
        leader_motor = self._viewmodel.get_motor_by_id(leader_id)
        if leader_motor:
            self._current_pos = leader_motor.angle
            self.target_position = leader_motor.angle

        self.is_active = True
        self._thread = threading.Thread(target=self._gearing_thread_func, daemon=True)
        self._thread.start()
        
        log_msg = "Electronic Gearing Started." if mode == "position" else "Drive-by-Wire Started."
        self._viewmodel.log_message(log_msg)


    def stop(self):
        self.is_active = False
        if self._thread:
            self._thread.join(timeout=0.5)
        
        # Smoothly ramp down motor speeds to zero
        if self._viewmodel.get_motor_by_id(self.leader_id):
            self._viewmodel.send_target_to_motor(self.leader_id, self._current_pos)
        if self._viewmodel.get_motor_by_id(self.follower_id):
            self._viewmodel.send_target_to_motor(self.follower_id, self._current_pos * self.follower_ratio)
            
        self._viewmodel.log_message("Gearing/Drive-by-Wire Stopped.")

    def _gearing_thread_func(self):
        vm = self._viewmodel
        last_time = time.perf_counter()

        try:
            vm.send_control_mode_to_motor(self.leader_id, "Angle")
            vm.send_control_mode_to_motor(self.follower_id, "Angle")
            
            while self.is_active:
                now = time.perf_counter()
                dt = now - last_time
                last_time = now

                # UPDATED: Handle different modes
                if self.mode == "drive_by_wire":
                    leader_motor = vm.get_motor_by_id(self.leader_id)
                    if leader_motor:
                        self.target_position = leader_motor.angle
                
                # --- Motion Profile ---
                distance_to_target = self.target_position - self._current_pos
                target_vel = np.sign(distance_to_target) * np.sqrt(2 * self.acceleration * abs(distance_to_target))
                target_vel = np.clip(target_vel, -self.max_velocity, self.max_velocity)

                if abs(distance_to_target) > 0.001:
                    self._current_vel = ramp_value(self._current_vel, target_vel, self.acceleration * 2, dt)
                else:
                    self._current_vel = 0

                self._current_pos += self._current_vel * dt
                leader_target = self._current_pos
                follower_target = self._current_pos * self.follower_ratio

                # Send commands to motors
                vm.send_target_to_motor(self.leader_id, leader_target)
                vm.send_target_to_motor(self.follower_id, follower_target)
                
                # UPDATED: Log the target to the data service so it appears on the plot
                now_ts = time.time()
                vm._data_service.add_data_point("gui_target", now_ts - 0.001, self._previous_gui_target)
                vm._data_service.add_data_point("gui_target", now_ts, leader_target)
                self._previous_gui_target = leader_target

                time.sleep(0.01)

        except Exception as e:
            vm.log_message(f"Gearing ERROR: {e}")
        finally:
            self.is_active = False