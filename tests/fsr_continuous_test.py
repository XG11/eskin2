"""
Continuous FSR Voltage Reading Test
This script continuously reads FSR (Force Sensitive Resistor) voltage data
from the serial sensor and displays it in real-time.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import tactile_calibration as tc


def continuous_read_with_live_plot(port: str = "COM26", baud: int = 115200, 
                                   buffer_size: int = 500, duration_s: float = None):
    """
    Continuously read FSR voltage and display live plot.
    
    Args:
        port: Serial port for the FSR sensor (default: "COM26")
        baud: Baud rate for serial connection (default: 115200)
        buffer_size: Size of the rolling buffer for plotting (default: 500)
        duration_s: Duration to run in seconds. None = infinite (until user closes window)
    """
    print(f"Initializing FSR sensor on {port}...")
    
    # Create and configure sensor
    fsr_sensor = tc.FSRStreamSensor(port=port, baud=baud, buffer_size=buffer_size)
    
    try:
        # Connect to sensor
        if not fsr_sensor.connect():
            print("ERROR: Failed to connect to FSR sensor!")
            return False
        
        print(f"Connected to FSR sensor successfully!")
        print(f"Buffer size: {buffer_size}")
        print(f"Baud rate: {baud}")
        
        # Initialize stream
        fsr_sensor.initialize_stream(buffer_size=buffer_size)
        
        # Start logging for data analysis
        fsr_sensor.start_logging()
        
        print("\nStarting continuous reading...")
        print("Close the plot window to stop reading.\n")
        
        # Display live plot
        fsr_sensor.plot_live(fps=30, ylim=1200, invert=True,
                           title="FSR Sensor: Continuous Voltage Reading")
        
        # After plot window is closed, get statistics
        fsr_sensor.stop_logging()
        stats = fsr_sensor.get_stats()
        
        print("\n=== FSR Reading Statistics ===")
        print(f"Total reads: {stats['total_reads']}")
        print(f"Failed reads: {stats['failed_reads']}")
        print(f"Reconnections: {stats['reconnections']}")
        print(f"Success rate: {stats['success_rate']:.2f}%")
        
        # Get logged data
        log_data = fsr_sensor.get_log()
        ts, vals = fsr_sensor.get_log_with_time()
        
        if log_data.size > 0:
            print(f"\n=== Data Statistics ===")
            print(f"Total samples: {log_data.size}")
            print(f"Min value: {log_data.min()}")
            print(f"Max value: {log_data.max()}")
            print(f"Mean value: {log_data.mean():.2f}")
            print(f"Std deviation: {log_data.std():.2f}")
            
            if ts.size > 0:
                duration = ts[-1] - ts[0] if ts.size > 1 else 0
                print(f"Duration: {duration:.2f} seconds")
                print(f"Sampling rate: {log_data.size / max(1, duration):.2f} Hz")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return False
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print("\nDisconnecting sensor...")
        fsr_sensor.disconnect()
        print("Done!")


def continuous_read_with_console_output(port: str = "COM26", baud: int = 115200,
                                       update_interval: float = 0.1,
                                       duration_s: float = None):
    """
    Continuously read FSR voltage and print to console.
    Useful for monitoring without GUI.
    
    Args:
        port: Serial port for the FSR sensor (default: "COM26")
        baud: Baud rate for serial connection (default: 115200)
        update_interval: Interval in seconds between console updates (default: 0.1)
        duration_s: Duration to run in seconds. None = infinite
    """
    print(f"Initializing FSR sensor on {port}...")
    
    # Create and configure sensor
    fsr_sensor = tc.FSRStreamSensor(port=port, baud=baud, buffer_size=50)
    
    try:
        # Connect to sensor
        if not fsr_sensor.connect():
            print("ERROR: Failed to connect to FSR sensor!")
            return False
        
        print(f"Connected to FSR sensor successfully!")
        print(f"Reading FSR data every {update_interval} seconds...")
        print("Press Ctrl+C to stop.\n")
        print(f"{'Time (s)':<10} {'Min':<8} {'Max':<8} {'Mean':<8} {'Samples':<10}")
        print("-" * 50)
        
        # Initialize stream
        fsr_sensor.initialize_stream(buffer_size=50)
        fsr_sensor.start_logging()
        
        start_time = time.time()
        
        # Continuous reading loop
        while True:
            time.sleep(update_interval)
            
            # Get current buffer data
            data = fsr_sensor.get_buffer()
            elapsed = time.time() - start_time
            
            if data.size > 0:
                print(f"{elapsed:<10.2f} {data.min():<8} {data.max():<8} "
                      f"{data.mean():<8.2f} {data.size:<10}")
            
            # Check duration limit
            if duration_s is not None and elapsed >= duration_s:
                print(f"\nDuration limit ({duration_s}s) reached.")
                break
                
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        fsr_sensor.stop_logging()
        stats = fsr_sensor.get_stats()
        
        print("\n=== FSR Reading Statistics ===")
        print(f"Total reads: {stats['total_reads']}")
        print(f"Failed reads: {stats['failed_reads']}")
        print(f"Success rate: {stats['success_rate']:.2f}%")
        
        fsr_sensor.disconnect()
        print("Disconnected.")


def read_and_save_data(port: str = "COM26", baud: int = 115200,
                       duration_s: float = 10.0, output_file: str = "fsr_data.csv"):
    """
    Read FSR data for a specified duration and save to CSV file.
    
    Args:
        port: Serial port for the FSR sensor (default: "COM26")
        baud: Baud rate for serial connection (default: 115200)
        duration_s: Duration to read in seconds (default: 10.0)
        output_file: Output CSV filename (default: "fsr_data.csv")
    """
    print(f"Reading FSR data for {duration_s} seconds...")
    print(f"Output will be saved to: {output_file}\n")
    
    # Create and configure sensor
    fsr_sensor = tc.FSRStreamSensor(port=port, baud=baud, buffer_size=200)
    
    try:
        # Connect to sensor
        if not fsr_sensor.connect():
            print("ERROR: Failed to connect to FSR sensor!")
            return False
        
        # Initialize and start logging
        fsr_sensor.initialize_stream()
        fsr_sensor.start_logging()
        
        print(f"Recording for {duration_s} seconds...")
        time.sleep(duration_s)
        
        # Stop logging and get data
        fsr_sensor.stop_logging()
        ts, vals = fsr_sensor.get_log_with_time()
        
        print(f"Recorded {vals.size} samples")
        
        # Save to CSV
        if vals.size > 0:
            # Normalize timestamps to start at 0
            ts_normalized = ts - ts[0]
            
            # Save to file
            output_path = Path(__file__).parent.parent / "results" / "sensordata" / output_file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            np.savetxt(output_path, np.column_stack([ts_normalized, vals]),
                      delimiter=',', header='Time(s),FSR_Value', comments='')
            
            print(f"Data saved to: {output_path}")
            print(f"\nData Statistics:")
            print(f"  Min value: {vals.min()}")
            print(f"  Max value: {vals.max()}")
            print(f"  Mean value: {vals.mean():.2f}")
            print(f"  Std deviation: {vals.std():.2f}")
            print(f"  Duration: {ts_normalized[-1]:.2f} seconds")
            
            return True
        else:
            print("ERROR: No data was recorded!")
            return False
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return False
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        fsr_sensor.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FSR Continuous Voltage Reading Test")
    parser.add_argument("--port", type=str, default="COM26", 
                       help="Serial port for FSR sensor (default: COM26)")
    parser.add_argument("--baud", type=int, default=115200,
                       help="Baud rate (default: 115200)")
    parser.add_argument("--mode", type=str, choices=["plot", "console", "save"],
                       default="plot",
                       help="Display mode: plot (live graph), console (text output), "
                            "or save (save to CSV)")
    parser.add_argument("--duration", type=float, default=None,
                       help="Duration in seconds (for save mode: default 10s)")
    parser.add_argument("--output", type=str, default="fsr_data.csv",
                       help="Output file for save mode (default: fsr_data.csv)")
    parser.add_argument("--buffer", type=int, default=500,
                       help="Rolling buffer size (default: 500)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FSR Continuous Voltage Reading Test")
    print("=" * 60)
    print(f"Port: {args.port}")
    print(f"Baud: {args.baud}")
    print(f"Mode: {args.mode}")
    print("=" * 60 + "\n")
    
    if args.mode == "plot":
        success = continuous_read_with_live_plot(
            port=args.port,
            baud=args.baud,
            buffer_size=args.buffer,
            duration_s=args.duration
        )
    elif args.mode == "console":
        success = continuous_read_with_console_output(
            port=args.port,
            baud=args.baud,
            duration_s=args.duration
        )
    elif args.mode == "save":
        duration = args.duration if args.duration else 10.0
        success = read_and_save_data(
            port=args.port,
            baud=args.baud,
            duration_s=duration,
            output_file=args.output
        )
    
    sys.exit(0 if success else 1)
