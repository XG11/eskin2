"""
Combined FSR (serial) + 6-axis FT (NI-DAQ) continuous reader

Usage examples:
  # Live plot (GUI)
  python tests/fsr_ft_continuous.py --mode plot --fsr-port COM26 --daq Dev1 --rate 1000

  # Console summary output
  python tests/fsr_ft_continuous.py --mode console --fsr-port COM26 --daq Dev1 --rate 1000

  # Save to CSV for 10s
  python tests/fsr_ft_continuous.py --mode save --duration 10 --output combined.csv

Notes:
- FSR uses the project's `FSRStreamSensor` (serial stream) and defaults to 115200 baud.
- 6-axis FT is read via `nidaqmx` (AI channels: Dev?/ai0:5). Adjust `--daq-ch` if needed.
"""

import sys
import time
from pathlib import Path
import argparse
import numpy as np

# FT calibration matrix (same as Main.py)
calibrationMatrix = np.array([
    [0.184843525290, -5.820387363434, -0.092974022031, 6.097970962624, -0.003208260983, -0.016541913152],
    [0.068360798061, -3.361389636993, 0.091561593115, -3.464745521545, -0.085913859308, -0.085913859308],
    [-10.499620437622, 0.371050596237, -10.746155738831, 0.277591109276, -10.430329322815, -0.058893989772],
    [-0.148816883564, -0.013231880032, 0.153296604753, -0.021977346390, -0.002836260983, 0.036689631641],
    [-0.085635080934, 0.034371923655, -0.084928609431, -0.030927008018, 0.170041531324, 0.001250812435],
    [-0.003102704883, 0.081076353788, -0.002182871802, 0.083423130214, -0.001354880980, 0.083512537181]
], dtype=float)

# ensure repo imports work
sys.path.insert(0, str(Path(__file__).parent.parent))
import tactile_calibration as tc

# Instantiate FT sensor for configuration (like Main.py)
ft_sensor = tc.FTSensor()

try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType
except Exception:
    nidaqmx = None

try:
    from pyqtgraph.Qt import QtWidgets, QtCore
    import pyqtgraph as pg
except Exception:
    QtWidgets = None
    pg = None


def combined_live_plot(fsr_port: str = "COM26", fsr_baud: int = 115200,
                       daq_device: str = "Dev1", daq_ch: str = "Dev1/ai0:5",
                       rate: float = 1000.0, samples_per_update: int = 10,
                       fsr_buffer: int = 500, invert_fsr: bool = False,
                       auto_bias: bool = True,
                       title: str = "FSR + FT Live Plot"):
    if nidaqmx is None:
        raise RuntimeError("nidaqmx not installed; install nidaqmx to use DAQ features")
    if pg is None or QtWidgets is None:
        raise RuntimeError("pyqtgraph or PyQt not installed; install them for live plotting")

    # Create and connect sensors
    fsr = tc.FSRStreamSensor(port=fsr_port, baud=fsr_baud, buffer_size=fsr_buffer)
    if not fsr.connect():
        raise RuntimeError(f"Could not connect to FSR on {fsr_port} at {fsr_baud}")
    fsr.initialize_stream(buffer_size=fsr_buffer)
    fsr.start_logging()

    # NI-DAQ task
    task = nidaqmx.Task()
    task.ai_channels.add_ai_voltage_chan(daq_ch)
    task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.CONTINUOUS)
    task.start()

    # optional auto-bias on FT channels
    bias = np.zeros((6, samples_per_update), dtype=float)
    if auto_bias:
        try:
            bias_data = task.read(number_of_samples_per_channel=samples_per_update)
            bias_np = np.array(bias_data)
            if bias_np.ndim == 2 and bias_np.shape[0] == 6:
                bias = bias_np
            elif bias_np.ndim == 2 and bias_np.shape[1] == 6:
                bias = bias_np.T
        except Exception:
            bias = np.zeros((6, samples_per_update), dtype=float)

    # Build GUI
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = pg.GraphicsLayoutWidget(title=title)

    # FT plot (top) - show only Z force like Calibrator.py
    plot_ft = win.addPlot(row=0, col=0)
    plot_ft.setLabel('left', 'Force Z (arb)')
    plot_ft.setLabel('bottom', 'Samples')
    plot_ft.showGrid(x=True, y=True, alpha=0.3)
    plot_ft.setYRange(-2.0, 2.0)
    curve_ft_z = plot_ft.plot(pen='g')

    # FSR plot (bottom)
    plot_fsr = win.addPlot(row=1, col=0)
    plot_fsr.setLabel('left', 'A0 ADC Value')
    plot_fsr.setLabel('bottom', 'Samples (rolling buffer)')
    plot_fsr.showGrid(x=True, y=True, alpha=0.3)
    plot_fsr.setYRange(0, 1200)
    fsr_curve = plot_fsr.plot(pen='y')

    fsr_buf = np.zeros(fsr_buffer, dtype=np.int16)
    ft_z_buf = np.zeros(fsr_buffer, dtype=float)  # rolling buffer for Z force

    ptr = 0

    def update():
        nonlocal ptr, fsr_buf, ft_z_buf
        # Read FT samples
        try:
            data = task.read(number_of_samples_per_channel=samples_per_update)
            data_np = np.array(data)
            if data_np.ndim == 2 and data_np.shape[0] == 6:
                ft_data = calibrationMatrix @ (data_np - bias)
            elif data_np.ndim == 2 and data_np.shape[1] == 6:
                ft_data = calibrationMatrix @ (data_np.T - bias)
            else:
                ft_data = np.zeros((6, samples_per_update), dtype=float)
        except Exception:
            ft_data = np.zeros((6, samples_per_update), dtype=float)

        # Update FT Z-force curve (only channel 2, like Calibrator.py)
        if ft_data.shape[1] > 0:
            valuez = np.mean(ft_data[2, :])
            ft_z_buf[:-1] = ft_z_buf[1:]
            ft_z_buf[-1] = valuez
        curve_ft_z.setData(ft_z_buf)

        # Read FSR buffer and plot rolling window
        y_fsr = fsr.get_buffer()
        if y_fsr.size > 0:
            if invert_fsr:
                y_plot = 1023 - y_fsr
            else:
                y_plot = y_fsr
            # pad or clip to fsr_buffer
            if y_plot.size < fsr_buffer:
                pad = np.full(fsr_buffer - y_plot.size, y_plot[0] if y_plot.size else 0, dtype=np.int16)
                y_plot_full = np.concatenate([pad, y_plot])
            else:
                y_plot_full = y_plot[-fsr_buffer:]
            fsr_curve.setData(y_plot_full)

        ptr += 1

    timer = QtCore.QTimer()
    timer.timeout.connect(update)
    ms = int(max(1, round(1000.0 * samples_per_update / max(1.0, rate))))
    timer.start(ms)

    win.show()
    app.exec_()

    # cleanup
    timer.stop()
    task.stop()
    task.close()
    fsr.stop_logging()
    fsr.disconnect()


def combined_console(fsr_port: str = "COM26", fsr_baud: int = 115200,
                     daq_ch: str = "Dev1/ai0:5", daq_device: str = "Dev1",
                     rate: float = 1000.0, samples_per_update: int = 10,
                     fsr_buffer: int = 200, update_interval: float = 0.2,
                     invert_fsr: bool = True, auto_bias: bool = True,
                     duration_s: float = None):
    if nidaqmx is None:
        raise RuntimeError("nidaqmx not installed; install nidaqmx to use DAQ features")

    fsr = tc.FSRStreamSensor(port=fsr_port, baud=fsr_baud, buffer_size=fsr_buffer)
    if not fsr.connect():
        raise RuntimeError("Could not connect to FSR sensor")
    fsr.initialize_stream(buffer_size=fsr_buffer)
    fsr.start_logging()

    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(daq_ch)
        task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.CONTINUOUS)
        task.start()

        bias = np.zeros((6, samples_per_update), dtype=float)
        if auto_bias:
            try:
                bias_data = task.read(number_of_samples_per_channel=samples_per_update)
                bias_np = np.array(bias_data)
                if bias_np.ndim == 2 and bias_np.shape[0] == 6:
                    bias = bias_np
                elif bias_np.ndim == 2 and bias_np.shape[1] == 6:
                    bias = bias_np.T
            except Exception:
                bias = np.zeros((6, samples_per_update), dtype=float)

        print(f"Time(s)   FT_Z       FSR_min FSR_max FSR_mean")
        start = time.time()
        try:
            while True:
                if duration_s is not None and (time.time() - start) >= duration_s:
                    break
                # read DAQ and apply calibration matrix with bias subtraction
                data = task.read(number_of_samples_per_channel=samples_per_update)
                data_np = np.array(data)
                if data_np.ndim == 2 and data_np.shape[0] == 6:
                    ft_data = calibrationMatrix @ (data_np - bias)
                elif data_np.ndim == 2 and data_np.shape[1] == 6:
                    ft_data = calibrationMatrix @ (data_np.T - bias)
                else:
                    ft_data = np.zeros((6, samples_per_update), dtype=float)

                ft_last = ft_data[:, 0] if ft_data.shape[1] > 0 else np.zeros(6, dtype=float)
                y = fsr.get_buffer()
                if y.size:
                    vals = 1023 - y if invert_fsr else y
                    print(f"{time.time()-start:6.2f}  {ft_last[2]:.6f}  {vals.min():4d} {vals.max():4d} {vals.mean():.1f}")
                else:
                    print(f"{time.time()-start:6.2f}  {ft_last[2]:.6f}  no_fsr")
                time.sleep(update_interval)
        except KeyboardInterrupt:
            print("Interrupted by user")
        finally:
            fsr.stop_logging()
            fsr.disconnect()
            task.stop()


def combined_save(fsr_port: str = "COM26", fsr_baud: int = 115200,
                  daq_ch: str = "Dev1/ai0:5", rate: float = 1000.0,
                  samples_per_update: int = 10, fsr_buffer: int = 500,
                  duration_s: float = 10.0,
                  output_file: str = "combined_fsr_ft.csv", invert_fsr: bool = True,
                  auto_bias: bool = True):
    if nidaqmx is None:
        raise RuntimeError("nidaqmx not installed; install nidaqmx to use DAQ features")

    fsr = tc.FSRStreamSensor(port=fsr_port, baud=fsr_baud, buffer_size=fsr_buffer)
    if not fsr.connect():
        raise RuntimeError("Could not connect to FSR sensor")
    fsr.initialize_stream(buffer_size=fsr_buffer)
    fsr.start_logging()

    out_path = Path(__file__).parent.parent / "results" / "sensordata" / output_file
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(daq_ch)
        task.timing.cfg_samp_clk_timing(rate, sample_mode=AcquisitionType.CONTINUOUS)
        task.start()

        bias = np.zeros((6, samples_per_update), dtype=float)
        if auto_bias:
            try:
                bias_data = task.read(number_of_samples_per_channel=samples_per_update)
                bias_np = np.array(bias_data)
                if bias_np.ndim == 2 and bias_np.shape[0] == 6:
                    bias = bias_np
                elif bias_np.ndim == 2 and bias_np.shape[1] == 6:
                    bias = bias_np.T
            except Exception:
                bias = np.zeros((6, samples_per_update), dtype=float)

        start = time.time()
        records = []
        try:
            while (time.time() - start) < duration_s:
                data = task.read(number_of_samples_per_channel=samples_per_update)
                data_np = np.array(data)
                if data_np.ndim == 2 and data_np.shape[0] == 6:
                    ft_data = calibrationMatrix @ (data_np - bias)
                elif data_np.ndim == 2 and data_np.shape[1] == 6:
                    ft_data = calibrationMatrix @ (data_np.T - bias)
                else:
                    ft_data = np.zeros((6, samples_per_update), dtype=float)
                ts = time.time() - start
                # copy FSR log so far
                ts_fsr, vals_fsr = fsr.get_log_with_time()
                if invert_fsr:
                    vals_fsr = 1023 - vals_fsr
                # store one record per block, using first calibrated sample like Main.py
                first_sample = ft_data[:, 0].tolist() if ft_data.shape[1] > 0 else [0.0] * 6
                records.append((ts, first_sample, vals_fsr.tolist()))
                time.sleep(max(0.0, samples_per_update / rate))
        except KeyboardInterrupt:
            pass
        finally:
            # write CSV: columns -> time, FT ch0..ch5 (first sample), FSR samples (as semi-colon list)
            import csv
            with open(out_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["time_s", "FT_Fx", "FT_Fy", "FT_Fz", "FT_Tx", "FT_Ty", "FT_Tz", "FSR_samples"])
                for rec in records:
                    ts, ft_block, fsr_vals = rec
                    writer.writerow([f"{ts:.6f}"] + [f"{float(ft_block[ch]):.6f}" for ch in range(min(6, len(ft_block)))] + [";".join(map(str, fsr_vals))])

            fsr.stop_logging()
            fsr.disconnect()
            task.stop()

    print(f"Saved data to: {out_path}")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description="Combined FSR + FT continuous reader")
    p.add_argument('--mode', choices=['plot','console','save'], default='plot')
    p.add_argument('--fsr-port', default='COM26')
    p.add_argument('--fsr-baud', type=int, default=115200)
    p.add_argument('--daq', default='Dev1')
    p.add_argument('--daq-ch', default='Dev1/ai0:5')
    p.add_argument('--rate', type=float, default= 3000)
    p.add_argument('--samples', type=int, default=500)
    p.add_argument('--buffer', type=int, default=500)
    p.add_argument('--invert', action='store_false')
    p.add_argument('--duration', type=float, default=10.0)
    p.add_argument('--output', type=str, default='combined_fsr_ft.csv')
    args = p.parse_args()

    if args.mode == 'plot':
        combined_live_plot(fsr_port=args.fsr_port, fsr_baud=args.fsr_baud,
                           daq_device=args.daq, daq_ch=args.daq_ch,
                           rate=args.rate, samples_per_update=args.samples,
                           fsr_buffer=args.buffer, invert_fsr=args.invert)
    elif args.mode == 'console':
        combined_console(fsr_port=args.fsr_port, fsr_baud=args.fsr_baud,
                         daq_ch=args.daq_ch, daq_device=args.daq,
                         rate=args.rate, samples_per_update=args.samples,
                         fsr_buffer=args.buffer,
                         update_interval=max(0.01, args.samples/args.rate),
                         duration_s=args.duration, invert_fsr=args.invert)
    elif args.mode == 'save':
        combined_save(fsr_port=args.fsr_port, fsr_baud=args.fsr_baud,
                      daq_ch=args.daq_ch, rate=args.rate,
                      samples_per_update=args.samples, fsr_buffer=args.buffer,
                      duration_s=args.duration,
                      output_file=args.output, invert_fsr=args.invert)
