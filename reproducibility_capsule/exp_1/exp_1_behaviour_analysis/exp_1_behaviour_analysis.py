import matplotlib.pyplot as plt
import numpy as np

# --- 1. CONFIGURATION & STYLE ---
COLOR_PALETTE = [
    "#0072B2",  # Blue (Used for Underestimation)
    "#E69F00",  # Orange (Used for Overestimation)
]


def generate_horizontal_bias_plot():
    """
    Generates a Horizontal Stacked Bar Chart comparing Underestimation vs Overestimation ratios.
    Based on the text:
    - FootPrinter: 99% Under, 1% Over
    - OpenDT: 44% Under, 56% Over
    """
    print("Generating horizontal simulation behavior plot...")

    # --- DATA FROM TEXT ---
    # Listed bottom-to-top for standard Matplotlib barh (OpenDT bottom, FootPrinter top)
    # OR reversed here so FootPrinter appears at the top if y-axis is inverted or naturally sorted
    # Let's use this order so "FootPrinter" is the top bar.
    models = ['OpenDT', 'FootPrinter']

    # Ratios corresponding to [OpenDT, FootPrinter]
    underestimation = np.array([44, 99])
    overestimation = np.array([56, 1])

    # --- PLOTTING ---
    fig, ax = plt.subplots(figsize=(8, 4))  # Shape 8x4

    # Height of the bars
    bar_height = 0.5

    # Plot Underestimation (Left bar)
    p1 = ax.barh(models, underestimation, height=bar_height,
                 label='Underestimation', color=COLOR_PALETTE[0], edgecolor='black', linewidth=1.5)

    # Plot Overestimation (Right bar, stacked on 'underestimation')
    # Note: using 'left' instead of 'bottom' for horizontal bars
    p2 = ax.barh(models, overestimation, height=bar_height, left=underestimation,
                 label='Overestimation', color=COLOR_PALETTE[1], edgecolor='black', linewidth=1.5)

    # --- FORMATTING ---

    # X-Axis formatting (Percentage)
    ax.set_xlabel("Ratio of Samples [%]", fontsize=22, labelpad=10)
    ax.set_xlim(0, 100)
    ax.tick_params(axis='x', labelsize=20)

    # Y-Axis formatting (Model Names)
    ax.tick_params(axis='y', labelsize=22)

    # Grid (Vertical dashed lines for horizontal plot)
    ax.grid(True, axis='x', linestyle='--', alpha=0.7, zorder=0)
    ax.set_axisbelow(True)

    # --- ANNOTATIONS (Adding the numbers inside the bars) ---
    def add_labels(rects):
        for rect in rects:
            width = rect.get_width()
            if width > 5:  # Only label if bar is wide enough to fit text
                ax.text(rect.get_x() + width / 2.,
                        rect.get_y() + rect.get_height() / 2.,
                        f'{int(width)}%',
                        ha='center', va='center', color='white', fontsize=20, fontweight='bold')

    add_labels(p1)
    add_labels(p2)

    # --- LEGEND ---
    # Adjusted bbox_to_anchor to fit the 8x4 aspect ratio nicely
    leg = ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.25),
                    ncol=2, fontsize=18, frameon=False)

    # Thicken legend patches for visibility
    for patch in leg.get_patches():
        patch.set_height(10)
        patch.set_y(-2)

    plt.tight_layout()

    # --- SAVE ---
    output_filename = "exp1_bias_ratio_plot_horizontal.pdf"
    plt.savefig(output_filename, format="pdf", bbox_inches="tight")
    print(f"Plot saved as '{output_filename}'")


if __name__ == "__main__":
    generate_horizontal_bias_plot()