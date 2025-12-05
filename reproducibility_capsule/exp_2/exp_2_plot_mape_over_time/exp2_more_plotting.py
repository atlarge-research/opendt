# %% [markdown]
# # Experiment 2: Diagnostic - Why is Calibration Worse?
# This script generates "Explanation Plots" to diagnose the higher MAPE.
# 1. **Error Histogram:** visualizes Bias vs. Variance.
# 2. **Cumulative MAPE:** visualizes the "Warm-up Cost".

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import seaborn as sns

# --- CONFIGURATION ---
COLOR_PALETTE = ["#0072B2", "#E69F00", "#009E73"]  # Blue, Orange, Green
METRIC = "power_draw"

plt.rcParams.update({'font.size': 14})


# --- 1. DATA LOADING (Experiment 1 Logic) ---
def load_and_align():
    print("Loading data...")
    # Load raw
    df_nc = pd.read_parquet("../data/opendt_no_calibration.parquet").groupby("timestamp")[METRIC].sum()
    df_c = pd.read_parquet("../data/opendt_calibration.parquet").groupby("timestamp")[METRIC].sum()
    df_rw = pd.read_parquet("../data/real_world.parquet").groupby("timestamp")[METRIC].sum()

    # Align (Exp 1 Logic: Average down to 5min)
    def avg_n(s, n): return s.groupby(np.arange(len(s)) // n).mean()

    df_nc = avg_n(df_nc, 2)  # 2.5m -> 5m
    df_c = avg_n(df_c, 2)  # 2.5m -> 5m
    df_rw = avg_n(df_rw, 10)  # 30s -> 5m

    # Trim & Index
    min_len = min(len(df_nc), len(df_c), len(df_rw))
    df_nc, df_c, df_rw = df_nc.iloc[:min_len], df_c.iloc[:min_len], df_rw.iloc[:min_len]

    timestamps = pd.date_range(start="2022-10-06 22:00:00", periods=min_len, freq="5min")
    return pd.DataFrame({"Real": df_rw.values, "NoCalib": df_nc.values, "Calib": df_c.values}, index=timestamps)


df = load_and_align()

# --- 2. CALCULATE ERRORS ---
# Percentage Error (Signed) to see Bias
df["Err_NC"] = (df["NoCalib"] - df["Real"]) / df["Real"] * 100
df["Err_C"] = (df["Calib"] - df["Real"]) / df["Real"] * 100

# Absolute Error for MAPE
df["Abs_NC"] = df["Err_NC"].abs()
df["Abs_C"] = df["Err_C"].abs()

# Cumulative MAPE (Average MAPE up to time t)
df["Cum_MAPE_NC"] = df["Abs_NC"].expanding().mean()
df["Cum_MAPE_C"] = df["Abs_C"].expanding().mean()

print(f"Final MAPE -> No Calib: {df['Abs_NC'].mean():.2f}% | Calib: {df['Abs_C'].mean():.2f}%")

# %%
# --- 3. PLOT A: ERROR HISTOGRAM (BIAS vs VARIANCE) ---
# This proves if Calibration is "noisy"
plt.figure(figsize=(10, 6))
sns.kdeplot(df["Err_NC"], color=COLOR_PALETTE[1], fill=True, label="No Calibration", linewidth=3)
sns.kdeplot(df["Err_C"], color=COLOR_PALETTE[2], fill=True, label="With Calibration", linewidth=3)

plt.axvline(0, color='black', linestyle='--', alpha=0.5, label="Perfect Accuracy")
plt.title("Why Calibration Fails: Bias vs. Variance", fontsize=16)
plt.xlabel("Percentage Error [%] (Negative = Underestimation)", fontsize=14)
plt.ylabel("Density", fontsize=14)
plt.legend(fontsize=12)
plt.grid(True, alpha=0.3)
plt.xlim(-20, 20)  # Zoom in on the center
plt.tight_layout()
plt.savefig("exp2_diagnosis_histogram.pdf")
plt.show()

# INTERPRETATION:
# If Orange is sharp but shifted left -> Consistent Underestimation (Bias).
# If Green is centered at 0 but wide/fat -> Accurate average, but noisy (Variance).

# %%
# --- 4. PLOT B: CUMULATIVE MAPE (WARM-UP EFFECT) ---
# This proves if the "Bad Start" ruins the score
plt.figure(figsize=(10, 5))
plt.plot(df.index, df["Cum_MAPE_NC"], label="No Calibration (Cumulative)", color=COLOR_PALETTE[1], linewidth=2)
plt.plot(df.index, df["Cum_MAPE_C"], label="With Calibration (Cumulative)", color=COLOR_PALETTE[2], linewidth=2)

plt.title("Cumulative MAPE over Time (The 'Warm-Up' Penalty)", fontsize=16)
plt.ylabel("Average MAPE so far [%]", fontsize=14)
plt.xlabel("Time", fontsize=14)
plt.legend(fontsize=12)
plt.grid(True, alpha=0.4)
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))

plt.tight_layout()
plt.savefig("exp2_diagnosis_cumulative.pdf")
plt.show()

# INTERPRETATION:
# If Green starts high and drops steeply, the "bad score" is just due to initialization.
# If Green stays above Orange, the calibration model is simply too reactive/noisy.