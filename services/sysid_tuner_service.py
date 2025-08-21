# services/sysid_tuner_service.py
import time
import threading
import numpy as np
from scipy.optimize import curve_fit

class SysIdTunerService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self.is_active = False

    def start(self, config):
        if self.is_active:
            return

        self.is_active = True
        self._viewmodel.sysid_results = None
        self._thread = threading.Thread(target=self._sysid_thread_func, args=(config,), daemon=True)
        self._thread.start()

    def _simulate_first_order_response(self, t, K, tau, torque_input):
        v = np.zeros_like(t)
        for i in range(len(t) - 1):
            dt = t[i+1] - t[i]
            v_dot = (K * torque_input[i] - v[i]) / tau
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
            
            # Use data_service to clear and get data
            velocity_stream_key = f"motor_{motor_id}_velocity"
            vm._data_service.get_stream_data(velocity_stream_key)["timestamps"].clear()
            vm._data_service.get_stream_data(velocity_stream_key)["values"].clear()

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
            measured_times = np.array(history["timestamps"])
            measured_velocities = np.array(history["values"])
            
            if len(measured_times) < 50:
                raise ValueError("Not enough telemetry data.")
                
            measured_times -= measured_times[0]
            cmd_times, cmd_torques = zip(*sent_commands)
            aligned_velocities = np.interp(cmd_times, measured_times, measured_velocities)
            
            vm.sysid_status = "3/4: Fitting model..."
            fit_func = lambda t, K, tau: self._simulate_first_order_response(t, K, tau, cmd_torques)
            params, _ = curve_fit(fit_func, cmd_times, aligned_velocities, p0=[10.0, 0.05])
            K, tau = params
            
            vm.sysid_status = "4/4: Calculating gains..."
            lmbda = config["lambda_tc"]
            kp = tau / (K * lmbda)
            ki = 1.0 / (K * lmbda)
            
            vm.sysid_results = {"K": K, "tau": tau, "p": kp, "i": ki}
            vm.sysid_status = "Done! Gains ready."

        except Exception as e:
            vm.log_message(f"SysID ERROR: {e}")
            vm.sysid_status = f"Error: {e}"
        finally:
            self.is_active = False