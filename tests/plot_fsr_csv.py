"""
Plot an FSR CSV file recorded by fsr_continuous_test_1min.py.
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def plot_fsr_csv(csv_path: str, save_path: str | None = None, title: str | None = None):
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    data = np.loadtxt(path, delimiter=',', skiprows=1)

    if data.ndim == 1:
        data = data.reshape(1, -1)

    if data.shape[1] >= 2:
        t = data[:, 0]
        vals = data[:, 1]
    else:
        t = np.arange(data.shape[0])
        vals = data[:, 0]

    plt.figure(figsize=(10, 4))
    plt.plot(t, vals, lw=1.2, color="tab:blue")
    plt.xlabel("Time (s)")
    plt.ylabel("FSR ADC")
    plt.title(title or f"FSR trace: {path.name}")
    plt.ylim(0, 1023)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    if save_path:
        save_file = Path(save_path)
        save_file.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_file, dpi=150)
        print(f"Saved plot to: {save_file}")

    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot a saved FSR CSV file")
    parser.add_argument("file", nargs="?", type=str, default=None, help="Path to the CSV file")
    parser.add_argument("--file", dest="file_option", type=str, default=None, help="Path to the CSV file")
    parser.add_argument("--save", type=str, default=None, help="Optional path to save the plot image")
    parser.add_argument("--title", type=str, default=None, help="Optional plot title")
    args = parser.parse_args()

    csv_path = args.file_option or args.file
    if not csv_path:
        parser.error("Please provide a CSV file path")

    plot_fsr_csv(csv_path, save_path=args.save, title=args.title)
