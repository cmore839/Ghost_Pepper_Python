# main.py
import dearpygui.dearpygui as dpg
import time
from viewmodels.main_viewmodel import MainViewModel
from views.main_view import MainView

def main():
    dpg.create_context()
    dpg.create_viewport(title='Refactored Motor GUI', width=1500, height=950)
    
    main_viewmodel = MainViewModel()
    main_view = MainView(main_viewmodel)
    main_view.create_window()

    dpg.setup_dearpygui()
    dpg.show_viewport()
    # Corrected: Use "primary_window" to match the tag in UIManager
    dpg.set_primary_window("primary_window", True)
    
    last_render_time = time.time()
    render_interval = 1.0 / 60.0

    while dpg.is_dearpygui_running():
        main_viewmodel.update()

        now = time.time()
        if now - last_render_time >= render_interval:
            last_render_time = now
            main_view.update()
            dpg.render_dearpygui_frame()
        
        time.sleep(0.001)

    main_viewmodel.disconnect()
    dpg.destroy_context()

if __name__ == "__main__":
    main()