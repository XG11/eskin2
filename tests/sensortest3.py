import nidaqmx
from nidaqmx.constants import READ_ALL_AVAILABLE, AcquisitionType
import numpy as np
import time
import matplotlib.pyplot as plt

calibrationMatrix = np.matrix([
    [0.184843525290, -5.820387363434, -0.092974022031, 6.097970962624, -0.003208260983, -0.016541913152],
    [0.068360798061, -3.361389636993, 0.091561593115, -3.464745521545, -0.085913859308, -0.085913859308], 
    [-10.499620437622, 0.371050596237, -10.746155738831, 0.277591109276, -10.430329322815, -0.058893989772],
    [-0.148816883564, -0.013231880032, 0.153296604753, -0.021977346390, -0.002836652799, 0.036689631641],
    [-0.085635080934, 0.034371923655, -0.084928609431, -0.030927008018, 0.170041531324, 0.001250812435],
    [-0.003102704883, 0.081076353788, -0.002182871802, 0.083423130214, -0.001354880980, 0.083512537181]]) 

with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan("Dev2/ai0:5")
    task.timing.cfg_samp_clk_timing(10, sample_mode=AcquisitionType.CONTINUOUS)
    task.in_stream.read_all_avail_samp = True
    task.start()

    data = task.read()
    #voltageArray = np.array(data).reshape((6, 1))
    #voltageArray = voltageArray - biasArray
    #FTMatrix = calibrationMatrix@voltageArray
    print(data)
    input("hiofiasdhifdas")
    task.stop()
    #biasArray = np.array([[0.181882411241531],[0.401370793581009],[0.188910976052284], [-0.345218628644943], [-0.0102932518348098], [-0.0757493004202843]])
    #voltageArray = np.array(data).reshape((6, 1))
    #voltageArray = voltageArray - biasArray
    #FTMatrix = calibrationMatrix@voltageArray

    #print(f"Acquired data: {FTMatrix[0,0]:f}")
    #print(f"Acquired data: {FTMatrix[1,0]:f}")
    #print(f"Acquired data: {FTMatrix[2,0]:f}")
    #print(f"Acquired data: {FTMatrix[3,0]:f}")
    #print(f"Acquired data: {FTMatrix[4,0]:f}")
    #print(f"Acquired data: {FTMatrix[5,0]:f}")