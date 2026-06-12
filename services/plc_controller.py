import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PLCController")

class PLCController:
    """Simulates communication with a Programmable Logic Controller (PLC) for sorting/rejection"""
    
    def __init__(self, ip_address="192.168.1.50", port=502):
        self.ip_address = ip_address
        self.port = port
        # In-memory Modbus coils simulation
        self.coils = {
            1001: False, # Coil 1001: Reject Actuator Trigger (True = Extend Arm)
            1002: False, # Coil 1002: Conveyor Stop Signal
            1003: True   # Coil 1003: Conveyor Running Status
        }
        self.log_history = []
        self._log("PLC simulation initialized. Listening on Modbus/TCP port 502.")

    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] PLC Status: {message}"
        self.log_history.append(entry)
        logger.info(entry)
        if len(self.log_history) > 50:
            self.log_history.pop(0)

    def trigger_reject(self, detection_id, defect_type, severity):
        """Simulates writing to Modbus registers to trigger physical reject arm"""
        self._log(f"Received Reject Request for Detection #{detection_id} ({defect_type}, Severity: {severity})")
        
        # Write Coil 1001 = True (Extend Reject Arm)
        self.coils[1001] = True
        self._log("Modbus Coil 1001 written to 1 (Reject Actuator Extended)")
        
        # If Critical, also trigger conveyor stop
        if severity == 'Critical':
            self.coils[1002] = True
            self.coils[1003] = False
            self._log("WARNING: Critical defect. Modbus Coil 1002 written to 1 (Conveyor Stopped).")
            
        # Simulate physical execution delay and reset the actuator trigger coil
        # in a real PLC this is done by timer circuits or limit switches.
        time.sleep(0.1) 
        self.coils[1001] = False
        self._log("Modbus Coil 1001 reset to 0 (Reject Actuator Retracted)")
        
        return {
            'actuator_status': 'Triggered',
            'coils': self.coils.copy(),
            'msg': f"Reject actuator triggered on line for defect '{defect_type}'"
        }

    def reset_conveyor(self):
        """Resets stop signals and restarts conveyor"""
        self.coils[1002] = False
        self.coils[1003] = True
        self._log("Modbus Coil 1002 reset to 0. Coil 1003 written to 1 (Conveyor Restarted)")
        return True

    def get_status(self):
        return {
            'ip': self.ip_address,
            'port': self.port,
            'coils': self.coils,
            'log': self.log_history[-10:]
        }
