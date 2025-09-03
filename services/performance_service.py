# services/performance_service.py
import time
import threading
import numpy as np

class PerformanceService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self.is_active = False

    def start_test(self, test_type, config):
        if self._thread and self._thread.is_alive():
            self._viewmodel.log_message("ERROR: A performance test is already running.")
            return

        self._viewmodel.performance_test_results = None
        
        target_function = None
        if test_type == "step_response":
            target_function = self._run_step_response_test
        elif test_type == "constant_velocity":
            target_function = self._run_constant_velocity_test
        elif test_type == "reversing_move":
            target_function = self._run_reversing_move_test
        
        if target_function:
            self._thread = threading.Thread(target=target_function, args=(config,), daemon=True)
            self._thread.start()

    def _prepare_for_test(self, motor_id):
        """Prepares motor and data streams for a new test."""
        vm = self._viewmodel
        vm.log_message(f"Preparing for performance test on motor {motor_id}...")

        vm.send_control_mode_to_motor(motor_id, "Angle")
        time.sleep(0.1)

        target_stream = vm._data_service.get_stream_data("gui_target")
        target_stream["timestamps"].clear()
        target_stream["values"].clear()

        angle_stream_key = f"motor_{motor_id}_angle"
        angle_stream = vm._data_service.get_stream_data(angle_stream_key)
        angle_stream["timestamps"].clear()
        angle_stream["values"].clear()
        
        motor = vm.get_motor_by_id(motor_id)
        if motor:
            vm.set_target(motor.angle)
            time.sleep(0.5)
        
        return angle_stream_key

    def _run_step_response_test(self, config):
        vm = self._viewmodel
        motor_id = vm.active_motor_id
        try:
            angle_stream_key = self._prepare_for_test(motor_id)
            motor = vm.get_motor_by_id(motor_id)
            start_pos = motor.angle

            vm.log_message(f"Running Step Response Test: Jumping {config['amplitude']} rad...")
            target_pos = start_pos + config['amplitude']
            vm.set_target(target_pos)
            
            time.sleep(config['duration'])
            
            vm.log_message("Step Response Test finished. Analyzing...")
            
            target_data = vm._data_service.get_stream_data("gui_target")
            angle_data = vm._data_service.get_stream_data(angle_stream_key)
            
            results = vm._analysis_service.analyze_step_response_performance(
                target_data, angle_data, target_pos
            )
            vm.performance_test_results = results
            vm.log_message("Analysis complete. Results are available.")

        except Exception as e:
            vm.log_message(f"Step Response Test ERROR: {e}")
        finally:
            self.is_active = False

    def _run_constant_velocity_test(self, config):
        vm = self._viewmodel
        motor_id = vm.active_motor_id
        try:
            angle_stream_key = self._prepare_for_test(motor_id)
            motor = vm.get_motor_by_id(motor_id)
            start_pos = motor.angle
            
            distance = config['distance']
            velocity = config['velocity']
            duration = abs(distance / velocity) if velocity != 0 else 1.0

            vm.log_message(f"Running Constant Velocity Test: Moving {distance} rad at {velocity} rad/s...")
            
            start_time = time.time()
            end_time = start_time + duration
            
            # --- FIX: Synchronize command rate with telemetry rate ---
            period = 1.0 / vm.active_telemetry_rate_hz
            last_command_time = 0
            
            while time.time() < end_time:
                now = time.time()
                if now - last_command_time >= period:
                    elapsed = now - start_time
                    target_pos = start_pos + velocity * elapsed
                    vm.set_target(target_pos)
                    last_command_time = now
                time.sleep(0.001) # Sleep briefly to prevent busy-waiting

            final_pos = start_pos + distance
            vm.set_target(final_pos)
            time.sleep(0.5)

            vm.log_message("Constant Velocity Test finished. Analyzing...")
            target_data = vm._data_service.get_stream_data("gui_target")
            angle_data = vm._data_service.get_stream_data(angle_stream_key)
            
            results = vm._analysis_service.analyze_tracking_error(target_data, angle_data)
            vm.performance_test_results = results
            vm.log_message("Analysis complete. Results are available.")

        except Exception as e:
            vm.log_message(f"Constant Velocity Test ERROR: {e}")
        finally:
            self.is_active = False

    def _run_reversing_move_test(self, config):
        vm = self._viewmodel
        motor_id = vm.active_motor_id
        try:
            angle_stream_key = self._prepare_for_test(motor_id)
            motor = vm.get_motor_by_id(motor_id)
            start_pos = motor.angle

            distance = config['distance']
            velocity = config['velocity']
            move_duration = abs(distance / velocity) if velocity != 0 else 1.0

            vm.log_message(f"Running Reversing Move Test...")
            
            # --- FIX: Synchronize command rate with telemetry rate ---
            period = 1.0 / vm.active_telemetry_rate_hz
            last_command_time = 0

            # Move 1: Forward
            end_time = time.time() + move_duration
            start_time_move1 = time.time()
            while time.time() < end_time:
                now = time.time()
                if now - last_command_time >= period:
                    elapsed = now - start_time_move1
                    target = start_pos + velocity * elapsed
                    vm.set_target(target)
                    last_command_time = now
                time.sleep(0.001)
            
            # Move 2: Reverse
            pos_at_turn = start_pos + distance
            end_time = time.time() + move_duration
            start_time_move2 = time.time()
            while time.time() < end_time:
                now = time.time()
                if now - last_command_time >= period:
                    elapsed = now - start_time_move2
                    target = pos_at_turn - velocity * elapsed
                    vm.set_target(target)
                    last_command_time = now
                time.sleep(0.001)

            vm.set_target(start_pos)
            time.sleep(0.5)

            vm.log_message("Reversing Move Test finished. Analyzing...")
            target_data = vm._data_service.get_stream_data("gui_target")
            angle_data = vm._data_service.get_stream_data(angle_stream_key)

            results = vm._analysis_service.analyze_tracking_error(target_data, angle_data)
            vm.performance_test_results = results
            vm.log_message("Analysis complete. Results are available.")

        except Exception as e:
            vm.log_message(f"Reversing Move Test ERROR: {e}")
        finally:
            self.is_active = False