import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import os

# --- 1. CONFIGURATION & STYLE ---
COLOR_PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#F0E442", "#8B4513",
    "#56B4E9", "#F0A3FF", "#FFB400", "#00BFFF", "#90EE90", "#FF6347", "#8A2BE2",
    "#CD5C5C", "#4682B4", "#FFDEAD", "#32CD32", "#D3D3D3", "#999999"
]
METRIC = "power_draw"


def load_and_process_data():
    """Loads parquet files and aligns timestamps."""
    print("Loading data...")

    # Check if data exists (Warning only)
    if not os.path.exists("../data/footprinter.parquet"):
        print("Warning: ../data/footprinter.parquet not found.")

    # Load Data
    fp = pd.read_parquet("../data/footprinter.parquet").groupby("timestamp")[METRIC].sum()
    odt = pd.read_parquet("../data/opendt_non_calibrated.parquet").groupby("timestamp")[METRIC].sum()
    rw = pd.read_parquet("../data/real_world.parquet").groupby("timestamp")[METRIC].sum()

    # --- Processing ---
    print("Processing and aligning data...")

    def average_every_n(series, n):
        return series.groupby(np.arange(len(series)) // n).mean()

    # Average to 5-min intervals
    odt = average_every_n(odt, 2)
    fp = average_every_n(fp, 10)
    rw = average_every_n(rw, 10)

    # Sync lengths
    min_len = min(len(odt), len(fp), len(rw))
    odt = odt.iloc[:min_len]
    fp = fp.iloc[:min_len]
    rw = rw.iloc[:min_len]

    # Force Start Time
    start_time = pd.Timestamp("2022-10-06 22:00:00")
    timestamps = pd.date_range(start=start_time, periods=min_len, freq="5min")

    odt.index = timestamps
    fp.index = timestamps
    rw.index = timestamps

    return fp, odt, rw, timestamps, min_len


def calculate_mape(ground_truth, simulation):
    """Calculates Mean Absolute Percentage Error (MAPE)."""
    R = ground_truth.values
    S = simulation.values
    mask = R != 0
    return np.mean(np.abs((R[mask] - S[mask]) / R[mask])) * 100


def calculate_uo_ratio_100(ground_truth, simulation):
    """
    Calculates the Underestimation vs Overestimation split summing to 100.
    Returns a string format "XX-YY" (e.g., "21-79").
    """
    R = ground_truth.values
    S = simulation.values

    under_count = np.sum(S < R)
    over_count = np.sum(S > R)
    total = under_count + over_count

    if total == 0:
        return "0-0"

    # Calculate percentage for Underestimation
    under_pct = int(round((under_count / total) * 100))
    # Remaining is Overestimation to ensure sum is 100
    over_pct = 100 - under_pct

    return f"{under_pct}-{over_pct}"


def generate_experiment_pdf(x, fp, odt, rw, timestamps, min_len):
    """Generates the final publication plot."""
    print("Generating final experiment PDF...")

    # Setup Figure
    plt.figure(figsize=(9, 4))
    plt.grid(True)

    # Plot Lines with lw=1 (Finer resolution)
    plt.plot(x, rw.values / 1000, label="Ground Truth", color=COLOR_PALETTE[0], lw=1)
    plt.plot(x, fp.values / 1000, label="FootPrinter", color=COLOR_PALETTE[1], lw=1)
    plt.plot(x, odt.values / 1000, label="OpenDT", color=COLOR_PALETTE[2], lw=1)

    ax = plt.gca()

    # --- Formatting X-Axis ---
    target_dates = ["2022-10-08", "2022-10-10", "2022-10-12", "2022-10-14"]
    tick_dates = pd.to_datetime(target_dates)
    tick_positions = []
    tick_labels = []

    for d in tick_dates:
        seconds_diff = (d - timestamps[0]).total_seconds()
        idx = int(seconds_diff / 300)
        tick_positions.append(idx)
        tick_labels.append(d.strftime("%d/%m"))

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=20)

    max_tick = max(tick_positions)
    if ax.get_xlim()[1] < max_tick:
        ax.set_xlim(right=max_tick + (min_len * 0.02))

    # --- Formatting Y-Axis ---
    y_formatter = FuncFormatter(lambda val, _: f"{int(val):,}")
    ax.yaxis.set_major_formatter(y_formatter)
    ax.tick_params(axis='y', labelsize=20)

    # Labels
    plt.ylabel("Power Draw [kW]", fontsize=22, labelpad=10)
    plt.xlabel("Time [day/month]", fontsize=22, labelpad=10)
    plt.ylim(bottom=0)

    # --- LEGEND CONFIGURATION ---
    # loc="lower right" places it in the bottom-right corner inside the plot
    leg = plt.legend(fontsize=18, loc="lower right", ncol=3, framealpha=1)

    # Make lines in the legend thicker (4.0)
    for line in leg.get_lines():
        line.set_linewidth(4.0)

    plt.tight_layout()

    # Save
    plt.savefig("exp1_plot_power_draw.pdf", format="pdf", bbox_inches="tight")
    print("Plot saved as 'exp1_plot_power_draw.pdf'")
    plt.close()


def main():
    # 1. Load Data
    fp, odt, rw, timestamps, min_len = load_and_process_data()
    x = np.arange(min_len)

    # 2. Calculate Stats
    mape_fp = calculate_mape(rw, fp)
    mape_odt = calculate_mape(rw, odt)

    # 3. Calculate Under-Over Split (Sum to 100)
    split_fp = calculate_uo_ratio_100(rw, fp)
    split_odt = calculate_uo_ratio_100(rw, odt)

    # --- PRINT STATS ---
    print("-" * 50)
    print(f"Stats (MAPE)        - FP: {mape_fp:.2f}%, ODT: {mape_odt:.2f}%")
    print(f"Split (Under-Over)  - FP: {split_fp}, ODT: {split_odt}")
    print("-" * 50)

    # 4. Generate Plot
    generate_experiment_pdf(x, fp, odt, rw, timestamps, min_len)
    print("Done!")


if __name__ == "__main__":
    main()