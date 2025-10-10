from tactile_calibration import Sensor
import numpy as np
import sys
import dwf
from dwfconstants import *

class AnalogD2(Sensor):
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
        self.name = "AnalogD2"
        
    def connect(self):
        #sensor connection 
        print("Connecting to " + self.name + " sensor...")
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

        
    def disconnect(self):
        """ Disconnects from the sensor

        Returns:
            bool: Returns True if disconnection was successful.
        """
        print("Disconnecting from " + self.name + " sensor...")

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
        
    def generate_signal(self, dwf, hdwf = c_int(), run = 5, amp = 3, freq = 515000, signal_type = funcPulse):
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
        dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(freq))  # 515 kHz
        dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(amp))    # 3 V peak
        dwf.FDwfAnalogOutNodeOffsetSet(hdwf, c_int(0), c_double(0.0))                              # Base at 0 V
        dwf.FDwfAnalogOutNodeSymmetrySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(20.0))     # 20% duty
        dwf.FDwfAnalogOutRunSet(hdwf, c_int(0), c_double(1e-6))    # Burst duration: 3 pulses ≈ 6 us
        dwf.FDwfAnalogOutWaitSet(hdwf, c_int(0), c_double(0.001))  # Wait 994 µs between bursts
        dwf.FDwfAnalogOutRepeatSet(hdwf, c_int(0), c_int(0))  # 0 = infinite repeat
        dwf.FDwfAnalogOutIdleSet(hdwf, c_int(0), DwfAnalogOutIdleOffset)  # Idle at 0 V between bursts
        dwf.FDwfAnalogOutTriggerSourceSet(hdwf, c_int(0),trigsrcNone)
        dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_int(1))  # Start output
        return True

    def initialize_oscilloscope(self, dwf, hdwf = c_int(), amp = c_double(5), freq = c_double(1000), samples = 1000):
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
    
    def capture_image(self, hdwf, nSamples):
        if hdwf.value == hdwfNone.value:
                szerr = create_string_buffer(512)
                dwf.FDwfGetLastErrorMsg(szerr)
                print(str(szerr.value))
                print("failed to open device")
                quit()
        dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))
        cSamples = 0
        rgdSamples = np.zeros(nSamples, dtype=np.float64)

        while cSamples < nSamples:
            # update acquisition status, returns a DwfState
            sts = dwf.FDwfAnalogInStatus(hdwf, 1)

            # wait until acquisition has actually started
            if cSamples == 0 and sts in (
                dwf.DwfStateConfig,
                dwf.DwfStatePrefill,
                dwf.DwfStateArmed,
            ):
                continue

            # query number of samples available
            cAvailable, cLost, cCorrupted = dwf.FDwfAnalogInStatusRecord(hdwf)

            if cAvailable <= 0:
                continue

            # don’t overrun buffer
            if cSamples + cAvailable > nSamples:
                cAvailable = nSamples - cSamples

            # read available samples into numpy slice
            data = dwf.FDwfAnalogInStatusData(hdwf, 0, cAvailable)

            cSamples += cAvailable

        return data
