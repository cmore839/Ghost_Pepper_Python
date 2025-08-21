# viewmodels/main_viewmodel.py
import dearpygui.dearpygui as dpg
import queue
import time
import math
import collections
from services.can_service import CanService
from services.motor_service import MotorService
from services.data_service import DataService
from services.tuning_service import TuningService
from services.winder_service import WinderService
from services.gearing_service import GearingService
from services.sysid_tuner_service import SysIdTunerService
from services.characterization_service import CharacterizationService
from models.motor import Motor
from models.plot_config import PlotConfig, SeriesConfig
from config import *
from ui_manager import UIManager

class MainViewModel:
    def __init__(self):
        # Services
        self._can_service = CanService()
        self._data_service = DataService()
        self._motor_service = MotorService(self._can_service, self._data_service)
        self._tuning_service = TuningService(self)
        self._winder_service = WinderService(self)
        self._gearing_service = GearingService(self)
        self._sysid_tuner_service = SysIdTunerService(self)
        self._characterization_service = CharacterizationService(self)
        
        self.ui_manager = UIManager(self)

        # State
        self.is_connected = False
        self.status_text = "Status: Disconnected"
        self.motors = []
        self.active_motor_id = None
        self.active_motor = None
        self.start_time = time.time()
        
        # Plotting State
        self.the_plot = PlotConfig()
        self.is_plot_paused = False
        
        # Event Log
        self.log_messages = collections.deque(maxlen=100)

        # Data Rate Tracking
        self.telemetry_packet_counter = 0
        self.last_freq_calc_time = 0

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
        
        self._data_service.register_stream("gui_target")
        self._previous_gui_target = 0.0
        self.log_message("Welcome! Connect to the CAN bus to begin.")

    def log_message(self, message):
        log_time = time.strftime("%H:%M:%S", time.localtime())
        self.log_messages.appendleft(f"[{log_time}] {message}")
        if dpg.is_dearpygui_running():
            self.ui_manager.update_log()

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

    def select_motor(self, motor_id_str):
        try:
            motor_id = int(motor_id_str)
            self.active_motor_id = motor_id
            self.active_motor = self.get_motor_by_id(motor_id)
            self.tuning_recommendations = None 
            self.log_message(f"Selected motor {motor_id}")
            if self.active_motor_id is not None:
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
        self._motor_service.send_command(self.active_motor_id, REG_ENABLE, 1 if enable else 0, 'b')
        time.sleep(0.05)
        self._motor_service.request_parameter(self.active_motor_id, REG_STATUS)
        
    def enable_motor_by_id(self, motor_id, enable):
        self._motor_service.send_command(motor_id, REG_ENABLE, 1 if enable else 0, 'b')

    def set_control_mode(self, mode_str):
        if self.active_motor is None: return
        mode_map = {"Torque": 0, "Velocity": 1, "Angle": 2}
        new_target = 0.0
        if mode_str == "Angle": new_target = self.active_motor.angle
        self.send_control_mode_to_motor(self.active_motor_id, mode_str)
        self.set_target(new_target)
        self.ui_manager.update_target_input(new_target)

    def set_target(self, target_value):
        target = float(target_value)
        self.send_target_to_motor(self.active_motor_id, target)
        
        now = time.time()
        self._data_service.add_data_point("gui_target", now - 0.001, self._previous_gui_target)
        self._data_service.add_data_point("gui_target", now, target)
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
        if self.is_connected:
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
        
        now = time.time()
        if now - self.last_freq_calc_time > 1.0:
            self.ui_manager.update_data_rate_display(self.telemetry_packet_counter)
            self.telemetry_packet_counter = 0
            self.last_freq_calc_time = now

        if self.active_motor_id not in [m.id for m in self.motors]: self.select_motor(None)

    def disconnect(self):
        if self.is_connected: self._can_service.disconnect()

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

    # NEW: Function to start the drive-by-wire mode
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
            self.ui_manager.update_pid_sliders(REG_VEL_PID_P, p_gain)
            self.ui_manager.update_pid_sliders(REG_VEL_PID_I, i_gain)
    
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
            
            self.log_message(f"Applying Current Gains from BW ({bandwidth_hz} Hz): P={p_gain:.4f}, I={i_gain:.4f}")

            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURQ_PID_P, p_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURQ_PID_I, i_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURD_PID_P, p_gain)
            self.send_pid_gain_to_motor(self.active_motor_id, REG_CURD_PID_I, i_gain)
            
            self.ui_manager.update_parameter_widgets(REG_CURQ_PID_P, p_gain)
            self.ui_manager.update_parameter_widgets(REG_CURQ_PID_I, i_gain)
            self.ui_manager.update_parameter_widgets(REG_CURD_PID_P, p_gain)
            self.ui_manager.update_parameter_widgets(REG_CURD_PID_I, i_gain)

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