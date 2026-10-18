// the view as the address has it, the twin's levers as the API has them
const view = { ...start, period: '${period}', markers: '${markers}' };
context.panel.patchFormValue(view);
context.panel.setInitial({ ...context.panel.initial, ...view });
