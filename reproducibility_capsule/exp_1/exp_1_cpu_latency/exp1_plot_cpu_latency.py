import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# --- CONFIGURATION ---
FILE_PATH = "../data/opendt_cpu_latency_bytime.csv"
OUTPUT_PLOT_NAME = "exp_1_plot_cpu_latency.pdf"

# Reference Start Time & Duration logic
REFERENCE_START_TIME = pd.Timestamp("2022-10-06 22:00:00")
TOTAL_DAYS = 7
TOTAL_RUNS = 167

# Re-adding smoothing to keep the graph clean (as requested previously)
ROLLING_WINDOW = 10

COLOR_PALETTE = [
    "#0072B2",  # Blue (for CPU)
    "#E69F00",  # Orange (for Latency)
]


def load_and_process_data():
    if not os.path.exists(FILE_PATH):
        print(f"Error: File not found at {FILE_PATH}")
        return None

    print(f"Loading data from {FILE_PATH}...")
    df = pd.read_csv(FILE_PATH)

    # 1. Extract Run ID as Integer
    if df['run_id'].dtype == object:
        df['run_id'] = df['run_id'].astype(str).str.extract(r'(\d+)').astype(int)

    # 2. FIX TIMESTAMPS: Ensure runs are spread over the 7 days based on ID
    time_delta = pd.Timedelta(days=TOTAL_DAYS) / TOTAL_RUNS
    df['calculated_start_time'] = REFERENCE_START_TIME + (df['run_id'] - 1) * time_delta

    # 3. Process Metrics
    df['duration_td'] = pd.to_timedelta(df['estimated_completion_duration'])
    df['latency_hours'] = df['duration_td'].dt.total_seconds() / 3600.0

    df = df.sort_values(by='calculated_start_time')

    # 4. Apply Smoothing
    df['cpu_smoothed'] = df['average_cpu'].rolling(window=ROLLING_WINDOW, center=True, min_periods=1).mean()
    df['latency_smoothed'] = df['latency_hours'].rolling(window=ROLLING_WINDOW, center=True, min_periods=1).mean()

    return df


def generate_plot(df):
    print("Generating plot...")

    timestamps = df['calculated_start_time']
    # Using smoothed values
    cpu_values = df['cpu_smoothed'] * 100
    latency_values = df['latency_smoothed']

    fig, ax1 = plt.subplots(figsize=(12, 6))

    # --- LEFT AXIS (CPU) ---
    color_cpu = COLOR_PALETTE[0]
    ax1.set_xlabel("Time [day/month]", fontsize=26, labelpad=10)
    ax1.set_ylabel("Average CPU Utilization [%]", color=color_cpu, fontsize=26, labelpad=10)

    # Plot CPU
    mark_step = max(1, len(timestamps) // 15)
    line1 = ax1.plot(timestamps, cpu_values,
                     color=color_cpu, linewidth=3, linestyle="-",
                     marker="o", markersize=8, markevery=mark_step,
                     label="Avg CPU Utilization")

    ax1.tick_params(axis='y', labelcolor=color_cpu, labelsize=28)
    ax1.tick_params(axis='x', labelsize=28)
    ax1.set_ylim(0, 110)

    # --- RIGHT AXIS (LATENCY) ---
    ax2 = ax1.twinx()
    color_latency = COLOR_PALETTE[1]
    ax2.set_ylabel("Latency [h]", color=color_latency, fontsize=26, labelpad=10)

    # Plot Latency
    line2 = ax2.plot(timestamps, latency_values,
                     color=color_latency, linewidth=3, linestyle="--",
                     marker="s", markersize=8, markevery=mark_step,
                     label="Latency [h]")

    ax2.tick_params(axis='y', labelcolor=color_latency, labelsize=28)

    # Dynamic limit for Latency
    max_lat = latency_values.max()
    ax2.set_ylim(0, max_lat * 1.2 if max_lat > 0 else 1)

    # --- FORMATTING ---
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))

    # --- LEGEND FIX ---
    # Removed bbox_to_anchor to keep it inside the plot
    # Added framealpha to make it slightly readable if lines cross it
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper center", fontsize=22, ncol=2, frameon=True, framealpha=0.8)

    # move the legend 2% up
    box = ax1.get_position()
    ax1.set_position([box.x0, box.y0 + 0.02,                    box.width, box.height * 0.98])


    ax1.grid(True, axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    plt.savefig(OUTPUT_PLOT_NAME, format="pdf", bbox_inches="tight")
    print(f"Plot saved as '{OUTPUT_PLOT_NAME}'")
    plt.close()


def main():
    df = load_and_process_data()
    if df is not None:
        generate_plot(df)
        print("Done!")


if __name__ == "__main__":
    main()