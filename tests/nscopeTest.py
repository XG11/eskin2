import matplotlib.pyplot as plt
import numpy as np
from nlabapi import LabBench, AnalogSignalPolarity
from pathlib import Path
import csv
import os

# Initialize nLab
nlab = LabBench.open_first_available()

# Create output directory
output_dir = Path(r"C:\Users\jrlin\Documents\nScope_captures")
output_dir.mkdir(parents=True, exist_ok=True)

# Output file path
csv_path = output_dir / "waveform_readings.csv"

# Start signal generation
nlab.ax_turn_on(1)
nlab.ax_set_amplitude(1, 5)
nlab.ax_set_polarity(1, AnalogSignalPolarity.Bipolar)

# Sampling parameters
number_of_samples = 10
sample_rate = 5000.0  # Hz

# Read data
data = nlab.read_all_channels(sample_rate, number_of_samples)  # data shape: (channels, samples)
nlab.ax_turn_off(1)

# Generate time array
time = np.arange(number_of_samples) / sample_rate
print(data)
# Write data to CSV
with open(csv_path, 'w', newline='') as csv_file:
    csv_writer = csv.writer(csv_file)
    # Write header
    header = ['Time (s)', 'Ch1', 'Ch2', 'Ch3', 'Ch4']
    csv_writer.writerow(header)

    # Write each sample row
    for i in range(number_of_samples):
        row = [time[i]] + [data[ch][i] for ch in range(len(data))]
        csv_writer.writerow(row)

print(f"Data written to {csv_path}")

# Plot data
for ch in range(len(data)):
    plt.plot(time, data[ch], label=f"Ch{ch+1}")

plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.legend()
plt.title("nScope Waveform Capture")
plt.grid(True)
plt.show()
