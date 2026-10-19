"""The screens: each panel and its place, (name, panel, x, y, width, height) on a 24-column grid."""

import steps
from form import (
    CALIBRATION,
    CALIBRATOR,
    HOSTS,
    INFRASTRUCTURE,
    SCHEDULER,
    SPEED,
    ZONE,
    control,
    lever,
    picker,
)
from layout import all_of, auto, custom, dashboard, grid, picked, query, row, when
from panels import PERIODS, STATUS, target
from plots import (
    BOXES,
    ROWS,
    STARTING,
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
    """The levers' bar and the placed panels under it, then the `rows` of the other `panels`."""
    placed = TOP + [(name, panel, x, y + BAR, w, h) for name, panel, x, y, w, h in placed]
    top = row(
        "",
        grid([(name, x, y, w, h) for name, _, x, y, w, h in placed]),
        shown=when("twin", "notEquals", ""),
    )
    panels = {name: panel for name, panel, *_ in placed} | STARTING | (panels or {})
    return dashboard(uid, title, panels, [STARTUP, top, *rows], [TWIN, *variables])


# the tiles, in one row: the twin's time, power, MAPE, CO₂, hosts, and jobs
TILE_PLACES = [
    ("twin-time", 6, 0, 3),
    ("power-now", 9, 0, 5),
    ("mape-now", 14, 0, 2),
    ("co2-now", 16, 0, 2),
    ("hosts-now", 18, 0, 3),
    ("jobs-now", 21, 0, 3),
]
# while the twin starts, a row above all: gone once its first window is complete
STARTUP = row("", grid([("start", 0, 0, 24, 28)]), shown=when("twin", "equals", ""))
# the twin's time, empty until its first window is complete (or while the API does not answer)
TWIN = query("twin", target(STATUS, [("twin_time", "twin_time", "string")]) | {"root_selector": ""})
# the levers' bar at the top of every screen: the hosts, the CO₂ zone, the speed, and the calibration
BAR = 4
TOP = [
    ("lever-hosts", lever([HOSTS, INFRASTRUCTURE]), 0, 0, 4, BAR),
    ("lever-twin", lever([ZONE, SPEED]), 4, 0, 6, BAR),
    ("lever-calibration", lever([CALIBRATION, *CALIBRATOR], split=True), 10, 0, 14, BAR),
]
PICKERS = {f"pick-{i}": picker(title, plots) for i, (title, plots) in enumerate(ROWS.items())}

detailed = screen(
    "opendt-overview",
    "OpenDT, detailed",
    [
        ("control", control("opendt-overview", [SCHEDULER]), 0, 0, 6, 7),
        ("decisions", decisions, 0, 7, 6, 6),  # what the markers on the graphs stand for
        *[(name, TILES[name], x, y, w, 3) for name, x, y, w in TILE_PLACES],
        ("power", power, 6, 3, 6, 10),
        ("co2", co2, 12, 3, 6, 10),
        ("hosts", hosts, 18, 3, 6, 10),
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
        ("control", control("opendt-simple", period=False), 0, 0, 6, 6),
        ("twin-state", twin_state, 0, 6, 6, 14),
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
        ("control", control("opendt-topology", period=False), 0, 0, 6, 6),
        ("groups", groups, 6, 0, 18, 6),
        ("catalog", catalog, 6, 6, 18, 9),
        ("hosts-topology", hosts, 6, 15, 18, 10),
    ],
)

# the Tutorial screen, one step at a time, each a row shown at its step: the twin on the left, its
# control panel and its state in boxes; the step on the right, its question and its plots
LEFT = [
    ("control", 0, 0, 6, 6),
    ("time-box", 0, 6, 6, 2),
    ("truth-box", 0, 8, 3, 2),
    ("opendt-box", 3, 8, 3, 2),
    ("mape-box", 0, 10, 3, 2),
    ("co2-box", 3, 10, 3, 2),
    ("decisions", 0, 12, 6, 9),  # what the markers on the step's graphs stand for
]
# the step's height, then its plots, all on a 1440x900 screen in full screen; with its solution, the
# step is taller and the screen scrolls
CARD, SOLUTION, PLOTS = 7, 10, 14


def split(names, x, y, width, height):
    """The plots of a step in the area, in two columns, each top to bottom, the left one with the
    fewer; a single plot takes it all."""
    if len(names) == 1:
        return [(names[0], x, y, width, height)]
    half, left = width // 2, len(names) // 2
    return stack(names[:left], x, y, half, height) + stack(
        names[left:], x + half, y, width - half, height
    )


def stack(names, x, y, width, height):
    """The names one under the other, to the bottom; the lower ones take what does not divide."""
    tops = [y + height * i // len(names) for i in range(len(names) + 1)]
    return [(name, x, tops[i], width, tops[i + 1] - tops[i]) for i, name in enumerate(names)]


def slide(value, step, shown):
    """The row shown while the step variable has this value."""
    card = SOLUTION if shown else CARD
    plots = split([f"plot-{key}" for key in step["plots"]], 6, BAR + card, 18, PLOTS)
    under = [(name, x, y + BAR, w, h) for name, x, y, w, h in LEFT]
    return row(
        "",
        grid(
            [
                *((name, x, y, w, h) for name, _, x, y, w, h in TOP),
                *under,
                (f"step-{value}", 6, BAR, 18, card),
                *plots,
            ]
        ),
        shown=all_of(when("step", "equals", value), when("twin", "notEquals", "")),
    )


tutorial = dashboard(
    "opendt-tutorial",
    "OpenDT, tutorial",
    {"control": control("opendt-tutorial")}
    | {name: panel for name, panel, *_ in TOP}
    | BOXES
    | {"decisions": decisions}
    | {f"step-{value}": card for value, _, card, _ in steps.SLIDES}
    | {f"plot-{key}": steps.PLOTS[key] for _, step in steps.ORDER for key in step["plots"]}
    | STARTING,
    [STARTUP, *(slide(value, step, shown) for value, step, _, shown in steps.SLIDES)],
    [
        TWIN,
        custom("period", "Interval", PERIODS, current="day"),
        custom("step", "Step", [value for value, *_ in steps.SLIDES], current="1"),
    ],
    window="day",
)
