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
from panels import PERIODS, STATUS, target
from plots import (
    BOXES,
    GROUPS,
    ROWS,
    STARTING,
    catalog,
    decisions,
    groups,
    hosts,
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
TWIN = query("twin", target(STATUS, [("twin_time", "twin_time", "string")]) | {"root_selector": ""})
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


def top(uid, plots=(), period=True):
    """The view, then the levers, all as wide."""
    levers = [(name, LEVERS[name], 8 + 4 * i, 0, 4, BAR) for i, name in enumerate(LEVERS)]
    return [("brand", brand(uid, plots, period), 0, 0, 8, BAR), *levers]


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
        *[(name, GROUPS[name], 8 + 4 * i, 0, 4, 5) for i, name in enumerate(GROUPS)],
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
            current=["none"],
        ),
    ],
)

topology = screen(
    "opendt-topology",
    "OpenDT, topology",
    [
        ("groups", groups, 0, 0, 24, 6),
        ("catalog", catalog, 0, 6, 24, 9),
        ("hosts-topology", hosts, 0, 15, 24, 10),
    ],
    period=False,
)

# the Tutorial screen, one step at a time, each a row shown at its step: the twin's state on the left, in
# boxes; the step on the right, its question and its plots
LEFT = [
    ("time-box", 0, 0, 6, 2),
    ("truth-box", 0, 2, 3, 2),
    ("opendt-box", 3, 2, 3, 2),
    ("mape-box", 0, 4, 3, 2),
    ("co2-box", 3, 4, 3, 2),
    ("decisions", 0, 6, 6, 15),  # what the markers on the step's graphs stand for
]
# the step's height, then its plots, all on a 1440x900 screen in full screen; its hint and solution scroll in it
CARD, PLOTS = 10, 11


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


def slide(value, step):
    """The row shown while the step variable has this value."""
    plots = split([f"plot-{key}" for key in step["plots"]], 6, BAR + CARD, 18, PLOTS)
    under = [(name, x, y + BAR, w, h) for name, x, y, w, h in LEFT]
    return row(
        "",
        grid(
            [
                *((name, x, y, w, h) for name, _, x, y, w, h in top("opendt-tutorial")),
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
    {name: panel for name, panel, *_ in top("opendt-tutorial")}
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
