# gui_layout.py
"""
Creates the entire Dear PyGui layout, including windows, panels,
buttons, and other widgets. Connects widgets to their callbacks.
"""
import dearpygui.dearpygui as dpg
from state import app_state
from config import *
from gui_callbacks import *

def apply_dark_theme():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (30, 30, 30)); dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (40, 40, 40))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (55, 55, 55)); dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (70, 70, 70))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (90, 90, 90)); dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 120, 190))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 140, 210)); dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 160, 230))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (60, 120, 190, 100)); dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (80, 140, 210, 200))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (100, 160, 230, 255)); dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (200, 200, 200))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (255, 255, 255)); dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (240, 240, 240))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5); dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 4); dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 5)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 2)
    dpg.bind_theme(theme)

def create_gui():
    with dpg.window(tag="main_window", width=-1, height=-1, no_move=True, no_title_bar=True):
        with dpg.table(header_row=False, resizable=True, borders_innerV=True):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=400)
            dpg.add_table_column()

            with dpg.table_row():
                with dpg.child_window(tag="left_pane", width=-1, height=-1):
                    dpg.add_text("Connection")
                    dpg.add_separator()
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Connect", callback=toggle_connection_cb, tag="connect_button", width=120)
                        dpg.add_text("Status: Disconnected", tag="status_text", color=[255, 255, 0])
                    
                    with dpg.collapsing_header(label="Motor Management", default_open=True):
                        dpg.add_button(label="Scan for Motors", callback=scan_for_motors, width=-1)
                        dpg.add_combo([], label="Active Motor", tag="motor_selector", callback=select_active_motor, width=-1)
                        dpg.add_spacer(height=5)
                        dpg.add_text("Set New CAN ID (for selected motor)")
                        with dpg.table(header_row=False):
                            dpg.add_table_column(width_stretch=True); dpg.add_table_column(width_fixed=True)
                            with dpg.table_row():
                                dpg.add_input_int(label="##can_id_input", width=-1, tag="new_can_id_input", default_value=2, min_value=1, max_value=127)
                                dpg.add_button(label="Set ID", callback=set_can_id)
                        
                        dpg.add_button(label="Flip Sensor Direction", callback=flip_sensor_dir_cb, width=-1)
                        dpg.add_text("Note: Saves automatically. Motor must be disabled.", color=[200,200,200])
                        dpg.add_button(label="Save All Parameters to Motor", callback=lambda: send_register_byte(app_state['active_motor_id'], REG_CUSTOM_SAVE_TO_EEPROM, 1), width=-1)

                    with dpg.group(tag="main_controls", enabled=False):
                        with dpg.collapsing_header(label="Motor Limits", default_open=True):
                            with dpg.table(header_row=False):
                                dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True); dpg.add_table_column(width_fixed=True)
                                with dpg.table_row():
                                    dpg.add_text("Voltage Limit")
                                    dpg.add_input_float(label="##vlim", tag="voltage_limit_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VOLTAGE_LIMIT, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="voltage_limit_input")
                                with dpg.table_row():
                                    dpg.add_text("Power Supply (V)")
                                    dpg.add_input_float(label="##psuv", tag="power_supply_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_DRIVER_VOLTAGE_PSU, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="power_supply_input")
                                with dpg.table_row():
                                    dpg.add_text("Current Limit (A)")
                                    dpg.add_input_float(label="##clim", tag="current_limit_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURRENT_LIMIT, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="current_limit_input")
                                with dpg.table_row():
                                    dpg.add_text("Velocity Limit (rad/s)")
                                    dpg.add_input_float(label="##vellim", tag="velocity_limit_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VELOCITY_LIMIT, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="velocity_limit_input")
                                with dpg.table_row():
                                    dpg.add_text("Alignment Voltage")
                                    dpg.add_input_float(label="##alignv", tag="alignment_voltage_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VOLTAGE_SENSOR_ALIGN, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="alignment_voltage_input")

                        with dpg.collapsing_header(label="Motor Physical Parameters", default_open=False):
                             with dpg.table(header_row=False):
                                dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True); dpg.add_table_column(width_fixed=True)
                                with dpg.table_row():
                                    dpg.add_text("Pole Pairs")
                                    dpg.add_input_int(label="##pp", tag="pole_pairs_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_byte(app_state['active_motor_id'], REG_POLE_PAIRS, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="pole_pairs_input")
                                with dpg.table_row():
                                    dpg.add_text("Phase Resistance (Ω)")
                                    dpg.add_input_float(label="##res", tag="phase_resistance_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_PHASE_RESISTANCE, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="phase_resistance_input")
                                with dpg.table_row():
                                    dpg.add_text("Phase Inductance (H)")
                                    dpg.add_input_float(label="##ind", tag="phase_inductance_input", readonly=True, width=-1, format="%.6f", on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_INDUCTANCE, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="phase_inductance_input")
                                with dpg.table_row():
                                    dpg.add_text("Motor KV Rating")
                                    dpg.add_input_float(label="##kv", tag="kv_rating_input", readonly=True, width=-1, on_enter=True, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_KV, a))
                                    dpg.add_checkbox(label="Unlock", callback=lambda s, a, u: dpg.configure_item(u, readonly=not a), user_data="kv_rating_input")
                        
                        with dpg.collapsing_header(label="Coil Winder", default_open=True):
                            dpg.add_text("Motor Selection")
                            with dpg.table(header_row=False):
                                dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
                                with dpg.table_row():
                                    dpg.add_text("Bobbin Motor (Turns)")
                                    dpg.add_combo([], tag="winder_bobbin_selector", width=-1)
                                with dpg.table_row():
                                    dpg.add_text("Winder Motor (Tension)")
                                    dpg.add_combo([], tag="winder_tension_selector", width=-1)
                            dpg.add_separator()
                            dpg.add_text("Winding Parameters")
                            with dpg.table(header_row=False):
                                dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
                                with dpg.table_row():
                                    dpg.add_text("Total Revolutions")
                                    dpg.add_input_float(tag="winder_revs", width=-1, default_value=100.0, step=10)
                                with dpg.table_row():
                                    dpg.add_text("Winding Speed (rad/s)")
                                    dpg.add_input_float(tag="winder_speed", width=-1, default_value=15.0, step=1)
                                with dpg.table_row():
                                    dpg.add_text("Acceleration (rad/s^2)")
                                    dpg.add_input_float(tag="winder_accel", width=-1, default_value=10.0, step=1)
                                with dpg.table_row():
                                    dpg.add_text("Winding Tension")
                                    dpg.add_input_float(tag="winder_torque", width=-1, default_value=0.1, step=0.05)
                                with dpg.table_row():
                                    dpg.add_text("Holding Tension")
                                    dpg.add_input_float(tag="winder_holding_torque", width=-1, default_value=0.05, step=0.05)
                            dpg.add_separator()
                            dpg.add_text("Winder Controls")
                            with dpg.group(horizontal=True):
                                dpg.add_button(label="Start", tag="winder_start_resume_btn", callback=start_resume_winding_cb, width=-1)
                                dpg.add_button(label="Pause", tag="winder_pause_btn", callback=pause_winding_cb, width=-1)
                            with dpg.group(horizontal=True):
                                dpg.add_button(label="Stop & Reset", tag="winder_stop_btn", callback=stop_reset_winding_cb, width=-1)
                                dpg.add_button(label="Unwind Spool", tag="winder_unwind_btn", callback=unwind_spool_cb, width=-1)
                            with dpg.group(horizontal=True, tag="winder_jog_input_group"):
                                dpg.add_button(label="Reverse Jog", tag="winder_jog_btn", callback=reverse_jog_cb)
                                dpg.add_input_float(tag="winder_jog_revs", width=80, default_value=1.0, step=0.5)
                                dpg.add_text("Revs")
                                dpg.add_button(label="Reverse to Start", tag="winder_rts_btn", callback=reverse_to_start_cb)
                            with dpg.group(horizontal=True):
                                dpg.add_text("Status:")
                                dpg.add_text("Idle", tag="winder_status_text")

                        with dpg.collapsing_header(label="Real-Time Control", default_open=False):
                            dpg.add_checkbox(label="Enable Motor", callback=enable_motor_cb)
                            dpg.add_radio_button(("Torque", "Velocity", "Angle"), default_value="Angle", horizontal=True, callback=set_control_mode_cb)
                            dpg.add_input_float(label="Target", callback=set_target_cb, on_enter=True, tag="target_input", default_value=0.0, width=-1)
                            dpg.add_separator()
                            dpg.add_text("Live Values (for selected motor):")
                            with dpg.group(horizontal=True): dpg.add_text("Angle:", color=[200, 200, 200]); dpg.add_text("--", tag="current_angle_text")
                            with dpg.group(horizontal=True): dpg.add_text("Velocity:", color=[200, 200, 200]); dpg.add_text("--", tag="current_velocity_text")
                            with dpg.group(horizontal=True): dpg.add_text("Current Iq:", color=[200, 200, 200]); dpg.add_text("--", tag="current_iq_text")
                            with dpg.group(horizontal=True): dpg.add_text("Current Id:", color=[200, 200, 200]); dpg.add_text("--", tag="current_id_text")
                            with dpg.group(horizontal=True): dpg.add_text("Voltage Vq:", color=[200, 200, 200]); dpg.add_text("--", tag="voltage_vq_text")
                            with dpg.group(horizontal=True): dpg.add_text("Voltage Vd:", color=[200, 200, 200]); dpg.add_text("--", tag="voltage_vd_text")

                        with dpg.collapsing_header(label="Autotuning (Ziegler-Nichols)", default_open=False):
                            dpg.add_text("Tune Velocity PI Controller (Classic Method)")
                            with dpg.table(header_row=False):
                                dpg.add_table_column(); dpg.add_table_column(width_stretch=True)
                                with dpg.table_row(): dpg.add_text("Amplitude (Torque)"); dpg.add_input_float(label="##autotune_amp", tag="autotune_amp", default_value=0.5, step=0.1, width=-1)
                                with dpg.table_row(): dpg.add_text("Duration (s)"); dpg.add_input_int(label="##autotune_dur", tag="autotune_dur", default_value=10, step=1, width=-1)
                                with dpg.table_row(): dpg.add_text("Status:"); dpg.add_text("Idle", tag="autotune_status_text")
                            dpg.add_spacer(height=5)
                            dpg.add_button(label="Start Autotune", tag="autotune_start_btn", callback=start_autotune_cb, width=-1)
                            dpg.add_button(label="Apply Calculated Gains", tag="autotune_apply_btn", callback=apply_gains_cb, width=-1, enabled=False)

                        with dpg.collapsing_header(label="System ID Autotuner", default_open=False):
                            dpg.add_text("Tune Velocity PI controller using a frequency sweep.")
                            dpg.add_text("This builds an accurate model of the motor for tuning.", color=[200,200,200])
                            dpg.add_separator()
                            
                            dpg.add_text("Chirp Signal Parameters")
                            with dpg.table(header_row=False):
                                dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
                                with dpg.table_row(): 
                                    dpg.add_text("Start Freq (Hz)")
                                    dpg.add_input_float(tag="sysid_start_freq", width=-1, default_value=1.0, step=1)
                                with dpg.table_row(): 
                                    dpg.add_text("End Freq (Hz)")
                                    dpg.add_input_float(tag="sysid_end_freq", width=-1, default_value=80.0, step=5)
                                with dpg.table_row(): 
                                    dpg.add_text("Torque Amplitude")
                                    dpg.add_input_float(tag="sysid_amp", width=-1, default_value=0.3, step=0.1)
                                with dpg.table_row(): 
                                    dpg.add_text("Duration (s)")
                                    dpg.add_input_float(tag="sysid_dur", width=-1, default_value=5.0, step=0.5)
                            
                            dpg.add_text("Tuning Goal")
                            dpg.add_slider_float(label="Response Time (s)", tag="sysid_lambda", min_value=0.01, max_value=0.5, default_value=0.05, format="%.3f s", width=-1)
                            dpg.add_text("Smaller values give a faster, more aggressive response.", color=[200,200,200])
                            dpg.add_separator()

                            dpg.add_button(label="Start System ID", tag="sysid_start_btn", callback=start_sysid_cb, width=-1)

                            with dpg.group(horizontal=True):
                                dpg.add_text("Status:")
                                dpg.add_text("Idle", tag="sysid_status_text")
                            
                            dpg.add_text("Identified Model:", color=[150, 255, 150])
                            with dpg.group(horizontal=True):
                                dpg.add_text("  K (Gain):")
                                dpg.add_text("--", tag="sysid_k_text")
                            with dpg.group(horizontal=True):
                                dpg.add_text("  τ (Time Const):")
                                dpg.add_text("--", tag="sysid_tau_text")

                            dpg.add_text("Calculated Gains:", color=[150, 255, 150])
                            with dpg.group(horizontal=True):
                                dpg.add_text("  P:")
                                dpg.add_text("--", tag="sysid_p_text")
                            with dpg.group(horizontal=True):
                                dpg.add_text("  I:")
                                dpg.add_text("--", tag="sysid_i_text")
                            
                            dpg.add_button(label="Apply Calculated Gains", tag="sysid_apply_btn", callback=apply_sysid_gains_cb, width=-1, enabled=False)

                        with dpg.collapsing_header(label="PID Tuning", default_open=True):
                            dpg.add_text("Advanced Current Tuning", color=[255, 255, 0])
                            dpg.add_checkbox(label="Calculate Current Gains from Bandwidth", callback=toggle_bandwidth_mode)
                            with dpg.group(tag="bandwidth_tuning_widgets", show=False):
                                with dpg.table(header_row=False):
                                    dpg.add_table_column(width_fixed=True); dpg.add_table_column(width_stretch=True)
                                    with dpg.table_row(): dpg.add_text("Current Bandwidth (Hz)"); dpg.add_input_float(tag="current_bw_input", width=-1, default_value=1000.0)
                                dpg.add_button(label="Calculate & Apply Current Gains", callback=apply_bandwidth_gains, width=-1)
                            
                            with dpg.group():
                                dpg.add_separator()
                                dpg.add_text("Current Controller Step Test")
                                with dpg.table(header_row=False):
                                    dpg.add_table_column(width_stretch=True); dpg.add_table_column(width_fixed=True)
                                    with dpg.table_row():
                                        dpg.add_input_float(label="##ctest", tag="current_test_amp", default_value=0.5, width=-1)
                                        dpg.add_button(label="Run Test", callback=run_current_step_test_cb)
                                dpg.add_text("Performance:", color=[150, 255, 150])
                                with dpg.group(horizontal=True):
                                    dpg.add_text("  Rise Time:"); dpg.add_text("--", tag="current_test_rise_time")
                                with dpg.group(horizontal=True):
                                    dpg.add_text("  Overshoot:"); dpg.add_text("--", tag="current_test_overshoot")
                                with dpg.group(horizontal=True):
                                    dpg.add_text("  Settling Time:"); dpg.add_text("--", tag="current_test_settling_time")
                            
                            dpg.add_separator()
                            dpg.add_text("Manual Gain Tuning")
                            
                            dpg.add_text("Angle Controller", color=[150, 255, 150])
                            dpg.add_slider_float(label="  P", tag="angle_p_slider", max_value=50.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_ANG_PID_P, a), width=-1)
                            dpg.add_slider_float(label="  I", tag="angle_i_slider", max_value=500.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_ANG_PID_I, a), width=-1)
                            dpg.add_slider_float(label="  D", tag="angle_d_slider", max_value=1.0, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_ANG_PID_D, a), width=-1)
                            dpg.add_slider_float(label="  Ramp", tag="angle_ramp_slider", max_value=1000.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_ANG_PID_RAMP, a), width=-1)
                            dpg.add_slider_float(label="  Limit", tag="angle_limit_slider", max_value=1000.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_ANG_PID_LIM, a), width=-1)

                            dpg.add_separator()
                            dpg.add_text("Velocity Controller", color=[150, 255, 150])
                            dpg.add_slider_float(label="  P", tag="vel_p_slider", max_value=5.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VEL_PID_P, a), width=-1)
                            dpg.add_slider_float(label="  I", tag="vel_i_slider", max_value=50.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VEL_PID_I, a), width=-1)
                            dpg.add_slider_float(label="  D", tag="vel_d_slider", max_value=0.5, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VEL_PID_D, a), width=-1)
                            dpg.add_slider_float(label="  LPF Tf", tag="vel_lpf_slider", max_value=0.1, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VEL_LPF_T, a), width=-1)
                            dpg.add_slider_float(label="  Ramp", tag="vel_ramp_slider", max_value=1000.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VEL_PID_RAMP, a), width=-1)
                            dpg.add_slider_float(label="  Limit", tag="vel_limit_slider", max_value=1000.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_VEL_PID_LIM, a), width=-1)

                            dpg.add_separator()
                            dpg.add_text("Current Iq Controller", color=[150, 255, 150])
                            dpg.add_slider_float(label="  P", tag="curq_p_slider", max_value=10.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURQ_PID_P, a), width=-1)
                            dpg.add_slider_float(label="  I", tag="curq_i_slider", max_value=1000.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURQ_PID_I, a), width=-1)
                            dpg.add_slider_float(label="  D", tag="curq_d_slider", max_value=0.5, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURQ_PID_D, a), width=-1)
                            dpg.add_slider_float(label="  LPF Tf", tag="curq_lpf_slider", max_value=0.1, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURQ_LPF_T, a), width=-1)

                            dpg.add_separator()
                            dpg.add_text("Current Id Controller", color=[150, 255, 150])
                            dpg.add_slider_float(label="  P", tag="curd_p_slider", max_value=10.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURD_PID_P, a), width=-1)
                            dpg.add_slider_float(label="  I", tag="curd_i_slider", max_value=1000.0, callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURD_PID_I, a), width=-1)
                            dpg.add_slider_float(label="  D", tag="curd_d_slider", max_value=0.5, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURD_PID_D, a), width=-1)
                            dpg.add_slider_float(label="  LPF Tf", tag="curd_lpf_slider", max_value=0.1, format="%.4f", callback=lambda s, a: send_register_float(app_state['active_motor_id'], REG_CURD_LPF_T, a), width=-1)
                        
                        with dpg.collapsing_header(label="Plot Manager", default_open=False):
                            dpg.add_combo([], label="Plot Motor", tag="plot_motor_selector", width=-1)
                            dpg.add_button(label="Add New Plot for Selected Motor", callback=add_new_plot, width=-1)
                            dpg.add_group(tag="plot_manager_controls")

                        with dpg.collapsing_header(label="General Settings", default_open=False):
                            dpg.add_text("Telemetry Rate"); dpg.add_combo(("100 Hz", "200 Hz", "500 Hz", "1000 Hz"), default_value="100 Hz", callback=set_telemetry_frequency, width=-1)
                            with dpg.group(horizontal=True): dpg.add_text("Packet Rate:", color=[200, 200, 200]); dpg.add_text("--", tag="actual_freq_text")
                            dpg.add_separator(); dpg.add_text("Plot Controls")
                            with dpg.group(horizontal=True): dpg.add_text("Plot FPS:", color=[200, 200, 200]); dpg.add_text("--", tag="plot_freq_text")
                            dpg.add_checkbox(label="Auto-Fit Plots", default_value=True, callback=lambda s, a: app_state.update({"auto_fit_plots": a}))
                            dpg.add_button(label="Pause/Resume Plot", callback=lambda: app_state.update({"is_paused": not app_state["is_paused"]}), width=-1)
                            dpg.add_slider_int(label="History (points)", default_value=1000, min_value=100, max_value=10000, callback=set_plot_history, width=-1, tag="history_slider")
                
                with dpg.group():
                    with dpg.child_window(tag="plot_container", width=-1, height=-150):
                        dpg.add_text("Scan for motors and add a plot to begin.", color=[150, 150, 150])
                    with dpg.child_window(tag="log_area", width=-1, height=-1):
                        dpg.add_text("Event Log"); dpg.add_separator()
                        dpg.add_input_text(tag="log_box", multiline=True, width=-1, height=-1, readonly=True, default_value="Welcome! Connect to the CAN bus.\n")