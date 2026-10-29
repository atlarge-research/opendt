// the step's answer, in Grafana's own components (ui.js): Tell me what to change, the choices, and one part at a time,
// so the card fits its panel; then Hint and Solution, which show or hide theirs, and Back and Next. A wrong choice (in
// red) says to try another, as in the notebooks; the right one (in green) shows the solution
const node = context.element.querySelector('.answer');
// kept on the node, as this code runs again at every refresh: the part shown, the choice, and whether the solution
// opened before it; a part scrolls into view as it opens (`scroll`, made once, so a refresh does not scroll again)
const state = (node.state ??= { part: null, chosen: null, peeked: false, scroll: (alert) => alert?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) });
// how each step was answered, kept over steps and reloads, its circle ringed in its colour: right at once (green), right
// after a wrong choice or the solution (yellow; darker on the light theme, grafana.js), or wrong so far (red)
const ANSWERS = 'opendt-answers';
const light = document.body.classList.contains('theme-light');
const answered = () => JSON.parse(sessionStorage.getItem(ANSWERS) || '{}');
const rings = (answers) => context.element.querySelectorAll('[data-step]').forEach((circle) => {
  const outcome = answers[circle.dataset.step];
  if (outcome) circle.style.border = '2px solid ' + colors[light && outcome === 'late' ? 'late-light' : outcome];
});
rings(answered());
const show = (part) => {
  if (part === 'solution' && state.part !== part) state.peeked = true;
  state.part = state.part === part ? null : part;
  draw();
};
const choose = (letter) => {
  const choice = letter === answer ? 'right' : 'wrong';
  const answers = answered();
  if (!answers[step] || answers[step] === 'wrong') answers[step] = choice === 'wrong' ? 'wrong' : answers[step] || state.peeked ? 'late' : 'right';
  sessionStorage.setItem(ANSWERS, JSON.stringify(answers));
  rings(answers);
  state.chosen = letter;
  state.part = choice === 'right' ? 'solution' : 'retry';
  draw();
};
const draw = () => render(node, (h, ui) => {
  // each button says what a click does: show its part, or hide it again
  const unfolds = (part, label, hide) => h(ui.Button, { variant: 'secondary', onClick: () => show(part) }, state.part === part ? hide : label);
  const [severity, prefix, text] = {
    change: ['info', 'Change:', change],
    retry: ['error', 'Not quite;', 'look at what the plots show, then try another.'],
    hint: ['warning', 'Hint:', hint],
    solution: ['success', state.chosen === answer ? 'Right. Solution:' : 'Solution:', solution],
  }[state.part] ?? [];
  // the part shown under its button or the choices, its prefix in bold and its text in one line (no title)
  const alert = state.part && h(ui.Alert, { key: state.part, ref: state.scroll, severity, title: '', bottomSpacing: 0 }, h('strong', null, prefix), ' ', text);
  return h(ui.Stack, { direction: 'column' },
    change && h('div', null, unfolds('change', 'Tell me what to change', 'Hide what to change')), // on a line of its own
    state.part === 'change' && alert,
    // on a click, not a change, so a click on the choice already made shows its part again
    h('div', { onClick: ({ target }) => target.type === 'radio' && choose(target.value) }, h(ui.RadioButtonList, {
      name: 'step-' + step,
      options: choices.map((text, i) => ({ value: 'ABCD'[i], label: 'ABCD'[i] + '. ' + text })),
      value: state.chosen,
    })),
    state.part !== 'change' && alert,
    h(ui.Stack, { justifyContent: 'space-between' },
      h(ui.Stack, null, unfolds('hint', 'Hint', 'Hide hint'), unfolds('solution', 'Solution', 'Hide solution')),
      h(ui.Stack, null, around.map(([i, label]) => h(ui.Button, { key: label, variant: 'secondary', onClick: () => context.grafana.locationService.push(context.grafana.replaceVariables(here + i)) }, label)))));
});
draw();
// opening a step sets the twin as the steps before it left it (`start`), once per visit, and says what it changed;
// the boxes show the changes until the twin follows them (box.js)
const LABELS = { hosts: 'Hosts', carbon_zone: 'CO₂ zone', calibration: 'Calibration', calibration_min: 'r from', calibration_max: 'r to', calibration_points: 'Values of r' };
const shown = (value) => (value === true ? 'On' : value === false ? 'Off' : Number.isFinite(value) ? value.toLocaleString('en') : value);
// a step that could not set the twin tries again at the next refresh (this code runs again) or reload, until it can
const failed = sessionStorage.getItem('opendt-failed') === step;
if (context.grafana.replaceVariables('${step}') === step && (sessionStorage.getItem('opendt-step') !== step || failed)) {
  sessionStorage.setItem('opendt-step', step);
  sessionStorage.removeItem('opendt-failed');
  fetch(status).then((response) => response.json()).then(async (now) => {
    // what the twin is about to run: a change sent and not yet followed (box.js, at most 10 minutes old) counts, so
    // going back a step undoes the change of the step after it
    const pending = JSON.parse(sessionStorage.getItem('opendt-pending') || '{}');
    const next = (key) => (Date.now() - (pending[key]?.at ?? 0) < 600000 ? pending[key].value : now[key]);
    const change = Object.fromEntries(Object.entries(start).filter(([key, value]) => String(next(key)) !== String(value)));
    if (!Object.keys(change).length) return;
    const response = await fetch(control, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) });
    if (!response.ok) throw Error(response.status);
    Object.entries(change).forEach(([key, value]) => (pending[key] = { value: String(value), at: Date.now() }));
    sessionStorage.setItem('opendt-pending', JSON.stringify(pending));
    const text = Object.entries(change).map(([key, value]) => LABELS[key] + ' ' + shown(value)).join(', ');
    context.grafana.notifySuccess(['OpenDT', 'Step ' + step + ' starts from ' + text]);
    context.grafana.refresh();
  }).catch(() => {
    sessionStorage.setItem('opendt-failed', step);
    if (!failed) warn('Step ' + step + ' could not set the twin'); // once, not at every try
  });
}
