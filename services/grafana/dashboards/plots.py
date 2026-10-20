"""What each plot shows, one definition per plot, from the API's endpoints."""

import re
from pathlib import Path

import yaml
from form import script
from panels import (
    ACCURACY,
    API,
    BARS,
    BLUE,
    BROWSER_API,
    CLUSTER,
    CO2,
    COLORS,
    GREEN,
    GREY,
    ORANGE,
    POWER,
    RANGE,
    RED,
    STATUS,
    TIME,
    YELLOW,
    editable,
    organize,
    override,
    ratio,
    stat,
    table,
    target,
    tile,
    tiles,
    timeseries,
    units,
)

SCHEDULING, TOTALS = f"{API}/api/scheduling", f"{API}/api/totals?period=$period"
EVENTS = f"{API}/api/events?markers=on"
# what tiles.yaml sets: the tiles of a share, and the (i) of each panel
CONFIG = yaml.safe_load((Path(__file__).parent / "tiles.yaml").read_text())
NOW = f"{CLUSTER}?points=1"  # the latest sample, for the tiles and boxes

# the top of the detailed screen

TILES = {
    "twin-time": tile(
        "Simulated time", STATUS, "twin_time", "timestamp", root="", unit="time:YYYY-MM-DD HH:mm"
    ),
    # the power draw, measured and predicted, and how far apart
    "power-now": tiles(
        POWER,
        [("actual_power", "actual_power"), ("simulated_power", "simulated_power")],
        [
            ("actual_power/1000", "Ground truth [kW]"),
            ("simulated_power/1000", "OpenDT [kW]"),
            ("(simulated_power - actual_power)/1000", "Gap [kW]"),
        ],
        ["actual_power", "simulated_power"],
        decimals=1,
    ),
    # of the power draw, the last 5 minutes; 10% is the community-accepted error rate (question 1.1)
    "mape-now": tile("Real-time MAPE [%]", f"{ACCURACY}?minutes=5", "mape", decimals=1, limit=10),
    "co2-now": tile("CO₂ emissions [kg/h]", CO2, "carbon_emission", scale="/1000", decimals=1),
    # the physical and digital twin apart, in the colours of their lines (Simple, Tutorial)
    "measured-now": tile(
        "Ground truth [kW]", POWER, "actual_power", scale="/1000", decimals=1, color=GREY
    ),
    "opendt-now": tile(
        "OpenDT [kW]", POWER, "simulated_power", scale="/1000", decimals=1, color=GREEN
    ),
    "gap-now": tiles(
        POWER,
        [("actual_power", "actual_power"), ("simulated_power", "simulated_power")],
        [("(simulated_power - actual_power)/1000", "Gap [kW]")],
        ["actual_power", "simulated_power"],
        decimals=1,
    ),
}
# the Tutorial screen's boxes, one value each, in the colour of its line in the plots
BOXES = {
    "time-box": tile(
        "Simulated time",
        STATUS,
        "twin_time",
        "timestamp",
        root="",
        unit="time:YYYY-MM-DD HH:mm",
        color=BLUE,
    ),
    "truth-box": TILES["measured-now"],
    "opendt-box": TILES["opendt-now"],
    "mape-box": TILES["mape-now"],
    "co2-box": tile(
        "CO₂ emissions [kg/h]", CO2, "carbon_emission", scale="/1000", decimals=1, color=ORANGE
    ),
}
power = timeseries(
    "Power draw",
    POWER,
    "Power draw [kW]",
    {"Ground truth": GREY, "OpenDT": GREEN},
    [("actual_power", "actual_power"), ("simulated_power", "simulated_power")],
    better="lower",
    computed=[("actual_power/1000", "Ground truth"), ("simulated_power/1000", "OpenDT")],
    hide=["actual_power", "simulated_power"],
    apart=["Ground truth"],
)
co2 = timeseries(
    "CO₂ emissions vs. carbon intensity",
    CO2,
    "CO₂ emissions [kg/h]",
    {"CO₂ emissions": ORANGE, "Carbon intensity": BLUE},
    [("carbon_emission", "carbon_emission"), ("carbon_intensity", "Carbon intensity")],
    computed=[("carbon_emission/1000", "CO₂ emissions")],
    hide=["carbon_emission"],
    right=("Carbon intensity", "Carbon intensity [gCO₂/kWh]"),
    apart=["Carbon intensity"],
)
hosts = timeseries(
    "Hosts available vs. in use",
    CLUSTER + RANGE,
    "Hosts",
    {"Available": BLUE, "In use": GREEN},
    [("hosts_up", "Available"), ("hosts_in_use", "In use")],
    unit="locale",
    decimals=0,
    apart=["Available"],
)

# the rows of the detailed screen, each plot shown or hidden in the Plots row

# the hosts in each CPU-utilization bucket over time, the busiest bucket on top; the key gives each step
BUCKETS = [(f"cpu_{low}_{low + 20}", f"{low}-{low + 20}%") for low in range(80, -1, -20)]
# blues from few hosts to many, the fewest still apart from the dark background
SHADES = {None: "#1d4e89", 50: "#2f74b5", 100: "#5b9bd5", 150: "#9cc3e6", 200: "#deebf7"}
heatmap = {
    "type": "status-history",
    "title": "Hosts per CPU utilization",
    # about 100 samples: with more, a status history draws none
    "targets": [target(CLUSTER + RANGE + "&points=100", [TIME, *BUCKETS])],
    "transformations": [organize([name for _, name in BUCKETS])],
    "fieldConfig": {
        "defaults": {
            "unit": "locale",
            "color": {"mode": "thresholds"},
            "thresholds": {
                "mode": "absolute",
                "steps": [{"value": count, "color": shade} for count, shade in SHADES.items()],
            },
        },
        "overrides": [],
    },
    "options": {
        "showValue": "never",
        "rowHeight": 0.95,
        "colWidth": 1,
        "legend": {"showLegend": True, "displayMode": "list"},
    },
}
# the calibrator's decisions, counted by the data source
automatic = target(EVENTS, [("text", "text", "string"), ("by", "by", "string")]) | {
    "filterExpression": "by == 'Automatic'",
    "summarizeExpression": "count(text)",
    "summarizeAlias": "Automatic decisions",
}

ROWS = {
    "Performance": {
        "scheduling-now": stat(
            "Performance now",
            SCHEDULING,
            [
                ("completion_h", "Total runtime [h]"),
                ("queue_median_min", "Queue time [min]"),
                ("started_in_10_min_pct", "Started in 10 min [%]"),
            ],
            units("locale", "Jobs waiting", "Jobs running", "Jobs finished", decimals=0),
            decimals=1,
            more=[
                target(
                    NOW,
                    [
                        ("tasks_pending", "Jobs waiting"),
                        ("tasks_active", "Jobs running"),
                        ("tasks_completed", "Jobs finished"),
                    ],
                )
            ],
        ),
        "completion": timeseries(
            "Total runtime",
            SCHEDULING,
            "Total runtime [h]",
            {"Total runtime": BLUE},
            [("completion_h", "Total runtime")],
            better="lower",
            gaps=True,
        ),
        "queue": timeseries(
            "Time in queue",
            SCHEDULING,
            "Time in queue [min]",
            {"Median": YELLOW},
            [("queue_median_min", "Median")],
            better="lower",
            gaps=True,
        ),
        "jobs": timeseries(
            "Jobs",
            CLUSTER + RANGE,
            "Jobs",
            {"Waiting": YELLOW, "Running": BLUE, "Finished": GREEN},
            [
                ("tasks_pending", "Waiting"),
                ("tasks_active", "Running"),
                ("tasks_completed", "Finished"),
            ],
            unit="locale",
            decimals=0,
            apart=["Running"],
        ),
        "jobs-left": table(
            "Jobs waiting or running",
            f"{API}/api/jobs",
            [("task_id", "Job"), ("state", "State", "string"), ("time_left_h", "Time left [h]")],
            [
                override("Job", unit="none", decimals=0, custom__width=64),  # an id, not a quantity
                override("State", custom__width=80),
                override(
                    "Time left [h]",
                    min=0,
                    fieldMinMax=True,  # the bars scale to the time left only, not to the job ids
                    decimals=1,
                    color={"mode": "fixed", "fixedColor": BLUE},
                    custom__cellOptions={"type": "gauge", "mode": "basic"},
                ),
            ],
        ),
        "arrivals": timeseries(
            "Jobs arriving per hour",
            f"{API}/api/arrivals",
            "Arrivals [jobs/h]",
            {"Arrivals": GREY},
            [("jobs", "Arrivals")],
            unit="locale",
            decimals=0,
            **BARS,
        ),
    },
    "Utilization": {
        "utilization-now": stat(
            "Utilization now",
            NOW,
            [
                ("cpu_utilization_busy_median", "CPU, busy hosts"),
                ("cpu_utilization", "CPU, all hosts"),
                ("hosts_up", "hosts_up"),
                ("hosts_in_use", "Hosts in use"),
                ("cpu_demand_cores", "CPU demand [cores]"),
                ("cpu_capacity_cores", "CPU capacity [cores]"),
            ],
            units("percentunit", "CPU, busy hosts", "CPU, all hosts", decimals=1),
            unit="locale",
            decimals=0,
            computed=[("hosts_up - hosts_in_use", "Idle hosts")],
            hide=["hosts_up"],
        ),
        "cpu": timeseries(
            "CPU utilization of the hosts",
            CLUSTER + RANGE,
            "CPU utilization [%]",
            {"Busy hosts, median": GREEN, "All hosts, mean": BLUE},
            [
                ("cpu_utilization_busy_median", "Busy hosts, median"),
                ("cpu_utilization", "All hosts, mean"),
            ],
            better="higher",
            unit="percentunit",
            apart=["All hosts, mean"],
        ),
        "demand": timeseries(
            "CPU demand vs. capacity",
            CLUSTER + RANGE,
            "CPU [cores]",
            {"Capacity": BLUE, "Demand": GREEN},
            [("cpu_capacity_cores", "Capacity"), ("cpu_demand_cores", "Demand")],
            unit="locale",
            decimals=0,
            apart=["Capacity"],
        ),
        "cpu-hosts": heatmap,
        "idle-hosts": timeseries(
            "Idle hosts",
            CLUSTER + RANGE,
            "Hosts",
            {"Running no job": ORANGE},
            [("hosts_up", "hosts_up"), ("hosts_in_use", "hosts_in_use")],
            better="lower",
            unit="locale",
            decimals=0,
            computed=[("hosts_up - hosts_in_use", "Running no job")],
            hide=["hosts_up", "hosts_in_use"],
        ),
    },
    "Sustainability": {
        "energy-now": stat(
            "This $period",
            TOTALS,
            [(c, c) for c in ("energy_kwh", "co2_kg", "embodied_co2_kg")],
            unit="locale",
            decimals=0,
            computed=[
                ("energy_kwh", "Energy [kWh]"),
                ("co2_kg", "CO₂ [kg]"),
                ("embodied_co2_kg", "Embodied CO₂ [kg]"),
                ("co2_kg + embodied_co2_kg", "CO₂ in total [kg]"),
                ("co2_kg * 1000 / energy_kwh", "Intensity [gCO₂/kWh]"),  # the mean of the period
                ("embodied_co2_kg * 100 / (co2_kg + embodied_co2_kg)", "Embodied share [%]"),
            ],
            hide=["energy_kwh", "co2_kg", "embodied_co2_kg"],
        ),
        "energy": timeseries(
            "Energy per $period",
            TOTALS,
            "Energy [kWh]",
            {"Energy": BLUE},
            [("energy_kwh", "Energy")],
            better="lower",
            unit="locale",
            **BARS,
        ),
        "carbon": timeseries(
            "CO₂ per $period",
            TOTALS,
            "CO₂ [kg]",
            {"Operational": ORANGE, "Embodied": ORANGE},
            [("co2_kg", "Operational"), ("embodied_co2_kg", "Embodied")],
            better="lower",
            unit="locale",
            stacking={"mode": "normal"},  # together, the CO₂ of the period
            apart=["Embodied"],
            **BARS,
        ),
        "intensity": timeseries(
            "Carbon intensity",
            CO2,
            "Carbon intensity [gCO₂/kWh]",
            {"Intensity": BLUE},
            [("carbon_intensity", "Intensity")],
            better="lower",
        ),
        # what the idle hosts cost
        "idle-power": timeseries(
            "Power draw of idle hosts",
            CLUSTER + RANGE,
            "Power draw [kW]",
            {"Idle hosts": ORANGE},
            [("idle_power_kw", "Idle hosts")],
            better="lower",
        ),
    },
    "Twin accuracy": {
        "accuracy-now": stat(
            "Accuracy now",
            ACCURACY,
            [
                ("mape", "MAPE, 1 h [%]"),
                ("error_kw", "Error, 1 h [kW]"),
                ("energy_error_pct", "Energy error [%]"),
                ("r", "r"),
            ],
            [override("Automatic decisions", decimals=0)],
            decimals=1,
            more=[target(f"{ACCURACY}?minutes=5", [("mape", "MAPE, 5 min [%]")]), automatic],
        ),
        "mape": timeseries(
            "Power draw MAPE per hour",
            ACCURACY,
            "Power draw MAPE [%]",
            {"MAPE": RED},
            [("mape", "MAPE")],
            better="lower",
            gaps=True,
            **BARS,
        ),
        "r": timeseries(
            "Calibration parameter r",
            ACCURACY,
            "r",
            {"r": BLUE},
            [("r", "r")],
            gaps=True,
            lineInterpolation="stepAfter",
        ),
        # above 0, OpenDT predicts more power than measured; calibration brings it to 0
        "error": timeseries(
            "Power draw error per hour",
            ACCURACY,
            "Power draw error [kW]",
            {"Error": RED},
            [("error_kw", "Error")],
            gaps=True,
            signed=True,
            **BARS,
        ),
        "energy-error": timeseries(
            "Energy error so far",
            ACCURACY,
            "Energy error [%]",
            {"Error": RED},
            [("energy_error_pct", "Error")],
            gaps=True,
            signed=True,
        ),
    },
}
# P1, U2, ...: the row's letter and the plot's place in it, for the tutorial and the talk to point at
for row, plots in ROWS.items():
    for i, (key, plot) in enumerate(plots.items(), 1):
        plots[key] = plot | {"title": f"{row[0]}{i}  {plot['title']}"}

decisions = table(
    "Decisions",
    EVENTS,
    [("time", "Time", "timestamp"), ("text", "Change", "string"), ("by", "By", "string")],
    [
        override("Time", unit="time:MM-DD HH:mm", custom__width=95),
        # a long change takes two lines
        override("Change", custom__cellOptions={"type": "auto", "wrapText": True}),
        override("By", custom__width=80),
    ],
    sort="Time",
    header=False,  # time, change, and by whom need no header
)

# the topology screen: the host groups, edited in place, with CPUs and GPUs from the lists or custom

SPECS = [
    ("cores", "Cores"),
    ("ghz", "Core speed [GHz]"),
    ("memory_gb", "Memory [GB]"),
    ("idle_w", "Idle power [W]"),
    ("max_w", "Max power [W]"),
]
groups = editable(
    "Hosts",
    f"{API}/api/hosts",
    [
        ("kind", "Name", "string"),
        ("count", "Count", "number"),
        ("cpu", "CPU", f"{API}/api/components?part=CPU"),
        *((field, name, "number") for field, name in SPECS),
        ("gpu", "GPU", f"{API}/api/components?part=GPU"),
        ("gpus", "GPUs per host", "number"),
    ],
    save=f"{API}/api/hosts",
    delete=f"{API}/api/hosts?id=${{payload.id}}&count=0",
)
groups["description"] = (
    "Edit a row with its pencil, add one with +. A CPU or GPU picked from the list brings its numbers. "
    "A new row is a copy of the first, without its GPUs. The twin runs the change from its next window."
)
catalog = table(
    "CPUs and GPUs to choose from",
    f"{API}/api/components",
    [("part", "Part", "string"), ("name", "Name", "string"), *SPECS],
)

# while the twin starts, the whole screen: what it does, a bar that never stands still, and a fact from the paper
PROGRESS = f"{API}/api/progress"
CARD = """<div class="opendt-start" data-step="{{step}}" data-steps="{{steps}}">
  <div class="doing">{{doing}}</div>
  <div class="bar"><div></div></div>
  <div class="tip">{{tip}}</div>
</div>"""
WAITING = """<div class="opendt-start" data-step="1" data-steps="3">
  <div class="doing">The services start</div>
  <div class="bar"><div></div></div>
</div>"""  # before the API answers
STYLE = """.opendt-start { min-height: 70vh; width: 56%; margin: 0 auto; display: flex; flex-direction: column;
  justify-content: center; gap: 18px; }
.opendt-start .doing { font-size: 17px; text-transform: uppercase; letter-spacing: 0.04em;
  white-space: nowrap; }
.opendt-start .bar { aspect-ratio: 24 / 1; background: rgba(128, 128, 128, 0.2); border-radius: 999px; overflow: hidden; }
.opendt-start .bar div { width: 0; height: 100%; border-radius: 999px; transition: width 0.2s linear;
  background: linear-gradient(90deg, #1f5f86, #338ec1 70%, #6cc0ee); box-shadow: 0 0 18px rgba(51, 142, 193, 0.55); }
.opendt-start .tip { position: fixed; bottom: 12%; left: 0; right: 0; text-align: center; color: #8e8e9e;
  font-size: 17px; white-space: nowrap; }"""
STARTING = {
    "start": {
        "type": "marcusolsson-dynamictext-panel",
        "title": "",
        "transparent": True,
        "targets": [
            target(
                PROGRESS,
                [
                    ("step", "step"),
                    ("steps", "steps"),
                    *((k, k, "string") for k in ("doing", "tip")),
                ],
            )
        ],
        "options": {
            "renderMode": "everyRow",
            "content": CARD,
            "defaultContent": WAITING,
            "styles": STYLE,
            "afterRender": script("start.js", progress=f"{BROWSER_API}/api/progress"),
        },
    },
}

TILES |= {
    name: ratio(tile["title"], NOW, tile["part"], tile["whole"], tile["colors"])
    for name, tile in CONFIG["ratios"].items()
}


def numbers(title, url, columns, computed=(), hide=(), more=(), overrides=(), decimals=1):
    """The numbers of a category in one box, each its name over its value; coloured by `overrides`."""
    panel = stat(title, url, columns, overrides, computed, hide=hide, more=more, decimals=decimals)
    panel["fieldConfig"]["defaults"]["color"]["fixedColor"] = "text"  # the theme's
    # two by two, also on a 1440-pixel screen
    panel["options"] |= {
        "colorMode": "value",
        "justifyMode": "center",
        "minVizWidth": 105,
        "minVizHeight": 48,
    }
    return panel


def colored(name, colors, **props):
    """A number in the colour of each value of `colors` on ({value: name})."""
    steps = [{"value": v or None, "color": COLORS[c]} for v, c in sorted(colors.items())]
    thresholds = {"mode": "absolute", "steps": steps}
    return override(name, color={"mode": "thresholds"}, thresholds=thresholds, **props)


# the top of the detailed screen: the twin's numbers now, by category, as the rows under it
SHARES = CONFIG["ratios"].values()
COUNTS = sorted({c for r in SHARES for c in re.findall(r"[a-z_]+", f"{r['part']} {r['whole']}")})
GROUPS = {
    "power-group": numbers(
        "Power [kW]",
        POWER,
        [("actual_power", "actual_power"), ("simulated_power", "simulated_power")],
        [
            ("actual_power/1000", "Ground truth"),
            ("simulated_power/1000", "OpenDT"),
            ("(simulated_power - actual_power)/1000", "Gap"),
        ],
        ["actual_power", "simulated_power"],
        overrides=[  # in the colours of their lines
            override("Ground truth", color={"mode": "fixed", "fixedColor": GREY}),
            override("OpenDT", color={"mode": "fixed", "fixedColor": GREEN}),
        ],
    ),
    "jobs-group": numbers(
        "Jobs and hosts",
        NOW,
        [(c, c) for c in COUNTS],
        [(f"({r['part']}) / ({r['whole']})", r["title"]) for r in SHARES],
        COUNTS,
        [
            target(
                NOW, [("tasks_completed", "Jobs finished"), ("cpu_utilization", "CPU utilization")]
            )
        ],
        [colored(r["title"], r["colors"], unit="percentunit", decimals=0) for r in SHARES]
        + [override("Jobs finished", unit="locale", decimals=0)]
        + [override("CPU utilization", unit="percentunit")],
    ),
    "sustainability-group": numbers(
        "Sustainability",
        CO2,
        [("carbon_emission", "carbon_emission"), ("carbon_intensity", "carbon_intensity")],
        [("carbon_emission/1000", "CO₂ [kg/h]"), ("carbon_intensity", "Intensity [gCO₂/kWh]")],
        ["carbon_emission", "carbon_intensity"],
        [target(TOTALS, [("energy_kwh", "Energy [kWh]"), ("co2_kg", "CO₂ [kg]")])],
        units("locale", "Intensity [gCO₂/kWh]", "Energy [kWh]", "CO₂ [kg]", decimals=0),
    ),
    # 10% is the community-accepted error rate (question 1.1)
    "accuracy-group": numbers(
        "Accuracy",
        f"{ACCURACY}?minutes=5",
        [("mape", "MAPE, 5 min [%]")],
        more=[
            target(
                ACCURACY,
                [("mape", "MAPE, 1 h [%]"), ("energy_error_pct", "Energy error [%]"), ("r", "r")],
            )
        ],
        overrides=[colored(f"MAPE, {t} [%]", {0: "green", 10: "red"}) for t in ("5 min", "1 h")],
    ),
}
# the (i) of each panel, by its name
PANELS = {"power": power, "co2": co2, "hosts": hosts, "decisions": decisions, **TILES, **GROUPS}
INFO = CONFIG["info"] | {name: tile["info"] for name, tile in CONFIG["ratios"].items()}
for name, text in INFO.items():
    PANELS[name]["description"] = text
