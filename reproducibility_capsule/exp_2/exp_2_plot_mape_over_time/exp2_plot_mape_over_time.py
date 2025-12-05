# %% [markdown]
# # Experiment 2: Calibration Lag Diagnosis
# This script "slides" the simulation data against the real world data to find the optimal time alignment.
# If calibration improves after shifting, the issue was purely timestamp misalignment.

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

# --- CONFIGURATION ---
COLOR_PALETTE = ["#0072B2", "#E69F00", "#009E73"]
METRIC = "power_draw"
ROLLING_WINDOW = 12
plt.rcParams.update({'font.size': 18})


# %%
# --- 1. LOAD & BASIC ALIGN (Exp 1 Method) ---
def load_basic_aligned():
    print("Loading data...")
    path_nc = "../data/opendt_no_calibration.parquet"
    path_c = "../data/opendt_calibration.parquet"
    path_rw = "../data/real_world.parquet"

    # Load
    df_nc = pd.read_parquet(path_nc).groupby("timestamp")[METRIC].sum()
    df_c = pd.read_parquet(path_c).groupby("timestamp")[METRIC].sum()
    df_rw = pd.read_parquet(path_rw).groupby("timestamp")[METRIC].sum()

    # Downsample (Exp 1 Logic)
    # RW: 30s -> 5min (avg 10)
    df_rw = df_rw.groupby(np.arange(len(df_rw)) // 10).mean()
    # Sim: 2.5m -> 5min (avg 2)
    df_nc = df_nc.groupby(np.arange(len(df_nc)) // 2).mean()
    df_c = df_c.groupby(np.arange(len(df_c)) // 2).mean()

    # Trim to shortest common length
    min_len = min(len(df_nc), len(df_c), len(df_rw))
    df_nc = df_nc.iloc[:min_len]
    df_c = df_c.iloc[:min_len]
    df_rw = df_rw.iloc[:min_len]

    return df_nc, df_c, df_rw, min_len


df_nc, df_c, df_rw, min_len = load_basic_aligned()

# %%
# --- 2. THE LAG HUNTER ---
# We calculate MAPE for various shifts to see if moving the data fixes the error.
print("\n--- Hunting for Optimal Lag ---")
best_shift = 0
best_mape = 100.0
stats = []

# Search range: +/- 12 steps (approx +/- 1 hour)
shifts = range(-12, 13)

for shift in shifts:
    # Shift the CALIBRATED data
    # shift > 0 moves data down (delayed), shift < 0 moves data up (earlier)
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
print(f"Original MAPE (Shift 0): {[s[1] for s in stats if s[0] == 0][0]:.2f}%")
print(f"Best MAPE (Shift {best_shift}):    {best_mape:.2f}%")

# %%
# --- 3. APPLY BEST SHIFT & PLOT ---
# Apply the discovered shift to BOTH simulations
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

# Recalculate Rolling MAPE on aligned data
ape_nc = np.abs((plot_df["Real"] - plot_df["NoCalib"]) / plot_df["Real"]) * 100
ape_c = np.abs((plot_df["Real"] - plot_df["Calib"]) / plot_df["Real"]) * 100

smooth_mape_nc = ape_nc.rolling(ROLLING_WINDOW).mean()
smooth_mape_c = ape_c.rolling(ROLLING_WINDOW).mean()

# --- PLOT ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [1, 1]})

# Top: MAPE
ax1.grid(True, linestyle='--', alpha=0.6)
ax1.plot(smooth_mape_nc.index, smooth_mape_nc, label="No Calibration", color=COLOR_PALETTE[1], lw=2, linestyle="--")
ax1.plot(smooth_mape_c.index, smooth_mape_c, label="With Calibration", color=COLOR_PALETTE[2], lw=2.5)

# NFR Line
ax1.axhline(y=10, color='red', linestyle=':', linewidth=2, alpha=0.8)
if len(smooth_mape_nc.dropna()) > 0:
    ax1.text(smooth_mape_nc.dropna().index[0], 10.5, "NFR Threshold (10%)", color='red', fontsize=14, fontweight='bold')

ax1.set_ylabel("MAPE [%]", fontsize=20)
ax1.legend(fontsize=16, loc="upper right")
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))

# Bottom: Power Draw
ax2.grid(True, linestyle='-', alpha=0.3)
ax2.plot(plot_df.index, plot_df["Real"] / 1000, label="Ground Truth", color=COLOR_PALETTE[0], lw=1.5, alpha=0.8)
ax2.plot(plot_df.index, plot_df["NoCalib"] / 1000, label="No Calibration", color=COLOR_PALETTE[1], lw=1.5,
         linestyle="--", alpha=0.9)
ax2.plot(plot_df.index, plot_df["Calib"] / 1000, label="With Calibration", color=COLOR_PALETTE[2], lw=1.5, alpha=0.9)

ax2.set_ylabel("Power Draw [kW]", fontsize=20)
ax2.set_xlabel("Time [day/month]", fontsize=20)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
ax2.legend(fontsize=16, loc="lower right", ncol=3)

# Add stats to title or text
plt.suptitle(f"Aligned Results (Shifted {best_shift} steps)\n"
             f"MAPE (No Calib): {ape_nc.mean():.2f}% | MAPE (Calib): {ape_c.mean():.2f}%",
             fontsize=16, y=0.92)

plt.tight_layout()
plt.savefig("exp2_lag_corrected_analysis.pdf", format="pdf", bbox_inches="tight")
plt.show()