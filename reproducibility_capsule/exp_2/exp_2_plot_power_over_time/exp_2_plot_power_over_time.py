import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes, mark_inset
import os

# --- CONFIGURATION ---
COLOR_PALETTE = ["#0072B2", "#E69F00", "#009E73"]  # Blue (Real), Orange (NoCalib), Green (Calib)
METRIC = "power_draw"
DATA_DIR = "../data"
OUTPUT_FILE = "exp2_power_draw_zoomed_fixed.pdf"

# --- STATE OF THE ART BENCHMARKS ---
# 1. FootPrinter [22]: Reported vs. Reproduced
MAPE_FP_REPORTED = 3.15  # As reported in original FootPrinter paper
MAPE_FP_QUANTIFIED = 7.86  # As reproduced in OpenDT Experiment 1

# 2. M3SA [8]
MAPE_MULTI = 7.59  # Multi-Model [cite: 710]
MAPE_META = 3.81  # Meta-Model [cite: 711]

plt.rcParams.update({'font.size': 16, 'font.family': 'serif'})


def load_and_align_data():
    """Loads parquet files, converts index to Datetime (Seconds), aligns, and returns unified DataFrame."""
    print("Loading and aligning data...")
    try:
        def load_single(filename):
            path = os.path.join(DATA_DIR, filename)
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path} does not exist.")

            df = pd.read_parquet(path)

            # --- FIX: Explicit Unit Conversion ---
            # Parquet timestamps are likely in Seconds (epochs).
            # pd.to_datetime defaults to ns, so we explicitly set unit='s'
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')
                df = df.set_index("timestamp")
            else:
                df.index = pd.to_datetime(df.index, unit='s')

            return df[METRIC].groupby(level=0).sum()

        df_nc = load_single("opendt_non_calibrated.parquet")
        df_c = load_single("opendt_calibrated.parquet")
        df_rw = load_single("real_world.parquet")

        # 2. Resample to common frequency (5 min)
        freq = "5min"
        df_rw = df_rw.resample(freq).mean().interpolate()
        df_nc = df_nc.resample(freq).mean().interpolate()
        df_c = df_c.resample(freq).mean().interpolate()

        # 3. Truncate to shortest common length
        min_len = min(len(df_nc), len(df_c), len(df_rw))

        # Guard clause for empty/collapsed data
        if min_len < 10:
            raise ValueError(f"Dataframe collapsed to {min_len} rows. Check timestamp units.")

        df_rw = df_rw.iloc[:min_len]
        df_nc = df_nc.iloc[:min_len]
        df_c = df_c.iloc[:min_len]

        # 4. Force align index to Experiment Date (2022-10-06)
        start_time = pd.Timestamp("2022-10-06 22:00:00")
        timestamps = pd.date_range(start=start_time, periods=min_len, freq=freq)

        df = pd.DataFrame({
            "Real": df_rw.values,
            "NoCalib": df_nc.values,
            "Calib": df_c.values
        }, index=timestamps)

        return df.dropna()

    except Exception as e:
        print(f"Error loading data: {e}")
        return None


def calculate_mape(y_true, y_pred):
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def find_best_zoom_region(df, window_size=36):
    """Finds the time window where Calibration improves error the most."""
    error_nc = np.abs(df["NoCalib"] - df["Real"])
    error_c = np.abs(df["Calib"] - df["Real"])

    # Score: How much error did Calibration remove?
    improvement = (error_nc - error_c)

    # Smooth score
    rolling_imp = improvement.rolling(window=window_size).mean()

    # Find best index (using idxmax to get Timestamp, or simple argmax for integer)
    # Using integer argmax is safer for bounds calculation
    best_idx = np.argmax(rolling_imp.fillna(0).values)

    # Radius (samples) - 24 samples = 2 hours
    radius = 24

    # Safe Index Bounds
    start_idx = max(0, best_idx - radius)
    end_idx = min(len(df) - 1, best_idx + radius)

    return df.index[start_idx], df.index[end_idx]


def generate_plot(df):
    print(f"Generating plot... saving to {OUTPUT_FILE}")

    zoom_start, zoom_end = find_best_zoom_region(df)

    fig, ax = plt.subplots(figsize=(8, 8))

    # --- Main Plot ---
    ax.plot(df.index, df["Real"] / 1000, label="Ground Truth", color=COLOR_PALETTE[0], lw=1.5, alpha=0.9)
    ax.plot(df.index, df["NoCalib"] / 1000, label="No Calibration", color=COLOR_PALETTE[1], lw=1.5, linestyle="--",
            alpha=0.9)
    ax.plot(df.index, df["Calib"] / 1000, label="With Calibration", color=COLOR_PALETTE[2], lw=1.5, alpha=0.9)

    ax.set_ylabel("Power Draw [kW]", fontsize=20)
    ax.set_xlabel("Time [day/month]", fontsize=20)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper left', fontsize=16, framealpha=0.95, ncol=3)

    # --- Zoomed Inset ---
    axins = zoomed_inset_axes(ax, zoom=2.5, loc='lower right', bbox_to_anchor=(0.96, 0.08), bbox_transform=ax.transAxes)

    axins.plot(df.index, df["Real"] / 1000, color=COLOR_PALETTE[0], lw=2.5)
    axins.plot(df.index, df["NoCalib"] / 1000, color=COLOR_PALETTE[1], lw=2.5, linestyle="--")
    axins.plot(df.index, df["Calib"] / 1000, color=COLOR_PALETTE[2], lw=2.5)

    # Apply Zoom Limits
    axins.set_xlim(zoom_start, zoom_end)

    # Y-Limits for Zoom
    subset = df.loc[zoom_start:zoom_end]
    if not subset.empty:
        y_min = subset[["Real", "NoCalib", "Calib"]].min().min() / 1000
        y_max = subset[["Real", "NoCalib", "Calib"]].max().max() / 1000
        margin = (y_max - y_min) * 0.1
        axins.set_ylim(y_min - margin, y_max + margin)

    axins.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    axins.set_title("Zoomed Detail", fontsize=14)
    axins.grid(True, linestyle=':', alpha=0.7)

    mark_inset(ax, axins, loc1=2, loc2=4, fc="none", ec="black", lw=1.2, linestyle="--")

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, format="pdf", bbox_inches="tight")
    print("Plot saved.")


def print_statistics(df):
    mape_nc = calculate_mape(df["Real"], df["NoCalib"])
    mape_c = calculate_mape(df["Real"], df["Calib"])

    print("\n" + "=" * 60)
    print(f"{'EXPERIMENT 2: ACCURACY & COMPARISON':^60}")
    print("=" * 60)

    print(f"\n--- OpenDT Results ---")
    print(f"MAPE (No Calibration):          {mape_nc:6.2f}%")
    print(f"MAPE (With Calibration):        {mape_c:6.2f}%")
    print(f"Improvement:                    {mape_nc - mape_c:6.2f} pp")

    print(f"\n--- State-of-the-Art Benchmarks ---")
    print(f"MAPE (FootPrinter - Reported):  {MAPE_FP_REPORTED:6.2f}%")
    print(f"MAPE (FootPrinter - Quantified):{MAPE_FP_QUANTIFIED:6.2f}%")
    print(f"MAPE (M3SA Multi-Model):        {MAPE_MULTI:6.2f}%")
    print(f"MAPE (M3SA Meta-Model):         {MAPE_META:6.2f}%")

    print("-" * 60)
    print("Analysis:")

    # Compare against Quantified FootPrinter (Apple-to-Apple reproduction)
    diff_fp_quant = mape_c - MAPE_FP_QUANTIFIED
    if diff_fp_quant < 0:
        print(
            f"SUCCESS: OpenDT ({mape_c:.2f}%) reduces error vs FootPrinter (Quantified) by {abs(diff_fp_quant):.2f} pp.")

    # Compare against Meta-Model
    diff_meta = mape_c - MAPE_META
    if diff_meta < 0:
        print(f"SUCCESS: OpenDT outperforms M3SA Meta-Model by {abs(diff_meta):.2f} pp.")
    else:
        print(f"RESULT: OpenDT is within {diff_meta:.2f} pp of M3SA Meta-Model.")

    print("=" * 60 + "\n")


def main():
    df = load_and_align_data()
    if df is not None:
        generate_plot(df)
        print_statistics(df)


if __name__ == "__main__":
    main()