"""The screens: each panel and its place, (name, panel, x, y, width, height) on a 24-column grid."""

import steps
from form import (
    CALIBRATION,
    HOSTS,
    MAPE_WINDOW,
    PARALLEL,
    R_FROM,
    R_TO,
    R_VALUES,
    SCHEDULER,
    SPEED,
    ZONE,
    brand,
    group,
)
from layout import all_of, auto, custom, dashboard, grid, picked, query, row, when
from panels import PERIODS, status
from plots import (
    BOXES,
    GROUPS,
    ROWS,
    STARTING,
    cpus,
    datacenter,
    decisions,
    gpus,
    hosts,
    racks,
)


def screen(uid, title, placed, rows=(), panels=None, variables=(), plots=(), period=True):
    """The view and the levers on top, the placed panels under them, then the `rows` of the other `panels`;
    `plots`, to show or hide; `period`, whether the screen has an interval."""
    placed = top(uid, plots, period) + [
        (name, panel, x, y + BAR, w, h) for name, panel, x, y, w, h in placed
    ]
    first = row(
        "",
        grid([(name, x, y, w, h) for name, _, x, y, w, h in placed]),
        shown=when("twin", "notEquals", ""),
    )
    panels = {name: panel for name, panel, *_ in placed} | STARTING | (panels or {})
    return dashboard(uid, title, panels, [STARTUP, first, *rows], [TWIN, *variables])


# while the twin starts, a row above all: gone once its first window is complete
STARTUP = row("", grid([("start", 0, 0, 24, 28)]), shown=when("twin", "equals", ""))
# the twin's time, empty until its first window is complete (or while the API does not answer)
TWIN = query("twin", status("twin_time"))
# the top of every screen: the view, then the levers by category
BAR = 4
LEVERS = {
    "lever-datacenter": group(
        "Datacenter",
        [("Hosts", [HOSTS]), ("Scheduler", [SCHEDULER])],
        link=("Infrastructure →", "/d/opendt-topology?kiosk"),
    ),
    "lever-grid": group("Grid", [("CO₂ zone", [ZONE])]),
    "lever-twin": group("Twin", [("Speed", [SPEED]), ("Calibration", [CALIBRATION])]),
    "lever-calibrator": group(
        "Self-Calibrator",
        [
            ("Parallel runs", [PARALLEL]),
            ("Range of r", [R_FROM, R_TO]),
            ("Values of r", [R_VALUES]),
            ("MAPE window", [MAPE_WINDOW]),
        ],
        # what r is: the exponent of OpenDC's power model, of the CPU utilization u (Fan et al., ISCA 2007)
        note="<small>P(u) = P<sub>idle</sub> + (P<sub>max</sub> − P<sub>idle</sub>)(2u − u<sup>r</sup>)</small>",
    ),
}


def side_by_side(names, x, y, width, height):
    """Panels in one row, as wide each; the last ones take what does not divide."""
    lefts = [x + width * i // len(names) for i in range(len(names) + 1)]
    return [(name, lefts[i], y, lefts[i + 1] - lefts[i], height) for i, name in enumerate(names)]


def top(uid, plots=(), period=True):
    """The view, then the levers, all as wide."""
    levers = [
        (name, LEVERS[name], *place) for name, *place in side_by_side(list(LEVERS), 8, 0, 16, BAR)
    ]
    return [("brand", brand(uid, plots, period), 0, 0, 8, BAR), *levers]


# the rows a fresh screen shows; ☰ Plots shows the others
SHOWN = ("Performance", "Twin accuracy")
# the plots of each row, by their titles, to show or hide
ROW_PLOTS = [
    (title, [(key, plot["title"].replace("$period", "period")) for key, plot in plots.items()])
    for title, plots in ROWS.items()
]

detailed = screen(
    "opendt-overview",
    "OpenDT, detailed",
    [
        # the top third: what the screen shows and the decisions, the twin now; then the plots
        ("decisions", decisions, 0, 0, 8, 5),  # what the markers on the graphs stand for
        *[(name, GROUPS[name], *place) for name, *place in side_by_side(list(GROUPS), 8, 0, 16, 5)],
    ],
    rows=[
        # a row shows while one of its plots is not hidden
        row(title, auto([(key, picked(key)) for key in plots], len(plots)), shown=picked(*plots))
        for title, plots in ROWS.items()
    ],
    panels={key: plot for plots in ROWS.values() for key, plot in plots.items()},
    plots=ROW_PLOTS,
    variables=[
        custom("period", "Interval", PERIODS, current="day"),
        # the hidden plots; "none", so the list is never empty
        custom(
            "hidden",
            "Hidden plots",
            ["none", *(k for p in ROWS.values() for k in p)],
            multi=True,
            current=["none", *(k for row, p in ROWS.items() if row not in SHOWN for k in p)],
        ),
    ],
)

topology = screen(
    "opendt-topology",
    "OpenDT, topology",
    [
        ("datacenter", datacenter, 0, 0, 24, 6),
        ("hosts-topology", hosts, 0, 6, 9, 10),  # about 3:2, by the racks it shows
        ("racks", racks, 9, 6, 15, 10),
        ("cpus", cpus, 0, 16, 12, 13),  # the nine shipped CPU prefabs, and a few more
        ("gpus", gpus, 12, 16, 12, 13),
    ],
    period=False,
)

# the Tutorial screen, one step at a time, each a row shown at its step: the twin's state on the left, in
# boxes; the step on the right, its question and its plots
TOP = top("opendt-tutorial")
LEFT = [
    ("time-box", 0, 0, 6, 2),
    ("truth-box", 0, 2, 3, 2),
    ("opendt-box", 3, 2, 3, 2),
    ("mape-box", 0, 4, 3, 2),
    ("co2-box", 3, 4, 3, 2),
    ("decisions", 0, 6, 6, 14),  # what the markers on the step's graphs stand for
]
# the step's height, its question with room for its hint and solution, then its plots side by side
CARD, PLOTS = 12, 8


def slide(value, step):
    """The row shown while the step variable has this value."""
    plots = side_by_side([f"plot-{key}" for key in step["plots"]], 6, BAR + CARD, 18, PLOTS)
    under = [(name, x, y + BAR, w, h) for name, x, y, w, h in LEFT]
    return row(
        "",
        grid(
            [
                *((name, x, y, w, h) for name, _, x, y, w, h in TOP),
                *under,
                (f"step-{value}", 6, BAR, 18, CARD),
                *plots,
            ]
        ),
        shown=all_of(when("step", "equals", value), when("twin", "notEquals", "")),
    )


tutorial = dashboard(
    "opendt-tutorial",
    "OpenDT, tutorial",
    {name: panel for name, panel, *_ in TOP}
    | BOXES
    | {"decisions": decisions}
    | {f"step-{value}": card for value, _, card in steps.SLIDES}
    | {f"plot-{key}": steps.PLOTS[key] for _, step in steps.ORDER for key in step["plots"]}
    | STARTING,
    [STARTUP, *(slide(value, step) for value, step, _ in steps.SLIDES)],
    [
        TWIN,
        custom("period", "Interval", PERIODS, current="day"),
        custom("step", "Step", [value for value, *_ in steps.SLIDES], current="1"),
    ],
    window="day",
)
