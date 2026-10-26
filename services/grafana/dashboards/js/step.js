// Tell me what to change, Hint, and Solution show or hide theirs; a wrong choice (in red) says to try another, as in
// the notebooks; the right one (in green) shows the solution
const card = context.element;
const solution = card.querySelector('.solution');
const retry = card.querySelector('.retry');
// one part at a time, so the card fits its panel: this one shown (or, `shown` false, hidden too), the others hidden
const parts = card.querySelectorAll('.change, .retry, .hint, .solution');
const only = (part, shown = true) => parts.forEach((p) => (p.hidden = p !== part || !shown));
// how each step was answered, kept over steps and reloads, its circle ringed in its colour: right at once (green), right
// after a wrong choice or the solution (yellow; darker on the light theme, grafana.js), or wrong so far (red)
const ANSWERS = 'opendt-answers';
const light = document.body.classList.contains('theme-light');
const answered = () => JSON.parse(sessionStorage.getItem(ANSWERS) || '{}');
const rings = (answers) => card.querySelectorAll('[data-step]').forEach((circle) => {
  const outcome = answers[circle.dataset.step];
  if (outcome) circle.style.outline = '2px solid ' + colors[light && outcome === 'late' ? 'late-light' : outcome];
});
rings(answered());
// each button says what a click does: show its part, or hide it again
const labels = () => card.querySelectorAll('[data-show]').forEach((button) => {
  const { show, folded, shown } = button.dataset;
  button.textContent = card.querySelector('.' + show).hidden ? folded : shown;
});
card.onclick = ({ target }) => {
  const { show } = target.dataset;
  if (show) {
    const part = card.querySelector('.' + show);
    // the solution opened before a choice, kept on the card, as this code runs again at every refresh
    if (show === 'solution' && part.hidden) solution.dataset.peeked = 'yes';
    only(part, part.hidden);
  }
  const option = target.closest('[data-choice]');
  if (!option) return labels();
  const { choice } = option.dataset;
  card.querySelectorAll('[data-choice]').forEach((c) => (c.style.borderColor = colors.none));
  option.style.borderColor = colors[choice];
  const answers = answered();
  if (!answers[step] || answers[step] === 'wrong') answers[step] = choice === 'wrong' ? 'wrong' : answers[step] || solution.dataset.peeked ? 'late' : 'right';
  sessionStorage.setItem(ANSWERS, JSON.stringify(answers));
  rings(answers);
  if (choice === 'right') solution.querySelector('strong').textContent = 'Right. Solution:';
  const part = choice === 'right' ? solution : retry;
  only(part);
  labels();
  part.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
};
// opening a step sets the twin as the steps before it left it (`start`), once per visit, and says what it changed;
// the boxes show the changes until the twin follows them (box.js)
const LABELS = { hosts: 'Hosts', carbon_zone: 'CO₂ zone', calibration: 'Calibration', calibration_min: 'r from', calibration_max: 'r to', calibration_points: 'Values of r' };
const shown = (value) => (value === true ? 'On' : value === false ? 'Off' : Number.isFinite(value) ? value.toLocaleString('en') : value);
if (context.grafana.replaceVariables('${step}') === step && sessionStorage.getItem('opendt-step') !== step) {
  sessionStorage.setItem('opendt-step', step);
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
    sessionStorage.removeItem('opendt-step'); // a reload tries again
    warn('Step ' + step + ' could not set the twin');
  });
}
