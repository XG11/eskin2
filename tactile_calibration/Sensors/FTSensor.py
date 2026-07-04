from tactile_calibration import Sensor
import nidaqmx
import numpy as np
# example coordiantes: 43 Z to clear top of testbed
# (58,59,18.3) usual coordinates for edge of test bed
# 18.3~ Z to touch top of testbed
# make sure to add penetration depth to Z-offset for the correct touch distance

class FTSensor(Sensor):
    """
    Defines parameters for sensor calibration

    Args:
    Sensor (object): sensor used for testing
    """
    def __init__(self):
        """
        Defines initial parameters for testing including start position for pritner

        Args:
        self (object): printer object
        """
        self.name = "FTSensor"
        self.x_offset = 0 #55 #x coordinate of corner of testbed
        self.y_offset = 0 #64.5 #y coordinate of corner of testbed
        self.z_offset = 80 #z coordinate of corner of testbed + 1.5 mm, 66 for with bendable plate, 98.1 for without bendable plate, 101.1 with membrane
        self.z_clearance = 6 #how high it moves when moving
        self.max_penetration = 25 #limit on how deep the z will move
        self.default_calibration_file = "calib_points.csv" #x,y,z coordinates probe will move to
        
    def connect(self):
        #sensor connection 
        pass
        
    def disconnect(self):
        #sensor disconnect
        pass

    def capture_image(self):
        #sensor capture
        with nidaqmx.Task() as G0task, nidaqmx.Task() as G1task, nidaqmx.Task() as G2task, nidaqmx.Task() as G3task, nidaqmx.Task() as G4task, nidaqmx.Task() as G5task:
            G0task.ai_channels.add_ai_voltage_chan("Dev2/ai0")
            G1task.ai_channels.add_ai_voltage_chan("Dev2/ai1")
            G2task.ai_channels.add_ai_voltage_chan("Dev2/ai2")
            G3task.ai_channels.add_ai_voltage_chan("Dev2/ai3")
            G4task.ai_channels.add_ai_voltage_chan("Dev2/ai4")
            G5task.ai_channels.add_ai_voltage_chan("Dev2/ai5")
            data0 = G0task.read()
            data1 = G1task.read()
            data2 = G2task.read()
            data3 = G3task.read()
            data4 = G4task.read()
            data5 = G5task.read()

            calibrationMatrix = np.matrix([
            [0.184843525290, -5.820387363434, -0.092974022031, 6.097970962624, -0.003208260983, -0.016541913152],
            [0.068360798061, -3.361389636993, 0.091561593115, -3.464745521545, -0.085913859308, -0.085913859308], 
            [-10.499620437622, 0.371050596237, -10.746155738831, 0.277591109276, -10.430329322815, -0.058893989772],
            [-0.148816883564, -0.013231880032, 0.153296604753, -0.021977346390, -0.002836652799, 0.036689631641],
            [-0.085635080934, 0.034371923655, -0.084928609431, -0.030927008018, 0.170041531324, 0.001250812435],
            [-0.003102704883, 0.081076353788, -0.002182871802, 0.083423130214, -0.001354880980, 0.083512537181]]) 
            biasArray = np.array([[0.181882411241531],[0.401370793581009],[0.188910976052284], [-0.345218628644943], [-0.0102932518348098], [-0.0757493004202843]])
            voltageArray = np.matrix([[data0],[data1],[data2],[data3],[data4],[data5]])
            voltageArray = voltageArray - biasArray
            FTMatrix = calibrationMatrix@voltageArray
            return FTMatrix
        
    def generate_signal(self):
        
        pass

    def initialize_oscilloscope(self):
        
        pass