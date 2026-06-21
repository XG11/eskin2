import numpy as np
#import arcade
import time
import csv
import sys
import os
import math
from pathlib import Path
from tqdm import tqdm
from matplotlib import pyplot as plt
import nidaqmx
from nidaqmx.constants import AcquisitionType
from tactile_calibration import Printer, Sensor
import threading
#from pyqtgraph.Qt import QtWidgets, QtCore
#import pyqtgraph as pg
#import dwf
from dwfconstants import *
from scipy.signal import butter, filtfilt, firwin, lfilter
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

class Calibrator:
    def __init__(self, printer:Printer, sensor1:Sensor, sensor2:Sensor, sensor3:Sensor):
        self.printer = printer
        self.FTSensor = sensor1
        self.AD2 = sensor2
        self.FSRStreamSensor = sensor3

        self.printer_connected = False
        self.sensor_connected = False

        try:
            self.printer_name = self.printer.name
        except:
            self.printer_name = "printer"
        try:
            self.sensor_name = self.FTSensor.name
        except:
            self.sensor_name = "FTSensor"
        try:
            self.sensor_name = self.AD2.name
        except:
            self.sensor_name = "AD2"
        try:
            self.sensor_name = self.FSRStreamSensor.name
        except:
            self.sensor_name = "FSRStreamSensor"

    def initialize_printer(self, absolute=True):
        """ Sends gcode to configure and home 3D Printer

        Args:
            absolute (bool): Determines whether to set 3D printer to absolute mode.

        Returns:
            bool: Returns True if initialization was successful.
        """
        # Probe must be detached to home printer
        print("Make sure probe is not attached to print head. ", end="")
        input("Press Enter to continue...")
        print("")
        
        if not self.printer_connected:
            self.connect_printer()
        
        try:
            print("Initializing printer...")

            self.printer.initialize()

            print("Printer initialization complete!")
            print("")
            return True
        except:
            print("Error sending initialization gcode to printer.")
            print("")
            return False
        
    def initalize_csv(self, path, filename = "", header = ['Probe #', 'Voltages']):
        output_dir = Path(path)
        output_dir.mkdir(parents=True, exist_ok=True)
        signal_path = output_dir / filename
        signal_file = open(signal_path,'w', newline ='')
        signal_writer = csv.writer(signal_file)
        signal_writer.writerow(header)
        return signal_writer, signal_file
        
    # def force_graphing(self):
    #     #builds force window and bias buttons
    #     app = QtWidgets.QApplication([])
    #     win = pg.GraphicsLayoutWidget(title="Real-Time Force Data")
    #     bias_button = QtWidgets.QPushButton("Bias")
    #     unbias_button = QtWidgets.QPushButton("Unbias")
    #     proxy1 = QtWidgets.QGraphicsProxyWidget()
    #     proxy1.setWidget(bias_button)
    #     proxy2 = QtWidgets.QGraphicsProxyWidget()
    #     proxy2.setWidget(unbias_button)
        
    #     plotz = win.addPlot()
    #     curvez = plotz.plot(pen='g')
    #     button_row = 1   
    #     win.addItem(proxy1, row=button_row, col=0)
    #     win.addItem(proxy2, row=button_row, col=1)
    #     return win, plotz, curvez, bias_button, unbias_button

    def force_graphing(self):
        # Reuse existing QApplication if present
        from pyqtgraph.Qt import QtWidgets, QtCore
        import pyqtgraph as pg
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])

        win = pg.GraphicsLayoutWidget(title="Real-Time Force + FSR")

        # ---- Force plot (top) ----
        plot_force = win.addPlot(row=0, col=0)
        plot_force.setLabel('left', 'Force Z (arb)')
        plot_force.setLabel('bottom', 'Samples')
        plot_force.showGrid(x=True, y=True, alpha=0.3)
        plot_force.setYRange(-2.0, 2.0)        # adjust for your expected range
        curve_force = plot_force.plot(pen='g')

        # ---- FSR plot (bottom) ----
        plot_fsr = win.addPlot(row=1, col=0)
        plot_fsr.setLabel('left', 'A0 ADC Value')
        plot_fsr.setLabel('bottom', 'Samples (rolling buffer)')
        plot_fsr.showGrid(x=True, y=True, alpha=0.3)
        curve_fsr = plot_fsr.plot(pen='y')

        # ---- Bias / Unbias buttons below both plots ----
        bias_button = QtWidgets.QPushButton("Bias")
        unbias_button = QtWidgets.QPushButton("Unbias")
        proxy1 = QtWidgets.QGraphicsProxyWidget(); proxy1.setWidget(bias_button)
        proxy2 = QtWidgets.QGraphicsProxyWidget(); proxy2.setWidget(unbias_button)
        win.addItem(proxy1, row=2, col=0)
        win.addItem(proxy2, row=2, col=1)

        return win, plot_force, curve_force, plot_fsr, curve_fsr, bias_button, unbias_button

    def create_filter(self, frequency = 5000000, taps = 256, low_cut = 500000, high_cut = 520000):
        fs = frequency          # Sampling frequency in Hz
        nyq = fs / 2            # Nyquist frequency
        numtaps = taps           # Number of FIR filter taps
        low_cut = low_cut         # Lower cutoff frequency (Hz)
        high_cut = high_cut       # Upper cutoff frequency (Hz)
        fir_coeff = firwin(
            numtaps,
            [low_cut / nyq, high_cut / nyq],  # Normalized frequencies
            window='blackman',
            pass_zero=False                   # Band-pass filter
        )
        return fir_coeff  
    
    def peak_plotting(self, signal_writer, signal_file, file_name, row_name, voltages = [], threshold = 2):
        #plots and saves signal data with peak detection
        peak_indices = [i for i, v in enumerate(voltages) if v >= threshold]
        peak_starts = []
        min_spacing = 1000 # samples apart
        controlrow = row_name
        for i in peak_indices:
            if not peak_starts or i - peak_starts[-1] >= min_spacing:
                if i + min_spacing <= len(voltages):
                    peak_starts.append(i)
        signal_file.flush()
        img_dir = Path("results/sensorimages")
        img_dir.mkdir(parents=True, exist_ok=True)
        base_filename = file_name
        for idx, start_idx in enumerate(peak_starts):
            segment = voltages[start_idx:start_idx + min_spacing]
            if idx == 0:
                controlrow.extend(segment)
            else:
                signal_writer.writerow([f"control_{idx}"] + list(segment))
            plt.figure()
            plt.plot(segment)
            plt.xlabel("Time (microseconds)")
            plt.ylabel("Voltage (V)")
            plt.title("control")
            plt.grid(True)
            plt.xlim(0, min_spacing)             # Always show 1000 samples on x-axis
            plt.ylim(-0.05, 0.05)
            filename = f"{base_filename}_{idx}.png"
            plt.savefig(img_dir / filename)
            plt.close()
        signal_writer.writerow(controlrow)
        return True

    def data_plotting_saving(self, signal_writer, signal_file, file_name, row_name, voltages):
        # plots and saves signal data
        signal_file.flush()
        img_dir = Path("results/sensorimages")
        img_dir.mkdir(parents=True, exist_ok=True)
        base_filename = file_name

        signal_writer.writerow([row_name] + list(voltages))

        plt.figure()
        plt.plot(voltages)
        plt.xlabel("Time (microseconds)")
        plt.ylabel("Voltage (V)")
        plt.title("Voltage vs Time")
        plt.grid(True)
        # plt.xlim(0, min_spacing)             # Always show 1000 samples on x-axis
        # plt.ylim(-0.05, 0.05)
        filename = f"{base_filename}_1.png"
        plt.savefig(img_dir / filename)
        plt.close()

        # for idx, start_idx in enumerate(peak_starts):
        #     segment = voltages[start_idx:start_idx + min_spacing]
        #     if idx == 0:
        #         controlrow.extend(segment)
        #     else:
        #         signal_writer.writerow([f"control_{idx}"] + list(segment))
        #     plt.figure()
        #     plt.plot(segment)
        #     plt.xlabel("Time (microseconds)")
        #     plt.ylabel("Voltage (V)")
        #     plt.title("control")
        #     plt.grid(True)
        #     plt.xlim(0, min_spacing)             # Always show 1000 samples on x-axis
        #     plt.ylim(-0.05, 0.05)
        #     filename = f"{base_filename}_{idx}.png"
        #     plt.savefig(img_dir / filename)
        #     plt.close()
        # signal_writer.writerow(controlrow)
        return True    

    def probe(self, home_printer=True, record_signal=True, calibration_file_path=None, data_save_path=None, 
              calibrationMatrix=None, rate=None, samples_per_update = 10, windowWidth = 200,
              auto_bias = True, apply_filter = True):
        """ Executes the probing procedure 

        Args:
            home_printer (bool): Determines whether to home the printer prior to probing.
            record_force (bool): Determines whether sensor forces are saved.
            calibration_file_path (str): The path of the calibration file. If no file is specified,
                a default calibration file will be used.
            data_save_path (str): The folder in which the data should be saved. If no folder is specified,
                data will be stored in a folder names "sensor_calibration_data" in the user's Downloads folder.
            calibrationMatrix (Matrix): The calibration matrix for converting the voltage data from the DAQ to force/torque data
            rate (int): the rate for which sensor data is read
            samples_per_update (int): the number of samples read by the sensor at the specified rate
            windowWidth (int): the amount of values shown on the screen when graphing
            auto_bias (bool): Determines whether force data is biased automatically
            apply_filter (bool): Determines whether filter is applied
            
        Returns:
            bool: Returns True when the probing procedure is complete.
        """
        
        # Connect to 3D printer if not already connected
        self.printer.connect()

        # Connect to sensor
        if record_signal == True:
            # dwf, hdwf = self.AD2.connect()
            self.FSRStreamSensor.connect()

        # Send initialization gcode to printer
        if home_printer == True:
            self.initialize_printer()

        # If no data path was provided, set default path to a folder called "sensor_calibration_data" in the Downloads folder
        if data_save_path == None:
            data_save_path = str("results/sensordata")
        else:
            data_save_path = os.path.join(data_save_path, "force_values")
            
        #initializes csv files and writers for signal and force readings
        signal_writer, signal_file = self.initalize_csv(data_save_path, "waveform_readings.csv", ['Probe #', 'Voltages'])
        csv_writer, csv_file = self.initalize_csv(data_save_path, "sensor_data.csv", ['img_num', 'Fx', 'Fy', 'Fz', 'Tx', 'Ty', 'Tz'])

        # If no calibration file path was provided, use the default calibration file for the specified sensor
        if calibration_file_path == None:
            calibration_file_path = self.FTSensor.default_calibration_file
        # Load CSV file into numpy array
        self.calibration_points = np.genfromtxt(calibration_file_path, delimiter=',', skip_header=1)
        # Get number of rows (i.e. calibration points)
        N = self.calibration_points.shape[0]
        
        # Move to offset Z and XY position
        Speed = 8000

        self.printer.send_gcode("G1 Z" + str(self.FTSensor.z_offset + self.FTSensor.z_clearance) + " F" + str(Speed))
        self.printer.send_gcode("G1 X" + str(self.FTSensor.x_offset) + " Y" + str(self.FTSensor.y_offset) + " F" + str(Speed))
        time.sleep(5)
        
        print("Attach probe to printer head. ", end="")
        input("Press Enter to continue...")
        print("")
        
        #declare amount of samples to aquire and how many
        hzAcq = c_double(5000000)
        nSamples = 6000
        Zbuffer = np.zeros(windowWidth)
        
        #declares state variables that are used in each method
        state = {
            "x_prev": self.FTSensor.x_offset,
            "y_prev": self.FTSensor.y_offset,
            "z_prev": self.FTSensor.z_offset + self.FTSensor.z_clearance,
            "probing_done": False,
            "bias" : np.zeros((6, samples_per_update)),
            "ptr" : 0,
            "all_datax" : [],
            "all_datay" : [],
            "all_dataz" : [],
            "scope_data" : [],
            "threshold":  .015,
            "probeNumber": 0,
            "all_fsr": [], # store all FSR samples over time
            "fsr_prev_len": 0, # how many samples we've already copied from the buffer
        }
        
        #creates fir filter coefficient for filter
        # fir_coeff = self.create_filter()
        
        if record_signal:
            PORT = "COM28"        
            BAUD = 115200
            DURATION_S = 0.1       # capture 1 seconds
            BUFFER = 200           # rolling buffer; should exceed expected samples in DURATION_S
            YLIM = 1200            # for plotting (10-bit ADC ≈ 1023)

            if not self.FSRStreamSensor.connect():
                raise RuntimeError(f"Could not open serial port {PORT} at {BAUD} baud.")

            self.FSRStreamSensor.initialize_stream(BUFFER)

            self.FSRStreamSensor.start_logging()

            # Let the background thread accumulate samples
            print(f"Recording {DURATION_S:.1f}s from FSR stream every pressing…")
            # import time; time.sleep(DURATION_S)

            # Get the last DURATION_S window (time-based)
            # t, control1 = self.FSRStreamSensor.capture_image(DURATION_S)
            # if control1.size == 0:
            #     raise RuntimeError("No samples captured from stream.")

            # # Plot (and optionally save an image of the last 10 s)
            # plt.ioff()
            # fig, ax = plt.subplots(figsize=(10, 5))
            # ax.plot(t, control1, linewidth=1.0)
            # ax.set_xlim(0, max(DURATION_S, float(t[-1]) if t.size else DURATION_S))
            # ax.set_ylim(0, YLIM)
            # ax.set_xlabel("Time (s)")
            # ax.set_ylabel("A0 ADC Value")
            # ax.set_title(f"FSR Stream: Last {DURATION_S:.0f}s")
            # ax.grid(True, alpha=0.3)
            # fig.tight_layout()

            # plt.show()

            # #starts signal generator
            # self.AD2.generate_signal(dwf, hdwf, 1, 3, 515000, funcPulse)
            # #starts oscilloscope
            # dwf, hdwf = self.AD2.initialize_oscilloscope(dwf, hdwf, c_double(5), hzAcq, nSamples)
            
            # #captures control data reading and plots it with peak detection reading
            # control1 = self.AD2.capture_image(hdwf, nSamples)
            # if apply_filter:
            #     # Apply filter with zero phase distortion
            #     control = filtfilt(fir_coeff, 1.0, control1)
            # else:
            #     control = control1
            # plt.plot(control)
            # plt.show()
            # state["threshold"] = float(input("Input threshold voltage: "))
            # print("")
            # self.peak_plotting(signal_writer,signal_file,"control",["control"], control, state["threshold"])
            
        #starts force plotting sequence
        win, plotz, curvez, plot_fsr, curve_fsr, bias_button, unbias_button = self.force_graphing()
        
        plot_fsr.setYRange(0, float(YLIM))
        plot_fsr.setXRange(0, float(self.FSRStreamSensor.buffer_size - 1))

        print("Beginning sensor calibration procedure...")
        print("")

        # threading task to probe the sensor and move to each location
        def probing():
        # Loop through every calibration point
            for i in tqdm(range(N), desc="Sensor Calibration Progress"):
                # If specified penetration depth exceeds maximum value, print message
                if abs(self.calibration_points[i][2]) > self.FTSensor.max_penetration:
                    print("Line " + str(i+1) + ": Maximum penetration depth for sensor exceeded. Skipping calibration point.")
                # If penetration depth does not exceed maximum value, move to calibration point
                else:
                    state["probeNumber"] += 1
                    # Get absolute XYZ coordinates
                    x = self.FTSensor.x_offset + self.calibration_points[i][0]
                    y = self.FTSensor.y_offset + self.calibration_points[i][1]
                    z = self.FTSensor.z_offset - abs(self.calibration_points[i][2])

                    # Move to Z clearance height
                    self.printer.send_gcode("G1 Z" + str(self.FTSensor.z_offset + self.FTSensor.z_clearance - 3.8) + " F" + str(Speed))
                    state["probed"] = False
                    # Move to desired XY locations
                    self.printer.send_gcode("G1 X" + str(x) + " Y" + str(y) + " F" + str(Speed))
                    time.sleep(0.1)

                    # Calculate time required to reach position
                    travel_time = abs(self.FTSensor.z_offset + self.FTSensor.z_clearance - state["z_prev"]) / 4 + max(abs(x - state["x_prev"]), abs(y - state["y_prev"])) / 10 + abs(z - (self.FTSensor.z_offset + self.FTSensor.z_clearance)) / 4
                    if self.calibration_points[i][3] != 0:
                        #if angle, calculate offset to move printer at desired depth at specified angle
                        angledz = self.FTSensor.z_offset - math.cos(math.radians(self.calibration_points[i][3]))*abs(self.calibration_points[i][2])
                        angledx = x + self.calibration_points[i][2]*math.sin(math.radians(self.calibration_points[i][3]))
                        self.printer.send_gcode("G1 Z" + str(angledz) + " X"+ str(angledx) + " F" + str(Speed))
                    else:
                        # Move to desired Z penetration
                        self.printer.send_gcode("G1 Z" + str(z) + " F" + str(Speed))
                        
                    # waits 5 second and opens scope data collection
                    time.sleep(float(self.calibration_points[i][4]))

                    # Update variables
                    state["x_prev"] = x
                    state["y_prev"] = y
                    state["z_prev"] = z
            #checks when probing is done
            state["probing_done"] = True

        # threading task to read FSR data
        def fsr_reading():
            # reads FSR data
            # if not state["probing_done"]:
            # while True:
            self.FSRStreamSensor.plot_live(fps=15, ylim=1200, invert=True,
                    title=f"FSR: Live Plot")
            # self.FSRStreamSensor.dummy_test()
                # state["scope_data"].extend(fsr_data)
                # time.sleep(0.01)
            return

        # starts probing thread
        thread = threading.Thread(target=probing)
        thread.start()

        # starts fsr reading thread
        # fsr_thread = threading.Thread(target=self.FSRStreamSensor.plot_live(fps=30, ylim=1200, invert=True,
        #                 title=f"FSR: Live Plot in Thread",))
        # fsr_thread.start()

        # declares FT sensor task
        with nidaqmx.Task() as task:
            # opens analog channels for FT sensor
            task.ai_channels.add_ai_voltage_chan("Dev1/ai0:5")
            # continuously reads FT sensor data at rate
            task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.CONTINUOUS)
            win.show()
            task.start()
            
            # if you want to auto bias, will get bias voltages
            if auto_bias:
                bias_data = task.read(number_of_samples_per_channel=samples_per_update)
                state["bias"] = np.array(bias_data)

            # update function for force animation
            def update():
                #checks if probing is done
                if state["probing_done"]:
                    # Move to Z clearance height    
                    self.printer.send_gcode("G1 Z" + str(self.FTSensor.z_offset + self.FTSensor.z_clearance) + " F" + str(Speed))
                    #when probing is done, stops reading from DAQ and timer
                    time.sleep(0.1)
                    task.stop()
                    timer.stop()
                    print("Stopped DAQ. You can now pan/zoom in the plot.")
                    self.FSRStreamSensor.stop_logging()

                    # ensures all csv data is written
                    signal_file.flush()
                    csv_file.flush()
                    csv_file.close()
                    signal_file.close()

                    # Removes previous live plot and replaces with plot with full data for analysis
                    # plots final force data
                    x_vals = np.arange(len(state["all_dataz"]))
                    plotz.clear()
                    final_force_curve = plotz.plot(x_vals, state["all_dataz"], pen='g')
                    plotz.enableAutoRange(x=True, y=True)

                    # ---- Final FSR plot: all samples ----
                    fsr_all = self.FSRStreamSensor.get_log()
                    if fsr_all.size > 0:
                        fsr_all_plot = 1023 - fsr_all  # invert to match live
                        x_fsr = np.arange(fsr_all_plot.size)

                        plot_fsr.clear()
                        plot_fsr.plot(x_fsr, fsr_all_plot, pen='y')
                        plot_fsr.enableAutoRange(x=True, y=True)
                    return
                
                # --- Force (FT) update ---    
                # Read new samples: shape (6s, N) {N = sample size}
                data = task.read(number_of_samples_per_channel=samples_per_update)
                data_np = np.array(data)
                # Apply bias voltages if there are any. (literally just reads voltages and subtracts them to make them closer to zero when no force)
                voltages = data_np - state["bias"]
                # Apply calibration matrix
                FT_final = calibrationMatrix @ voltages  # shape (6, N)

                # only plots for z
                valuez = np.mean(FT_final[2, :])
                state["all_dataz"].append(valuez)
                Zbuffer[:-1] = Zbuffer[1:]
                Zbuffer[-1] = valuez
                state["ptr"] += 1
                curvez.setData(Zbuffer)
                curvez.setPos((state["ptr"] - windowWidth), 0)
                # write to csv file
                csv_writer.writerow([(state["ptr"]/rate)*samples_per_update, FT_final[0][0], FT_final[1][0], FT_final[2][0], FT_final[3][0], FT_final[4][0], FT_final[5][0]])
                
                # --- FSR update (same timer) ---
                y = self.FSRStreamSensor.get_buffer()  # rolling buffer (length <= buffer_size)
                if y.size:
                    # 1) Accumulate *new* samples into state["all_fsr"]
                    prev_len = state["fsr_prev_len"]
                    if y.size > prev_len:
                        new_samples = y[prev_len:]            # assume buffer grows until full
                        state["all_fsr"].extend(new_samples.tolist())
                        state["fsr_prev_len"] = y.size

                    # pad if buffer not yet full
                    if y.size < self.FSRStreamSensor.buffer_size:
                        pad = np.full(self.FSRStreamSensor.buffer_size - y.size,
                                    y[0] if y.size else 0, dtype=np.int16)
                        y_plot = np.concatenate([pad, y])
                    else:
                        y_plot = y[-self.FSRStreamSensor.buffer_size:]

                    # invert:
                    y_plot = 1023 - y_plot

                    curve_fsr.setData(y_plot)                
                   
                return
            
            # biases data
            def bias():
                bias_data = task.read(number_of_samples_per_channel=samples_per_update)
                state["bias"] = np.array(bias_data)
            # unbiases data
            def unbias():
                state["bias"] = np.zeros((6, samples_per_update))        
                         
            bias_button.clicked.connect(bias)
            unbias_button.clicked.connect(unbias)

            # starts force animation
            from pyqtgraph.Qt import QtWidgets, QtCore
            timer = QtCore.QTimer()
            timer.timeout.connect(update)
            timer.start(int(1000 * samples_per_update / rate)) # ms
            QtWidgets.QApplication.instance().exec()
    
            # Move to Z clearance height    
            self.printer.send_gcode("G1 Z" + str(self.FTSensor.z_offset + self.FTSensor.z_clearance) + " F" + str(Speed))

            print("")
            task.stop()

        # Disconnect from 3D printer
        self.printer.disconnect()

        # Disconnect from sensor
        if record_signal == True:
            # self.AD2.disconnect()
            self.FSRStreamSensor.disconnect()

        print("Sensor calibration procedure complete!")
        print("")

        return True