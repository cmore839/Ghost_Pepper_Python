# ui_manager.py
import dearpygui.dearpygui as dpg
from config import *
import numpy as np

class UIManager:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._ui_needs_rebuild = False

    def create_all_ui_panels(self):
        self._create_motor_management_panel()
        self._create_motor_limits_panel()
        self._create_motor_params_panel()
        self._create_real_time_control_panel()
        self._create_pid_tuning_panel()
        self._create_winder_panel()
        self._create_gearing_panel() 
        self._create_advanced_tuning_panel()
        self._create_performance_panel() # New Panel Added Here
        self._create_plot_manager_panel()
        self._create_general_settings_panel()

    def rebuild_dynamic_ui(self):
        self._ui_needs_rebuild = True

    def create_and_update_dynamic_ui(self):
        if self._ui_needs_rebuild:
            if dpg.does_item_exist("plot_manager_content"):
                dpg.delete_item("plot_manager_content", children_only=True)
            if dpg.does_item_exist("plots_area_content"):
                dpg.delete_item("plots_area_content", children_only=True)
            
            self._build_plot_manager_content(parent="plot_manager_content")
            self._build_plots_area_content(parent="plots_area_content")
            
            self._ui_needs_rebuild = False
        
        # --- Start of Frequent UI Updates ---
        motor_ids = [str(m.id) for m in self._viewmodel.motors]
        if dpg.does_item_exist("gearing_leader_selector"):
            dpg.configure_item("gearing_leader_selector", items=motor_ids)
            dpg.configure_item("gearing_follower_selector", items=motor_ids)
        if dpg.does_item_exist("winder_bobbin_selector"):
            dpg.configure_item("winder_bobbin_selector", items=motor_ids)
            dpg.configure_item("winder_tension_selector", items=motor_ids)
            
        if dpg.does_item_exist("gearing_status_group"):
            dpg.delete_item("gearing_status_group", children_only=True)
            if self._viewmodel._gearing_service.is_active:
                gear_service = self._viewmodel._gearing_service
                dpg.add_text(f"Leader: {gear_service.leader_id}", parent="gearing_status_group")
                dpg.add_text(f"Follower: {gear_service.follower_id}", parent="gearing_status_group")
        
        if dpg.does_item_exist("autotune_status_text"):
            dpg.set_value("autotune_status_text", self._viewmodel.autotune_status)
            dpg.configure_item("autotune_start_btn", enabled=not self._viewmodel.autotune_active)
            dpg.configure_item("autotune_apply_btn", enabled=self._viewmodel.autotune_results is not None)
            
        if dpg.does_item_exist("winder_status_text"):
            dpg.set_value("winder_status_text", self._viewmodel.winder_status)
            
        if dpg.does_item_exist("sysid_status_text"):
            dpg.set_value("sysid_status_text", self._viewmodel.sysid_status)
            dpg.configure_item("sysid_start_btn", enabled=not self._viewmodel._sysid_tuner_service.is_active)
            if self._viewmodel.sysid_results:
                dpg.set_value("sysid_k_text", f"{self._viewmodel.sysid_results['K']:.4f}")
                dpg.set_value("sysid_tau_text", f"{self._viewmodel.sysid_results['tau']:.4f} s")
                dpg.set_value("sysid_p_text", f"{self._viewmodel.sysid_results['p']:.4f}")
                dpg.set_value("sysid_i_text", f"{self._viewmodel.sysid_results['i']:.4f}")
                dpg.enable_item("sysid_apply_btn")
            else:
                dpg.set_value("sysid_k_text", "--"); dpg.set_value("sysid_tau_text", "--"); dpg.set_value("sysid_p_text", "--"); dpg.set_value("sysid_i_text", "--")
                dpg.disable_item("sysid_apply_btn")

        if dpg.does_item_exist("current_test_rise_time"):
            results = self._viewmodel.current_test_results
            if results:
                dpg.set_value("current_test_rise_time", f"{results['rise_time']*1000:.2f} ms" if results['rise_time'] > 0 else "N/A")
                dpg.set_value("current_test_overshoot", f"{results['overshoot']:.2f} %")
                dpg.set_value("current_test_settling_time", f"{results['settling_time']*1000:.2f} ms" if results['settling_time'] > 0 else "N/A")
                dpg.set_value("current_test_peak_time", f"{results['peak_time']*1000:.2f} ms" if results['peak_time'] > 0 else "N/A")
            else:
                dpg.set_value("current_test_rise_time", "--"); dpg.set_value("current_test_overshoot", "--"); dpg.set_value("current_test_settling_time", "--"); dpg.set_value("current_test_peak_time", "--")
                
        recs = self._viewmodel.tuning_recommendations
        if recs:
            dpg.set_value("reco_time_constant_text", f"{recs['electrical_time_constant_ms']:.3f} ms")
            dpg.set_value("reco_current_bw_text", f"{recs['recommended_current_bw']:.0f} Hz")
            dpg.set_value("reco_vel_p_text", f"{recs['recommended_vel_p']:.2f}")
            dpg.set_value("reco_vel_i_text", f"{recs['recommended_vel_i']:.2f}")
            dpg.set_value("reco_angle_p_text", f"{recs['recommended_angle_p']:.2f}")
        else:
            dpg.set_value("reco_time_constant_text", "--"); dpg.set_value("reco_current_bw_text", "--"); dpg.set_value("reco_vel_p_text", "--"); dpg.set_value("reco_vel_i_text", "--"); dpg.set_value("reco_angle_p_text", "--")
            
        if dpg.does_item_exist("characterization_status_text"):
            dpg.set_value("characterization_status_text", self._viewmodel.characterization_status)
            dpg.configure_item("characterize_start_btn", enabled=not self._viewmodel._characterization_service.is_active)
        
        # New call to update performance results
        self.update_performance_results_ui()

    def _create_motor_management_panel(self):
        with dpg.collapsing_header(label="Device Configuration", default_open=False):
            dpg.add_button(label="Flip Sensor Direction", width=-1, callback=self._viewmodel.flip_sensor_direction)
            dpg.add_button(label="Save All Parameters to Motor", width=-1, callback=self._viewmodel.save_to_eeprom)
            dpg.add_separator()
            dpg.add_text("Set CAN ID and Restart", color=[255, 255, 150])
            dpg.add_text("Warning: This will restart the motor.", color=[255, 100, 100])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("New CAN ID")
                    dpg.add_input_int(tag="new_can_id_input", width=-1, min_value=1, max_value=127, default_value=1)
            dpg.add_button(label="Set ID, Save & Restart", width=-1, callback=self._viewmodel.set_id_save_and_restart)

    def _create_motor_limits_panel(self):
        with dpg.collapsing_header(label="Motor Limits", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                
                def create_limit_row(label, tag, register):
                    with dpg.table_row():
                        dpg.add_text(label)
                        dpg.add_input_float(tag=tag, width=-1, on_enter=True,
                                            callback=lambda s, a, u: self._viewmodel.set_motor_parameter_float(u, a),
                                            user_data=register)

                create_limit_row("Voltage Limit (V)", "voltage_limit_input", REG_VOLTAGE_LIMIT)
                create_limit_row("Current Limit (A)", "current_limit_input", REG_CURRENT_LIMIT)
                create_limit_row("Velocity Limit (rad/s)", "velocity_limit_input", REG_VELOCITY_LIMIT)
                create_limit_row("Power Supply (V)", "power_supply_input", REG_DRIVER_VOLTAGE_PSU)
                create_limit_row("Alignment Voltage", "alignment_voltage_input", REG_VOLTAGE_SENSOR_ALIGN)

    def _create_motor_params_panel(self):
        with dpg.collapsing_header(label="Motor Physical Parameters", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Pole Pairs")
                    dpg.add_input_int(tag="pole_pairs_input", width=-1, on_enter=True,
                                        callback=lambda s, a, u: self._viewmodel.set_motor_parameter_byte(u, a),
                                        user_data=REG_POLE_PAIRS)
                with dpg.table_row():
                    dpg.add_text("Phase Resistance (Ω)")
                    dpg.add_input_float(tag="phase_resistance_input", width=-1, on_enter=True,
                                        callback=lambda s, a, u: self._viewmodel.set_motor_parameter_float(u, a),
                                        user_data=REG_PHASE_RESISTANCE)
                with dpg.table_row():
                    dpg.add_text("Phase Inductance (H)")
                    dpg.add_input_float(tag="phase_inductance_input", width=-1, format="%.6f", on_enter=True,
                                        callback=lambda s, a, u: self._viewmodel.set_motor_parameter_float(u, a),
                                        user_data=REG_INDUCTANCE)
                with dpg.table_row():
                    dpg.add_text("Motor KV Rating")
                    dpg.add_input_float(tag="kv_rating_input", width=-1, on_enter=True,
                                        callback=lambda s, a, u: self._viewmodel.set_motor_parameter_float(u, a),
                                        user_data=REG_KV)

    def _create_real_time_control_panel(self):
        with dpg.collapsing_header(label="Real-Time Control", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Motor Status")
                    dpg.add_checkbox(label="Enable", tag="enable_motor_checkbox", callback=lambda s, a: self._viewmodel.enable_motor(a))
                with dpg.table_row():
                    dpg.add_text("Control Mode")
                    dpg.add_radio_button(("Torque", "Velocity", "Angle"), default_value="Angle", horizontal=True, callback=lambda s, a: self._viewmodel.set_control_mode(a), tag="control_mode_radio")
                with dpg.table_row():
                    dpg.add_text("Target")
                    dpg.add_input_float(tag="target_input", default_value=0.0, width=-1, on_enter=True, callback=lambda s, a: self._viewmodel.set_target(a))
            dpg.add_separator()
            dpg.add_text("Live Values:")
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Angle:")
                    dpg.add_text("--", tag="live_angle_text")
                with dpg.table_row():
                    dpg.add_text("Velocity:")
                    dpg.add_text("--", tag="live_velocity_text")
                with dpg.table_row():
                    dpg.add_text("Current Iq:")
                    dpg.add_text("--", tag="live_iq_text")

    def _create_pid_tuning_panel(self):
        with dpg.collapsing_header(label="PID Tuning", default_open=False):
            dpg.add_text("Angle Controller", color=[150, 255, 150])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("P Gain")
                    dpg.add_slider_float(tag="angle_p_slider", max_value=500.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_ANG_PID_P, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("I Gain")
                    dpg.add_slider_float(tag="angle_i_slider", max_value=500.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_ANG_PID_I, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("D Gain")
                    dpg.add_slider_float(tag="angle_d_slider", max_value=1.0, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_ANG_PID_D, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("Output Ramp (rad/s²)")
                    dpg.add_slider_float(tag="angle_ramp_slider", max_value=1000.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_ANG_PID_RAMP, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("Output Limit (rad/s)")
                    dpg.add_slider_float(tag="angle_limit_slider", max_value=1000.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_ANG_PID_LIM, a), width=-1)
            
            dpg.add_separator()
            dpg.add_text("Velocity Controller", color=[150, 255, 150])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("P Gain")
                    dpg.add_slider_float(tag="vel_p_slider", max_value=5.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_VEL_PID_P, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("I Gain")
                    dpg.add_slider_float(tag="vel_i_slider", max_value=50.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_VEL_PID_I, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("D Gain")
                    dpg.add_slider_float(tag="vel_d_slider", max_value=0.5, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_VEL_PID_D, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("LPF Time Const (s)")
                    dpg.add_slider_float(tag="vel_lpf_slider", max_value=0.1, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_VEL_LPF_T, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("Output Ramp (V/s)")
                    dpg.add_slider_float(tag="vel_ramp_slider", max_value=1000.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_VEL_PID_RAMP, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("Output Limit (V)")
                    dpg.add_slider_float(tag="vel_limit_slider", max_value=10.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_VEL_PID_LIM, a), width=-1)

            dpg.add_separator()
            dpg.add_text("Current Iq Controller", color=[150, 255, 150])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("P Gain")
                    dpg.add_slider_float(tag="curq_p_slider", max_value=10.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURQ_PID_P, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("I Gain")
                    dpg.add_slider_float(tag="curq_i_slider", max_value=1000.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURQ_PID_I, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("D Gain")
                    dpg.add_slider_float(tag="curq_d_slider", max_value=0.5, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURQ_PID_D, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("LPF Time Const (s)")
                    dpg.add_slider_float(tag="curq_lpf_slider", max_value=0.1, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURQ_LPF_T, a), width=-1)
            
            dpg.add_separator()
            dpg.add_text("Current Id Controller", color=[150, 255, 150])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("P Gain")
                    dpg.add_slider_float(tag="curd_p_slider", max_value=10.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURD_PID_P, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("I Gain")
                    dpg.add_slider_float(tag="curd_i_slider", max_value=1000.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURD_PID_I, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("D Gain")
                    dpg.add_slider_float(tag="curd_d_slider", max_value=0.5, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURD_PID_D, a), width=-1)
                with dpg.table_row():
                    dpg.add_text("LPF Time Const (s)")
                    dpg.add_slider_float(tag="curd_lpf_slider", max_value=0.1, format="%.4f", callback=lambda s, a: self._viewmodel.set_pid_gain(REG_CURD_LPF_T, a), width=-1)

    def _create_winder_panel(self):
        with dpg.collapsing_header(label="Coil Winder", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Bobbin Motor")
                    dpg.add_combo([], tag="winder_bobbin_selector", width=-1)
                with dpg.table_row():
                    dpg.add_text("Tension Motor")
                    dpg.add_combo([], tag="winder_tension_selector", width=-1)
            dpg.add_separator()
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Total Revolutions")
                    dpg.add_input_float(tag="winder_revs", width=-1, default_value=100.0)
                with dpg.table_row():
                    dpg.add_text("Winding Speed (rad/s)")
                    dpg.add_input_float(tag="winder_speed", width=-1, default_value=15.0)
                with dpg.table_row():
                    dpg.add_text("Acceleration (rad/s²)")
                    dpg.add_input_float(tag="winder_accel", width=-1, default_value=10.0)
                with dpg.table_row():
                    dpg.add_text("Winding Tension (Nm)")
                    dpg.add_input_float(tag="winder_torque", width=-1, default_value=0.1)
                with dpg.table_row():
                    dpg.add_text("Holding Tension (Nm)")
                    dpg.add_input_float(tag="winder_holding_torque", width=-1, default_value=0.05)

            def start_winder_callback():
                try:
                    config = {
                        "bobbin_id": int(dpg.get_value("winder_bobbin_selector")),
                        "tension_id": int(dpg.get_value("winder_tension_selector")),
                        "revolutions": dpg.get_value("winder_revs"),
                        "speed": dpg.get_value("winder_speed"),
                        "accel": dpg.get_value("winder_accel"),
                        "torque": dpg.get_value("winder_torque"),
                        "holding_torque": dpg.get_value("winder_holding_torque"),
                    }
                    self._viewmodel.start_or_resume_winder(config)
                except (ValueError, TypeError):
                    self._viewmodel.winder_status = "Error: Select motors"

            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Start / Resume", width=-1, callback=start_winder_callback)
                dpg.add_button(label="Pause", width=-1, callback=self._viewmodel.pause_winder)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Stop & Reset", width=-1, callback=self._viewmodel.stop_winder)
                dpg.add_button(label="Unwind", width=-1, callback=self._viewmodel.unwind_winder)
            with dpg.group(horizontal=True):
                dpg.add_input_float(tag="winder_jog_revs", width=80, default_value=1.0)
                dpg.add_button(label="Reverse Jog (Revs)", callback=lambda: self._viewmodel.jog_winder(dpg.get_value("winder_jog_revs")))
            with dpg.group(horizontal=True):
                dpg.add_text("Status:")
                dpg.add_text("Idle", tag="winder_status_text")

    def _create_gearing_panel(self):
        with dpg.collapsing_header(label="Electronic Gearing", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Leader Motor")
                    dpg.add_combo([], tag="gearing_leader_selector", width=-1)
                with dpg.table_row():
                    dpg.add_text("Follower Motor")
                    dpg.add_combo([], tag="gearing_follower_selector", width=-1)
                with dpg.table_row():
                    dpg.add_text("Follower Ratio")
                    dpg.add_input_float(tag="gearing_follower_ratio", default_value=-1.0, width=-1)
            
            def start_gearing_callback():
                leader_id = dpg.get_value("gearing_leader_selector")
                follower_id = dpg.get_value("gearing_follower_selector")
                ratio = dpg.get_value("gearing_follower_ratio")
                self._viewmodel.start_gearing(leader_id, follower_id, ratio)
                
            def start_drive_by_wire_callback():
                leader_id = dpg.get_value("gearing_leader_selector")
                follower_id = dpg.get_value("gearing_follower_selector")
                ratio = dpg.get_value("gearing_follower_ratio")
                self._viewmodel.start_drive_by_wire(leader_id, follower_id, ratio)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Start Gearing", width=-1, callback=start_gearing_callback)
                dpg.add_button(label="Stop Gearing", width=-1, callback=self._viewmodel.stop_gearing)
            
            dpg.add_button(label="Start Drive-by-Wire", width=-1, callback=start_drive_by_wire_callback)
            dpg.add_separator()
            
            dpg.add_text("Virtual Master Control (Position Mode)")
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Target Position (rad)")
                    dpg.add_input_float(width=-1, tag="gearing_target_input", on_enter=True,
                                        callback=lambda s, a: self._viewmodel.set_gearing_target(a))
            dpg.add_group(tag="gearing_status_group")

    def _create_advanced_tuning_panel(self):
        with dpg.collapsing_header(label="Advanced Tuning", default_open=False):
            self._create_characterization_panel()
            dpg.add_separator()
            self._create_recommendations_panel()
            dpg.add_separator()
            self._create_current_bw_panel()
            dpg.add_separator()
            self._create_current_test_panel()
            dpg.add_separator()
            dpg.add_text("Autotuning (Ziegler-Nichols)", color=[150, 255, 150])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Amplitude (Torque)")
                    dpg.add_input_float(tag="autotune_amp", default_value=0.5, width=-1)
                with dpg.table_row():
                    dpg.add_text("Duration (s)")
                    dpg.add_input_int(tag="autotune_dur", default_value=10, width=-1)
            
            def start_autotune_callback():
                amp = dpg.get_value("autotune_amp")
                dur = dpg.get_value("autotune_dur")
                self._viewmodel.start_autotune(amp, dur)

            dpg.add_button(label="Start Autotune", tag="autotune_start_btn", width=-1,
                           callback=start_autotune_callback)
            dpg.add_button(label="Apply Calculated Gains", tag="autotune_apply_btn", width=-1, enabled=False,
                           callback=self._viewmodel.apply_autotune_gains)
            with dpg.group(horizontal=True):
                dpg.add_text("Status:")
                dpg.add_text("Idle", tag="autotune_status_text")

            dpg.add_separator()
            self._create_sysid_panel()

    def _create_performance_panel(self):
        """Creates the new panel for performance analysis tests."""
        with dpg.collapsing_header(label="Performance Analysis", default_open=False):
            dpg.add_text("Run standardized tests to measure performance.")
            with dpg.tab_bar():
                with dpg.tab(label="Step Response"):
                    dpg.add_text("Tests stability and responsiveness.")
                    dpg.add_input_float(label="Step Amplitude (rad)", default_value=1.0, tag="perf_step_amp", width=150)
                    dpg.add_input_float(label="Test Duration (s)", default_value=2.0, tag="perf_step_dur", width=150)
                    dpg.add_button(label="Run Step Test", callback=lambda: self._viewmodel.start_performance_test("step_response"))
                with dpg.tab(label="Constant Velocity"):
                    dpg.add_text("Tests tracking error during a constant speed move.")
                    dpg.add_input_float(label="Move Distance (rad)", default_value=10.0, tag="perf_velo_dist", width=150)
                    dpg.add_input_float(label="Move Velocity (rad/s)", default_value=5.0, tag="perf_velo_speed", width=150)
                    dpg.add_button(label="Run Velocity Test", callback=lambda: self._viewmodel.start_performance_test("constant_velocity"))
                with dpg.tab(label="Reversing Move"):
                    dpg.add_text("Tests dynamic error during a direction change.")
                    dpg.add_input_float(label="Move Distance (rad)", default_value=5.0, tag="perf_rev_dist", width=150)
                    dpg.add_input_float(label="Move Velocity (rad/s)", default_value=10.0, tag="perf_rev_speed", width=150)
                    dpg.add_button(label="Run Reversing Test", callback=lambda: self._viewmodel.start_performance_test("reversing_move"))
            dpg.add_separator()
            dpg.add_text("Test Results:")
            with dpg.child_window(tag="perf_results_area", height=100, border=True):
                 dpg.add_text("No results yet.", tag="perf_results_text")

    def _create_characterization_panel(self):
        dpg.add_text("Motor Characterization", color=[150, 255, 150])
        with dpg.table(header_row=False):
            dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
            with dpg.table_row():
                dpg.add_text("Test Voltage (V)")
                dpg.add_input_float(tag="characterize_voltage", width=-1, default_value=1.0)
        dpg.add_button(label="Characterize Motor", tag="characterize_start_btn", width=-1, callback=self._viewmodel.start_characterization)
        with dpg.group(horizontal=True):
            dpg.add_text("Status:")
            dpg.add_text("Idle", tag="characterization_status_text")

    def _create_recommendations_panel(self):
        dpg.add_text("Tuning Recommendations", color=[150, 255, 150])
        dpg.add_button(label="Calculate Recommendations", width=-1, callback=self._viewmodel.calculate_tuning_recommendations)
        with dpg.table(header_row=False):
            dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
            with dpg.table_row():
                dpg.add_text("Electrical Time Constant")
                dpg.add_text("--", tag="reco_time_constant_text")
            with dpg.table_row():
                dpg.add_text("Recommended Current BW")
                dpg.add_text("--", tag="reco_current_bw_text")
            with dpg.table_row():
                dpg.add_text("Safe Velocity P Gain")
                dpg.add_text("--", tag="reco_vel_p_text")
            with dpg.table_row():
                dpg.add_text("Safe Velocity I Gain")
                dpg.add_text("--", tag="reco_vel_i_text")
            with dpg.table_row():
                dpg.add_text("Safe Angle P Gain")
                dpg.add_text("--", tag="reco_angle_p_text")
            with dpg.table_row():
                dpg.add_text("Aggression (multiplier)")
                dpg.add_input_float(tag="reco_aggression", width=-1, default_value=1.0, min_value=0.1, max_value=10.0)
        dpg.add_button(label="Apply Recommended Gains", width=-1, callback=self._viewmodel.apply_recommended_gains)

    def _create_sysid_panel(self):
        dpg.add_text("System ID Autotuner", color=[150, 255, 150])
        with dpg.table(header_row=False):
            dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
            with dpg.table_row(): 
                dpg.add_text("Start Freq (Hz)")
                dpg.add_input_float(tag="sysid_start_freq", width=-1, default_value=1.0)
            with dpg.table_row(): 
                dpg.add_text("End Freq (Hz)")
                dpg.add_input_float(tag="sysid_end_freq", width=-1, default_value=80.0)
            with dpg.table_row(): 
                dpg.add_text("Torque Amplitude")
                dpg.add_input_float(tag="sysid_amp", width=-1, default_value=0.3)
            with dpg.table_row(): 
                dpg.add_text("Duration (s)")
                dpg.add_input_float(tag="sysid_dur", width=-1, default_value=5.0)
            with dpg.table_row():
                dpg.add_text("Response Time (s)")
                dpg.add_slider_float(label="##lambda", tag="sysid_lambda", min_value=0.01, max_value=0.5, default_value=0.05, format="%.3f s", width=-1)
        
        dpg.add_button(label="Start System ID", tag="sysid_start_btn", callback=self._viewmodel.start_sysid, width=-1)
        with dpg.group(horizontal=True):
            dpg.add_text("Status:")
            dpg.add_text("Idle", tag="sysid_status_text")
        
        dpg.add_text("Identified Model:")
        with dpg.group(horizontal=True):
            dpg.add_text("  K (Gain):"); dpg.add_text("--", tag="sysid_k_text")
        with dpg.group(horizontal=True):
            dpg.add_text("  τ (Time Const):"); dpg.add_text("--", tag="sysid_tau_text")

        dpg.add_text("Calculated Gains:")
        with dpg.group(horizontal=True):
            dpg.add_text("  P:"); dpg.add_text("--", tag="sysid_p_text")
        with dpg.group(horizontal=True):
            dpg.add_text("  I:"); dpg.add_text("--", tag="sysid_i_text")
        
        dpg.add_button(label="Apply SysID Gains", tag="sysid_apply_btn", callback=self._viewmodel.apply_sysid_gains, width=-1)

    def _create_current_test_panel(self):
        dpg.add_text("Current Controller Step Test", color=[150, 255, 150])
        with dpg.table(header_row=False):
            dpg.add_table_column(width_stretch=True); dpg.add_table_column(width_fixed=True)
            with dpg.table_row():
                dpg.add_input_float(label="##ctest_amp", tag="current_test_amp", default_value=0.5, width=-1)
                dpg.add_button(label="Run Test", callback=self._viewmodel.run_current_step_test)
        dpg.add_text("Performance:")
        with dpg.group(horizontal=True):
            dpg.add_text("  Rise Time:"); dpg.add_text("--", tag="current_test_rise_time")
        with dpg.group(horizontal=True):
            dpg.add_text("  Overshoot:"); dpg.add_text("--", tag="current_test_overshoot")
        with dpg.group(horizontal=True):
            dpg.add_text("  Settling Time:"); dpg.add_text("--", tag="current_test_settling_time")
        with dpg.group(horizontal=True):
            dpg.add_text("  Peak Time:"); dpg.add_text("--", tag="current_test_peak_time")

    def _create_current_bw_panel(self):
        dpg.add_text("Current Controller Tuning from Bandwidth", color=[150, 255, 150])
        with dpg.table(header_row=False):
            dpg.add_table_column(width_fixed=True)
            dpg.add_table_column(width_stretch=True)
            with dpg.table_row():
                dpg.add_text("Target Bandwidth (Hz)")
                dpg.add_input_float(tag="current_bw_input", default_value=1000.0, width=-1)
        
        def apply_bw_gains_callback():
            bw = dpg.get_value("current_bw_input")
            self._viewmodel.calculate_and_apply_bandwidth_gains(bw)
            
        dpg.add_button(label="Calculate & Apply Current Gains", width=-1, callback=apply_bw_gains_callback)

    def _create_plot_manager_panel(self):
        with dpg.collapsing_header(label="Plot Manager", default_open=False):
            dpg.add_group(tag="plot_manager_content")
            
            with dpg.window(label="Create Following Error Signal", modal=True, show=False, tag="modal_following_error", width=400):
                dpg.add_input_text(label="Signal Name", tag="fe_name")
                dpg.add_combo([], label="Target Signal (A)", tag="fe_combo1", width=-1)
                dpg.add_combo([], label="Actual Signal (B)", tag="fe_combo2", width=-1)
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Create", callback=lambda: self._viewmodel.create_following_error_signal(dpg.get_value("fe_name"), dpg.get_value("fe_combo1"), dpg.get_value("fe_combo2")))
                    dpg.add_button(label="Cancel", callback=lambda: self.close_popups())

            with dpg.window(label="Create Derivative Signal", modal=True, show=False, tag="modal_derivative", width=400):
                dpg.add_input_text(label="New Signal Name (e.g., accel)", tag="deriv_name")
                dpg.add_combo([], label="Source Signal (e.g., motor_1_velocity)", tag="deriv_combo", width=-1)
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Create", callback=lambda: self._viewmodel.create_derivative_signal(dpg.get_value("deriv_name"), dpg.get_value("deriv_combo")))
                    dpg.add_button(label="Cancel", callback=lambda: self.close_popups())

    def _create_general_settings_panel(self):
        with dpg.collapsing_header(label="General Settings", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Telemetry Rate")
                    dpg.add_combo(("100 Hz", "200 Hz", "500 Hz", "1000 Hz"), default_value="100 Hz", width=-1,
                                  callback=lambda s, a: self._viewmodel.set_telemetry_rate(a))
                with dpg.table_row():
                    dpg.add_text("Packet Rate")
                    dpg.add_text("--", tag="actual_freq_text")
                with dpg.table_row():
                    dpg.add_text("Plot FPS")
                    dpg.add_text("--", tag="plot_fps_text")
                with dpg.table_row():
                    dpg.add_text("Plot Controls")
                    dpg.add_checkbox(label="Pause Plots", default_value=False, callback=lambda s, a: self._viewmodel.set_plot_pause_state(a))
                with dpg.table_row():
                    dpg.add_text("History (points)")
                    dpg.add_slider_int(default_value=1000, min_value=100, max_value=10000, width=-1, callback=lambda s, a: self._viewmodel.set_plot_history_length(a))

    def _create_log_panel(self):
        with dpg.child_window(height=150, border=True):
            dpg.add_text("Event Log")
            dpg.add_separator()
            dpg.add_input_text(tag="log_box", multiline=True, width=-1, height=-1, readonly=True)

    def create_plots_area(self, parent):
        with dpg.child_window(parent=parent, width=-1, height=-1):
            dpg.add_group(tag="plots_area_content")
        self.rebuild_dynamic_ui()

    def _build_plot_manager_content(self, parent):
        with dpg.table(header_row=False, parent=parent):
            dpg.add_table_column(width_fixed=True)
            dpg.add_table_column(width_stretch=True)
            with dpg.table_row():
                dpg.add_text("Add Plottable Signal")
                dpg.add_combo(self._viewmodel.get_available_data_keys(), tag="combo_add_series", width=-1,
                              callback=lambda s, a: self._viewmodel.add_series_to_plot(a))
        
        dpg.add_separator(parent=parent)
        dpg.add_text("Calculated Signals", parent=parent)
        dpg.add_button(label="Following Error (A - B)", width=-1, parent=parent, 
                       callback=lambda: dpg.configure_item("modal_following_error", show=True))
        dpg.add_button(label="Derivative (d/dt)", width=-1, parent=parent,
                       callback=lambda: dpg.configure_item("modal_derivative", show=True))
        dpg.add_separator(parent=parent)

        dpg.add_text("Active Series", parent=parent)
        for series in self._viewmodel.the_plot.series_list:
            with dpg.group(horizontal=True, parent=parent):
                dpg.add_text(f" - {series.data_key}")
                dpg.add_button(label="x", small=True, callback=lambda s, a, u: self._viewmodel.remove_series(u), user_data=series.id)
        
        all_keys = self._viewmodel.get_available_data_keys()
        if dpg.does_item_exist("fe_combo1"):
            dpg.configure_item("fe_combo1", items=all_keys)
            dpg.configure_item("fe_combo2", items=all_keys)
            dpg.configure_item("deriv_combo", items=all_keys)

    def _build_plots_area_content(self, parent):
        plot_config = self._viewmodel.the_plot
        plot_config.dpg_tag = dpg.add_plot(label=plot_config.name, height=-1, width=-1, parent=parent)
        dpg.add_plot_legend(parent=plot_config.dpg_tag)
        dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", parent=plot_config.dpg_tag)
        
        y_axis_tag = dpg.add_plot_axis(dpg.mvYAxis, label="Value", parent=plot_config.dpg_tag)
        
        for series_config in plot_config.series_list:
            series_config.dpg_tag = dpg.add_line_series([], [], label=series_config.data_key, parent=y_axis_tag)
    
    def update_plots_data(self):
        if self._viewmodel.is_plot_paused: return
        plot = self._viewmodel.the_plot

        if not dpg.does_item_exist(plot.dpg_tag): return
        
        for series in plot.series_list:
            data = self._viewmodel.get_stream_data(series.data_key)
            if data and dpg.does_item_exist(series.dpg_tag):
                timestamps = np.array(data["timestamps"]) - self._viewmodel.start_time
                values = data["values"]
                dpg.set_value(series.dpg_tag, [list(timestamps), list(values)])
        
        if not dpg.get_plot_query_rects(plot.dpg_tag):
             dpg.fit_axis_data(dpg.get_item_children(plot.dpg_tag, 1)[0]) # X-axis
             dpg.fit_axis_data(dpg.get_item_children(plot.dpg_tag, 1)[1]) # Y-axis

    def update_live_data(self):
        motor = self._viewmodel.active_motor
        if not motor:
            if dpg.does_item_exist("live_angle_text"):
                dpg.set_value("live_angle_text", "--"); dpg.set_value("live_velocity_text", "--"); dpg.set_value("live_iq_text", "--")
            return
        if dpg.does_item_exist("live_angle_text"):
            dpg.set_value("live_angle_text", f"{motor.angle:.2f} rad")
            dpg.set_value("live_velocity_text", f"{motor.velocity:.2f} rad/s")
            dpg.set_value("live_iq_text", f"{motor.current_q:.3f} A")
            
    def update_log(self):
        log_text = "\n".join(self._viewmodel.log_messages)
        if dpg.does_item_exist("log_box"):
            dpg.set_value("log_box", log_text)

    def update_data_rate_display(self, packet_rate, plot_rate=0):
        if dpg.does_item_exist("actual_freq_text"):
            dpg.set_value("actual_freq_text", f"{packet_rate} Hz")
        if dpg.does_item_exist("plot_fps_text"):
            dpg.set_value("plot_fps_text", f"{plot_rate} FPS")

    def update_enable_checkbox(self, is_enabled):
        if dpg.does_item_exist("enable_motor_checkbox"):
            dpg.set_value("enable_motor_checkbox", is_enabled)

    def update_can_id_input(self, motor_id):
        if dpg.does_item_exist("new_can_id_input"):
            dpg.set_value("new_can_id_input", motor_id)

    def update_performance_results_ui(self):
        """Updates the UI with the latest performance test results."""
        if dpg.does_item_exist("perf_results_text"):
            if self._viewmodel.performance_test_results:
                results = self._viewmodel.performance_test_results
                if "error" in results:
                    result_str = f"Error: {results['error']}"
                else:
                    result_str = "\n".join([f"{key}: {value}" for key, value in results.items()])
                dpg.set_value("perf_results_text", result_str)
            else:
                dpg.set_value("perf_results_text", "Run a test to see results.")

    def update_parameter_widgets(self, reg_id, value):
        widget_map = {
            REG_VOLTAGE_LIMIT: "voltage_limit_input", REG_CURRENT_LIMIT: "current_limit_input",
            REG_VELOCITY_LIMIT: "velocity_limit_input", REG_DRIVER_VOLTAGE_PSU: "power_supply_input",
            REG_VOLTAGE_SENSOR_ALIGN: "alignment_voltage_input", REG_POLE_PAIRS: "pole_pairs_input",
            REG_PHASE_RESISTANCE: "phase_resistance_input", REG_KV: "kv_rating_input",
            REG_INDUCTANCE: "phase_inductance_input",
            REG_ANG_PID_P: "angle_p_slider", REG_ANG_PID_I: "angle_i_slider", REG_ANG_PID_D: "angle_d_slider",
            REG_ANG_PID_RAMP: "angle_ramp_slider", REG_ANG_PID_LIM: "angle_limit_slider",
            REG_VEL_PID_P: "vel_p_slider", REG_VEL_PID_I: "vel_i_slider", REG_VEL_PID_D: "vel_d_slider",
            REG_VEL_LPF_T: "vel_lpf_slider", REG_VEL_PID_RAMP: "vel_ramp_slider", REG_VEL_PID_LIM: "vel_limit_slider",
            REG_CURQ_PID_P: "curq_p_slider", REG_CURQ_PID_I: "curq_i_slider", REG_CURQ_PID_D: "curq_d_slider",
            REG_CURQ_LPF_T: "curq_lpf_slider",
            REG_CURD_PID_P: "curd_p_slider", REG_CURD_PID_I: "curd_i_slider", REG_CURD_PID_D: "curd_d_slider",
            REG_CURD_LPF_T: "curd_lpf_slider"
        }
        if reg_id in widget_map:
            tag = widget_map[reg_id]
            if dpg.does_item_exist(tag):
                if tag == "pole_pairs_input":
                    dpg.set_value(tag, int(value))
                else:
                    dpg.set_value(tag, value)
    
    def update_target_input(self, value):
        if dpg.does_item_exist("target_input"):
            dpg.set_value("target_input", value)
            
    def close_popups(self):
        if dpg.does_item_exist("modal_following_error"):
            dpg.configure_item("modal_following_error", show=False)
        if dpg.does_item_exist("modal_derivative"):
            dpg.configure_item("modal_derivative", show=False)