import nidaqmx
from nidaqmx.constants import AcquisitionType
import numpy as np
from pyqtgraph.Qt import QtWidgets, QtCore
import pyqtgraph as pg

# Configuration
rate = 2000  # Hz
samples_per_update = 100
windowWidth = 500  # plot window width

calibrationMatrix = np.array([
    [0.184843525290, -5.820387363434, -0.092974022031, 6.097970962624, -0.003208260983, -0.016541913152],
    [0.068360798061, -3.361389636993, 0.091561593115, -3.464745521545, -0.085913859308, -0.085913859308], 
    [-10.499620437622, 0.371050596237, -10.746155738831, 0.277591109276, -10.430329322815, -0.058893989772],
    [-0.148816883564, -0.013231880032, 0.153296604753, -0.021977346390, -0.002836652799, 0.036689631641],
    [-0.085635080934, 0.034371923655, -0.084928609431, -0.030927008018, 0.170041531324, 0.001250812435],
    [-0.003102704883, 0.081076353788, -0.002182871802, 0.083423130214, -0.001354880980, 0.083512537181]
])

# Setup UI
app = QtWidgets.QApplication([])  # Use QApplication instead of QGuiApplication
win = pg.GraphicsLayoutWidget(title="Fz Real-Time")
plot = win.addPlot()
curve = plot.plot(pen='y')
win.show()
stop_button = QtWidgets.QPushButton("Stop")
proxy = QtWidgets.QGraphicsProxyWidget()
proxy.setWidget(stop_button)
win.addItem(proxy, row=1, col=4)
# Create rolling data buffer
Xm = np.zeros(windowWidth)
ptr = 0
all_data = []
time = []
running = True
# DAQ setup
task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan("Dev2/ai0:5")
task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.CONTINUOUS)
task.start()

# Timer callback function
def update():
    global Xm, ptr, curve, all_data  
    try:
        if not running:
            return
        
        data = task.read(number_of_samples_per_channel=samples_per_update)
        data_np = np.array(data)
        FT_all = calibrationMatrix @ data_np
        value = np.mean(FT_all[2, :])  # Fz average
        all_data.append(value)
        # Update buffer
        Xm[:-1] = Xm[1:]
        Xm[-1] = value
        ptr += 1
        time = ptr*samples_per_update/rate
        curve.setData(time,Xm)
        curve.setPos(ptr - windowWidth, 0)
    except Exception as e:
        print("Error:", e)
        
def stop():
    global running
    running = False
    timer.stop()
    curve.setPos(0, 0)
    curve.setData(all_data)
    plot.setRange(xRange=[0, len(all_data)], padding=0)
    task.stop()
    print("Stopped DAQ. You can now pan/zoom in the plot.")
    
# Use QTimer for non-blocking updates
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(int(samples_per_update / rate))  # ms interval
stop_button.clicked.connect(stop)
# Start Qt event loop
QtWidgets.QApplication.instance().exec()


# After live session ends, show full data

