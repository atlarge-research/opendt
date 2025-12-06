import pandas as pd
import numpy as np
import os
import glob

# --- CONFIGURATION ---
DATA_FOLDER = '../data/raw_uncalibrated'

# 1. Reference Start Time (Run 1 starts here)
REFERENCE_START_TIME = pd.Timestamp("2022-10-06 22:00:00")

# 2. Timing Logic (Total 167 runs spread over 7 days)
TOTAL_DAYS = 7
TOTAL_RUNS = 167
# Delta is the spacing between consecutive runs (approx 1 hour)
TIME_DELTA = pd.Timedelta(days=TOTAL_DAYS) / TOTAL_RUNS


def process_single_run(run_id, file_path):
    print(f"Processing Run {run_id}...")
    try:
        # Load Data
        df = pd.read_parquet(file_path)
        cols = df.columns.tolist()

        # Identify Time Column
        if "timestamp" in cols:
            time_col = "timestamp"
        elif "time" in cols:
            time_col = "time"
        else:
            print(f"  Skipping Run {run_id}: No timestamp column.")
            return None

        # Identify CPU Column
        cpu_col = next((c for c in cols if "cpu" in c.lower() and "util" in c.lower()), None)
        if not cpu_col:
            cpu_col = next((c for c in cols if "cpu" in c.lower() and "usage" in c.lower()), None)
        if not cpu_col:
            print(f"  Skipping Run {run_id}: No CPU column.")
            return None

        # 1. Group by timestamp to average out core readings if necessary
        df_grouped = df.groupby(time_col)[cpu_col].mean().reset_index()
        df_grouped.rename(columns={cpu_col: 'avg_cpu_utilization'}, inplace=True)

        # 2. Calculate Start Time for THIS SPECIFIC RUN
        # Formula: Start = Reference + (RunID - 1) * Delta
        run_start_time = REFERENCE_START_TIME + (run_id - 1) * TIME_DELTA

        # 3. Calculate Absolute Datetime
        df_grouped['datetime'] = run_start_time + pd.to_timedelta(df_grouped[time_col], unit='ms')

        # Add Run ID (Integer)
        df_grouped['run_id'] = int(run_id)

        return df_grouped

    except Exception as e:
        print(f"  Error processing Run {run_id}: {e}")
        return None


def generate_summary_metrics(df):
    print("\n--- Generating Summary Metrics ---")

    # Group by the integer run_id
    grouped = df.groupby('run_id')

    # 1. Average CPU
    avg_cpu = grouped['avg_cpu_utilization'].mean()

    # 2. Start Time (Min datetime for each run)
    start_times = grouped['datetime'].min()

    # 3. Estimated Completion Duration (Latency)
    # Duration = End Time - Start Time
    end_times = grouped['datetime'].max()
    durations = end_times - start_times

    # Create Summary DataFrame
    summary_df = pd.DataFrame({
        'run_id': avg_cpu.index.astype(int),
        'start_time': start_times.values,
        'average_cpu': avg_cpu.values,
        'estimated_completion_duration': durations.values
    })

    # Sort by Run ID (1, 2, 3...)
    summary_df = summary_df.sort_values(by='run_id')

    # Save to CSV
    output_filename = 'run_summary_metrics.csv'
    summary_df.to_csv(output_filename, index=False)

    print(f"Success! Processed {len(summary_df)} runs.")
    print(f"Summary saved to: {output_filename}")
    print("Preview:")
    print(summary_df.head())


def main():
    abs_path = os.path.abspath(DATA_FOLDER)
    print(f"Searching for data in: {abs_path}")

    # Find all host.parquet files
    search_pattern = os.path.join(DATA_FOLDER, "run_*", "**", "host.parquet")
    files = glob.glob(search_pattern, recursive=True)

    if not files:
        print("No 'host.parquet' files found!")
        print(f"Please check if the folder exists: {abs_path}")
        return

    print(f"Found {len(files)} files.")

    all_results = []

    for file_path in files:
        # Robustly extract run_id from path
        parts = file_path.split(os.sep)
        run_folder = next((p for p in parts if p.startswith("run_")), None)

        if run_folder:
            try:
                # Extract integer ID (e.g., "run_132" -> 132)
                run_id = int(run_folder.split('_')[-1])

                result_df = process_single_run(run_id, file_path)
                if result_df is not None:
                    all_results.append(result_df)
            except ValueError:
                continue

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)

        # Only generate the summary, do not save the detailed intermediate file
        generate_summary_metrics(final_df)
    else:
        print("No data was successfully processed.")


if __name__ == "__main__":
    main()