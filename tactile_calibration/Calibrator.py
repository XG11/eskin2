import numpy as np
import arcade
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
from tactile_calibration import Printer, Sensor, Joystick
import threading
from pyqtgraph.Qt import QtWidgets, QtCore
import pyqtgraph as pg
from nlabapi import LabBench, AnalogSignalPolarity
import dwf
from dwfconstants import *
from scipy.signal import butter, filtfilt, firwin,lfilter

class Calibrator:
    def __init__(self, printer:Printer, sensor:Sensor):
        self.printer = printer
        self.sensor = sensor

        self.printer_connected = False
        self.sensor_connected = False

        try:
            self.printer_name = self.printer.name
        except:
            self.printer_name = "printer"
        try:
            self.sensor_name = self.sensor.name
        except:
            self.sensor_name = "tactile"
    
    def connect_printer(self):
        """ Connects to the 3D Printer

        Returns:
            bool: Returns True if connection was successful.
        """
        print("Connecting to " + str(self.printer_name) + "...")

        try:
            self.printer.connect()
            self.printer_connected = True

            print("Connected to " + str(self.printer_name) + "!")
            print("")
            return True
        except:
            self.printer_connected = False
            print("Error connecting to " + str(self.printer_name) + ".")
            print("")
            return False
        
    def disconnect_printer(self):
        """ Disconnects from the 3D Printer

        Returns:
            bool: Returns True if disconnection was successful.
        """
        print("Disconnecting from " + str(self.printer_name) + "...")

        try:
            self.printer.disconnect()
            self.printer_connected = False
            print("Disconnected from " + str(self.printer_name) + "!")
            print("")
            return True
        except:
            print("Error disconnecting from " + str(self.printer_name) + ".")
            print("")
            return False

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
        
    def connect_sensor(self):
        """ Connects to the sensor

        Returns:
            bool: Returns True if connection was successful.
        """
        print("Connecting to " + self.sensor_name + " sensor...")
        try:
            # Connects to sensor from library system
            if sys.platform.startswith("win"):
                dwf = cdll.dwf
            elif sys.platform.startswith("darwin"):
                dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
            else:
                dwf = cdll.LoadLibrary("libdwf.so")
            #declares intialization pointor hdwf
            hdwf = c_int()    
            #checks version
            version = create_string_buffer(16)
            dwf.FDwfGetVersion(version)
            print("DWF Version: "+str(version.value))
            print("Opening first device")
            #opens device
            dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))
            #if can't connect, prints and quits
            if hdwf.value == hdwfNone.value:
                szerr = create_string_buffer(512)
                dwf.FDwfGetLastErrorMsg(szerr)
                print(str(szerr.value))
                print("failed to open device")
                quit()
            print("Sensor Connected!")
            return dwf, hdwf
        except:
            print("Error connecting to sensor.")
            print("")
            
    def disconnect_sensor(self):
        """ Disconnects from the sensor

        Returns:
            bool: Returns True if disconnection was successful.
        """
        print("Disconnecting from " + self.sensor.name + " sensor...")

        try:
            dwf.FDwfDeviceCloseAll()
            self.printer_connected = False
            print("Disconnected from sensor!")
            print("")
            return True
        except:
            print("Error disconnecting from sensor.")
            print("")
            return False
    
    def generate_signal(self, dwf, hdwf = c_int(), run = 5, amp = 1, freq = 1000, signal_type = funcSine):
        """ Generates signal from wave channel 1
        
        Args:
            dwf: sensor object
            hdwf: sensor pointer
            amp: amplitude of signal to generate
            freq: frequency of signal
            signal_type: type of signal
        Returns:
            bool: Returns True if signal was generated
        """
        run = run/(1e-6)
        dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))
        dwf.FDwfAnalogOutNodeEnableSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_int(1))
        dwf.FDwfAnalogOutNodeFunctionSet(hdwf, c_int(0), AnalogOutNodeCarrier, signal_type)
        dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(515000))  # 515 kHz
        dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(3))    # 2 V peak
        dwf.FDwfAnalogOutNodeOffsetSet(hdwf, c_int(0), c_double(0.0))                              # Base at 0 V
        dwf.FDwfAnalogOutNodeSymmetrySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(20.0))     # 20% duty
        dwf.FDwfAnalogOutRunSet(hdwf, c_int(0), c_double(1e-6))    # Burst duration: 3 pulses ≈ 6 us
        dwf.FDwfAnalogOutWaitSet(hdwf, c_int(0), c_double(0.001))  # Wait 994 µs between bursts
        dwf.FDwfAnalogOutRepeatSet(hdwf, c_int(0), c_int(0))  # 0 = infinite repeat
        dwf.FDwfAnalogOutIdleSet(hdwf, c_int(0), DwfAnalogOutIdleOffset)  # Idle at 0 V between bursts
        dwf.FDwfAnalogOutTriggerSourceSet(hdwf, c_int(0),trigsrcNone)
        dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_int(1))  # Start output
        return True
    
    def initialize_sensor(self, dwf, hdwf = c_int(), amp = c_double(5), freq = c_double(1000), samples = 1000):
        """ Initializes oscilloscope for data collection
        
        Args:
            dwf: sensor object
            hdwf: sensor pointer
            amp: max amp of signal read
            freq: frequency read
            samples: amount of samples expected to read
        Returns:
            dwf: sensor object
            hdwf: sensor pointer
        """
        dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0)) 
        dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(0), c_int(1)) #opens scope
        dwf.FDwfAnalogInChannelRangeSet(hdwf, c_int(0), amp) #sets voltage range
        dwf.FDwfAnalogInAcquisitionModeSet(hdwf, acqmodeRecord) #sets mode (either single trigger or record)
        dwf.FDwfAnalogInFrequencySet(hdwf, freq) #sets frequence in Hz
        dwf.FDwfAnalogInRecordLengthSet(hdwf, c_double(samples/freq.value)) # -1 infinite record length
        dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(0)) #sets scope as closed (if second to last is 1 and last is 0 then closed)
        return dwf, hdwf
    
    def probe(self, home_printer=True, record_signal=True, calibration_file_path=None, data_save_path=None, 
              calibrationMatrix=None, rate=None, samples_per_update = 10, plotxy = True, windowWidth = 200,
              auto_bias = True, apply_filter = True):
        """ Executes the probing procedure on 3D printer

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
            plotxy (bool): Determines whether we want to plot the x and y forces from the sensor
            windowWidth (int): the amount of values shown on the screen when graphing
            auto-bias (bool): Determines whether force data is biased automatically
            
        Returns:
            bool: Returns True when the probing procedure is complete.
        """
        # Connect to 3D printer if not already connected
        if not self.printer_connected:
            self.connect_printer()

        # Connect to sensor
        if record_signal == True:
            dwf, hdwf = self.connect_sensor()

            for i in range(30):
                self.sensor.capture_image()

        # Send initialization gcode to printer
        if home_printer == True:
            self.initialize_printer()

        # If no data path was provided, set default path to a folder called "sensor_calibration_data" in the Downloads folder
        if data_save_path == None:
            data_save_path = str("results/sensordata")
        else:
            data_save_path = os.path.join(data_save_path, "force_values")
    
        #writes the signal data to a csv file in sensordata
        output_dir = Path("results/sensordata")
        output_dir.mkdir(parents=True, exist_ok=True)
        signal_path = output_dir / "waveform_readings.csv"
        signal_file = open(signal_path,'w', newline ='')
        signal_writer = csv.writer(signal_file)
        header = ['Probe #', 'Voltages']
        signal_writer.writerow(header)
        
        # Create folder to save sensor data if it doesn't already exist
        Path(data_save_path).mkdir(parents=True, exist_ok=True)
        # Open a csv file to write calibration data
        csv_file = open(data_save_path + '/sensor_data.csv', 'w', newline='') #'w' means to wipe before each run
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['img_num', 'Fx', 'Fy', 'Fz', 'Tx', 'Ty', 'Tz'])
        
        # If no calibration file path was provided, use the default calibration file for the specified sensor
        if calibration_file_path == None:
            calibration_file_path = self.sensor.default_calibration_file

        # Load CSV file into numpy array
        self.calibration_points = np.genfromtxt(calibration_file_path, delimiter=',', skip_header=1)

        # Get number of rows (i.e. calibration points)
        N = self.calibration_points.shape[0]
        

        # Move to offset Z and XY position
        self.printer.send_gcode("G0  Z" + str(self.sensor.z_offset + self.sensor.z_clearance))
        self.printer.send_gcode("G0 X" + str(self.sensor.x_offset) + " Y" + str(self.sensor.y_offset))
        time.sleep(5)

        print("Attach probe to printer head. ", end="")
        input("Press Enter to continue...")
        print("")
        #declare amount of samples to aquire and how many
        hzAcq = c_double(5000000)
        nSamples = 6000
        
        #declares state variables that are used in each method
        state = {
            "x_prev": self.sensor.x_offset,
            "y_prev": self.sensor.y_offset,
            "z_prev": self.sensor.z_offset + self.sensor.z_clearance,
            "probing_done": False,
            "bias" : np.zeros((6, samples_per_update)),
            "Xbuffer": np.zeros(windowWidth),
            "Ybuffer": np.zeros(windowWidth),
            "Zbuffer": np.zeros(windowWidth),
            "ptr" : 0,
            "all_datax" : [],
            "all_datay" : [],
            "all_dataz" : [],
            "scope_time" : [],
            "scope_data" : [],
            "cAvailable": c_int(),
            "cLost": c_int(),
            "cCorrupted": c_int(),
            "samples": [],
            "probed": False,
            "rgdSamples": (c_double*nSamples)(),
            "image_saved": True,
            "lock": threading.Lock(),
            "threshold":  .015,
            "probeNumber": 0
        }
        if record_signal == True:
            sts = c_byte() #variable to receive states from functions
            rgdSamples = (c_double*nSamples)() #buffer that holds samples when collected

            #checks if device is open
            if hdwf.value == hdwfNone.value:
                szerr = create_string_buffer(512)
                dwf.FDwfGetLastErrorMsg(szerr)
                print(str(szerr.value))
                print("failed to open device")
                quit()
                
            #starts signal generator
            self.generate_signal(dwf, hdwf, 1, 3, 515000, funcPulse)
            #starts oscilloscope
            dwf, hdwf = self.initialize_sensor(dwf, hdwf, c_double(5), hzAcq, nSamples)
            dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))
            cSamples = 0
            
            #applies FIR Frequency filter
            fs = 5_000_000          # Sampling frequency in Hz
            nyq = fs / 2            # Nyquist frequency
            # === Filter Parameters ===
            numtaps = 256           # Number of FIR filter taps
            low_cut = 500_000         # Lower cutoff frequency (Hz)
            high_cut = 520_000       # Upper cutoff frequency (Hz)
            # === FIR Filter Design (Hamming window) ===
            fir_coeff = firwin(
                numtaps,
                [low_cut / nyq, high_cut / nyq],  # Normalized frequencies
                window='blackman',
                pass_zero=False                   # Band-pass filter
            )

            while cSamples < nSamples:
                dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts)) #sets fReadData to true and checks aquisition status (c_int(1))
                if cSamples == 0 and (sts == DwfStateConfig or sts == DwfStatePrefill or sts == DwfStateArmed) : #checks if aquisition started
                    # Acquisition not yet started.
                    continue

                dwf.FDwfAnalogInStatusRecord(hdwf, byref(state["cAvailable"]), byref(state["cLost"]), byref(state["cCorrupted"])) #gets status and available samples of data

                if state["cAvailable"].value==0 : #if no available samples breaks loop
                    continue

                if cSamples+state["cAvailable"].value > nSamples : #checks if more aquired data than buffer size
                    state["cAvailable"] = c_int(nSamples-cSamples)
                
                #collects data and stores in rgdSamples buffer
                dwf.FDwfAnalogInStatusData(hdwf, c_int(0), byref(rgdSamples, sizeof(c_double)*cSamples), state["cAvailable"]) # get channel 1 data
                #dwf.FDwfAnalogInStatusData(hdwf, c_int(1), byref(rgdSamples, sizeof(c_double)*cSamples), cAvailable) # get channel 2 data
                
                #updates how many samples we've collected 
                cSamples += state["cAvailable"].value
            control1 = np.ctypeslib.as_array(rgdSamples)
            controlrow = ["control_0"]
            if apply_filter:
                # Apply filter with zero phase distortion
                control = filtfilt(fir_coeff, 1.0, control1)
            else:
                control = control1
                
            plt.plot(control)
            plt.show()
            state["threshold"] = float(input("Input threshold voltage: "))
            print("")
            peak_indices = [i for i, v in enumerate(control) if v >= state["threshold"]]
            peak_starts = []
            min_spacing = 1000 # samples apart

            for i in peak_indices:
                if not peak_starts or i - peak_starts[-1] >= min_spacing:
                    if i + min_spacing <= len(control):
                        peak_starts.append(i)

            signal_file.flush()
            img_dir = Path("results/sensorimages")
            img_dir.mkdir(parents=True, exist_ok=True)
            base_filename = "control"

            for idx, start_idx in enumerate(peak_starts):
                segment = control[start_idx:start_idx + min_spacing]
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

            signal_writer.writerow(controlrow)  # Save first waveform to CSV

        #builds force window and bias buttons
        app = QtWidgets.QApplication([])
        win = pg.GraphicsLayoutWidget(title="Real-Time Force Data")
        bias_button = QtWidgets.QPushButton("Bias")
        unbias_button = QtWidgets.QPushButton("Unbias")
        proxy1 = QtWidgets.QGraphicsProxyWidget()
        proxy1.setWidget(bias_button)
        proxy2 = QtWidgets.QGraphicsProxyWidget()
        proxy2.setWidget(unbias_button)
        
        #if plotting x and y, adds a plot for each force
        if plotxy == True:
            plotx = win.addPlot()
            curvex = plotx.plot(pen='r')
            ploty = win.addPlot()
            curvey = ploty.plot(pen='y')
            plotz = win.addPlot()
            curvez = plotz.plot(pen='g')
            button_row = 3
        #plots only z force
        else:
            plotz = win.addPlot()
            curvez = plotz.plot(pen='g')
            button_row = 1   
        win.addItem(proxy1, row=button_row, col=0)
        win.addItem(proxy2, row=button_row, col=1)
        #waits 2 seconds to allow scope to open
        time.sleep(2)
        print("Beginning sensor calibration procedure...")
        print("")
        #declares FT sensor task
        with nidaqmx.Task() as task:
            #opens analog channels for FT sensor
            task.ai_channels.add_ai_voltage_chan("Dev1/ai0:5")
            #continously reads FT sensor data at rate
            task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.CONTINUOUS)
            win.show()
            task.start()
            
            #if you want to auto bias, will get bias voltages
            if auto_bias:
                bias_data = task.read(number_of_samples_per_channel=samples_per_update)
                state["bias"] = np.array(bias_data)
                
            #threading task to probe the sensor and move to each location
            def probing():
                # Loop through every calibration point
                    for i in tqdm(range(N), desc="Sensor Calibration Progress"):
                        # If specified penetration depth exceeds maximum value, print message
                        if abs(self.calibration_points[i][2]) > self.sensor.max_penetration:
                            print("Line " + str(i+1) + ": Maximum penetration depth for sensor exceeded. Skipping calibration point.")
                        # If penetration depth does not exceed maximum value, move to calibration point
                        else:
                            state["probeNumber"] += 1
                            # Get absolute XYZ coordinates
                            x = self.sensor.x_offset + self.calibration_points[i][0]
                            y = self.sensor.y_offset + self.calibration_points[i][1]
                            z = self.sensor.z_offset - abs(self.calibration_points[i][2])

                            # Move to Z clearance height
                            self.printer.send_gcode("G0 Z" + str(self.sensor.z_offset + self.sensor.z_clearance))
                            state["probed"] = False
                            # Move to desired XY locations
                            self.printer.send_gcode("G0 X" + str(x) + " Y" + str(y))
                            
                            # Calculate time required to reach position
                            travel_time = abs(self.sensor.z_offset + self.sensor.z_clearance - state["z_prev"]) / 4 + max(abs(x - state["x_prev"]), abs(y - state["y_prev"])) / 10 + abs(z - (self.sensor.z_offset + self.sensor.z_clearance)) / 4
                            if self.calibration_points[i][3] != 0:
                                #if angle, calculate offset to move printer at desired depth at specified angle
                                angledz = self.sensor.z_offset - math.cos(math.radians(self.calibration_points[i][3]))*abs(self.calibration_points[i][2])
                                angledx = x + self.calibration_points[i][2]*math.sin(math.radians(self.calibration_points[i][3]))
                                self.printer.send_gcode("G0 Z" + str(angledz) + " X"+ str(angledx))
                            else:
                                # Move to desired Z penetration
                                self.printer.send_gcode("G0 Z" + str(z))
                                
                            #waits 5 second and opens scope data collection
                            time.sleep(5)
                            if record_signal == True:
                                dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))
                                cSamples = 0

                                while cSamples < nSamples:
                                    dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts)) #sets fReadData to true and checks aquisition status (c_int(1))
                                    if cSamples == 0 and (sts == DwfStateConfig or sts == DwfStatePrefill or sts == DwfStateArmed) : #checks if aquisition started
                                        # Acquisition not yet started.
                                        continue

                                    dwf.FDwfAnalogInStatusRecord(hdwf, byref(state["cAvailable"]), byref(state["cLost"]), byref(state["cCorrupted"])) #gets status and available samples of data

                                    if state["cAvailable"].value==0 : #if no available samples breaks loop
                                        continue

                                    if cSamples+state["cAvailable"].value > nSamples : #checks if more aquired data than buffer size
                                        state["cAvailable"] = c_int(nSamples-cSamples)
                                    
                                    #collects data and stores in rgdSamples buffer
                                    dwf.FDwfAnalogInStatusData(hdwf, c_int(0), byref(rgdSamples, sizeof(c_double)*cSamples), state["cAvailable"]) # get channel 1 data
                                    #dwf.FDwfAnalogInStatusData(hdwf, c_int(1), byref(rgdSamples, sizeof(c_double)*cSamples), cAvailable) # get channel 2 data
                                    
                                    #updates how many samples we've collected 
                                    cSamples += state["cAvailable"].value
                                #converts ctype array to np array
                                state["samples"] = np.ctypeslib.as_array(rgdSamples)
                                if apply_filter:
                                    # Apply filter with zero phase distortion
                                    state["samples"] = lfilter(fir_coeff, 1.0, state["samples"] )
                                    state["scope_data"].append(state["samples"])
                                #appends array to scope data to save for later and sets probed to true to graph data
                                else:
                                    state["scope_data"].append(state["samples"])
                                with state["lock"]:
                                    state["probed"] = True
                                    state["image_saved"] = False
                            time.sleep(travel_time)

                            # Update variables
                            state["x_prev"] = x
                            state["y_prev"] = y
                            state["z_prev"] = z
                
                    #checks when probing is done
                    state["probing_done"] = True
        
    #update function for animation
            def update():
                try:
                    #checks if probing is done
                    if state["probing_done"]:
                        # Move to Z clearance height    
                        self.printer.send_gcode("G0 Z" + str(self.sensor.z_offset + self.sensor.z_clearance))
                        #when probing is done, stops reading from DAQ and timer
                        time.sleep(0.1)
                        task.stop()
                        timer.stop()
                        print("Stopped DAQ. You can now pan/zoom in the plot.")
                        
                        #if plotting x and y, removes previous plot and replaces with plot with full data (doesn't work rn)
                        if plotxy:
                            win.removeItem(plotz)
                            win.removeItem(proxy1)
                            win.removeItem(proxy2)
                            plotfinalx = win.addPlot()
                            plotfinaly = win.addPlot()
                            plotfinalz = win.addPlot()
                            curvefinalx = plotfinalx.plot(pen='r')
                            curvefinalx.setData(state["all_datax"])
                            plotfinalx.setRange(xRange=[0, len(state["all_datax"])], padding=0)
                            curvefinaly = plotfinaly.plot(pen='y')
                            curvefinaly.setData(state["all_datay"])
                            plotfinaly.setRange(xRange=[0, len(state["all_datay"])], padding=0)
                            curvefinalz = plotfinalz.plot(pen='g')
                            curvefinalz.setData(state["all_dataz"])
                            plotfinalz.setRange(xRange=[0, len(state["all_dataz"])], padding=0)
                            
                        #Removes previous live plot and replaces with plot with full data for analysis
                        else:
                            if record_signal == True:
                            #writes oscilloscope to csv file waveform_readings with each probe labeled with voltage values
                                row = []
                                dwf.FDwfDeviceCloseAll()

                                # for i in range(len(state["scope_data"])):
                                #     start_idx = next((i for i, v in enumerate(state["scope_data"][i]) if v >= 0.1), None)
                                #     if start_idx is not None and start_idx + 800 <= len(state["scope_data"][i]):
                                #         row.clear()
                                #         row.append(i+1)
                                #         usabledata = state["scope_data"][i][start_idx:start_idx + 800]
                                #         for j in range(len(usabledata)):
                                #             row.append(usabledata[j])
                                #         signal_writer.writerow(row)
                            #plots final force data
                            x_vals = np.arange(len(state["all_dataz"]))
                            #ensures all csv data is written
                            signal_file.flush()
                            csv_file.flush()
                            # Close csv file
                            csv_file.close()
                            signal_file.close()
                            win.removeItem(plotz)
                            win.removeItem(proxy1)
                            win.removeItem(proxy2)
                            plotfinal = win.addPlot()
                            curvefinal = plotfinal.plot(pen='g')
                            curvefinal.setData(x_vals, state["all_dataz"])
                            plotfinal.setRange(xRange=[0, len(state["all_dataz"])], padding=0)

                    #after collected probed data, graphs data and stores to sensorimages folder with corresponding probe #        
                    with state["lock"]:
                        if state["probed"] and not state["image_saved"]:
                                try:
                                    plt.close()
                                    samples = state["samples"]
                                    row = [state["probeNumber"]]

                                    # Find all indices above threshold
                                    peak_indices = [i for i, v in enumerate(samples) if v >= state["threshold"]]

                                    # Select peak starts spaced apart to avoid overlapping
                                    peak_starts = []
                                    min_spacing = 1000  # samples apart

                                    for i in peak_indices:
                                        if not peak_starts or i - peak_starts[-1] >= min_spacing:
                                            if i + min_spacing <= len(samples):
                                                peak_starts.append(i)

                                    signal_file.flush()
                                    img_dir = Path("results/sensorimages")
                                    img_dir.mkdir(parents=True, exist_ok=True)
                                    probe_id = state["probeNumber"]
                                    x, y = self.calibration_points[probe_id - 1][0], self.calibration_points[probe_id - 1][1]
                                    base_filename = f"waveform{probe_id}-{x}-{y}"

                                    for idx, start_idx in enumerate(peak_starts):
                                        segment = state["samples"][start_idx:start_idx + min_spacing]
                                        if idx == 0:
                                            row.extend(segment)
                                        else:
                                            signal_writer.writerow([f"{probe_id}_{idx}"] + list(segment))
                                        plt.figure()
                                        plt.plot(segment)
                                        plt.xlabel("Time (microseconds)")
                                        plt.ylabel("Voltage (V)")
                                        plt.title(f"Waveform Capture #{probe_id} Segment {idx + 1}")
                                        plt.xlim(0, min_spacing)             # Always show 1000 samples on x-axis
                                        plt.ylim(-0.05, 0.05)
                                        plt.grid(True)
                                        filename = f"{base_filename}.png" if idx == 0 else f"{base_filename}_{idx}.png"
                                        plt.savefig(img_dir / filename)
                                        plt.close()

                                    signal_writer.writerow(row)  # Save first waveform to CSV
                                    state["image_saved"] = True

                                except Exception as e:
                                    print(f"Image save failed: {e}")
                        else:
                            plt.close()
                        
                    #Read new samples: shape (6s, N) {N = sample size}
                    data = task.read(number_of_samples_per_channel=samples_per_update)
                    data_np = np.array(data)
                    # Apply bias voltages if there are any. (literally just reads voltages and subtracts them to make them closer to zero when no force)
                    voltages = data_np - state["bias"]
                    # Apply calibration matrix
                    FT_final = calibrationMatrix @ voltages  # shape (6, N)
                    
                    #stores new force data
                    if plotxy:
                        #plots for x
                        valuex = np.mean(FT_final[0, :])
                        state["all_datax"].append(valuex)
                        state["Xbuffer"][:-1] = state["Xbuffer"][1:]
                        state["Xbuffer"][-1] = valuex
                        curvex.setData(state["Xbuffer"])
                        curvex.setPos(state["ptr"] - windowWidth, 0)
                        #plots for y
                        valuey = np.mean(FT_final[1, :])
                        state["all_datay"].append(valuey)
                        state["Ybuffer"][:-1] = state["Ybuffer"][1:]
                        state["Ybuffer"][-1] = valuey
                        curvey.setData(state["Ybuffer"])
                        curvey.setPos(state["ptr"] - windowWidth, 0)
                        #plots for z
                        valuez = np.mean(FT_final[2, :])
                        state["all_dataz"].append(valuez)
                        state["Zbuffer"][:-1] = state["Zbuffer"][1:]
                        state["Zbuffer"][-1] = valuez
                        state["ptr"] += 1
                        curvez.setData(state["Zbuffer"])
                        curvez.setPos(state["ptr"] - windowWidth, 0)
                        
                    else:
                        #only plots for z
                        valuez = np.mean(FT_final[2, :])
                        state["all_dataz"].append(valuez)
                        state["Zbuffer"][:-1] = state["Zbuffer"][1:]
                        state["Zbuffer"][-1] = valuez
                        state["ptr"] += 1
                        curvez.setData(state["Zbuffer"])
                        curvez.setPos((state["ptr"] - windowWidth), 0)
                    #write to csv file
                    csv_writer.writerow([(state["ptr"]/rate)*samples_per_update, FT_final[0][0], FT_final[1][0], FT_final[2][0], FT_final[3][0], FT_final[4][0], FT_final[5][0]])

                except Exception as e:
                    print(e)
                    return
            #threaded scope task that reads the data from the Nscope and plots in CSV file   
            #def scope():
                #gets time when scope starts
                #scope_start = time.perf_counter()
                #opens nlab data reading
                #nlab = LabBench.open_first_available()
                #nlab.ax_turn_on(1)
                #nlab.ax_set_amplitude(1, 5)
                #nlab.ax_set_frequency(1,10)
                #nlab.ax_set_polarity(1, AnalogSignalPolarity.Unipolar)
                #number_of_samples = 10    
                #sample_rate = 1000000   # Hz
                #reads data and stores in csv and seperate variables to graph
                #try:
                    #while not state["probing_done"]:
                        #data = nlab.read_all_channels(sample_rate, number_of_samples)

                        #for i in range(number_of_samples):
                #             state["scope_time"].append(time.perf_counter() - scope_start)
                #             state["scope_data"].append(data[1][i])
                #             row = [time.perf_counter() - scope_start] + [data[2][i]]
                #             signal_writer.writerow(row)
                #         signal_file.flush()
                #         os.fsync(signal_file.fileno())  


                # except Exception as e:
                #     print("Error in scope thread:", e)

                # finally:
                #     nlab.ax_turn_off(1)
                    
            #biases data
            def bias():
                bias_data = task.read(number_of_samples_per_channel=samples_per_update)
                state["bias"] = np.array(bias_data)
            #unbiases data
            
            def unbias():
                state["bias"] = np.zeros((6, samples_per_update))        
                         
            bias_button.clicked.connect(bias)
            unbias_button.clicked.connect(unbias)
            
            #starts probing thread
            thread = threading.Thread(target=probing)
            thread.start()

            #starts scope thread for nscope
            #scopethread = threading.Thread(target=scope)
            #scopethread.start()
            #starts animation
            timer = QtCore.QTimer()
            timer.timeout.connect(update)
            timer.start(int(samples_per_update / rate))
            QtWidgets.QApplication.instance().exec()
    
            
            # Move to Z clearance height    
            self.printer.send_gcode("G0 Z" + str(self.sensor.z_offset + self.sensor.z_clearance))

            print("")
            task.stop()
        
        # Disconnect from 3D printer
        self.disconnect_printer()

        # Disconnect from sensor
        if record_signal == True:
            self.disconnect_sensor()

        print("Sensor calibration procedure complete!")
        print("")

        return True
    
    def jog_mode(self):
        """ Jogs the print head of the 3D printer. Default jog unit is 1 mm.

        Inputs:
            RIGHT ARROW: Moves in the +X direction
            LEFT ARROW: Moves in the -X direction
            UP ARROW: Moves in the +Y direction
            DOWN ARROW: Moves in the -Y direction
            W: Moves in the +Z direction
            S: ARROW: Moves in the -Z direction
            P: Sets jog increment to 0.1 mm
            M: Sets jog increment to 1 mm
        """
        self.initialize_printer(absolute=False)
        Joystick(self.printer.send_gcode)
        arcade.run()