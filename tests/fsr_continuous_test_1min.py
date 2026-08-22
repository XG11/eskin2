"""
One-minute FSR recording and plotting test.
This script is based on fsr_continuous_test.py but runs for a fixed 60 seconds,
plots the incoming data live, and saves the results to disk.
"""

import sys
import time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import tactile_calibration as tc


def record_and_plot_for_1_min(port: str = "COM26", baud: int = 115200,
                             duration_s: float = 60.0,
                             buffer_size: int = 200,
                             output_basename: str = "fsr_1min_recording"):
    """
    Connect to the FSR sensor, plot incoming samples live for one minute,
    and save the recorded data and a final plot to disk.
    """
    print(f"Initializing FSR sensor on {port}...")
    fsr_sensor = tc.FSRStreamSensor(port=port, baud=baud, buffer_size=buffer_size)

    try:
        if not fsr_sensor.connect():
            print("ERROR: Failed to connect to FSR sensor!")
            return False

        print("Connected to FSR sensor successfully.")
        fsr_sensor.initialize_stream(buffer_size=buffer_size)
        fsr_sensor.start_logging()

        plt.ion()
        fig, ax = plt.subplots(figsize=(10, 4))
        line, = ax.plot([], [], lw=1.2, color="tab:blue")
        ax.set_title("FSR Sensor: 1-Minute Recording")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("FSR ADC")
        ax.set_ylim(0, 1023)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.show()

        start_time = time.time()
        last_count = 0

        print(f"Recording for {duration_s:.0f} seconds...")
        while time.time() - start_time < duration_s:
            time.sleep(0.2)
            ts, vals = fsr_sensor.get_log_with_time()

            if vals.size > 0 and vals.size != last_count:
                t = ts - ts[0] if ts.size > 0 else np.array([])
                if t.size > 0:
                    line.set_data(t, vals)
                    ax.relim()
                    ax.autoscale_view()
                    ax.set_xlim(0, max(1.0, float(t[-1]) if t.size else duration_s))
                    ax.set_ylim(0, 1023)
                    fig.canvas.draw_idle()
                    fig.canvas.flush_events()
                    last_count = vals.size

        fsr_sensor.stop_logging()
        ts, vals = fsr_sensor.get_log_with_time()

        if vals.size > 0:
            t = ts - ts[0] if ts.size > 0 else np.array([])
            if t.size > 0:
                line.set_data(t, vals)
                ax.relim()
                ax.autoscale_view()
                ax.set_xlim(0, max(1.0, float(t[-1]) if t.size else duration_s))
                ax.set_ylim(0, 1023)
                fig.canvas.draw_idle()
                fig.canvas.flush_events()

        output_dir = Path(__file__).parent.parent / "results" / "sensordata"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_dir = Path(__file__).parent.parent / "results" / "sensorimages"
        image_dir.mkdir(parents=True, exist_ok=True)

        csv_path = output_dir / f"{output_basename}.csv"
        png_path = image_dir / f"{output_basename}.png"

        if vals.size > 0:
            t = ts - ts[0] if ts.size > 0 else np.array([])
            data_to_save = np.column_stack([t, vals])
            np.savetxt(csv_path, data_to_save, delimiter=',', header='Time(s),FSR_Value', comments='')
            print(f"Saved CSV: {csv_path}")

        fig.savefig(png_path, dpi=150)
        print(f"Saved plot: {png_path}")
        plt.close(fig)

        stats = fsr_sensor.get_stats()
        print("\n=== FSR Reading Statistics ===")
        print(f"Total reads: {stats['total_reads']}")
        print(f"Failed reads: {stats['failed_reads']}")
        print(f"Success rate: {stats['success_rate']:.2f}%")

        return True

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return False

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print("Disconnecting sensor...")
        fsr_sensor.disconnect()
        print("Done!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Record and plot FSR data for 1 minute")
    parser.add_argument("--port", type=str, default="COM26", help="Serial port for FSR sensor")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--duration", type=float, default=60.0, help="Duration in seconds")
    parser.add_argument("--buffer", type=int, default=200, help="Rolling buffer size")
    parser.add_argument("--output", type=str, default="fsr_1min_recording", help="Base output filename")

    args = parser.parse_args()

    success = record_and_plot_for_1_min(
        port=args.port,
        baud=args.baud,
        duration_s=args.duration,
        buffer_size=args.buffer,
        output_basename=args.output,
    )

    sys.exit(0 if success else 1)
