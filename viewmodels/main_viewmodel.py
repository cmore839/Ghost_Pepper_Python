# viewmodels/main_viewmodel.py
import dearpygui.dearpygui as dpg
import queue
import time
import math
import collections
import numpy as np
from services.can_service import CanService
from services.motor_service import MotorService
from services.data_service import DataService
from services.tuning_service import TuningService
from services.winder_service import WinderService
from services.gearing_service import GearingService
from services.sysid_tuner_service import SysIdTunerService
from services.characterization_service import CharacterizationService
from services.performance_service import PerformanceService
from services.analysis_service import AnalysisService
from models.motor import Motor
from models.plot_config import PlotConfig, SeriesConfig
from config import *
from ui_manager import UIManager

class MainViewModel:
    def __init__(self):
        # Services
        self._can_service = CanService()
        self._data_service = DataService()
        self._analysis_service = AnalysisService()
        self._motor_service = MotorService(self._can_service, self._data_service)
        self._tuning_service = TuningService(self)
        self._winder_service = WinderService(self)
        self._gearing_service = GearingService(self)
        self._sysid_tuner_service = SysIdTunerService(self)
        self._characterization_service = CharacterizationService(self)
        self._performance_service = PerformanceService(self)
        
        self.ui_manager = UIManager(self)

        # State
        self.is_connected = False
        self.status_text = "Status: Disconnected"
        self.motors = []
        self.active_motor_id = None
        self.active_motor = None
        self.start_time = time.time()
        self.sync_motors = []
        
        # Trajectory Planner State
        self.is_moving = False
        self.trajectory_points = []
        self.trajectory_start_time = 0.0
        self.trajectory_index = 0
        self.trajectory_update_period = 1.0 / 500.0 # Send setpoints at
        
        # Plotting State
        self.the_plot = PlotConfig()
        self.is_plot_paused = False
        
        # Event Log
        self.log_messages = collections.deque(maxlen=100)

        # Data Rate Tracking
        self.telemetry_packet_counter = 0
        self.plot_update_counter = 0
        self.last_freq_calc_time = 0
        self.telemetry_rate_hz = 0.0
        self.plot_rate_fps = 0.0
        
        # Telemetry Rate Synchronization
        self.active_telemetry_rate_hz = 100.0
        self.last_gui_target_update_time = 0

        # Autotuning State
        self.autotune_active = False
        self.autotune_status = "Idle"
        self.autotune_results = None

        # SysID State
        self.sysid_status = "Idle"
        self.sysid_results = None

        # Current Test State
        self.current_test_results = None
        
        # Recommendations State
        self.tuning_recommendations = None
        
        # Characterization State
        self.characterization_status = "Idle"
        self.characterization_results = None

        # Winder State
        self.winder_status = "Idle"
        self.winder_config = {}
        self.winder_dynamic = {}
        
        # Performance Test State
        self.performance_test_results = None

        self._data_service.register_stream("gui_target")
        self._data_service.register_stream("plan_pos")
        self._data_service.register_stream("plan_vel")
        self._data_service.register_stream("plan_acc")
        self._previous_gui_target = 0.0
        self.log_message("Welcome! Connect to the CAN bus to begin.")

    def log_message(self, message):
        log_time = time.strftime("%H:%M:%S", time.localtime())
        self.log_messages.appendleft(f"[{log_time}] {message}")
        if dpg.is_dearpygui_running():
            self.ui_manager.update_log()
    
    def connect(self):
        if not self.is_connected:
            self.connect_disconnect()

    def connect_disconnect(self):
        if self.is_connected:
            self.stop_winder()
            self.stop_gearing()
            self.autotune_active = False
            self._can_service.disconnect()
            self.is_connected = False
            self.status_text = "Status: Disconnected"
            self.log_message("Disconnected from CAN bus.")
        else:
            self.log_message("Connecting to CAN bus...")
            if self._can_service.connect():
                self.is_connected = True
                self.status_text = "Status: Connected"
                self.start_time = time.time()
                self.log_message("Connection successful.")
            else:
                self.log_message("ERROR: Connection failed.")

    def scan_for_motors(self):
        if not self.is_connected:
            self.log_message("ERROR: Must be connected to scan.")
            return
        self.log_message("Scanning for motors...")
        self.motors.clear()
        if self.is_connected: self._motor_service.scan_for_motors()

    def select_motor(self, sender, app_data, user_data):
        if app_data is None:
            self.active_motor_id = None
            self.active_motor = None
            self.tuning_recommendations = None
            self.ui_manager.update_can_id_input(1)
            return

        try:
            motor_id_str = app_data.replace("Motor ", "")
            motor_id = int(motor_id_str)
            self.active_motor_id = motor_id
            self.active_motor = self.get_motor_by_id(motor_id)
            self.tuning_recommendations = None 
            self.log_message(f"Selected motor {motor_id}")
            if self.active_motor_id is not None:
                self.active_telemetry_rate_hz = 100.0
                if dpg.does_item_exist("telemetry_rate_selector"):
                    dpg.set_value("telemetry_rate_selector", "100 Hz")
                
                self.request_motor_params(self.active_motor_id)
                self._motor_service.request_parameter(self.active_motor_id, REG_STATUS)
                self.ui_manager.update_can_id_input(self.active_motor_id)
        except (ValueError, TypeError):
            self.active_motor_id = None
            self.active_motor = None
            self.tuning_recommendations = None
            self.ui_manager.update_can_id_input(1)

    def get_motor_by_id(self, motor_id):
        return next((m for m in self.motors if m.id == motor_id), None)

    def send_target_to_motor(self, motor_id, target):
        self._motor_service.send_command(motor_id, REG_TARGET, float(target), 'f')

    def send_control_mode_to_motor(self, motor_id, mode_str):
        mode_map = {"Torque": 0, "Velocity": 1, "Angle": 2}
        self._motor_service.send_command(motor_id, REG_CONTROL_MODE, mode_map.get(mode_str, 2), 'b')

    def send_pid_gain_to_motor(self, motor_id, register, value):
         self._motor_service.send_command(motor_id, register, float(value), 'f')

    def set_pid_gain(self, register, value):
        self.send_pid_gain_to_motor(self.active_motor_id, register, value)

    def enable_motor(self, enable):
        if self.active_motor_id is None: return
        self._motor_service.send_command(self.active_motor_id, REG_ENABLE, 1 if enable else 0, 'b')
        
    def enable_motor_by_id(self, motor_id, enable):
        self._motor_service.send_command(motor_id, REG_ENABLE, 1 if enable else 0, 'b')

    def set_control_mode(self, mode_str):
        if self.active_motor is None: return
        new_target = 0.0
        if mode_str == "Angle": new_target = self.active_motor.angle
        self.send_control_mode_to_motor(self.active_motor_id, mode_str)
        self.set_target(new_target)
        self.ui_manager.update_target_input(new_target)

    def set_target(self, target_value):
        target = float(target_value)
        self.send_target_to_motor(self.active_motor_id, target)
        self._previous_gui_target = target

    def set_motor_parameter_float(self, register, value):
        self._motor_service.send_command(self.active_motor_id, register, float(value), 'f')
    
    def set_motor_parameter_byte(self, register, value):
        self._motor_service.send_command(self.active_motor_id, register, int(value), 'b')

    def flip_sensor_direction(self):
        if self.active_motor_id is None:
            self.log_message("ERROR: No motor selected.")
            return
        self.log_message(f"Sending Flip Sensor Direction command to motor {self.active_motor_id}...")
        self._motor_service.send_command(self.active_motor_id, REG_CUSTOM_FLIP_SENSOR_DIR, 1, 'b')

    def save_to_eeprom(self):
        if self.active_motor_id is None:
            self.log_message("ERROR: No motor selected.")
            return
        self.log_message(f"Sending Save to EEPROM command to motor {self.active_motor_id}...")
        self._motor_service.send_command(self.active_motor_id, REG_CUSTOM_SAVE_TO_EEPROM, 1, 'b')

    def set_id_save_and_restart(self):
            if self.active_motor_id is None:
                self.log_message("ERROR: No motor selected.")
                return
            try:
                new_id = dpg.get_value("new_can_id_input")
                if not (1 <= new_id <= 127):
                    self.log_message("ERROR: CAN ID must be between 1 and 127.")
                    return
                self.log_message(f"Sending command to motor {self.active_motor_id} to set new ID to {new_id} and restart.")
                self._motor_service.send_command(self.active_motor_id, REG_CUSTOM_SET_ID_AND_RESTART, new_id, 'b')
                self.log_message("Command sent. The motor should restart with the new ID. Please re-scan for motors after a moment.")
            except Exception as e:
                self.log_message(f"Error during set and restart sequence: {e}")

    def request_all_params(self):
        if self.active_motor_id is not None:
            self.request_motor_params(self.active_motor_id)

    def request_motor_params(self, motor_id):
        self.log_message(f"Requesting all parameters from motor {motor_id}...")
        params_to_request = [
            REG_VOLTAGE_LIMIT, REG_CURRENT_LIMIT, REG_VELOCITY_LIMIT,
            REG_DRIVER_VOLTAGE_PSU, REG_VOLTAGE_SENSOR_ALIGN,
            REG_POLE_PAIRS, REG_PHASE_RESISTANCE, REG_KV, REG_INDUCTANCE,
            REG_ANG_PID_P, REG_ANG_PID_I, REG_ANG_PID_D, REG_ANG_PID_RAMP, REG_ANG_PID_LIM,
            REG_VEL_PID_P, REG_VEL_PID_I, REG_VEL_PID_D, REG_VEL_LPF_T, REG_VEL_PID_RAMP, REG_VEL_PID_LIM,
            REG_CURQ_PID_P, REG_CURQ_PID_I, REG_CURQ_PID_D, REG_CURQ_LPF_T,
            REG_CURD_PID_P, REG_CURD_PID_I, REG_CURD_PID_D, REG_CURD_LPF_T
        ]
        for param in params_to_request:
            self._motor_service.request_parameter(motor_id, param)
            time.sleep(0.05)
            
    def update(self):
        now = time.time()

        # --- MODIFIED: This block now handles multiple motors ---
        if self.is_moving and self.sync_motors: # Check against the new list
            elapsed_time = now - self.trajectory_start_time
            
            if self.trajectory_index < len(self.trajectory_points):
                if now >= self.trajectory_start_time + self.trajectory_points[self.trajectory_index][0]:
                    pos_sp, vel_sp, acc_sp = self.trajectory_points[self.trajectory_index][1:]
                    
                    # Loop through all selected motors and send the command
                    for motor in self.sync_motors:
                        self._motor_service.send_motion_command(motor.id, pos_sp, vel_sp, acc_sp)

                    self._data_service.add_data_point("plan_pos", now, pos_sp)
                    self._data_service.add_data_point("plan_vel", now, vel_sp)
                    self._data_service.add_data_point("plan_acc", now, acc_sp)
                    self.trajectory_index += 1
            else:
                self.is_moving = False
                self.log_message("Trajectory complete.")
                final_pos = self.trajectory_points[-1][1]
                # Send final position to all motors
                for motor in self.sync_motors:
                    self._motor_service.send_motion_command(motor.id, final_pos, 0.0, 0.0)
        # --- END MODIFICATION ---

        if self.is_connected:
            period = 1.0 / self.active_telemetry_rate_hz if self.active_telemetry_rate_hz > 0 else 0.01
            if now - self.last_gui_target_update_time >= period:
                self._data_service.add_data_point("gui_target", now, self._previous_gui_target)
                self.last_gui_target_update_time = now

            message_queue = self._can_service.get_message_queue()
            try:
                while not message_queue.empty():
                    msg = message_queue.get_nowait()
                    self.telemetry_packet_counter += 1
                    result = self._motor_service.process_message(msg, self.motors)
                    
                    if not result: continue
                    event_type, data = result
                    if event_type == 'new_motor':
                        if data.id not in [m.id for m in self.motors]:
                            self.motors.append(data)
                            self.log_message(f"Discovered new motor with ID: {data.id}")
                            self.ui_manager.rebuild_dynamic_ui()
                    elif event_type == 'telemetry':
                        motor = self.get_motor_by_id(data['motor_id'])
                        if motor:
                            motor.angle, motor.velocity, motor.current_q = data['angle'], data['velocity'], data['current_q']
                    
                    elif event_type == 'status_feedback':
                        motor = self.get_motor_by_id(data['motor_id'])
                        if motor:
                            motor.status_angle = data['angle']
                            motor.status_velocity = data['velocity']
                            motor.state = data['state']
                            
                    elif event_type == 'param_response':
                        motor = self.get_motor_by_id(data['motor_id'])
                        if motor:
                            if data['reg_id'] == REG_PHASE_RESISTANCE: motor.phase_resistance = data['value']
                            elif data['reg_id'] == REG_INDUCTANCE: motor.phase_inductance = data['value']
                        self.ui_manager.update_parameter_widgets(reg_id=data['reg_id'], value=data['value'])
                    elif event_type == 'status_response':
                        motor = self.get_motor_by_id(data['motor_id'])
                        if motor:
                            motor.is_enabled = data['is_enabled']
                            if motor.id == self.active_motor_id: self.ui_manager.update_enable_checkbox(motor.is_enabled)
                    elif event_type == 'char_response':
                        self.characterization_results = {'R': data['R'], 'L': data['L']}
                        if self.active_motor:
                            self.active_motor.phase_resistance = data['R']
                            self.active_motor.phase_inductance = data['L']
                        self.ui_manager.update_parameter_widgets(REG_PHASE_RESISTANCE, data['R'])
                        self.ui_manager.update_parameter_widgets(REG_INDUCTANCE, data['L'])
            except queue.Empty: pass
        
        if now - self.last_freq_calc_time > 1.0:
            self.telemetry_rate_hz = self.telemetry_packet_counter
            self.plot_rate_fps = self.plot_update_counter
            self.ui_manager.update_data_rate_display(self.telemetry_rate_hz, self.plot_rate_fps)
            self.telemetry_packet_counter = 0
            self.plot_update_counter = 0
            self.last_freq_calc_time = now

        if self.active_motor_id not in [m.id for m in self.motors]: 
            if self.active_motor_id is not None:
                self.select_motor(None, None, None)

    def disconnect(self):
        if self.is_connected: self._can_service.disconnect()

    def send_sync(self):
        self._motor_service.send_sync()

    def plan_and_execute_trajectory(self):
        # --- MODIFIED: This method now finds all selected items in our custom list ---
        self.sync_motors.clear()
        all_motor_names = [f"Motor {m.id}" for m in self.motors]

        for name in all_motor_names:
            # Check if the selectable item for this motor exists and is selected (value is True)
            if dpg.does_item_exist(f"selectable_{name}") and dpg.get_value(f"selectable_{name}"):
                try:
                    motor_id = int(name.split(" ")[1])
                    motor = self.get_motor_by_id(motor_id)
                    if motor:
                        self.sync_motors.append(motor)
                except (ValueError, IndexError):
                    self.log_message(f"Warning: Could not parse motor ID from '{name}'")
        
        if not self.sync_motors:
            self.log_message("ERROR: No motors selected for synchronized move.")
            return

        if self.is_moving:
            self.log_message("Cannot start new move: A move is already in progress.")
            return

        # Use the first motor in the list as the reference for current position
        reference_motor = self.sync_motors[0]
        current_pos = reference_motor.angle
        # --- END MODIFICATION ---
        
        target_pos = dpg.get_value("pos_cmd_input")
        max_vel = dpg.get_value("vel_cmd_input")
        max_acc = dpg.get_value("acc_cmd_input")

        if max_vel <= 0 or max_acc <= 0:
            self.log_message("ERROR: Max Velocity and Acceleration must be positive.")
            return
            
        self.trajectory_points = self._generate_s_curve_trajectory_points(current_pos, target_pos, max_vel, max_acc)
        
        if not self.trajectory_points:
            self.log_message("Could not plan trajectory.")
            return
            
        self.log_message(f"Starting S-Curve trajectory for {len(self.sync_motors)} motors with {len(self.trajectory_points)} points.")
        self.is_moving = True
        self.trajectory_index = 0
        self.trajectory_start_time = time.time()
        
        for motor in self.sync_motors:
            self.enable_motor_by_id(motor.id, True)

        time.sleep(0.02)
        self.send_sync()

    def _generate_trapezoidal_fallback(self, p0, p1, v_max, a_max):
        delta_p = p1 - p0
        direction = np.sign(delta_p)
        
        t_ramp = v_max / a_max
        p_ramp = 0.5 * a_max * t_ramp**2

        if abs(delta_p) < 2 * p_ramp:
            t_ramp = np.sqrt(abs(delta_p) / a_max)
            t_total = 2 * t_ramp
            v_actual_max = a_max * t_ramp
            t_cruise = 0
        else:
            p_cruise = abs(delta_p) - 2 * p_ramp
            t_cruise = p_cruise / v_max
            t_total = 2 * t_ramp + t_cruise
            v_actual_max = v_max
        
        points = []
        t = 0
        while t <= t_total:
            if t < t_ramp:
                acc = direction * a_max
                vel = acc * t
                pos = p0 + 0.5 * acc * t**2
            elif t < t_ramp + t_cruise:
                acc = 0.0
                vel = direction * v_actual_max
                p_so_far = 0.5 * direction * a_max * t_ramp**2
                pos = p0 + p_so_far + vel * (t - t_ramp)
            else:
                t_decel = t - (t_ramp + t_cruise)
                acc = -direction * a_max
                vel = direction * v_actual_max + acc * t_decel
                p_so_far = direction * (p_ramp + v_actual_max * t_cruise)
                pos = p0 + p_so_far + (direction * v_actual_max * t_decel) + (0.5 * acc * t_decel**2)

            points.append((t, pos, vel, acc))
            t += self.trajectory_update_period
        
        points.append((t_total, p1, 0, 0))
        return points

    def _generate_s_curve_trajectory_points(self, p0, p1, v_max, a_max):
        """
        Generates a 7-phase S-curve trajectory.

        This version corrects a fundamental error in the planning stage. The previous
        calculation for `p_ramp` (distance during acceleration) was incorrect,
        overestimating the distance and causing the cruise phase to be too short.
        This resulted in the trajectory undershooting the target. The formula has
        been replaced with the kinematically correct equation, ensuring the planner
        accurately computes phase timings and total displacement.
        """
        j_max = a_max * 10  # A common heuristic for jerk

        delta_p = p1 - p0
        if abs(delta_p) < 1e-6:
            return [(0, p0, 0, 0)]
        direction = np.sign(delta_p)
        abs_delta_p = abs(delta_p)

        # --- 1. Planning Stage: Determine Profile Shape and Timings ---

        # Condition 1: Check if v_max is reachable given a_max.
        if v_max * a_max / j_max > v_max**2:
            # This is equivalent to a_max**2 / j_max > v_max
            self.log_message("Move too short for S-Curve (a_max unreachable), using Trapezoidal fallback.")
            return self._generate_trapezoidal_fallback(p0, p1, v_max, a_max)

        # Time to reach a_max from zero acceleration
        t_j = a_max / j_max
        # Time at constant a_max to reach v_max
        t_a = v_max / a_max - t_j

        # --- THE CORE FIX ---
        # Calculate the distance covered during the acceleration and deceleration ramps.
        # The previous formula `p_ramp = v_max * (t_j + t_a)` was incorrect as it
        # calculated the area of a rectangle, not the area under the S-shaped curve.
        # The correct formula is:
        p_ramp = 0.5 * v_max * (v_max / a_max + a_max / j_max)

        # Condition 2: Check if there is a cruise phase.
        if abs_delta_p < 2 * p_ramp:
            self.log_message("Move too short for S-Curve cruise phase, using Trapezoidal fallback.")
            # Note: A full implementation would calculate a triangular or abbreviated profile here.
            return self._generate_trapezoidal_fallback(p0, p1, v_max, a_max)

        # If a cruise phase exists, calculate its duration.
        p_cruise = abs_delta_p - 2 * p_ramp
        t_cruise = p_cruise / v_max

        # Calculate phase transition timestamps
        t1 = t_j
        t2 = t1 + t_a
        t3 = t2 + t_j
        t4 = t3 + t_cruise
        t5 = t4 + t_j
        t6 = t5 + t_a
        t7 = t6 + t_j
        t_total = t7

        # --- 2. Boundary Condition Calculation ---
        # Calculate the true kinematic state at the end of each phase.

        # End of Phase 1
        a1_end = direction * j_max * t1
        v1_end = direction * 0.5 * j_max * t1**2
        p1_end = p0 + direction * (1/6) * j_max * t1**3
        
        # End of Phase 2
        a2_end = a1_end
        v2_end = v1_end + a1_end * t_a
        p2_end = p1_end + v1_end * t_a + 0.5 * a1_end * t_a**2

        # End of Phase 3
        a3_end = a2_end - direction * j_max * t_j
        v3_end = v2_end + a2_end * t_j - 0.5 * direction * j_max * t_j**2
        p3_end = p2_end + v2_end * t_j + 0.5 * a2_end * t_j**2 - (1/6) * direction * j_max * t_j**3

        # End of Phase 4
        a4_end = 0.0
        v4_end = v3_end
        p4_end = p3_end + v3_end * t_cruise

        # End of Phase 5
        a5_end = a4_end - direction * j_max * t_j
        v5_end = v4_end - 0.5 * direction * j_max * t_j**2
        p5_end = p4_end + v4_end * t_j - (1/6) * direction * j_max * t_j**3

        # End of Phase 6
        a6_end = a5_end
        v6_end = v5_end + a5_end * t_a
        p6_end = p5_end + v5_end * t_a + 0.5 * a5_end * t_a**2

        # --- 3. Generation Stage: Create Trajectory Points ---
        points = []
        t = 0.0
        while t <= t_total:
            pos, vel, acc = 0.0, 0.0, 0.0
            
            if t <= t1:
                _t = t
                jerk = direction * j_max
                p_initial, v_initial, a_initial = p0, 0.0, 0.0
                acc = a_initial + jerk * _t
                vel = v_initial + a_initial * _t + 0.5 * jerk * _t**2
                pos = p_initial + v_initial * _t + 0.5 * a_initial * _t**2 + (1/6) * jerk * _t**3
            
            elif t <= t2:
                _t = t - t1
                p_initial, v_initial, a_initial = p1_end, v1_end, a1_end
                acc = a_initial
                vel = v_initial + a_initial * _t
                pos = p_initial + v_initial * _t + 0.5 * a_initial * _t**2

            elif t <= t3:
                _t = t - t2
                jerk = -direction * j_max
                p_initial, v_initial, a_initial = p2_end, v2_end, a2_end
                acc = a_initial + jerk * _t
                vel = v_initial + a_initial * _t + 0.5 * jerk * _t**2
                pos = p_initial + v_initial * _t + 0.5 * a_initial * _t**2 + (1/6) * jerk * _t**3

            elif t <= t4:
                _t = t - t3
                p_initial, v_initial, a_initial = p3_end, v3_end, a3_end
                acc = 0.0
                vel = v_initial
                pos = p_initial + v_initial * _t

            elif t <= t5:
                _t = t - t4
                jerk = -direction * j_max
                p_initial, v_initial, a_initial = p4_end, v4_end, a4_end
                acc = a_initial + jerk * _t
                vel = v_initial + a_initial * _t + 0.5 * jerk * _t**2
                pos = p_initial + v_initial * _t + 0.5 * a_initial * _t**2 + (1/6) * jerk * _t**3

            elif t <= t6:
                _t = t - t5
                p_initial, v_initial, a_initial = p5_end, v5_end, a5_end
                acc = a_initial
                vel = v_initial + a_initial * _t
                pos = p_initial + v_initial * _t + 0.5 * a_initial * _t**2

            else:  # t <= t7
                _t = t - t6
                jerk = direction * j_max
                p_initial, v_initial, a_initial = p6_end, v6_end, a6_end
                acc = a_initial + jerk * _t
                vel = v_initial + a_initial * _t + 0.5 * jerk * _t**2
                pos = p_initial + v_initial * _t + 0.5 * a_initial * _t**2 + (1/6) * jerk * _t**3

            points.append((t, pos, vel, acc))
            t += self.trajectory_update_period

        # Ensure the final point is exactly at the target with zero velocity/acceleration.
        points.append((t_total, p1, 0.0, 0.0))
        return points

    # --- ALL OTHER METHODS (gearing, tuning, etc.) ---
    def start_gearing(self, leader_id_str, follower_id_str, ratio_str):
        try:
            leader_id = int(leader_id_str)
            follower_id = int(follower_id_str)
            ratio = float(ratio_str)
            if leader_id == follower_id:
                self.log_message("ERROR: Leader and follower cannot be the same motor.")
                return
            self._gearing_service.start(leader_id, follower_id, ratio, mode="position")
        except (ValueError, TypeError):
            self.log_message("ERROR: Invalid motor ID or ratio for gearing.")

    def start_drive_by_wire(self, leader_id_str, follower_id_str, ratio_str):
        try:
            leader_id = int(leader_id_str)
            follower_id = int(follower_id_str)
            ratio = float(ratio_str)
            if leader_id == follower_id:
                self.log_message("ERROR: Leader and follower cannot be the same motor.")
                return
            self._gearing_service.start(leader_id, follower_id, ratio, mode="drive_by_wire")
        except (ValueError, TypeError):
            self.log_message("ERROR: Invalid motor ID or ratio for drive-by-wire.")

    def stop_gearing(self):
        self._gearing_service.stop()
        
    def set_gearing_target(self, target):
        if self._gearing_service.is_active and self._gearing_service.mode == "position":
            try:
                self._gearing_service.target_position = float(target)
            except ValueError:
                self.log_message("ERROR: Invalid gearing target.")

    def start_autotune(self, amp, dur):
        if self.active_motor_id is None:
            self.autotune_status = "Error: No motor selected."
            return
        self._tuning_service.start_autotune(self.active_motor_id, amp, dur)

    def apply_autotune_gains(self):
        if self.autotune_results and self.active_motor_id is not None:
            p_gain = self.autotune_results["p"]
            i_gain = self.autotune_results["i"]
            self.send_pid_gain_to_motor(self.active_motor_id, REG_VEL_PID_P, p_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_VEL_PID_I, i_gain)
            self.ui_manager.update_parameter_widgets(REG_VEL_PID_P, p_gain)
            self.ui_manager.update_parameter_widgets(REG_VEL_PID_I, i_gain)
    
    def calculate_and_apply_bandwidth_gains(self, bandwidth_hz):
        if self.active_motor is None:
            self.log_message("ERROR: No active motor selected.")
            return
        
        motor_r = self.active_motor.phase_resistance
        motor_l = self.active_motor.phase_inductance

        if motor_r <= 0 or motor_l <= 0:
            self.log_message("ERROR: Motor phase resistance and inductance must be known and positive.")
            return

        try:
            bw_rads = float(bandwidth_hz) * 2 * math.pi
            p_gain = motor_l * bw_rads
            i_gain = motor_r * bw_rads
            lpf_hz = float(bandwidth_hz) * 5
            lpf_t = 1.0 / (2 * math.pi * lpf_hz) if lpf_hz > 0 else 0.0
            
            self.log_message(f"Applying Current Gains from BW ({bandwidth_hz} Hz): P={p_gain:.4f}, I={i_gain:.4f}, LPF={lpf_t*1000:.2f}ms")
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURQ_PID_P, p_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURQ_PID_I, i_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURD_PID_P, p_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURD_PID_I, i_gain)
            self.set_motor_parameter_float(REG_CURQ_LPF_T, lpf_t)
            self.set_motor_parameter_float(REG_CURD_LPF_T, lpf_t)
            self.ui_manager.update_parameter_widgets(REG_CURQ_PID_P, p_gain)
            self.ui_manager.update_parameter_widgets(REG_CURQ_PID_I, i_gain)
            self.ui_manager.update_parameter_widgets(REG_CURD_PID_P, p_gain)
            self.ui_manager.update_parameter_widgets(REG_CURD_PID_I, i_gain)
            self.ui_manager.update_parameter_widgets(REG_CURQ_LPF_T, lpf_t)
            self.ui_manager.update_parameter_widgets(REG_CURD_LPF_T, lpf_t)
        except Exception as e:
            self.log_message(f"Error applying bandwidth gains: {e}")
            
    def add_series_to_plot(self, data_key):
        if not data_key: return
        if any(s.data_key == data_key for s in self.the_plot.series_list): return
        new_series = SeriesConfig(data_key=data_key)
        self.the_plot.series_list.append(new_series)
        self.ui_manager.rebuild_dynamic_ui()

    def remove_series(self, series_id):
        self.the_plot.series_list = [s for s in self.the_plot.series_list if s.id != series_id]
        self.ui_manager.rebuild_dynamic_ui()

    def set_telemetry_rate(self, rate_str):
        if self.active_motor_id is None: return
        try:
            freq_hz = int(rate_str.replace(" Hz", ""))
            self.active_telemetry_rate_hz = float(freq_hz)
            period_us = int(1_000_000 / freq_hz) if freq_hz > 0 else 0
            self._motor_service.send_command(self.active_motor_id, REG_CUSTOM_TELEMETRY_PERIOD, period_us, 'L')
        except ValueError:
            self.log_message(f"Invalid frequency format: {rate_str}")

    def set_plot_pause_state(self, is_paused):
        self.is_plot_paused = is_paused

    def set_plot_history_length(self, length):
        self._data_service.change_history_length(length)

    def get_available_data_keys(self):
        return self._data_service.get_all_stream_keys()

    def get_stream_data(self, key):
        return self._data_service.get_stream_data(key)

    def start_or_resume_winder(self, config):
        self._winder_service.start_or_resume(config)

    def pause_winder(self):
        self._winder_service.pause()

    def stop_winder(self):
        self._winder_service.stop()

    def unwind_winder(self):
        self._winder_service.unwind()

    def jog_winder(self, jog_revs):
        self._winder_service.jog(jog_revs)

    def start_sysid(self):
        if self.active_motor_id is None:
            self.sysid_status = "Error: No motor selected."
            return
        config = {
            "motor_id": self.active_motor_id,
            "start_freq": dpg.get_value("sysid_start_freq"),
            "end_freq": dpg.get_value("sysid_end_freq"),
            "amplitude": dpg.get_value("sysid_amp"),
            "duration": dpg.get_value("sysid_dur"),
            "lambda_tc": dpg.get_value("sysid_lambda"),
        }
        self._sysid_tuner_service.start(config)

    def apply_sysid_gains(self):
        if self.sysid_results and self.active_motor_id is not None:
            p_gain = self.sysid_results["p"]
            i_gain = self.sysid_results["i"]
            self.send_pid_gain_to_motor(self.active_motor_id, REG_VEL_PID_P, p_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_VEL_PID_I, i_gain)
            self.ui_manager.update_parameter_widgets(REG_VEL_PID_P, p_gain)
            self.ui_manager.update_parameter_widgets(REG_VEL_PID_I, i_gain)

    def run_current_step_test(self):
        if self.active_motor_id is None:
            self.log_message("ERROR: No motor selected for test.")
            return
        amplitude = dpg.get_value("current_test_amp")
        self._tuning_service.run_current_step_test(self.active_motor_id, amplitude)
        
    def calculate_tuning_recommendations(self):
        if self.active_motor is None:
            self.log_message("ERROR: No active motor selected.")
            return
        motor_r = self.active_motor.phase_resistance
        motor_l = self.active_motor.phase_inductance
        if motor_r <= 0 or motor_l <= 0:
            self.log_message("ERROR: Motor phase resistance and inductance must be known and positive.")
            self.tuning_recommendations = None
            return
        tau_e = motor_l / motor_r
        reco_bw = (1 / tau_e) / 10 
        aggression = dpg.get_value("reco_aggression")
        self.tuning_recommendations = {
            "electrical_time_constant_ms": tau_e * 1000,
            "recommended_current_bw": reco_bw * aggression,
            "recommended_vel_p": 0.2 * aggression,
            "recommended_vel_i": 2.0 * aggression,
            "recommended_angle_p": 20.0 * aggression
        }
        self.log_message("Calculated tuning recommendations based on L/R time constant.")

    def apply_recommended_gains(self):
        if not self.tuning_recommendations or self.active_motor_id is None:
            self.log_message("ERROR: No recommendations to apply.")
            return
        recs = self.tuning_recommendations
        self.log_message("Applying recommended safe gains for smooth start.")
        bw = recs['recommended_current_bw']
        self.calculate_and_apply_bandwidth_gains(bw)
        dpg.set_value("current_bw_input", bw)
        vel_p = recs['recommended_vel_p']
        self.send_pid_gain_to_motor(self.active_motor_id, REG_VEL_PID_P, vel_p)
        self.ui_manager.update_parameter_widgets(REG_VEL_PID_P, vel_p)
        vel_i = recs['recommended_vel_i']
        self.send_pid_gain_to_motor(self.active_motor_id, REG_VEL_PID_I, vel_i)
        self.ui_manager.update_parameter_widgets(REG_VEL_PID_I, vel_i)
        angle_p = recs['recommended_angle_p']
        self.send_pid_gain_to_motor(self.active_motor_id, REG_ANG_PID_P, angle_p)
        self.ui_manager.update_parameter_widgets(REG_ANG_PID_P, angle_p)
        
    def start_characterization(self):
        if self.active_motor_id is None:
            self.characterization_status = "Error: No motor selected."
            return
        voltage = dpg.get_value("characterize_voltage")
        self._characterization_service.start(self.active_motor_id, voltage)

    def create_following_error_signal(self, name, key1, key2):
        if not name or not key1 or not key2:
            self.log_message("ERROR: Please provide a name and select two signals.")
            return
        if name in self.get_available_data_keys():
            self.log_message(f"ERROR: A signal named '{name}' already exists.")
            return
        self._data_service.register_calculated_stream(name, "subtract", [key1, key2])
        self.log_message(f"Created new signal '{name}' = {key1} - {key2}")
        self.ui_manager.rebuild_dynamic_ui()
        self.ui_manager.close_popups()
        
    def create_derivative_signal(self, name, key):
        if not name or not key:
            self.log_message("ERROR: Please provide a name and select a source signal.")
            return
        if name in self.get_available_data_keys():
            self.log_message(f"ERROR: A signal named '{name}' already exists.")
            return
        self._data_service.register_calculated_stream(name, "differentiate", [key])
        self.log_message(f"Created new signal '{name}' = d/dt({key})")
        self.ui_manager.rebuild_dynamic_ui()
        self.ui_manager.close_popups()
        
    def start_performance_test(self, test_type):
        if self.active_motor_id is None:
            self.log_message("ERROR: No motor selected for performance test.")
            return

        config = {}
        if test_type == "step_response":
            config = { "amplitude": dpg.get_value("perf_step_amp"), "duration": dpg.get_value("perf_step_dur") }
        elif test_type == "constant_velocity":
            config = { "distance": dpg.get_value("perf_velo_dist"), "velocity": dpg.get_value("perf_velo_speed") }
        elif test_type == "reversing_move":
            config = { "distance": dpg.get_value("perf_rev_dist"), "velocity": dpg.get_value("perf_rev_speed") }
        
        self._performance_service.start_test(test_type, config)