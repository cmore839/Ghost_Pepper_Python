# ui_manager.py
import dearpygui.dearpygui as dpg
from config import *
import numpy as np

class UIManager:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._ui_needs_rebuild = False

    def create_all_ui_panels(self):
        """Creates all the main UI panels in the left pane."""
        self._create_motor_management_panel()
        self._create_motor_limits_panel()
        self._create_motor_params_panel()
        self._create_real_time_control_panel()
        self._create_pid_tuning_panel()
        self._create_winder_panel()
        self._create_ganging_panel()
        self._create_advanced_tuning_panel()
        self._create_plot_manager_panel()
        self._create_general_settings_panel()

    def rebuild_dynamic_ui(self):
        """Flags that the dynamic parts of the UI need to be redrawn."""
        self._ui_needs_rebuild = True

    def create_and_update_dynamic_ui(self):
        """
        This method is called only when the UI structure needs to change.
        """
        if self._ui_needs_rebuild:
            if dpg.does_item_exist("plot_manager_content"):
                dpg.delete_item("plot_manager_content", children_only=True)
            if dpg.does_item_exist("plots_area_content"):
                dpg.delete_item("plots_area_content", children_only=True)
            
            self._build_plot_manager_content(parent="plot_manager_content")
            self._build_plots_area_content(parent="plots_area_content")
            
            self._ui_needs_rebuild = False
        
        motor_ids = [str(m.id) for m in self._viewmodel.motors]
        if dpg.does_item_exist("ganging_leader_selector"):
            dpg.configure_item("ganging_leader_selector", items=motor_ids)
            dpg.configure_item("ganging_follower_selector", items=motor_ids)
        if dpg.does_item_exist("winder_bobbin_selector"):
            dpg.configure_item("winder_bobbin_selector", items=motor_ids)
            dpg.configure_item("winder_tension_selector", items=motor_ids)

        if dpg.does_item_exist("ganging_status_group"):
            dpg.delete_item("ganging_status_group", children_only=True)
            for gang in self._viewmodel.gangs:
                dpg.add_text(f"Leader: {gang['leader']}", parent="ganging_status_group")
                for f in gang['followers']:
                    dpg.add_text(f" - Follower: {f['id']} ({f['mode']})", parent="ganging_status_group")
        
        if dpg.does_item_exist("autotune_status_text"):
            dpg.set_value("autotune_status_text", self._viewmodel.autotune_status)
            dpg.configure_item("autotune_start_btn", enabled=not self._viewmodel.autotune_active)
            dpg.configure_item("autotune_apply_btn", enabled=self._viewmodel.autotune_results is not None)
            
        if dpg.does_item_exist("winder_status_text"):
            dpg.set_value("winder_status_text", self._viewmodel.winder_status)

    def _create_motor_management_panel(self):
        with dpg.collapsing_header(label="Motor Management", default_open=False):
            dpg.add_button(label="Flip Sensor Direction", width=-1, callback=self._viewmodel.flip_sensor_direction)
            dpg.add_button(label="Save All Parameters to Motor", width=-1, callback=self._viewmodel.save_to_eeprom)

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
                    dpg.add_slider_float(tag="angle_p_slider", max_value=50.0, callback=lambda s, a: self._viewmodel.set_pid_gain(REG_ANG_PID_P, a), width=-1)
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

    def _create_ganging_panel(self):
        with dpg.collapsing_header(label="Motion Ganging", default_open=False):
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Leader Motor")
                    dpg.add_combo([], tag="ganging_leader_selector", width=-1)
                with dpg.table_row():
                    dpg.add_text("Follower Motor")
                    dpg.add_combo([], tag="ganging_follower_selector", width=-1)
                with dpg.table_row():
                    dpg.add_text("Ganging Mode")
                    dpg.add_combo(("Sync", "Anti-Sync"), tag="ganging_mode_selector", default_value="Sync", width=-1)
            
            def add_gang_callback():
                leader_id = dpg.get_value("ganging_leader_selector")
                follower_id = dpg.get_value("ganging_follower_selector")
                mode = dpg.get_value("ganging_mode_selector")
                self._viewmodel.add_gang(leader_id, follower_id, mode)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Create Gang", width=-1, callback=add_gang_callback)
                dpg.add_button(label="Remove Gang", width=-1, callback=self._viewmodel.remove_gang)
            dpg.add_separator()
            
            dpg.add_text("Ganged Control")
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Ganged Target")
                    dpg.add_input_float(width=-1, tag="ganged_target_input", on_enter=True,
                                        callback=lambda s, a: self._viewmodel.set_ganged_target(a))
            
            dpg.add_group(tag="ganging_status_group")

    def _create_advanced_tuning_panel(self):
        with dpg.collapsing_header(label="Advanced Tuning", default_open=False):
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
            dpg.add_text("Advanced Current Tuning", color=[150, 255, 150])
            with dpg.table(header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    dpg.add_text("Motor R (Ohm)")
                    dpg.add_input_float(tag="bw_motor_r", width=-1, default_value=0.5)
                with dpg.table_row():
                    dpg.add_text("Motor L (Henry)")
                    dpg.add_input_float(tag="bw_motor_l", width=-1, default_value=0.0015, format="%.5f")
                with dpg.table_row():
                    dpg.add_text("Bandwidth (Hz)")
                    dpg.add_input_float(tag="current_bw_input", default_value=1000.0, width=-1)
            
            def apply_bw_gains_callback():
                bw = dpg.get_value("current_bw_input")
                r = dpg.get_value("bw_motor_r")
                l = dpg.get_value("bw_motor_l")
                self._viewmodel.calculate_and_apply_bandwidth_gains(bw, r, l)
                
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
        
        for series_config in plot_config.series_list:
            y_axis_tag = dpg.add_plot_axis(dpg.mvYAxis, label=series_config.data_key, parent=plot_config.dpg_tag)
            series_config.dpg_tag = dpg.add_line_series([], [], label=series_config.data_key, parent=y_axis_tag)
    
    def update_plots_data(self):
        if self._viewmodel.is_plot_paused: return
        start_time = self._viewmodel.start_time
        plot = self._viewmodel.the_plot

        if not dpg.does_item_exist(plot.dpg_tag): return
        
        for series in plot.series_list:
            data = self._viewmodel.get_stream_data(series.data_key)
            if data and dpg.does_item_exist(series.dpg_tag):
                timestamps = data["timestamps"]
                values = data["values"]
                dpg.set_value(series.dpg_tag, [list(timestamps), list(values)])
        
        if not dpg.get_plot_query_rects(plot.dpg_tag):
             dpg.fit_axis_data(dpg.get_item_children(plot.dpg_tag, 1)[0])
             for y_axis in dpg.get_item_children(plot.dpg_tag, 1)[1:]:
                dpg.fit_axis_data(y_axis)

    def update_live_data(self):
        motor = self._viewmodel.active_motor
        if not motor:
            if dpg.does_item_exist("live_angle_text"):
                dpg.set_value("live_angle_text", "--")
                dpg.set_value("live_velocity_text", "--")
                dpg.set_value("live_iq_text", "--")
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