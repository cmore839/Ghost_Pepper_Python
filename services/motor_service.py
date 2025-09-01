# services/motor_service.py
import can
import struct
import time
from config import *
from models.motor import Motor

class MotorService:
    def __init__(self, can_service, data_service):
        self._can_service = can_service
        self._data_service = data_service

    def scan_for_motors(self):
        message = can.Message(arbitration_id=CAN_ID_SCAN_BROADCAST, is_extended_id=False)
        self._can_service.send_message(message)
        
    def send_sync(self):
        message = can.Message(arbitration_id=CAN_ID_SYNC, is_extended_id=False, dlc=0)
        self._can_service.send_message(message)

    def process_message(self, msg, existing_motors):
        # --- Telemetry Messages ---
        if CAN_ID_TELEMETRY_BASE <= msg.arbitration_id < (CAN_ID_TELEMETRY_BASE + 128):
            motor_id = msg.arbitration_id - CAN_ID_TELEMETRY_BASE
            if motor_id not in [m.id for m in existing_motors]:
                self._data_service.register_stream(f"motor_{motor_id}_angle")
                self._data_service.register_stream(f"motor_{motor_id}_velocity")
                self._data_service.register_stream(f"motor_{motor_id}_current_q")
                return ('new_motor', Motor(id=motor_id))
            return self._unpack_telemetry(motor_id, msg.data)

        # --- Status Feedback Messages ---
        elif CAN_ID_STATUS_FEEDBACK_BASE <= msg.arbitration_id < (CAN_ID_STATUS_FEEDBACK_BASE + 128):
            motor_id = msg.arbitration_id - CAN_ID_STATUS_FEEDBACK_BASE
            return self._unpack_status_feedback(motor_id, msg.data)
        
        # --- Standard Parameter Responses ---
        elif CAN_ID_RESPONSE_BASE <= msg.arbitration_id < (CAN_ID_RESPONSE_BASE + 128):
            motor_id = msg.arbitration_id - CAN_ID_RESPONSE_BASE
            if not msg.data: return None
            reg_id = msg.data[0]
            
            if reg_id == REG_STATUS and len(msg.data) >= 2:
                is_enabled = msg.data[1] > 0
                return ('status_response', {'motor_id': motor_id, 'is_enabled': is_enabled})
            
            if len(msg.data) >= 5:
                value = struct.unpack('<f', msg.data[1:5])[0]
                return ('param_response', {'motor_id': motor_id, 'reg_id': reg_id, 'value': value})
        
        # --- Special Characterization Response ---
        elif (CAN_ID_RESPONSE_BASE + 0x80) <= msg.arbitration_id < (CAN_ID_RESPONSE_BASE + 0x80 + 128):
            motor_id = msg.arbitration_id - (CAN_ID_RESPONSE_BASE + 0x80)
            if len(msg.data) == 8:
                resistance, inductance = struct.unpack('<ff', msg.data)
                return ('char_response', {'motor_id': motor_id, 'R': resistance, 'L': inductance})

        return None

    def _unpack_telemetry(self, motor_id, data):
        if len(data) < 8: return None
        try:
            # Data format is 32-bit angle, 16-bit velocity, 16-bit current
            angle_raw, vel_raw, cur_q_raw = struct.unpack('<ihh', data[0:8])
            angle = angle_raw * 0.0001
            velocity = vel_raw * 0.01
            current_q = cur_q_raw * 0.001
            
            ts = time.time()
            self._data_service.add_data_point(f"motor_{motor_id}_angle", ts, angle)
            self._data_service.add_data_point(f"motor_{motor_id}_velocity", ts, velocity)
            self._data_service.add_data_point(f"motor_{motor_id}_current_q", ts, current_q)
            return ('telemetry', {'motor_id': motor_id, 'angle': angle, 'velocity': velocity, 'current_q': current_q})
        except (struct.error): 
            return None
            
    def _unpack_status_feedback(self, motor_id, data):
        if len(data) < 8: return None
        try:
            angle_raw, vel_raw, status_flags, state = struct.unpack('<ihBB', data[0:7])
            angle = angle_raw / 10000.0
            velocity = vel_raw / 100.0
            return ('status_feedback', {'motor_id': motor_id, 'angle': angle, 'velocity': velocity, 'status_flags': status_flags, 'state': state})
        except (struct.error):
            return None


    def send_command(self, motor_id, register, value, fmt):
        if motor_id is None: return
        command_id = CAN_ID_COMMAND_BASE + motor_id
        data = [register]
        if fmt == 'b': data.append(value)
        elif fmt == 'f': data.extend(list(struct.pack('<f', value)))
        elif fmt == 'L': data.extend(list(struct.pack('<L', value)))
        elif fmt == 'none': pass
        else: return
        message = can.Message(arbitration_id=command_id, data=data, is_extended_id=False)
        self._can_service.send_message(message)

    def send_motion_command(self, motor_id, pos, vel, acc):
        # Prepare the data payload with new scaling factors
        pos_raw = int(pos * 10000.0)
        # --- FIX: New scaling factor for velocity ---
        vel_raw = int(vel * 100.0)
        # --- FIX: New scaling factor for acceleration ---
        acc_raw = int(acc * 10.0)

        try:
            # --- FIX: Revert to 8-byte packet structure ---
            data = struct.pack('<ihh', pos_raw, vel_raw, acc_raw)
            
            # The 'dlc' is no longer needed as 8 bytes is the default
            message = can.Message(
                arbitration_id=(CAN_ID_MOTION_COMMAND_BASE + motor_id),
                data=data,
                is_extended_id=False
            )
            self._can_service.send_message(message)
        except Exception as e:
            print(f"Error sending motion command: {e}")
            
    def request_parameter(self, motor_id, register):
        if motor_id is None: return
        command_id = CAN_ID_COMMAND_BASE + motor_id
        message = can.Message(arbitration_id=command_id, data=[register], is_extended_id=False)
        self._can_service.send_message(message)