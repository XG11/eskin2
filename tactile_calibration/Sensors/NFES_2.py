
from typing import Optional, Tuple, Deque
from collections import deque
import threading
import time
import numpy as np
import matplotlib.pyplot as plt

try:
    import serial  # pyserial at runtime
except Exception:
    serial = None  # lazy-checked

try:
    # If your project defines a Sensor base (as in AnalogD2.py), import it.
    from tactile_calibration import Sensor  # type: ignore
except Exception:
    class Sensor:  # fallback base, keeps this file standalone
        def __init__(self):
            self.name = "Sensor"


class FSRStreamSensor(Sensor):
    """
    Serial-stream sensor refactor that follows the structure of AnalogD2.py:
    connect(), disconnect(), initialize_stream(), capture_window(), get_stats().
    Adds plot_live() for interactive visualization and save_window_image() to export PNGs.
    """

    def __init__(self, port: str = "COM6", baud: int = 115200, buffer_size: int = 200):
        super().__init__()
        self.name = "FSRStreamSensor"
        self.port = port
        self.baud = baud
        self.buffer_size = int(buffer_size)

        # Rolling buffers (values and timestamps for time-based slicing)
        self._buf: Deque[int] = deque([0] * self.buffer_size, maxlen=self.buffer_size)
        self._ts: Deque[float] = deque([time.time()] * self.buffer_size, maxlen=self.buffer_size)

        # Concurrency / connection state
        self._lock = threading.Lock()
        self._alive = False
        self._thread: Optional[threading.Thread] = None
        self._ser = None  # type: ignore

        # Diagnostics
        self._total_reads = 0
        self._failed_reads = 0
        self._reconnections = 0

        # Policy
        self._max_connect_attempts = 5
        self._read_timeout_s = 0.1
        self._inter_byte_timeout_s = 0.05

    # ---- Lifecycle ---------------------------------------------------------
    def connect(self) -> bool:
        """Establish the serial connection and start the reader thread."""
        if self._alive:
            return True
        self._alive = True
        ok = self._connect_once_or_retry()
        if not ok:
            self._alive = False
            return False

        # Start read loop
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def disconnect(self) -> bool:
        """Stop the reader thread and close the serial connection."""
        self._alive = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

        return True

    # ---- API mirroring AnalogD2-style entry points ------------------------
    def initialize_stream(self, buffer_size: Optional[int] = None) -> Deque[int]:
        """
        Prepare the rolling window memory (optionally resizing it).
        Returns a reference to the internal deque of values.
        """
        if buffer_size is not None and int(buffer_size) != self.buffer_size:
            self.buffer_size = int(buffer_size)
            with self._lock:
                vals = list(self._buf)[-self.buffer_size:]
                ts = list(self._ts)[-self.buffer_size:]
                self._buf = deque(vals, maxlen=self.buffer_size)
                self._ts = deque(ts, maxlen=self.buffer_size)
        return self._buf

    def get_buffer(self) -> np.ndarray:
        """Return a copy of the current buffer as numpy array of int16."""
        with self._lock:
            return np.asarray(self._buf, dtype=np.int16)

    def capture_window(self, n_samples: int) -> np.ndarray:
        """Return the most recent n_samples (clipped to buffer length)."""
        with self._lock:
            data = np.asarray(self._buf, dtype=np.int16)
        if n_samples <= 0:
            return np.empty((0,), dtype=np.int16)
        return data[-min(n_samples, data.size):]

    def capture_image(self, duration_s: float):
        """
        Return (t_seconds_forward, values) for the last `duration_s` seconds.

        - Uses timestamps to slice the rolling buffer.
        - Time vector starts at 0 and increases monotonically.
        - If there are no samples in the window, returns ([], []).
        """
        duration_s = float(duration_s)
        if duration_s <= 0:
            return np.array([]), np.array([])

        now = time.time()
        cutoff = now - duration_s

        # Snapshot buffers under the lock
        with self._lock:
            ts = np.asarray(self._ts, dtype=float)
            ys = np.asarray(self._buf, dtype=np.int16)

        if ts.size == 0:
            return np.array([]), np.array([])

        # Find the first index where timestamp >= cutoff (inclusive boundary)
        # Assumes ts is non-decreasing because we append in time order.
        idx = np.searchsorted(ts, cutoff, side="left")

        tsw = ts[idx:]
        ysw = ys[idx:]

        if tsw.size == 0:
            return np.array([]), np.array([])

        # Build a forward-going time axis starting at 0
        t = tsw - tsw[0]
        return t, ysw

    def save_window_image(self, duration_s: float = 10.0, out_path: str = "fsr_last10.png",
                          ylim: int = 1200, invert: bool = False, title: Optional[str] = None) -> str:
        """
        Save the last `duration_s` seconds of data to a PNG image.
        Returns the output path.
        """
        t, vals = self.capture_image(duration_s)
        if t.size == 0:
            raise RuntimeError(f"No samples available in the last {duration_s} seconds.")

        if invert:
            vals = 1023 - vals

        plt.ioff()
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(t, vals, linewidth=1.0)
        ax.set_xlim(0, max(duration_s, float(t[-1]) if t.size else duration_s))
        ax.set_ylim(0, ylim)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("A0 ADC Value")
        ax.set_title(title or f"{self.name}: Last {duration_s:.2f}s")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return out_path

    def get_stats(self) -> dict:
        ok_reads = self._total_reads - self._failed_reads
        return {
            "total_reads": int(self._total_reads),
            "failed_reads": int(self._failed_reads),
            "reconnections": int(self._reconnections),
            "success_rate": float(ok_reads / max(1, self._total_reads) * 100.0),
        }

    def dummy_test(self):
        print("This is a dummy test for FSRStreamSensor.")
        return

    def fsr_reading_test(self):
        # reads FSR data
        # if not state["probing_done"]:
        # while True:
        self.plot_live(fps=15, ylim=1200, invert=True,
                title=f"FSR: Live Plot")
        # self.FSRStreamSensor.dummy_test()
            # state["scope_data"].extend(fsr_data)
            # time.sleep(0.01)
        return        

    # ---- Live plotting -----------------------------------------------------
    def plot_live(self, fps: float = 30.0, ylim: int = 1200, invert: bool = False,
                  title: str = "", save_last10_path: Optional[str] = None) -> None:
        """
        Start an interactive matplotlib plot that updates at the target FPS.
        If save_last10_path is provided, saves the last 10 seconds as a PNG
        when the window is closed.
        """
        if not self._alive or not self._ser:
            raise RuntimeError("Sensor is not connected. Call connect() first.")

        plt.ion()
        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(self.buffer_size, dtype=np.int32)
        y = self.get_buffer()
        (line,) = ax.plot(x, y, linewidth=1.0)

        ax.set_xlim(0, self.buffer_size - 1)
        # ax.set_xlim(0, 200)
        ax.set_ylim(0, ylim)
        ax.set_xlabel("Samples (rolling buffer)")
        ax.set_ylabel("A0 ADC Value")
        ax.set_title(title or f"{self.name}: Live Plot (Ctrl+C or close window to exit)")
        ax.grid(True, alpha=0.3)

        interval = 1.0 / max(0.1, min(float(fps), 60.0))
        last_update = time.time()
        last_stats = time.time()

        print("plot live...")
        try:
            while True:
                if not plt.fignum_exists(fig.number):
                    break

                now = time.time()
                if now - last_update >= interval:
                    y = self.get_buffer()
                    if invert:
                        y = 1023 - y
                    # Update line with rolling buffer
                    if y.size < self.buffer_size:
                        # pad if buffer not full
                        pad = np.full(self.buffer_size - y.size, y[0] if y.size else 0, dtype=np.int16)
                        y_plot = np.concatenate([pad, y])
                    else:
                        y_plot = y[-self.buffer_size:]
                    line.set_ydata(y_plot)

                    try:
                        fig.canvas.draw_idle()
                        fig.canvas.flush_events()
                    except Exception:
                        pass

                    last_update = now

                if now - last_stats >= 10.0:
                    stats = self.get_stats()
                    if stats["total_reads"] > 0:
                        print(
                            f"Stats: {stats['total_reads']} reads, "
                            f"{stats['success_rate']:.1f}% success, "
                            f"{stats['reconnections']} reconnections"
                        )
                    last_stats = now

                plt.pause(0.001)
        finally:
            try:
                plt.close(fig)
            finally:
                if save_last10_path:
                    try:
                        path = self.save_window_image(10.0, save_last10_path, ylim=ylim, invert=invert,
                                                      title=f"{self.name}: Final 10s")
                        print(f"Saved last 10s image to: {path}")
                    except Exception as e:
                        print(f"Could not save last 10s image: {e}")

    # ---- Internals ---------------------------------------------------------
    def _connect_once_or_retry(self) -> bool:
        """Try to connect with bounded retries and a quick sanity check."""
        if serial is None:
            print(f"[{self.name}] pyserial not available; please pip install pyserial.")
            return False

        attempts = 0
        while self._alive and attempts < self._max_connect_attempts:
            attempts += 1
            try:
                if self._ser:
                    try:
                        self._ser.close()
                    except Exception:
                        pass

                print(f"[{self.name}] Connecting to {self.port} (attempt {attempts})")
                self._ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    timeout=self._read_timeout_s,
                    inter_byte_timeout=self._inter_byte_timeout_s,
                    write_timeout=1.0,
                )

                # Flush any stale data
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

                # Sanity-read a few lines
                good = 0
                start = time.time()
                while good < 3 and (time.time() - start) < 2.0:
                    line = self._ser.readline()
                    if not line:
                        continue
                    decoded = line.decode("utf-8", errors="ignore").strip()
                    if not decoded:
                        continue
                    # first token before comma
                    tok = decoded.split(",")[0].strip()
                    try:
                        val = int(tok)
                        if 0 <= val <= 1023:
                            good += 1
                    except Exception:
                        pass

                if good >= 3:
                    print(f"[{self.name}] Connected.")
                    return True

                raise Exception("Stream sanity check failed.")

            except PermissionError as e:
                print(f"[{self.name}] PermissionError: {e}")
                print(f"  → {self.port} is already in use by another application")
                print(f"  → Close: Serial Monitor, Arduino IDE, other Python instances")
                print(f"  → Or: Unplug USB device and reconnect it")
                time.sleep(2.0)
            except Exception as e:
                print(f"[{self.name}] Connection error: {e}")
                print(f"  → Port: {self.port}, Baud: {self.baud}")
                print(f"  → Check device connection and driver status in Device Manager")
                time.sleep(1.0)

        print(f"[{self.name}] Failed to connect after {self._max_connect_attempts} attempts.")
        return False

    def _read_loop(self):
        """Background reader loop with guarded reconnection."""
        consecutive_failures = 0
        max_consecutive_failures = 10

        while self._alive:
            if not self._ser or not self._ser.is_open:
                self._reconnections += 1
                if not self._connect_once_or_retry():
                    time.sleep(0.1)
                    continue
                consecutive_failures = 0

            try:
                raw = self._ser.readline()
                self._total_reads += 1

                if not raw:
                    consecutive_failures += 1
                    if consecutive_failures > max_consecutive_failures:
                        # trigger reconnection
                        self._safe_close()
                        consecutive_failures = 0
                    else:
                        time.sleep(0.001)
                    continue

                consecutive_failures = 0
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                tok = line.split(",")[0].strip()
                try:
                    val = int(tok)
                    if 0 <= val <= 1023:
                        now = time.time()
                        with self._lock:
                            self._buf.append(val)
                            self._ts.append(now)
                    else:
                        self._failed_reads += 1
                except (ValueError, IndexError):
                    self._failed_reads += 1
                    continue

            except Exception:
                # SerialException / OSError, or other unexpected errors
                self._failed_reads += 1
                consecutive_failures += 1
                if consecutive_failures > max_consecutive_failures:
                    self._safe_close()
                    consecutive_failures = 0
                time.sleep(0.01)

    def _safe_close(self):
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None


    def generate_signal(self):
        
        pass

    def initialize_oscilloscope(self):
        
        pass


# ------------------------- CLI entry point ----------------------------------
def main():
    import argparse

    p = argparse.ArgumentParser(description="FSR A0 live plotting")
    p.add_argument("--port", default="COM6",
                   help="Serial port, e.g., COM5 (Windows), /dev/ttyACM0 (Linux), /dev/tty.usbmodem* (macOS)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--buffer", type=int, default=200, help="Rolling buffer length (samples)")
    p.add_argument("--ylim", type=int, default=1200, help="Y-axis max (10-bit ADC≈1023)")
    p.add_argument("--fps", type=float, default=30.0, help="Plot refresh rate (Hz)")
    p.add_argument("--invert", action="store_true", help="Invert the Y-axis values")
    p.add_argument("--save_last10", default="", help="If provided, save the last 10 seconds to this PNG when closing")
    args = p.parse_args()

    sensor = FSRStreamSensor(args.port, args.baud, args.buffer)
    if not sensor.connect():
        print("Could not establish serial connection.")
        return 1

    try:
        sensor.initialize_stream(args.buffer)
        # samples = sensor.capture_image(1.0)
        # print("Captured samples:", len(samples[1]))
        save_path = args.save_last10 if args.save_last10 else None
        # sensor.plot_live(fps=args.fps, ylim=args.ylim, invert=args.invert,
        #                  title=f"{sensor.name}: Live Plot",
        #                  save_last10_path=save_path)
        # starts fsr reading thread
        fsr_thread = threading.Thread(target=sensor.plot_live(fps=30, ylim=1200, invert=True,
                        title=f"FSR: Live Plot in Thread",))
        fsr_thread.start()
    
    finally:
        sensor.disconnect()

    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())