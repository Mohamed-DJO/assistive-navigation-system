import serial
import pynmea2

class Neo7MGPS:
    def __init__(self, port="/dev/serial0", baudrate=9600, timeout=2):
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)

    def get_location(self):
        try:
            for _ in range(20):  # read up to 20 lines before giving up
                line = self.ser.readline().decode("ascii", errors="replace").strip()
                if line.startswith("$GPRMC") or line.startswith("$GPGGA"):
                    msg = pynmea2.parse(line)
                    if hasattr(msg, "latitude") and msg.latitude:
                        return float(msg.latitude), float(msg.longitude)
        except Exception as e:
            print(f"[GPS] Error: {e}")
        return None, None