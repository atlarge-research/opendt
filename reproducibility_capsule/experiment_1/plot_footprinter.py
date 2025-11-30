import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.ticker import MaxNLocator, FuncFormatter
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

    # Check if data exists
    if not os.path.exists("data/footprinter.parquet"):
        raise FileNotFoundError("Could not find 'data/footprinter.parquet'. Please ensure the 'data' folder exists.")

    # Load
    fp = pd.read_parquet("data/footprinter.parquet").groupby("timestamp")[METRIC].sum()
    odt = pd.read_parquet("data/opendt.parquet").groupby("timestamp")[METRIC].sum()
    rw = pd.read_parquet("data/real_world.parquet").groupby("timestamp")[METRIC].sum()

    # --- Processing ---
    print("Processing and aligning data...")

    def average_every_n(series, n):
        return series.groupby(np.arange(len(series)) // n).mean()

    # Average to 5-min intervals
    # OpenDT (2.5m) -> 2 samples = 5 min
    # Others (30s) -> 10 samples = 5 min
    odt = average_every_n(odt, 2)
    fp = average_every_n(fp, 10)
    rw = average_every_n(rw, 10)

    # Sync lengths (trim to shortest)
    min_len = min(len(odt), len(fp), len(rw))
    odt = odt.iloc[:min_len]
    fp = fp.iloc[:min_len]
    rw = rw.iloc[:min_len]

    # Force Start Time to 2022-10-06 22:00:00
    start_time = pd.Timestamp("2022-10-06 22:00:00")
    timestamps = pd.date_range(start=start_time, periods=min_len, freq="5T")

    # Apply clean timestamps
    odt.index = timestamps
    fp.index = timestamps
    rw.index = timestamps

    return fp, odt, rw, timestamps, min_len


def calculate_mape(ground_truth, simulation):
    """Calculates Mean Absolute Percentage Error (MAPE)."""
    R = ground_truth.values
    S = simulation.values
    return np.mean(np.abs((R - S) / R)) * 100


def generate_simple_plot(x, fp, odt, rw, timestamps, min_len):
    """Generates the initial overview plot (Figure 1)."""
    print("Generating simple overview plot...")
    plt.figure(figsize=(10, 5))
    plt.grid(True)

    plt.plot(x, rw.values / 1000, label="Ground Truth", color=COLOR_PALETTE[0], lw=1.5)
    plt.plot(x, fp.values / 1000, label="FootPrinter", color=COLOR_PALETTE[1], lw=1.5)
    plt.plot(x, odt.values / 1000, label="OpenDT", color=COLOR_PALETTE[2], lw=1.5)

    ax = plt.gca()
    ax.xaxis.set_major_locator(MaxNLocator(6))
    tick_positions = ax.get_xticks()
    tick_positions = tick_positions[(tick_positions >= 0) & (tick_positions < min_len)].astype(int)
    tick_labels = [timestamps[pos].strftime("%d/%m") for pos in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=20)

    y_formatter = FuncFormatter(lambda val, _: f"{int(val):,}")
    ax.yaxis.set_major_formatter(y_formatter)
    ax.tick_params(axis='y', labelsize=20)
    ax.set_ylim(bottom=0)

    plt.ylabel("Power Draw (kW)", fontsize=20)
    plt.xlabel("Time (day/month)", fontsize=20)
    plt.legend(fontsize=20, loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
    plt.tight_layout()

    plt.savefig("overview_plot.png", dpi=300)
    plt.close()  # Close to free memory


def generate_experiment_pdf(x, fp, odt, rw, timestamps, min_len, mape_fp, mape_odt):
    """Generates the final publication plot with MAPE boxes (Figure 2)."""
    print("Generating final experiment PDF...")

    # Setup Figure
    plt.figure(figsize=(20, 8))
    plt.grid(True)

    # Plot Lines (Thinner: lw=3)
    plt.plot(x, rw.values / 1000, label="Ground Truth", color=COLOR_PALETTE[0], lw=3)
    plt.plot(x, fp.values / 1000, label="FootPrinter", color=COLOR_PALETTE[1], lw=3)
    plt.plot(x, odt.values / 1000, label="OpenDT", color=COLOR_PALETTE[2], lw=3)

    ax = plt.gca()

    # --- Draw Custom Info Boxes ---
    # Box Parameters
    box_width = min_len * 0.30
    box_height = 5
    box_y_center = 7.5
    box_y_bottom = box_y_center - (box_height / 2)

    def draw_stat_box(x_center, color, title, value):
        rect = patches.Rectangle(
            (x_center - box_width / 2, box_y_bottom),
            box_width, box_height,
            linewidth=4, edgecolor=color, facecolor='white', zorder=10
        )
        ax.add_patch(rect)
        # Title
        ax.text(x_center, box_y_center + 1.5,
                title,
                fontsize=24, color=color, ha='center', va='center', zorder=11)
        # Value
        ax.text(x_center, box_y_center - 1.0,
                value,
                fontsize=42, fontweight='bold', color=color, ha='center', va='center', zorder=11)

    # Draw Box 1: Footprinter
    draw_stat_box(min_len * 0.25, COLOR_PALETTE[1], "MAPE Footprinter", f"{mape_fp:.2f}%")
    # Draw Box 2: OpenDT
    draw_stat_box(min_len * 0.75, COLOR_PALETTE[2], "MAPE OpenDT", f"{mape_odt:.2f}%")

    # --- Formatting Axes ---
    # X-Axis
    ax.xaxis.set_major_locator(MaxNLocator(6))
    tick_positions = ax.get_xticks()
    tick_positions = tick_positions[(tick_positions >= 0) & (tick_positions < min_len)].astype(int)
    tick_labels = [timestamps[pos].strftime("%d/%m") for pos in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=32)

    # Y-Axis
    y_formatter = FuncFormatter(lambda val, _: f"{int(val):,}")
    ax.yaxis.set_major_formatter(y_formatter)
    ax.tick_params(axis='y', labelsize=32)

    # Labels
    plt.ylabel("Power Draw [kW]", fontsize=34, labelpad=20)
    plt.xlabel("Time [day/month]", fontsize=34, labelpad=20)
    plt.ylim(bottom=0)

    # Legend (Overlapping Plot, Bottom Center)
    plt.legend(fontsize=28, loc="lower center", ncol=3, framealpha=1, borderpad=0.5)

    plt.tight_layout()

    # Save final file
    plt.savefig("experiment1.pdf", format="pdf", bbox_inches="tight")
    plt.close()


def main():
    # 1. Load Data
    fp, odt, rw, timestamps, min_len = load_and_process_data()
    x = np.arange(min_len)

    # 2. Calculate Stats
    mape_fp = calculate_mape(rw, fp)
    mape_odt = calculate_mape(rw, odt)
    print(f"Stats Calculated - FP: {mape_fp:.2f}%, ODT: {mape_odt:.2f}%")

    # 3. Generate Plots
    generate_simple_plot(x, fp, odt, rw, timestamps, min_len)
    generate_experiment_pdf(x, fp, odt, rw, timestamps, min_len, mape_fp, mape_odt)

    print("Done! Files generated: 'overview_plot.png' and 'experiment1.pdf'")


if __name__ == "__main__":
    main()