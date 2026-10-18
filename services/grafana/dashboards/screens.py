"""The three screens: each panel and its place, (name, panel, x, y, width, height) on a 24-column grid."""

import steps
from form import HOSTS, control, group, picker, stepper
from layout import auto, custom, dashboard, grid, picked, row, when
from panels import PERIODS
from plots import (
    ROWS,
    TILES,
    arrivals,
    catalog,
    co2,
    decisions,
    groups,
    heatmap,
    hosts,
    power,
    twin_state,
)


def screen(uid, title, placed, rows=(), panels=None, variables=()):
    """The placed panels at the top, then the `rows` of the other `panels`."""
    top = row("", grid([(name, x, y, w, h) for name, _, x, y, w, h in placed]))
    panels = {name: panel for name, panel, *_ in placed} | (panels or {})
    return dashboard(uid, title, panels, [top, *rows], variables)


# the tiles: Simulated time and Scheduler wide, the others in four columns
TILE_PLACES = [
    ("twin-time", 6, 0, 6),
    ("measured-now", 12, 0, 3),
    ("opendt-now", 15, 0, 3),
    ("mape-now", 18, 0, 3),
    ("co2-now", 21, 0, 3),
    ("scheduler-now", 6, 3, 6),
    ("in-use-now", 12, 3, 3),
    ("cpu-now", 15, 3, 3),
    ("waiting-now", 18, 3, 3),
    ("zone-now", 21, 3, 3),
]
PICKERS = {f"pick-{i}": picker(title, plots) for i, (title, plots) in enumerate(ROWS.items())}

detailed = screen(
    "opendt-overview",
    "OpenDT, detailed",
    [
        ("control", control("opendt-overview", [HOSTS]), 0, 0, 6, 11),
        ("decisions", decisions, 0, 11, 6, 5),  # what the markers on the graphs stand for
        *[(name, TILES[name], x, y, w, 3) for name, x, y, w in TILE_PLACES],
        ("power", power, 6, 6, 6, 10),
        ("co2", co2, 12, 6, 6, 10),
        ("hosts", hosts, 18, 6, 6, 10),
    ],
    rows=[
        row(
            "Plots", grid([(name, 6 * i, 0, 6, 7) for i, name in enumerate(PICKERS)]), collapse=True
        ),
        # a row shows while one of its plots is not hidden
        *[
            row(
                title, auto([(key, picked(key)) for key in plots], len(plots)), shown=picked(*plots)
            )
            for title, plots in ROWS.items()
        ],
    ],
    panels=PICKERS | {key: plot for plots in ROWS.values() for key, plot in plots.items()},
    variables=[
        custom("period", "Interval", PERIODS, current="day"),
        # the hidden plots; "none", so the list is never empty
        custom(
            "hidden",
            "Hidden plots",
            ["none", *(k for p in ROWS.values() for k in p)],
            True,
            ["none"],
        ),
    ],
)

# the physical twin on the left, the digital twin on the right
simple = screen(
    "opendt-simple",
    "OpenDT, simple",
    [
        ("control", control("opendt-simple", [HOSTS], period=False), 0, 0, 6, 13),
        ("twin-state", twin_state, 0, 13, 6, 8),
        ("physical", TILES["measured-now"], 6, 0, 9, 4),
        ("power-simple", power, 6, 4, 9, 9),
        ("arrivals", arrivals, 6, 13, 9, 8),
        ("twin", TILES["opendt-now"], 15, 0, 9, 4),
        ("heatmap", heatmap, 15, 4, 9, 9),
        ("decisions", decisions, 15, 13, 9, 8),
    ],
)

groups_control = control("opendt-topology", group(1) + group(2) + group(3), period=False)
topology = screen(
    "opendt-topology",
    "OpenDT, topology",
    [
        ("control", groups_control, 0, 0, 6, 21),
        ("groups", groups, 6, 0, 18, 5),
        ("catalog", catalog, 6, 5, 18, 8),
        ("hosts-topology", hosts, 6, 13, 18, 8),
    ],
)

# the Tutorial screen: the twin's state at the top, then the current step, its question and its plots
STEPS = [(use_case, step) for use_case, items in steps.STEPS.items() for step in items]
TEXTS = {
    f"text-{n}": steps.text(f"Step {n} of {len(STEPS)}: {use_case}", step)
    for n, (use_case, step) in enumerate(STEPS, 1)
}
# each plot once, shown at the steps that name it
AT = {}
for n, (_, step) in enumerate(STEPS, 1):
    for key in step["plots"]:
        AT.setdefault(key, []).append(str(n))
tutorial = screen(
    "opendt-tutorial",
    "OpenDT, tutorial",
    [
        ("control", control("opendt-tutorial", [HOSTS]), 0, 0, 6, 11),
        ("steps", stepper(len(STEPS)), 0, 11, 6, 3),
        *[(name, TILES[name], x, y, w, 3) for name, x, y, w in TILE_PLACES],
        ("decisions", decisions, 6, 6, 18, 8),
    ],
    rows=[
        row(
            "Step",
            auto(
                [(name, when("step", "equals", str(n))) for n, name in enumerate(TEXTS, 1)]
                + [(f"step-{key}", when("step", "equals", *at)) for key, at in AT.items()],
                3,
            ),
        )
    ],
    panels=TEXTS | {f"step-{key}": steps.PLOTS[key] for key in AT},
    variables=[
        custom("period", "Interval", PERIODS, current="day"),
        custom("step", "Step", [str(n) for n in range(1, len(STEPS) + 1)], current="1"),
    ],
)
