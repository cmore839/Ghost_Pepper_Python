# services/sysid_tuner_service.py
import time
import threading
import numpy as np
import math
from scipy.optimize import curve_fit

class SysIdTunerService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self.is_active = False

    def start(self, config):
        if self.is_active:
            print("SysID is already running.")
            return

        self.is_active = True
        self._viewmodel.sysid_results = None
        self._thread = threading.Thread(target=self._sysid_thread_func, args=(config,), daemon=True)
        self._thread.start()

    def _simulate_fopdt_response(self, t, K, tau, delay, torque_input):
        """ Simulates a First-Order Plus Dead Time response. """
        v = np.zeros_like(t)
        delayed_torque = np.interp(t - delay, t, torque_input, left=0, right=0)
        
        for i in range(len(t) - 1):
            dt = t[i+1] - t[i]
            if tau <= 1e-6: tau = 1e-6
            v_dot = (K * delayed_torque[i] - v[i]) / tau
            v[i+1] = v[i] + v_dot * dt
        return v

    def _sysid_thread_func(self, config):
        vm = self._viewmodel
        motor_id = config["motor_id"]
        
        try:
            vm.log_message(f"SysID: Starting chirp test for motor {motor_id}...")
            vm.sysid_status = "1/4: Running frequency sweep..."
            
            vm.send_control_mode_to_motor(motor_id, "Torque")
            time.sleep(0.2)
            
            velocity_stream_key = f"motor_{motor_id}_velocity"
            velocity_stream = vm._data_service.get_stream_data(velocity_stream_key)
            velocity_stream["timestamps"].clear()
            velocity_stream["values"].clear()

            # --- ADD THIS: Clear the gui_target stream ---
            gui_target_stream = vm._data_service.get_stream_data("gui_target")
            gui_target_stream["timestamps"].clear()
            gui_target_stream["values"].clear()
            # --- END ADD ---

            sent_commands = []
            start_time = time.perf_counter()
            
            duration = config["duration"]
            f0, f1 = config["start_freq"], config["end_freq"]
            amplitude = config["amplitude"]
            
            while time.perf_counter() - start_time < duration and self.is_active:
                t = time.perf_counter() - start_time
                k = (f1 / f0)**(t / duration)
                instantaneous_phase = 2 * np.pi * duration * f0 * (k - 1) / np.log(f1 / f0)
                torque_cmd = amplitude * np.sin(instantaneous_phase)
                
                vm.send_target_to_motor(motor_id, torque_cmd)
                sent_commands.append((t, torque_cmd))
                time.sleep(0.002)

            vm.send_target_to_motor(motor_id, 0.0)
            time.sleep(0.5)
            
            vm.sysid_status = "2/4: Aligning data..."
            
            history = vm._data_service.get_stream_data(velocity_stream_key)
            measured_times = np.array(list(history["timestamps"]))
            measured_velocities = np.array(list(history["values"]))
            
            if len(measured_times) < 50:
                raise ValueError("Not enough telemetry data for analysis.")
                
            measured_times -= measured_times[0]
            cmd_times, cmd_torques = zip(*sent_commands)
            aligned_velocities = np.interp(cmd_times, measured_times, measured_velocities)
            
            vm.sysid_status = "3/4: Fitting model..."
            
            fit_func = lambda t, K, tau, delay: self._simulate_fopdt_response(t, K, tau, delay, cmd_torques)
            
            initial_guesses = [10.0, 0.05, 0.005]
            bounds = ([0, 0, 0], [1000, 1, 0.1])
            
            params, _ = curve_fit(fit_func, cmd_times, aligned_velocities, p0=initial_guesses, bounds=bounds, maxfev=5000)
            
            K_v, tau, delay = params

            if delay < 0:
                print(f"Warning: Calculated negative delay ({delay:.4f}s). Clamping to 0.")
                delay = 0

            vm.sysid_status = "4/4: Calculating gains..."

            lambda_tc = config.get("lambda_tc", 0.1)
            
            Kp = (1 / K_v) * (tau / (lambda_tc + delay))
            Ti = tau
            Ki = Kp / Ti if Ti > 0 else 0
            
            if not math.isfinite(Kp) or not math.isfinite(Ki) or Kp <= 0 or Ki <= 0:
                raise ValueError(f"Resulted in invalid gains: P={Kp:.2f}, I={Ki:.2f}")

            vm.sysid_results = {"K": K_v, "tau": tau, "delay": delay, "p": Kp, "i": Ki}
            vm.sysid_status = "Done! Gains ready to apply."

        except Exception as e:
            vm.log_message(f"SysID ERROR: {e}")
            vm.sysid_status = f"Error: {e}"
        finally:
            self.is_active = False