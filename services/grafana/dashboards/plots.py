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
    stat,
    table,
    target,
    text,
    thresholds,
    tile,
    timeseries,
    units,
)

SCHEDULING, TOTALS = f"{API}/api/scheduling", f"{API}/api/totals?period=$period"
EVENTS = f"{API}/api/events?markers=on"
# what tiles.yaml sets: the tiles of a share, and the (i) of each panel
CONFIG = yaml.safe_load((Path(__file__).parent / "tiles.yaml").read_text())
NOW = f"{CLUSTER}?points=1"  # the latest sample, for the tiles and boxes
# the power draw, from the API's W to kW
WATTS = [("actual_power", "actual_power"), ("simulated_power", "simulated_power")]
KW = [("actual_power/1000", "Ground truth"), ("simulated_power/1000", "OpenDT")]

# the top of the Dashboard screen

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
    "truth-box": tile(
        "Ground truth [kW]", POWER, "actual_power", scale="/1000", decimals=1, color=GREY
    ),
    "opendt-box": tile(
        "OpenDT [kW]", POWER, "simulated_power", scale="/1000", decimals=1, color=GREEN
    ),
    # of the power draw, the last 5 minutes; 10% is the community-accepted error rate (question 1.1)
    "mape-box": tile("Real-time MAPE [%]", f"{ACCURACY}?minutes=5", "mape", decimals=1, limit=10),
    "co2-box": tile(
        "CO₂ emissions [kg/h]", CO2, "carbon_emission", scale="/1000", decimals=1, color=ORANGE
    ),
}
power = timeseries(
    "Power draw",
    POWER,
    "Power draw [kW]",
    {"Ground truth": GREY, "OpenDT": GREEN},
    WATTS,
    computed=KW,
    hide=["actual_power", "simulated_power"],
    apart=["Ground truth"],
)
# the carbon intensity of the CO₂ zone the twin runs on now (the screens' variable `zone`)
ZONED = "(${zone}) [gCO₂/kWh]"


def zoned(panel, *names):
    """The panel's carbon intensities, `names`, shown with the zone: Grafana fills a variable in a name it shows,
    not in the name of the API's column."""
    shown = [override(n, displayName=n.replace("[gCO₂/kWh]", ZONED)) for n in names]
    panel["fieldConfig"]["overrides"] += shown
    return panel


co2 = zoned(
    timeseries(
        "CO₂ emissions vs. carbon intensity (${zone})",
        CO2,
        "CO₂ emissions [kg/h]",
        {"CO₂ emissions": ORANGE, "Carbon intensity": BLUE},
        [("carbon_emission", "carbon_emission"), ("carbon_intensity", "Carbon intensity")],
        computed=[("carbon_emission/1000", "CO₂ emissions")],
        hide=["carbon_emission"],
        right=("Carbon intensity", f"Carbon intensity {ZONED}"),
        apart=["Carbon intensity"],
    ),
    "Carbon intensity [gCO₂/kWh]",
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

# the rows of the Dashboard screen, each plot shown or hidden in the Plots row

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

ROWS = {
    "Performance": {
        "scheduling-now": stat(
            "Now",
            SCHEDULING,
            [
                ("completion_h", "Total runtime [h]"),
                ("queue_median_min", "Queue time [min]"),
                ("started_in_10_min_pct", "Started in 10 min"),
            ],
            [
                *units("locale", "Jobs waiting", "Jobs running", decimals=0),
                override("Started in 10 min", unit="percent", decimals=0),
            ],
            decimals=1,
            more=[
                target(NOW, [("tasks_pending", "Jobs waiting"), ("tasks_active", "Jobs running")])
            ],
        ),
        "completion": timeseries(
            "Total runtime",
            SCHEDULING,
            "Total runtime [h]",
            {"Total runtime": BLUE},
            [("completion_h", "Total runtime")],
        ),
        "queue": timeseries(
            "Time in queue",
            SCHEDULING,
            "Time in queue [min]",
            {"Median": YELLOW},
            [("queue_median_min", "Median")],
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
            "Now",
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
            unit="locale",
            decimals=0,
            computed=[("hosts_up - hosts_in_use", "Running no job")],
            hide=["hosts_up", "hosts_in_use"],
        ),
    },
    "Sustainability": {
        "energy-now": zoned(
            stat(
                "This $period",
                TOTALS,
                [(c, c) for c in ("energy_kwh", "co2_kg", "embodied_co2_kg")],
                [override("Embodied share", unit="percent")],
                unit="locale",
                decimals=0,
                computed=[
                    ("energy_kwh", "Energy [kWh]"),
                    ("co2_kg", "CO₂ [kg]"),
                    ("embodied_co2_kg", "Embodied CO₂ [kg]"),
                    ("co2_kg + embodied_co2_kg", "CO₂ in total [kg]"),
                    ("co2_kg * 1000 / energy_kwh", "Intensity [gCO₂/kWh]"),  # the period's mean
                    ("embodied_co2_kg * 100 / (co2_kg + embodied_co2_kg)", "Embodied share"),
                ],
                hide=["energy_kwh", "co2_kg", "embodied_co2_kg"],
            ),
            "Intensity [gCO₂/kWh]",
        ),
        "energy": timeseries(
            "Energy per $period",
            TOTALS,
            "Energy [kWh]",
            {"Energy": BLUE},
            [("energy_kwh", "Energy")],
            unit="locale",
            **BARS,
        ),
        "intensity": zoned(
            timeseries(
                "Carbon intensity (${zone})",
                CO2,
                f"Carbon intensity {ZONED}",
                {"Carbon intensity": BLUE},
                [("carbon_intensity", "Carbon intensity")],
            ),
            "Carbon intensity [gCO₂/kWh]",
        ),
        # what the idle hosts cost
        "idle-power": timeseries(
            "Power draw of idle hosts",
            CLUSTER + RANGE,
            "Power draw [kW]",
            {"Idle hosts": ORANGE},
            [("idle_power_kw", "Idle hosts")],
        ),
    },
    # its numbers now are on top (Accuracy); first, the power draw of the datacenter and of the twin instead
    "Twin accuracy": {
        "power": power,
        "mape": timeseries(
            "Power draw MAPE per hour",
            ACCURACY,
            "Power draw MAPE [%]",
            {"MAPE": RED},
            [("mape", "MAPE")],
            **BARS,
        ),
        "r": timeseries(
            "Calibration parameter r",
            ACCURACY,
            "r",
            {"r": BLUE},
            [("r", "r")],
            lineInterpolation="stepAfter",
        ),
        # above 0, OpenDT predicts more power than measured; calibration brings it to 0
        "error": timeseries(
            "Power draw error per hour",
            ACCURACY,
            "Power draw error [kW]",
            {"Error": RED},
            [("error_kw", "Error")],
            signed=True,
            **BARS,
        ),
        "energy-error": timeseries(
            "Energy error so far",
            ACCURACY,
            "Energy error [%]",
            {"Error": RED},
            [("energy_error_pct", "Error")],
            signed=True,
        ),
    },
}

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
# the Topology screen: the datacenter, racks of hosts, and the prefabs of CPUs, GPUs, and racks they come from
LISTS = {part: f"{API}/api/components?part={part}" for part in ("CPU", "GPU", "Rack")}
PREFABS = f"{API}/api/prefabs"
datacenter = editable(
    "Datacenter",
    f"{API}/api/hosts",
    [
        ("kind", "Rack", LISTS["Rack"]),
        ("count", "Hosts", "number"),
        ("cpu", "CPU", LISTS["CPU"]),
        *((field, name, "number") for field, name in SPECS),
        ("gpu", "GPU", LISTS["GPU"]),
        ("gpus", "GPUs per host", "number"),
    ],
    save=f"{API}/api/hosts",
    delete=f"{API}/api/hosts?id=${{payload.id}}&count=0",
)
datacenter["description"] = (
    "The racks the twin runs, with their hosts. Add one with +, picking a rack prefab; edit one "
    "with its pencil: a rack, CPU, or GPU picked from its list brings its numbers. The twin runs a change from its "
    "next window."
)


def prefabs(part, title, columns, info):
    """A table of prefabs, edited in place: a new one is a copy of the first, with the numbers given."""
    panel = editable(
        title,
        f"{PREFABS}?kind={part}",
        [("name", "Name", "string"), *columns],
        save=f"{PREFABS}?kind={part}",
        delete=f"{PREFABS}?kind={part}&id=${{payload.id:percentencode}}&remove=true",
    )
    panel["description"] = (
        f"{info} Edit, add (+), or delete them; your changes are kept across runs."
    )
    return panel


cpus = prefabs(
    "CPU",
    "CPU prefabs",
    [(field, name, "number") for field, name in SPECS if field != "memory_gb"],
    "CPUs to build racks from, with the idle and maximum power of their server.",
)
gpus = prefabs(
    "GPU",
    "GPU prefabs",
    [(field, name, "number") for field, name in SPECS],
    "GPUs to build racks from, with their idle and maximum power.",
)
racks = prefabs(
    "Rack",
    "Rack prefabs",
    [
        ("cpu", "CPU", LISTS["CPU"]),
        ("memory_gb", "Memory [GB]", "number"),
        ("gpu", "GPU", LISTS["GPU"]),
        ("gpus", "GPUs per host", "number"),
        ("hosts", "Hosts", "number"),
    ],
    "Kinds of hosts: a CPU, memory, and GPUs per host, and how many hosts a rack brings to the datacenter (277, "
    "as SURF-SARA, to compare like with like).",
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
    "start": text(
        CARD,
        script("css.js", "grafana.js", "start.js", progress=f"{BROWSER_API}/api/progress"),
        [
            target(
                PROGRESS,
                [
                    ("step", "step"),
                    ("steps", "steps"),
                    *((k, k, "string") for k in ("doing", "tip")),
                ],
            )
        ],
        WAITING,
        STYLE,
    )
    | {"transparent": True},
}


def colored(name, colors, **props):
    """A number in the colour of each value of `colors` on ({value: name})."""
    return override(name, **thresholds(colors), **props)


# the top of the Dashboard screen: the twin's numbers now, by category, as the rows under it
SHARES = CONFIG["ratios"].values()
COUNTS = sorted({c for r in SHARES for c in re.findall(r"[a-z_]+", f"{r['part']} {r['whole']}")})
GROUPS = {
    "power-group": stat(
        "Power [kW]",
        POWER,
        WATTS,
        [  # in the colours of their lines
            override("Ground truth", color={"mode": "fixed", "fixedColor": GREY}),
            override("OpenDT", color={"mode": "fixed", "fixedColor": GREEN}),
        ],
        [*KW, ("(simulated_power - actual_power)/1000", "Gap")],
        hide=["actual_power", "simulated_power"],
        decimals=1,
    ),
    "jobs-group": stat(
        "Jobs and hosts",
        NOW,
        [(c, c) for c in COUNTS],
        [colored(r["title"], r["colors"]) for r in SHARES] + units("locale", "Jobs finished"),
        [(f"({r['part']}) / ({r['whole']})", r["title"]) for r in SHARES],
        hide=COUNTS,
        more=[
            target(
                NOW, [("tasks_completed", "Jobs finished"), ("cpu_utilization", "CPU utilization")]
            )
        ],
        unit="percentunit",
        decimals=0,
    ),
    # the energy and the CO₂ of the interval shown, named by it
    "sustainability-group": zoned(
        stat(
            "Sustainability",
            CO2,
            [("carbon_emission", "carbon_emission"), ("carbon_intensity", "carbon_intensity")],
            [
                *units("locale", "Intensity [gCO₂/kWh]", "Energy [kWh]", "CO₂ [kg]", decimals=0),
                override("Energy [kWh]", displayName="Energy this ${period} [kWh]"),
                override("CO₂ [kg]", displayName="CO₂ this ${period} [kg]"),
            ],
            [("carbon_emission/1000", "CO₂ [kg/h]"), ("carbon_intensity", "Intensity [gCO₂/kWh]")],
            hide=["carbon_emission", "carbon_intensity"],
            more=[target(TOTALS, [("energy_kwh", "Energy [kWh]"), ("co2_kg", "CO₂ [kg]")])],
            decimals=1,
        ),
        "Intensity [gCO₂/kWh]",
    ),
    # 10% is the community-accepted error rate (question 1.1)
    "accuracy-group": stat(
        "Accuracy",
        f"{ACCURACY}?minutes=5",
        [("mape", "MAPE, 5 min")],
        [
            *(
                colored(f"MAPE, {t}", {0: "green", 10: "red"}, unit="percent")
                for t in ("5 min", "1 h")
            ),
            override("Energy error so far", unit="percent"),
        ],
        more=[
            target(
                ACCURACY,
                [("mape", "MAPE, 1 h"), ("energy_error_pct", "Energy error so far"), ("r", "r")],
            )
        ],
        decimals=1,
    ),
}
# the (i) of each panel, by its name
PANELS = {"power": power, "co2": co2, "hosts": hosts, "decisions": decisions, **BOXES, **GROUPS}
for name, info in CONFIG["info"].items():
    PANELS[name]["description"] = info
