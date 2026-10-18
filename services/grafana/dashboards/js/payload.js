// on Apply, the changed levers go to the twin; the view changes once the twin has them (applied.js)
const levers = changed(context.panel).filter((e) => !view.includes(e.id));
return Object.fromEntries(levers.map((e) => [e.id, e.value]));
