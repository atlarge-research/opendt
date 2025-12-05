import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# --- CONFIGURATION ---
FILE_PATH = "../data/footprinter.parquet"
METRIC_1 = "cpu_utilization"
METRIC_2 = "carbon_intensity" # Using 'carbon_intensity' as source for the second axis per snippet

COLOR_PALETTE = [
    "#0072B2", # Blue (for CPU)
    "#E69F00", # Orange (for Latency)
]

def load_and_process_data():
    """Loads data and computes aggregated metrics."""
    if not os.path.exists(FILE_PATH):
        print(f"Error: File not found at {FILE_PATH}")
        return None, None, None

    print(f"Loading data from {FILE_PATH}...")
    opendt = pd.read_parquet(FILE_PATH)

    # Calculate Mean CPU and Sum of Metric 2 (Latency/Carbon) per timestamp
    print("Processing metrics...")
    df_cpu = opendt.groupby("timestamp")[METRIC_1].mean()
    df_metric2 = opendt.groupby("timestamp")[METRIC_2].sum()

    return df_cpu, df_metric2

def generate_plot(df_cpu, df_metric2):
    """Generates the dual-axis plot."""
    print("Generating plot...")

    # --- Time Alignment ---
    # Footprinter data is every 30 seconds.
    # Creating a date range starting from 2022-10-06 22:00:00
    start_time = pd.Timestamp("2022-10-06 22:00:00")
    timestamps = pd.date_range(start=start_time, periods=len(df_cpu), freq="30S")

    # --- Plotting ---
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # --- LEFT AXIS (CPU) ---
    color_cpu = COLOR_PALETTE[0]
    ax1.set_xlabel("Time [day/month]", fontsize=26, labelpad=10)
    ax1.set_ylabel("Average CPU Utilization [%]", color=color_cpu, fontsize=26, labelpad=10)

    # Plot CPU: Solid Blue Line with circle markers
    line1 = ax1.plot(timestamps, df_cpu.values * 100,
                     color=color_cpu, linewidth=3, linestyle="-",
                     marker="o", markersize=8, markevery=len(timestamps)//15,
                     label="Avg CPU Utilization")

    ax1.tick_params(axis='y', labelcolor=color_cpu, labelsize=28)
    ax1.tick_params(axis='x', labelsize=28)
    ax1.set_ylim(0, 110) # CPU % usually 0-100

    # --- RIGHT AXIS (LATENCY) ---
    ax2 = ax1.twinx() # Create a second y-axis sharing the same x-axis
    color_latency = COLOR_PALETTE[1]
    ax2.set_ylabel("Latency [h]", color=color_latency, fontsize=26, labelpad=10)

    # Plot Latency: Dashed Orange Line with square markers
    line2 = ax2.plot(timestamps, df_metric2.values,
                     color=color_latency, linewidth=3, linestyle="--",
                     marker="s", markersize=8, markevery=len(timestamps)//15,
                     label="Latency [h]")

    ax2.tick_params(axis='y', labelcolor=color_latency, labelsize=28)
    ax2.set_ylim(bottom=0) # Ensure Latency axis starts at 0

    # --- FORMATTING ---
    # X-Axis Date Format (Day/Month)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2)) # Tick every 2 days

    # Legend (Combine lines from both axes)
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper center", fontsize=22, ncol=2, bbox_to_anchor=(0.5, 1.20))

    # Grid (Horizontal dashed lines)
    ax1.grid(True, axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()

    # Save as PDF
    output_filename = "exp_1_plot_cpu_latency.pdf"
    plt.savefig(output_filename, format="pdf", bbox_inches="tight")
    print(f"Plot saved as '{output_filename}'")
    plt.close()

def main():
    df_cpu, df_metric2 = load_and_process_data()
    if df_cpu is not None:
        generate_plot(df_cpu, df_metric2)
        print("Done!")

if __name__ == "__main__":
    main()