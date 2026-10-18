// on Apply, the changed levers go to the twin; the view changes once the twin has them (applied.js)
const { elements, initial } = context.panel;
const levers = elements.filter((e) => !view.includes(e.id) && e.value !== initial[e.id]);
return Object.fromEntries(levers.map((e) => [e.id, e.value]));
