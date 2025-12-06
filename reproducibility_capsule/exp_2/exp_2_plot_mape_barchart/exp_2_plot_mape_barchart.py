import matplotlib.pyplot as plt
import numpy as np

# --- 1. CONFIGURATION & STYLE ---
# Exact palette from your reference code (Wong/Okabe-Ito friendly)
COLOR_PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#F0E442", "#8B4513",
    "#56B4E9", "#F0A3FF", "#FFB400", "#00BFFF", "#90EE90", "#FF6347", "#8A2BE2",
    "#CD5C5C", "#4682B4", "#FFDEAD", "#32CD32", "#D3D3D3", "#999999"
]


def generate_mape_barplot():
    print("Generating MAPE comparison plot...")

    # --- 2. DATA PREPARATION ---
    # Methods ordered for display (Top to Bottom)
    methods = ['NFR2', 'FootPrinter', 'Multi-Model', 'Meta-Model', 'OpenDT', 'OpenDT-C ']
    # Updated FootPrinter value to 7.86% as requested
    mapes = [10.0, 7.86, 7.59, 3.81, 5.13, 4.39]

    # --- 3. COLOR ASSIGNMENT ---
    # Using the provided palette indices to ensure consistency and accessibility
    bar_colors = [
        COLOR_PALETTE[3],  # NFR: Vermillion (Red) -> Good for Limits/Alerts
        COLOR_PALETTE[1],  # FootPrinter: Orange -> Matches your Time Series plot
        COLOR_PALETTE[7],  # MultiModel: Sky Blue -> Distinct SOTA
        COLOR_PALETTE[4],  # MetaModel: Reddish Purple -> Distinct SOTA
        COLOR_PALETTE[2],  # OpenDT: Bluish Green -> Matches your Time Series plot
        COLOR_PALETTE[0]  # OpenDT-C: Blue -> Strong color for best result
    ]

    # --- 4. PLOTTING ---
    fig, ax = plt.subplots(figsize=(8, 4))

    # Horizontal Bar Chart
    bars = ax.barh(methods, mapes, color=bar_colors, edgecolor='black', linewidth=1)

    # --- 5. FORMATTING ---
    # Grid behind bars
    ax.set_axisbelow(True)
    ax.grid(True, axis='x', linestyle='-', alpha=0.5)

    # Invert Y axis so 'NFR' is at the top
    ax.invert_yaxis()

    # X-Axis configuration
    ax.set_xlim(0, 12)  # Scale from 0% to 12%
    ax.set_xlabel("MAPE [%]", fontsize=22, labelpad=10)

    # Tick formatting to match your style sizes
    ax.tick_params(axis='x', labelsize=20)
    ax.tick_params(axis='y', labelsize=20)

    # --- 6. ANNOTATIONS ---
    # Add vertical dashed line for NFR Limit (10%)
    ax.axvline(x=10, color=COLOR_PALETTE[3], linestyle='--', linewidth=2, alpha=0.8)

    # Label for NFR Limit
    ax.text(10.2, -0.7, 'Limit', color=COLOR_PALETTE[3],
            fontsize=18, fontweight='bold', va='top')

    # Add numeric value labels next to each bar
    for bar in bars:
        width = bar.get_width()
        y = bar.get_y() + bar.get_height() / 2

        ax.text(width + 0.2, y,
                f'{width:.2f}%',
                va='center', ha='left',
                fontsize=18, fontweight='bold', color='black')

    plt.tight_layout()

    # Save
    output_filename = "exp_2_plot_mape_barchart.pdf"
    plt.savefig(output_filename, format='pdf', bbox_inches='tight')
    print(f"Plot saved to {output_filename}")
    plt.show()


if __name__ == "__main__":
    generate_mape_barplot()