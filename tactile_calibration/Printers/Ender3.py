from tactile_calibration import Printer
import serial

class Ender3(Printer):
    def __init__(self, port):
        self.port = port
        self.name = "Ender 3"

    def connect(self):
        """ Connects to the 3D Printer

        Returns:
            bool: Returns True if connection was successful.
        """
        print("Connecting to " + str(self.name) + "...")

        try:
            self.ser = serial.Serial(self.port, 115200)
            self.printer_connected = True

            print("Connected to " + str(self.name) + "!")
            print("")
            return True
        except:
            self.printer_connected = False
            print("Error connecting to " + str(self.name) + ".")
            print("")
            return False

    def disconnect(self):
        """ Disconnects from the 3D Printer

        Returns:
            bool: Returns True if disconnection was successful.
        """
        print("Disconnecting from " + str(self.name) + "...")

        try:
            self.ser.close()
            self.printer_connected = False
            print("Disconnected from " + str(self.name) + "!")
            print("")
            return True
        except:
            print("Error disconnecting from " + str(self.name) + ".")
            print("")
            return False
        

    def send_gcode(self, command):
        # Code to execute gcode command on the printer
        self.ser.write(str.encode(command + "\r\n"))

    def get_response(self):
        # Code to return message from the printer
        reading = self.ser.readline().decode('utf-8')

        return reading

    def initialize(self):
        # Code to initialize printer (home, set units, set absolute/relative movements, adjust fan speeds, etc.)

        # Use Metric Values
        self.send_gcode("G21")

        # Absolute Positioning
        self.send_gcode("G90")

        # Fan Off
        self.send_gcode("M107")

        # Home Printer X Y
        self.send_gcode("G28")

        # Check if homing is complete
        ok_count = 0

        while ok_count < 4:
            if "ok" in self.get_response():
                ok_count += 1

        return True