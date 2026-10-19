// while the twin starts, the API has no status yet: ask again in 5 s
if (!context.panel.initial?.twin_time) setTimeout(() => context.panel.initialRequest(), 5000);
