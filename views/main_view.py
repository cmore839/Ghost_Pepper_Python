# views/main_view.py
import dearpygui.dearpygui as dpg

class MainView:
    def __init__(self, viewmodel):
        self.viewmodel = viewmodel
        # The view uses the UIManager from the ViewModel
        self.ui_manager = self.viewmodel.ui_manager

    def create_window(self):
        """
        Creates the main application window and delegates the creation of all UI panels
        to the UIManager.
        """
        # Let the UIManager build the entire UI structure
        self.ui_manager.create_all_ui_panels()

    def update(self):
        """
        This function is called every frame and tells the UIManager to update
        the values of all dynamic UI elements.
        """
        self.ui_manager.update_live_data()
        self.ui_manager.update_plots_data()
        self.ui_manager.update_log()
        # This handles UI elements that need to be rebuilt (like plot series)
        self.ui_manager.create_and_update_dynamic_ui()