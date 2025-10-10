"""
   DWF Python Example
   Author:  Digilent, Inc.
   Revision:  2018-07-19

   Requires:                       
       Python 2.7, 3
"""

from ctypes import *
from dwfconstants import *
import math
import time
import matplotlib.pyplot as plt
import sys
import numpy
from scipy.signal import butter, filtfilt, savgol_filter, firwin,lfilter
import numpy as np

if sys.platform.startswith("win"):
    dwf = cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

#declare ctype variables
hdwf = c_int()
sts = c_byte()
hzAcq = c_double(5000000)
nSamples = 5000
rgdSamples = (c_double*nSamples)()
cAvailable = c_int()
cLost = c_int()
cCorrupted = c_int()
fLost = 0
fCorrupted = 0

#print(DWF version
version = create_string_buffer(16)
dwf.FDwfGetVersion(version)
print("DWF Version: "+str(version.value))

#open device
print("Opening first device")
dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

if hdwf.value == hdwfNone.value:
    szerr = create_string_buffer(512)
    dwf.FDwfGetLastErrorMsg(szerr)
    print(str(szerr.value))
    print("failed to open device")
    quit()

dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(0)) # 0 = the device will only be configured when FDwf###Configure is called

print("Generating wave...")
dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))
dwf.FDwfAnalogOutNodeEnableSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_int(1))
dwf.FDwfAnalogOutNodeFunctionSet(hdwf, c_int(0), AnalogOutNodeCarrier, funcPulse)
dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(515000))  # 515 kHz
dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(3.0))    # 2 V peak
dwf.FDwfAnalogOutNodeOffsetSet(hdwf, c_int(0), c_double(0.0))                              # Base at 0 V
dwf.FDwfAnalogOutNodeSymmetrySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(20.0))     # 20% duty
dwf.FDwfAnalogOutRunSet(hdwf, c_int(0), c_double(1e-6))    # Burst duration: 3 pulses ≈ 6 us
dwf.FDwfAnalogOutWaitSet(hdwf, c_int(0), c_double(0.001))  # Wait 994 µs between bursts
dwf.FDwfAnalogOutRepeatSet(hdwf, c_int(0), c_int(0))  # 0 = infinite repeat
dwf.FDwfAnalogOutIdleSet(hdwf, c_int(0), DwfAnalogOutIdleOffset)  # Idle at 0 V between bursts
dwf.FDwfAnalogOutTriggerSourceSet(hdwf, c_int(0),trigsrcNone)
dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_int(1))  # Start output


#set up acquisition
dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(0), c_int(1))
dwf.FDwfAnalogInChannelRangeSet(hdwf, c_int(0), c_double(5))
dwf.FDwfAnalogInAcquisitionModeSet(hdwf, acqmodeRecord)
dwf.FDwfAnalogInFrequencySet(hdwf, hzAcq)
dwf.FDwfAnalogInRecordLengthSet(hdwf, c_double(nSamples/hzAcq.value)) # -1 infinite record length
dwf.FDwfAnalogInChannelFilterSet(hdwf, c_int(0), filterAverage)

dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(0))
#wait at least 2 seconds for the offset to stabilize
time.sleep(2)

print("Starting oscilloscope")
dwf.FDwfAnalogInConfigure(hdwf, c_int(0), c_int(1))
cSamples = 0

while cSamples < nSamples:
    dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts))
    if cSamples == 0 and (sts == DwfStateConfig or sts == DwfStatePrefill or sts == DwfStateArmed) :
        # Acquisition not yet started.
        continue

    dwf.FDwfAnalogInStatusRecord(hdwf, byref(cAvailable), byref(cLost), byref(cCorrupted))
    
    cSamples += cLost.value

    if cLost.value :
        fLost = 1
    if cCorrupted.value :
        fCorrupted = 1

    if cAvailable.value==0 :
        continue

    if cSamples+cAvailable.value > nSamples :
        cAvailable = c_int(nSamples-cSamples)
    
    dwf.FDwfAnalogInStatusData(hdwf, c_int(0), byref(rgdSamples, sizeof(c_double)*cSamples), cAvailable) # get channel 1 data
    #dwf.FDwfAnalogInStatusData(hdwf, c_int(1), byref(rgdSamples, sizeof(c_double)*cSamples), cAvailable) # get channel 2 data
    cSamples += cAvailable.value

dwf.FDwfAnalogOutReset(hdwf, c_int(0))
dwf.FDwfDeviceCloseAll()
samples = np.ctypeslib.as_array(rgdSamples)


# Design Butterworth bandpass filter
fs = 5_000_000          # Sampling frequency in Hz
nyq = fs / 2            # Nyquist frequency

# === Filter Parameters ===
numtaps = 128           # Number of FIR filter taps
low_cut = 490e3         # Lower cutoff frequency (Hz)
high_cut = 540e3        # Upper cutoff frequency (Hz)
order = 8
numtaps = 256           # Number of FIR filter taps
low_cut = 490_000         # Lower cutoff frequency (Hz)
high_cut = 540_000       # Upper cutoff frequency (Hz)
# === FIR Filter Design (Hamming window) ===
b, a = butter(order, [low_cut, high_cut], btype='bandpass', fs=fs)

# === FIR Filter Design (Hamming window) ===

filtered = filtfilt(b, a, samples)

print("Recording done")
if fLost:
    print("Samples were lost! Reduce frequency")
if fCorrupted:
    print("Samples could be corrupted! Reduce frequency")

f = open("record.csv", "w")
for v in rgdSamples:
    f.write("%s\n" % v)
f.close()
  
plt.plot(filtered)
plt.show()


