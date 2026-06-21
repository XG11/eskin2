import tactile_calibration as tc
import numpy as np


#tc.list_com_ports()

#connects to printer via COM port
ender3 = tc.Ender3("COM29")
ender3.connect()

#declares sensing method to use
FTSensor = tc.FTSensor()
AD2 = tc.AnalogD2()
FSR = tc.FSRStreamSensor()

rate = 3000 # Hz
samples_per_update = 500 # How many samples to read per animation frame

calibrationMatrix = np.array([
    [0.184843525290, -5.820387363434, -0.092974022031, 6.097970962624, -0.003208260983, -0.016541913152],
    [0.068360798061, -3.361389636993, 0.091561593115, -3.464745521545, -0.085913859308, -0.085913859308], 
    [-10.499620437622, 0.371050596237, -10.746155738831, 0.277591109276, -10.430329322815, -0.058893989772],
    [-0.148816883564, -0.013231880032, 0.153296604753, -0.021977346390, -0.002836652799, 0.036689631641],
    [-0.085635080934, 0.034371923655, -0.084928609431, -0.030927008018, 0.170041531324, 0.001250812435],
    [-0.003102704883, 0.081076353788, -0.002182871802, 0.083423130214, -0.001354880980, 0.083512537181]
])

#declares the calibration object with printer and sensor
calib = tc.Calibrator(printer=ender3, sensor1=FTSensor, sensor2=AD2, sensor3=FSR)

#probe method, will probe the sensor, moving to each point individually
calib.probe(home_printer=False, record_signal=True, calibration_file_path="calibration_paths/calib_points_test1.csv", 
                calibrationMatrix=calibrationMatrix, rate=rate, samples_per_update= samples_per_update, 
                 auto_bias=True)