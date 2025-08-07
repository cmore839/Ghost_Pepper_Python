# views/main_view.py
import dearpygui.dearpygui as dpg
import time

class MainView:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._last_known_motor_ids = []
        self._plot_update_counter = 0
        self._last_fps_calc_time = time.time()

    def create_window(self):
        with dpg.window(tag="main_window", width=-1, height=-1, no_move=True, no_title_bar=True):
            with dpg.table(header_row=False, resizable=True, borders_innerV=True):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=400)
                dpg.add_table_column(width_stretch=True)
                with dpg.table_row():
                    with dpg.table_cell():
                        # Main control area
                        with dpg.child_window(tag="left_pane", height=-170): # Reserve space for log
                            with dpg.collapsing_header(label="Connection & Motors", default_open=True):
                                with dpg.table(header_row=False):
                                    dpg.add_table_column(width_stretch=True)
                                    dpg.add_table_column(width_stretch=True)
                                    with dpg.table_row():
                                        dpg.add_button(label="Connect", tag="connect_button", callback=self._viewmodel.connect_disconnect, width=-1)
                                        dpg.add_text(self._viewmodel.status_text, tag="status_text")
                                dpg.add_button(label="Scan for Motors", width=-1, callback=self._viewmodel.scan_for_motors)
                                with dpg.table(header_row=False):
                                    dpg.add_table_column(width_fixed=True)
                                    dpg.add_table_column(width_stretch=True)
                                    with dpg.table_row():
                                        dpg.add_text("Active Motor")
                                        dpg.add_combo([], tag="motor_selector", width=-1, callback=lambda s, a: self._viewmodel.select_motor(a))
                            
                            self._viewmodel.ui_manager.create_all_ui_panels()
                        
                        # Log panel at the bottom of the left pane
                        self._viewmodel.ui_manager._create_log_panel()

                    with dpg.table_cell() as right_cell:
                        self._viewmodel.ui_manager.create_plots_area(parent=right_cell)

    def update(self):
        """The View's update loop is responsible for all rendering updates."""
        dpg.set_value("status_text", self._viewmodel.status_text)
        dpg.set_item_label("connect_button", "Disconnect" if self._viewmodel.is_connected else "Connect")
        
        motor_ids = [str(m.id) for m in self._viewmodel.motors]
        if motor_ids != self._last_known_motor_ids:
            current_selection = str(self._viewmodel.active_motor_id) if self._viewmodel.active_motor_id is not None else ""
            dpg.configure_item("motor_selector", items=motor_ids, default_value=current_selection)
            self._last_known_motor_ids = motor_ids
        
        self._viewmodel.ui_manager.create_and_update_dynamic_ui()
        self._viewmodel.ui_manager.update_live_data()
        
        if not self._viewmodel.is_plot_paused:
            self._viewmodel.ui_manager.update_plots_data()
            self._plot_update_counter += 1

        now = time.time()
        if now - self._last_fps_calc_time > 1.0:
            self._viewmodel.ui_manager.update_data_rate_display(
                self._viewmodel.telemetry_packet_counter,
                self._plot_update_counter
            )
            self._plot_update_counter = 0
            self._last_fps_calc_time = now