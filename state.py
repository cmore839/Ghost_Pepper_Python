# state.py
"""
Defines and manages the shared application state.
"""
import collections
import queue

# The central dictionary holding the entire state of the application.
app_state = {
    "bus": None,
    "is_running": False,
    "read_thread": None,
    "data_queue": queue.Queue(),
    "start_time": 0,
    
    # Multi-motor state
    "active_motor_id": None,
    "motors": {},

    # UI and Feature states
    "plots": [],
    "plot_id_counter": 0,
    "gangs": [],
    "autotune_thread": None,
    "autotune_active": False,
    "autotune_status": "Idle",
    "autotune_results": None,
    "is_paused": False,
    "auto_fit_plots": True,

    # Advanced Coil Winder State
    "winding_thread": None,
    "winding_mode": "idle",  # idle, winding, pausing, paused, reversing, stopping
    "winding_status": "Idle",
    "winding_config": {},    # Static config from the GUI
    "winding_dynamic": {},   # Dynamic state used by the thread (e.g., current velocity)
    
    # System ID Autotuner State
    "sysid_thread": None,
    "sysid_active": False,
    "sysid_status": "Idle",
    "sysid_config": {},
    "sysid_results": None,
}

def create_new_motor_state(motor_id, history_len=1000):
    """Initializes the state dictionary for a newly discovered motor."""
    if motor_id not in app_state["motors"]:
        app_state["motors"][motor_id] = {
            "live_data": {s: 0.0 for s in ["angle", "velocity", "current_q"]},
            "telemetry_history": {
                "timestamps": collections.deque(maxlen=history_len),
                "angle": collections.deque(maxlen=history_len),
                "velocity": collections.deque(maxlen=history_len),
                "current_q": collections.deque(maxlen=history_len),
            }
        }