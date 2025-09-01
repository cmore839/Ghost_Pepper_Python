# services/can_service.py
import can
import queue
import threading
from config import CAN_INTERFACE, CAN_CHANNEL, CAN_BITRATE, CAN_ID_TELEMETRY_BASE, CAN_ID_RESPONSE_BASE, CAN_ID_STATUS_FEEDBACK_BASE

class CanService:
    def __init__(self):
        self._bus = None
        self._is_running = False
        self._read_thread = None
        self._message_queue = queue.Queue()

    def connect(self):
        try:
            can_filters = [
                {"can_id": CAN_ID_TELEMETRY_BASE, "can_mask": 0x780}, 
                {"can_id": CAN_ID_RESPONSE_BASE, "can_mask": 0x700},
                {"can_id": CAN_ID_STATUS_FEEDBACK_BASE, "can_mask": 0x700}
            ]
            self._bus = can.interface.Bus(interface=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=CAN_BITRATE, can_filters=can_filters)
            self._is_running = True
            self._read_thread = threading.Thread(target=self._read_messages, daemon=True)
            self._read_thread.start()
            return True
        except Exception as e:
            print(f"Error connecting to CAN bus: {e}")
            return False

    def disconnect(self):
        if self._is_running:
            self._is_running = False
            if self._read_thread: self._read_thread.join(timeout=1)
            if self._bus: self._bus.shutdown()

    def _read_messages(self):
        while self._is_running:
            try:
                msg = self._bus.recv(timeout=0.1)
                if msg: self._message_queue.put(msg)
            except Exception as e:
                print(f"Error in CAN read thread: {e}")
                break

    def get_message_queue(self):
        return self._message_queue

    def send_message(self, message):
        if self._bus and self._is_running:
            try: self._bus.send(message)
            except can.CanError as e: print(f"Error sending message: {e}")