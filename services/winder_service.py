# services/winder_service.py
import time
import math
import threading
from utils import ramp_value

class WinderService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self.mode = "idle"

    def start_or_resume(self, config):
        if self.mode == "idle":
            if self._thread and self._thread.is_alive():
                return
            self._viewmodel.winder_config = config
            self._thread = threading.Thread(target=self._winder_thread_func, daemon=True)
            self.mode = "winding"
            self._thread.start()
        elif self.mode == "paused":
            self.mode = "winding"

    def pause(self):
        if self.mode == "winding":
            self.mode = "pausing"

    def stop(self):
        if self.mode not in ["idle", "stopping", "exit"]:
            self.mode = "stopping"

    def unwind(self):
        if self.mode == "finished":
            self.mode = "unwinding"

    def jog(self, jog_revs):
        vm = self._viewmodel
        if self.mode == "paused" and vm.winder_dynamic:
            bobbin_motor = vm.get_motor_by_id(vm.winder_config.get("bobbin_id"))
            if bobbin_motor:
                current_angle = bobbin_motor.angle
                vm.winder_dynamic["reverse_target_angle"] = current_angle - (jog_revs * 2 * math.pi)
                self.mode = "reversing"

    def _winder_thread_func(self):
        vm = self._viewmodel
        config = vm.winder_config
        bobbin_id = config.get("bobbin_id")
        tension_id = config.get("tension_id")

        if bobbin_id is None or tension_id is None:
            vm.winder_status = "Error: Motor not selected"
            self.mode = "idle"
            return
        
        dyn = {
            "start_angle": 0.0,
            "current_velocity": 0.0,
            "last_update_time": time.perf_counter()
        }
        vm.winder_dynamic = dyn
        
        try:
            vm.log_message(f"Winder: Thread started. Bobbin={bobbin_id}, Tension={tension_id}.")
            
            vm.send_control_mode_to_motor(bobbin_id, "Velocity")
            vm.send_control_mode_to_motor(tension_id, "Torque")
            time.sleep(0.1)
            vm.enable_motor_by_id(bobbin_id, True)
            vm.enable_motor_by_id(tension_id, True)

            time.sleep(0.2)
            bobbin_motor = vm.get_motor_by_id(bobbin_id)
            if bobbin_motor:
                dyn["start_angle"] = bobbin_motor.angle

            total_angle_to_wind = config.get("revolutions", 0) * 2 * math.pi
            
            while self.mode != "exit":
                now = time.perf_counter()
                dt = now - dyn["last_update_time"]
                dyn["last_update_time"] = now
                
                bobbin_motor = vm.get_motor_by_id(bobbin_id)
                if not bobbin_motor:
                    time.sleep(0.01)
                    continue

                current_bobbin_angle = bobbin_motor.angle
                dyn["progress_angle"] = abs(current_bobbin_angle - dyn["start_angle"])
                
                target_velocity = 0.0
                if self.mode == "winding":
                    target_velocity = config.get("speed", 0)
                elif self.mode in ["reversing", "unwinding"]:
                    target_velocity = -config.get("speed", 0)

                dyn["current_velocity"] = ramp_value(dyn["current_velocity"], target_velocity, config.get("accel", 10), dt)
                vm.send_target_to_motor(bobbin_id, dyn["current_velocity"])
                
                if self.mode == "winding":
                    percent_complete = (dyn["progress_angle"] / total_angle_to_wind) * 100 if total_angle_to_wind > 0 else 0
                    vm.winder_status = f"Winding... {percent_complete:.1f}%"
                    vm.send_target_to_motor(tension_id, config.get("torque", 0))
                    if dyn["progress_angle"] >= total_angle_to_wind:
                        self.mode = "finishing"
                elif self.mode == "pausing":
                    vm.winder_status = "Pausing..."
                    if dyn["current_velocity"] == 0.0:
                        self.mode = "paused"
                elif self.mode == "paused":
                    revs = dyn.get('progress_angle', 0) / (2 * math.pi)
                    vm.winder_status = f"Paused at {revs:.2f} revs"
                elif self.mode == "reversing":
                    vm.winder_status = "Reversing..."
                    if current_bobbin_angle <= dyn.get("reverse_target_angle", current_bobbin_angle):
                        self.mode = "pausing"
                elif self.mode == "unwinding":
                    percent_unwound = (dyn["progress_angle"] / total_angle_to_wind) * 100 if total_angle_to_wind > 0 else 0
                    vm.winder_status = f"Unwinding... {100.0 - percent_unwound:.1f}%"
                    vm.send_target_to_motor(tension_id, config.get("torque", 0))
                    if current_bobbin_angle <= dyn["start_angle"]:
                        self.mode = "stopping"
                elif self.mode == "stopping":
                    vm.winder_status = "Stopping..."
                    if dyn["current_velocity"] == 0.0:
                        self.mode = "exit"
                elif self.mode == "finishing":
                    vm.winder_status = "Finishing..."
                    if dyn["current_velocity"] == 0.0:
                        self.mode = "finished"
                elif self.mode == "finished":
                    vm.send_target_to_motor(tension_id, config.get("holding_torque", 0))
                    vm.winder_status = "Finished. Holding tension."

                time.sleep(0.01)

        except Exception as e:
            vm.log_message(f"Winder FATAL ERROR: {e}")
            vm.winder_status = f"Error: {e}"
        
        finally:
            vm.log_message("Winder: Thread exit. Disabling motors.")
            vm.send_target_to_motor(bobbin_id, 0)
            vm.send_target_to_motor(tension_id, 0)
            time.sleep(0.1)
            vm.enable_motor_by_id(bobbin_id, False)
            vm.enable_motor_by_id(tension_id, False)
            vm.winder_status = "Idle"
            self.mode = "idle"