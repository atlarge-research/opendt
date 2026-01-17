# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# --- CONFIGURATION ---
COLOR_PALETTE = ["#0072B2", "#E69F00", "#009E73"]
METRIC = "power_draw"
ROLLING_WINDOW = 12
plt.rcParams.update({'font.size': 18})


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
    # --- 3. APPLY BEST SHIFT & PLOT ---
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

    # Recalculate Rolling MAPE
    ape_nc = np.abs((plot_df["Real"] - plot_df["NoCalib"]) / plot_df["Real"]) * 100
    ape_c = np.abs((plot_df["Real"] - plot_df["Calib"]) / plot_df["Real"]) * 100

    smooth_mape_nc = ape_nc.rolling(ROLLING_WINDOW).mean().dropna()
    smooth_mape_c = ape_c.rolling(ROLLING_WINDOW).mean().dropna()

    # --- PLOT (MAPE ONLY) ---
    fig, ax = plt.subplots(figsize=(8, 4))

    # --- NEW: GREY EMPHASIS BOXES ---
    # Plotted FIRST so they appear behind the lines

    # 1. Box around 09/10 (Performance is equal)
    date_9_10 = pd.Timestamp("2022-10-09 00:00:00")
    ax.axvspan(date_9_10 - pd.Timedelta(hours=5),
               date_9_10 + pd.Timedelta(hours=3),
               ymin=0, ymax=0.05,  # Covers bottom 20%
               color='#000', alpha=0.3, lw=0)  # Alpha 0.3 for visibility

    # 2. Box around 11/10 (No Calibration is better)
    date_11_10 = pd.Timestamp("2022-10-11 05:00:00")
    ax.axvspan(date_11_10 - pd.Timedelta(hours=6),
               date_11_10 + pd.Timedelta(hours=6),
               ymin=0, ymax=0.05,
               color='#000', alpha=0.9, lw=0)

    # --- MAIN PLOT LINES ---
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.plot(smooth_mape_nc.index, smooth_mape_nc, label="No Calibration", color=COLOR_PALETTE[1], lw=2, linestyle="--")
    ax.plot(smooth_mape_c.index, smooth_mape_c, label="With Calibration", color=COLOR_PALETTE[2], lw=2.5)

    # Threshold Lines
    ax.axhline(y=10, color='red', linestyle=':', linewidth=2, alpha=0.8)
    fp_val = 7.86
    ax.axhline(y=fp_val, color=COLOR_PALETTE[0], linestyle='-.', linewidth=2, alpha=0.8)

    # Labels on graph
    if len(smooth_mape_nc) > 0:
        ax.text(smooth_mape_nc.index[0], 10.5, "NFR Threshold (10%)",
                color='red', fontsize=14, fontweight='bold')
        ax.text(smooth_mape_nc.index[0], fp_val + 0.4, f"FootPrinter ({fp_val}%)",
                color=COLOR_PALETTE[0], fontsize=14, fontweight='bold')

    # Formatting
    ax.set_ylabel("MAPE [%]", fontsize=20)
    ax.set_xlabel("Time [day/month]", fontsize=20)
    ax.legend(fontsize=16, loc="upper left", ncol=2)

    # Date Formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))

    plt.tight_layout()
    plt.savefig("fig_exp_2_plot_mape_over_time.pdf", format="pdf", bbox_inches="tight")
    plt.show()

    # %%
    # --- 4. TERMINAL STATISTICS ---
    print("\n" + "=" * 60)
    print("        EXP 2: DETAILED ACCURACY & BIAS STATISTICS")
    print("=" * 60)


    # --- A. General MAPE Stats ---
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

    # --- B. Underestimation vs Overestimation ---
    print("\n" + "-" * 60)
    print("        DIRECTIONAL BIAS (UNDER vs OVER)")
    print("-" * 60)


    def analyze_bias(real, model, name):
        """
        Calculates percentage of time steps where the model
        predicts higher (Over) or lower (Under) than Real data.
        """
        # Calculate raw difference: Model - Real
        diff = model - real
        total = len(diff)

        # Count occurrences
        n_over = (diff > 0).sum()
        n_under = (diff < 0).sum()
        n_exact = (diff == 0).sum()  # Rare with floats, but good to know

        # Calculate percentages
        pct_over = (n_over / total) * 100
        pct_under = (n_under / total) * 100

        print(f"\n--- {name} ---")
        print(f"   > Overestimation  (Model > Real): {pct_over:.2f}%")
        print(f"   > Underestimation (Model < Real): {pct_under:.2f}%")
        if n_exact > 0:
            print(f"   > Exact Match:                    {(n_exact / total) * 100:.2f}%")


    # Note: We use the raw 'plot_df' values here, not the smoothed MAPE
    analyze_bias(plot_df["Real"], plot_df["NoCalib"], "NO CALIBRATION")
    analyze_bias(plot_df["Real"], plot_df["Calib"], "WITH CALIBRATION")

    print("\n" + "=" * 60)

else:
    print("No data available to process.")