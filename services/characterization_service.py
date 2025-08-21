# services/characterization_service.py
import time
import threading
from config import REG_CUSTOM_CHARACTERIZE_MOTOR # <-- ADDED THIS IMPORT

class CharacterizationService:
    def __init__(self, viewmodel):
        self._viewmodel = viewmodel
        self._thread = None
        self.is_active = False

    def start(self, motor_id, voltage):
        if self.is_active:
            return
        self.is_active = True
        self._viewmodel.characterization_results = None
        self._thread = threading.Thread(
            target=self._characterize_thread_func,
            args=(motor_id, voltage),
            daemon=True
        )
        self._thread.start()

    def _characterize_thread_func(self, motor_id, voltage):
        vm = self._viewmodel
        try:
            vm.log_message(f"Characterization: Starting for motor {motor_id}...")
            vm.characterization_status = "1/2: Running test..."
            
            # This custom command will trigger the firmware's characterization function
            vm._motor_service.send_command(motor_id, REG_CUSTOM_CHARACTERIZE_MOTOR, float(voltage), 'f')
            
            # Wait for the results to come back via CAN
            timeout = time.time() + 15  # 15-second timeout
            while time.time() < timeout:
                if vm.characterization_results:
                    break
                time.sleep(0.1)
            
            if vm.characterization_results:
                vm.characterization_status = "Done! Results received."
            else:
                raise TimeoutError("Did not receive characterization results from motor.")

        except Exception as e:
            vm.log_message(f"Characterization ERROR: {e}")
            vm.characterization_status = f"Error: {e}"
        finally:
            self.is_active = False