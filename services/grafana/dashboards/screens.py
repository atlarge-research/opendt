"""The screens: each panel and its place, (name, panel, x, y, width, height) on a 24-column grid."""

import steps
from form import HOSTS, control, picker
from layout import auto, custom, dashboard, grid, picked, row, when
from panels import PERIODS
from plots import (
    BOXES,
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


# the tiles: the twin's time and power on top, then its CO₂, hosts, and jobs
TILE_PLACES = [
    ("twin-time", 6, 0, 6),
    ("power-now", 12, 0, 9),
    ("mape-now", 21, 0, 3),
    ("co2-now", 6, 3, 4),
    ("hosts-now", 10, 3, 7),
    ("jobs-now", 17, 3, 7),
]
PICKERS = {f"pick-{i}": picker(title, plots) for i, (title, plots) in enumerate(ROWS.items())}

detailed = screen(
    "opendt-overview",
    "OpenDT, detailed",
    [
        ("control", control("opendt-overview", [HOSTS]), 0, 0, 6, 16),
        ("decisions", decisions, 0, 16, 6, 5),  # what the markers on the graphs stand for
        *[(name, TILES[name], x, y, w, 3) for name, x, y, w in TILE_PLACES],
        ("power", power, 6, 6, 6, 15),
        ("co2", co2, 12, 6, 6, 15),
        ("hosts", hosts, 18, 6, 6, 15),
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
            multi=True,
            current=["none"],
        ),
    ],
)

# the physical twin on the left, the digital twin on the right
simple = screen(
    "opendt-simple",
    "OpenDT, simple",
    [
        ("control", control("opendt-simple", [HOSTS], period=False), 0, 0, 6, 18),
        ("twin-state", twin_state, 0, 18, 6, 8),
        ("physical", TILES["measured-now"], 6, 0, 9, 4),
        ("power-simple", power, 6, 4, 9, 11),
        ("arrivals", arrivals, 6, 15, 9, 11),
        ("twin", TILES["opendt-now"], 15, 0, 9, 4),
        ("heatmap", heatmap, 15, 4, 9, 11),
        ("decisions", decisions, 15, 15, 9, 11),
    ],
)

topology = screen(
    "opendt-topology",
    "OpenDT, topology",
    [
        ("control", control("opendt-topology", [], period=False), 0, 0, 6, 25),
        ("groups", groups, 6, 0, 18, 6),
        ("catalog", catalog, 6, 6, 18, 9),
        ("hosts-topology", hosts, 6, 15, 18, 10),
    ],
)

# the Tutorial screen, one step at a time, each step a row shown at its step: the twin on the left, its control
# panel and its state in boxes; the step on the right, its question and its plots
BOX_PLACES = [
    ("time-box", 0, 16, 6),
    ("truth-box", 0, 18, 3),
    ("opendt-box", 3, 18, 3),
    ("mape-box", 0, 20, 3),
    ("co2-box", 3, 20, 3),
]
# the step's height, then its plots down to the boxes' bottom; with its solution shown, the step is taller
CARD, SOLUTION, BOTTOM = 8, 10, 22


def split(names, x, y, width, height):
    """The plots of a step in the area, in two columns, each top to bottom, the left one with the fewer;
    a single plot takes it all."""
    if len(names) == 1:
        return [(names[0], x, y, width, height)]
    half, left = width // 2, len(names) // 2
    return stack(names[:left], x, y, half, height) + stack(
        names[left:], x + half, y, width - half, height
    )


def stack(names, x, y, width, height):
    """The names one under the other, in equal parts of the height."""
    h = height // len(names)
    return [(name, x, y + i * h, width, h) for i, name in enumerate(names)]


def slide(value, step, card):
    """The row shown while the step variable has this value: n, or ns with the solution shown."""
    plots = split([f"plot-{key}" for key in step["plots"]], 6, card, 18, BOTTOM - card)
    boxes = [(name, x, y, w, 2) for name, x, y, w in BOX_PLACES]
    places = [("control", 0, 0, 6, 16), *boxes, (f"step-{value}", 6, 0, 18, card), *plots]
    return row("", grid(places), shown=when("step", "equals", value))


SLIDES = []  # (value of the step variable, step, its card)
for n, (_, step) in enumerate(steps.ORDER, 1):
    SLIDES.append((str(n), step, steps.card(n)))
    if "solution" in steps.QUESTIONS[step["question"]]:
        SLIDES.append((f"{n}s", step, steps.card(n, shown=True)))
tutorial = dashboard(
    "opendt-tutorial",
    "OpenDT, tutorial",
    {"control": control("opendt-tutorial", [HOSTS])}
    | BOXES
    | {f"step-{value}": card for value, _, card in SLIDES}
    | {f"plot-{key}": steps.PLOTS[key] for _, step, _ in SLIDES for key in step["plots"]},
    [slide(value, step, SOLUTION if value.endswith("s") else CARD) for value, step, _ in SLIDES],
    [
        custom("period", "Interval", PERIODS, current="day"),
        custom("step", "Step", [value for value, _, _ in SLIDES], current="1"),
    ],
)
