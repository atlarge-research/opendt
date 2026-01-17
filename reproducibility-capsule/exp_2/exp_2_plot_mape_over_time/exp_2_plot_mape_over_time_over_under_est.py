import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# --- CONFIGURATION ---
COLOR_PALETTE = ["#0072B2", "#E69F00", "#009E73"]
METRIC = "power_draw"
ROLLING_WINDOW = 12

# INCREASED DEFAULT FONT SIZE FROM 18 TO 22
plt.rcParams.update({'font.size': 22})


# %%
# --- 1. LOAD & BASIC ALIGN (Exp 1 Method) ---
def load_basic_aligned():
    print("Loading data...")
    path_nc = "../data/opendt_non_calibrated.parquet"
    path_c = "../data/opendt_calibrated.parquet"
    path_rw = "../data/real_world.parquet"

    # Check if files exist
    if not os.path.exists(path_nc) or not os.path.exists(path_rw):
        print("Warning: Data files not found. Ensure paths are correct.")
        return pd.Series(), pd.Series(), pd.Series(), 0

    # Load
    df_nc = pd.read_parquet(path_nc).groupby("timestamp")[METRIC].sum()
    df_c = pd.read_parquet(path_c).groupby("timestamp")[METRIC].sum()
    df_rw = pd.read_parquet(path_rw).groupby("timestamp")[METRIC].sum()

    # Downsample
    df_rw = df_rw.groupby(np.arange(len(df_rw)) // 10).mean()
    df_nc = df_nc.groupby(np.arange(len(df_nc)) // 2).mean()
    df_c = df_c.groupby(np.arange(len(df_c)) // 2).mean()

    # Trim to shortest common length
    min_len = min(len(df_nc), len(df_c), len(df_rw))
    df_nc = df_nc.iloc[:min_len]
    df_c = df_c.iloc[:min_len]
    df_rw = df_rw.iloc[:min_len]

    return df_nc, df_c, df_rw, min_len


df_nc, df_c, df_rw, min_len = load_basic_aligned()

if min_len > 0:
    # %%
    # --- 2. THE LAG HUNTER ---
    print("\n--- Hunting for Optimal Lag ---")
    best_shift = 0
    best_mape = 100.0
    stats = []

    # Search range: +/- 12 steps (approx +/- 1 hour)
    shifts = range(-12, 13)

    for shift in shifts:
        # Shift the CALIBRATED data
        sim_shifted = df_c.shift(shift).dropna()

        # Align Real World to the valid shifted range
        rw_aligned = df_rw.loc[sim_shifted.index]

        # Calc MAPE
        mask = rw_aligned != 0
        mape = np.mean(np.abs((rw_aligned[mask] - sim_shifted[mask]) / rw_aligned[mask])) * 100

        stats.append((shift, mape))
        if mape < best_mape:
            best_mape = mape
            best_shift = shift

    print(f"Optimal Shift Found: {best_shift} steps")
    original_mape = [s[1] for s in stats if s[0] == 0][0]
    print(f"Original MAPE (Shift 0): {original_mape:.0f}%")
    print(f"Best MAPE (Shift {best_shift}):    {best_mape:.0f}%")

    # %%
    # --- 3. APPLY BEST SHIFT & PLOT (BIGGER TEXT) ---
    df_nc_shifted = df_nc.shift(best_shift)
    df_c_shifted = df_c.shift(best_shift)

    # Re-align index for plotting
    start_time = pd.Timestamp("2022-10-06 22:00:00")
    timestamps = pd.date_range(start=start_time, periods=min_len, freq="5min")

    # Create Plotting DataFrame
    plot_df = pd.DataFrame({
        "Real": df_rw.values,
        "NoCalib": df_nc_shifted.values,
        "Calib": df_c_shifted.values
    }, index=timestamps).dropna()

    # --- CALCULATE BIAS STATES ---
    bias_nc_mask = plot_df["NoCalib"] > plot_df["Real"]
    bias_c_mask = plot_df["Calib"] > plot_df["Real"]

    # Recalculate Rolling MAPE
    ape_nc = np.abs((plot_df["Real"] - plot_df["NoCalib"]) / plot_df["Real"]) * 100
    ape_c = np.abs((plot_df["Real"] - plot_df["Calib"]) / plot_df["Real"]) * 100

    smooth_mape_nc = ape_nc.rolling(ROLLING_WINDOW).mean().dropna()
    smooth_mape_c = ape_c.rolling(ROLLING_WINDOW).mean().dropna()

    # --- SETUP SINGLE SUBPLOT ---
    fig, ax = plt.subplots(figsize=(10, 5))

    # --- A. INTEGRATED BIAS STRIPS ---
    y_top = 17.5
    strip_height = 0.7
    y_nc_bottom = y_top - strip_height  # 16.8
    y_c_bottom = y_nc_bottom - strip_height  # 16.1

    # 1. No Calib Strip (Top)
    ax.fill_between(plot_df.index, y_nc_bottom, y_top, where=bias_nc_mask,
                    color=COLOR_PALETTE[1], alpha=1.0, linewidth=0, step='mid', zorder=1)
    ax.fill_between(plot_df.index, y_nc_bottom, y_top, where=~bias_nc_mask,
                    color=COLOR_PALETTE[1], alpha=0.4, linewidth=0, step='mid', zorder=1)

    # 2. Calibrated Strip (Below it)
    ax.fill_between(plot_df.index, y_c_bottom, y_nc_bottom, where=bias_c_mask,
                    color=COLOR_PALETTE[2], alpha=1.0, linewidth=0, step='mid', zorder=1)
    ax.fill_between(plot_df.index, y_c_bottom, y_nc_bottom, where=~bias_c_mask,
                    color=COLOR_PALETTE[2], alpha=0.4, linewidth=0, step='mid', zorder=1)

    # 3. White separator line
    ax.axhline(y=y_nc_bottom, color='white', linewidth=1, zorder=2)

    # 4. Text Labels for the Strips
    label_x_pos = plot_df.index[0]
    # Removed explicit fontsize here to inherit the larger global font, or you can set fontsize=14

    # --- B. MAIN PLOT ELEMENTS ---

    # Emphasis Boxes
    date_9_10 = pd.Timestamp("2022-10-09 00:00:00")
    ax.axvspan(date_9_10 - pd.Timedelta(hours=5), date_9_10 + pd.Timedelta(hours=3),
               ymin=0, ymax=0.05, facecolor='darkgrey', alpha=1.0, zorder=3)

    date_11_10 = pd.Timestamp("2022-10-11 05:00:00")
    ax.axvspan(date_11_10 - pd.Timedelta(hours=6), date_11_10 + pd.Timedelta(hours=6),
               ymin=0, ymax=0.05, facecolor='black', alpha=0.9, zorder=3)

    # Grid
    ax.grid(True, linestyle='--', alpha=0.6)

    # Lines
    ax.plot(smooth_mape_nc.index, smooth_mape_nc, label="No Calibration",
            color=COLOR_PALETTE[1], lw=2, linestyle="--", zorder=4)
    ax.plot(smooth_mape_c.index, smooth_mape_c, label="With Calibration",
            color=COLOR_PALETTE[2], lw=2.5, zorder=4)

    # Thresholds
    ax.axhline(y=10, color='red', linestyle=':', linewidth=2, alpha=0.8)
    fp_val = 7.86
    ax.axhline(y=fp_val, color=COLOR_PALETTE[0], linestyle='-.', linewidth=2, alpha=0.8)

    # Threshold Labels - INCREASED SIZE (14 -> 16)
    if len(smooth_mape_nc) > 0:
        ax.text(smooth_mape_nc.index[0], 10.5, "NFR Threshold (10%)",
                color='red', fontsize=16, fontweight='bold')
        ax.text(smooth_mape_nc.index[0], fp_val + 0.5, f"FootPrinter (7.86%)",
                color=COLOR_PALETTE[0], fontsize=16, fontweight='bold')

    # Axes Labels - INCREASED SIZE (20 -> 24)
    ax.set_ylabel("MAPE [%]", fontsize=24)
    ax.set_xlabel("Time [day/month]", fontsize=24)

    # --- Y-AXIS FORMATTING ---
    ax.set_ylim(0, 17.5)
    ax.set_yticks([0, 5, 10, 15])

    ax.set_xlim(plot_df.index[0], plot_df.index[-1])

    # Date Formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))

    # Tick Labels - INCREASED SIZE (20 -> 22)
    ax.tick_params(axis='x', labelsize=22)
    ax.tick_params(axis='y', labelsize=22)

    # Legend - INCREASED SIZE (14 -> 16)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 0.92),
              ncol=2, framealpha=0.95, fontsize=16)

    plt.subplots_adjust(top=0.95, bottom=0.15)
    plt.savefig("fig_exp_2_final_bigger_text.pdf", format="pdf", bbox_inches="tight")
    plt.show()

    # %%
    # --- 4. TERMINAL STATISTICS (Unchanged) ---
    print("\n" + "=" * 60)
    print("        EXP 2: DETAILED ACCURACY & BIAS STATISTICS")
    print("=" * 60)


    def print_model_stats(name, mape_series, nfr_threshold=10.0):
        avg_mape = mape_series.mean()
        above_count = (mape_series > nfr_threshold).sum()
        below_count = (mape_series <= nfr_threshold).sum()
        total_count = len(mape_series)
        pct_above = (above_count / total_count) * 100
        pct_below = (below_count / total_count) * 100

        print(f"\n--- {name} (General Accuracy) ---")
        print(f"1. Average MAPE:           {avg_mape:.2f}%")
        print(f"2. Time > 10% (Violation): {pct_above:.1f}%")
        print(f"3. Time <= 10% (Compliant):{pct_below:.1f}%")


    print_model_stats("NO CALIBRATION", smooth_mape_nc)
    print_model_stats("WITH CALIBRATION", smooth_mape_c)

    print("\n" + "-" * 60)
    print("        DIRECTIONAL BIAS (UNDER vs OVER)")
    print("-" * 60)


    def analyze_bias(real, model, name):
        diff = model - real
        total = len(diff)
        n_over = (diff > 0).sum()
        n_under = (diff < 0).sum()
        pct_over = (n_over / total) * 100
        pct_under = (n_under / total) * 100

        print(f"\n--- {name} ---")
        print(f"   > Overestimation  (Model > Real): {pct_over:.2f}%")
        print(f"   > Underestimation (Model < Real): {pct_under:.2f}%")


    analyze_bias(plot_df["Real"], plot_df["NoCalib"], "NO CALIBRATION")
    analyze_bias(plot_df["Real"], plot_df["Calib"], "WITH CALIBRATION")

    print("\n" + "=" * 60)

else:
    print("No data available to process.")