# services/tuning_service.py
import time
import threading
import numpy as np
from services.analysis_service import AnalysisService

class TuningService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self._analysis_service = AnalysisService()

    def start_autotune(self, motor_id, relay_amplitude, duration):
        """Starts the autotuning process in a separate thread."""
        if self._thread and self._thread.is_alive():
            print("Autotune is already running.")
            return

        self._viewmodel.autotune_active = True
        self._viewmodel.autotune_results = None
        
        self._thread = threading.Thread(
            target=self._autotune_thread_func,
            args=(motor_id, relay_amplitude, duration),
            daemon=True
        )
        self._thread.start()

    def _autotune_thread_func(self, motor_id, relay_amplitude, duration):
        """The actual autotuning logic that runs in the background."""
        try:
            vm = self._viewmodel
            vm.autotune_status = "1/3: Running relay test..."
            vm.send_control_mode_to_motor(motor_id, "Torque")
            time.sleep(0.2)

            # --- ADD THIS: Clear the gui_target stream ---
            gui_target_stream = vm._data_service.get_stream_data("gui_target")
            gui_target_stream["timestamps"].clear()
            gui_target_stream["values"].clear()
            # --- END ADD ---

            relay_data = []
            start_time = time.time()
            last_output = 0

            while time.time() - start_time < duration and vm.autotune_active:
                motor_state = vm.get_motor_by_id(motor_id)
                if not motor_state:
                    time.sleep(0.01)
                    continue
                
                current_velocity = motor_state.velocity
                output = relay_amplitude if current_velocity <= 0 else -relay_amplitude
                
                if output != last_output:
                    vm.send_target_to_motor(motor_id, output)
                    last_output = output
                    
                relay_data.append((time.time(), current_velocity))
                time.sleep(0.01)

            if not vm.autotune_active:
                vm.autotune_status = "Canceled."
                vm.send_target_to_motor(motor_id, 0.0)
                return

            vm.autotune_status = "2/3: Analyzing response..."
            vm.send_target_to_motor(motor_id, 0.0)

            stable_data = np.array([d for d in relay_data if d[0] > start_time + (duration / 4)])
            if len(stable_data) < 20: raise ValueError("Not enough stable data.")
                
            velocities = stable_data[:, 1]
            crossings = np.where(np.diff(np.sign(velocities)))[0]
            if len(crossings) < 3: raise ValueError("Could not detect oscillations.")
                
            periods = np.diff(stable_data[crossings, 0]) * 2
            Tu = np.mean(periods)
            a = (np.max(velocities) - np.min(velocities)) / 2.0
            
            if a < 0.01: raise ValueError(f"Oscillation amplitude is too small.")

            vm.autotune_status = "3/3: Calculating gains..."
            Ku = (4 * relay_amplitude) / (np.pi * a)
            Kp = 0.45 * Ku
            Ti = Tu / 1.2
            Ki = Kp / Ti if Ti > 0 else 0
            
            vm.autotune_results = {"p": Kp, "i": Ki}
            vm.autotune_status = "Done! Gains ready to apply."

        except Exception as e:
            vm.autotune_status = f"Error: {e}"
        finally:
            vm.autotune_active = False

    def run_current_step_test(self, motor_id, amplitude):
        if self._thread and self._thread.is_alive():
            return
        
        self._thread = threading.Thread(
            target=self._current_step_test_thread,
            args=(motor_id, amplitude),
            daemon=True
        )
        self._thread.start()

    def _current_step_test_thread(self, motor_id, amplitude):
        vm = self._viewmodel
        try:
            stream_key = f"motor_{motor_id}_current_q"
            vm._data_service.get_stream_data(stream_key)["timestamps"].clear()
            vm._data_service.get_stream_data(stream_key)["values"].clear()
            
            # --- ADD THIS: Clear the gui_target stream ---
            gui_target_stream = vm._data_service.get_stream_data("gui_target")
            gui_target_stream["timestamps"].clear()
            gui_target_stream["values"].clear()
            # --- END ADD ---
            
            vm.log_message("Current Test: Starting...")
            vm.send_control_mode_to_motor(motor_id, "Torque")
            time.sleep(0.1)
            vm.send_target_to_motor(motor_id, amplitude)
            time.sleep(0.3)
            vm.send_target_to_motor(motor_id, 0.0)
            time.sleep(0.2)
            vm.log_message("Current Test: Finished.")

            stream_data = vm._data_service.get_stream_data(stream_key)
            timestamps = list(stream_data["timestamps"])
            currents = list(stream_data["values"])
            
            stats = self._analysis_service.analyze_step_response(timestamps, currents, amplitude)
            vm.current_test_results = stats

        except Exception as e:
            vm.log_message(f"Current Test ERROR: {e}")