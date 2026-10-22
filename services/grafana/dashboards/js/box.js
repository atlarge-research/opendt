// a click opens the box larger, over the screen, with what its levers take; Apply, once confirmed, sends the
// changes to the twin. Over the screen, the open box outlives the screen's refreshes
const box = context.element.querySelector('.lever');
const rows = [...box.querySelectorAll('[data-name]')];
const levers = [...box.querySelectorAll('[data-key]')];
// a choice by its label, a number with its thousands separators
const label = ({ dataset: { choices, labels } }, value) =>
  choices ? labels.split('|')[choices.split(',').indexOf(value)] : Number(value).toLocaleString('en');
// a change sent, shown (old → new, in blue) until the twin follows it: the hosts and the CO2 zone from its next
// window, which takes longer with more hosts; shared by the boxes of every screen
const pending = (window.opendtPending ??= {});
const same = ({ dataset: { choices } }, a, b) => (choices ? a === b : Number(a) === Number(b));
levers.forEach((lever) => {
  const { key, value } = lever.dataset;
  if (key in pending && same(lever, pending[key], value)) delete pending[key];
  const sent = key in pending;
  lever.textContent = label(lever, value) + (sent ? ' → ' + label(lever, pending[key]) : '');
  lever.style.color = sent ? '#6e9fff' : '';
  lever.title = sent ? 'Sent; the twin follows from its next window' : '';
});
css('opendt-lever', style);
// a lever's choices as buttons, or its number
const edit = ({ dataset: { key, choices, labels, min = '', max = '', step = 'any' } }, draft) => choices
  ? choices.split(',').map((c, i) => '<button class="choice' + (c === draft[key] ? ' on' : '') + '" data-key="' + key + '" value="' + c + '">' + labels.split('|')[i] + '</button>').join('')
  : '<input type="number" data-key="' + key + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + draft[key] + '">';
const open = () => {
  document.querySelector('.opendt-lever')?.remove();
  const draft = Object.fromEntries(levers.map(({ dataset: { key, value } }) => [key, value]));
  const { left, top, width } = (box.closest('section') ?? box).getBoundingClientRect();
  const big = document.createElement('div');
  big.className = 'opendt-lever';
  big.style.cssText = 'left: ' + (left + scrollX) + 'px; top: ' + (top + scrollY) + 'px; width: ' + width + 'px';
  big.innerHTML =
    rows.map((row) => '<small>' + row.dataset.name + '</small><div>' + [...row.querySelectorAll('[data-key]')].map((l) => edit(l, draft)).join('to') + '</div>').join('') +
    '<div><button class="apply">Apply</button><button class="cancel">Cancel</button></div>';
  big.oninput = ({ target }) => (draft[target.dataset.key] = target.value);
  big.onclick = async ({ target }) => {
    const { key } = target.dataset;
    if (target.classList.contains('choice')) {
      draft[key] = target.value;
      big.querySelectorAll('.choice[data-key="' + key + '"]').forEach((c) => c.classList.toggle('on', c === target));
    }
    if (target.className === 'cancel') big.remove();
    if (target.className !== 'apply') return;
    const changed = levers.filter(({ dataset }) => draft[dataset.key] !== dataset.value);
    if (!changed.length) return big.remove();
    // e.g., Hosts: 277 to 300; Range of r: 3-9 to 3-10
    const text = rows.filter((row) => changed.some((l) => row.contains(l))).map((row) => {
      const mine = [...row.querySelectorAll('[data-key]')];
      const values = (value) => mine.map((l) => label(l, value(l))).join('-');
      return row.dataset.name + ': ' + values((l) => l.dataset.value) + ' to ' + values((l) => draft[l.dataset.key]);
    });
    if (!confirm(text.join('; ') + '? The twin follows from its next window.')) return;
    const change = Object.fromEntries(changed.map(({ dataset: { key, choices } }) => [key, choices ? draft[key] : Number(draft[key])]));
    const response = await fetch(control, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) });
    if (response.ok) {
      changed.forEach(({ dataset: { key } }) => (pending[key] = draft[key]));
      big.remove();
      context.grafana.notifySuccess(['OpenDT', 'Applied']);
      context.grafana.refresh();
    } else {
      const { detail } = await response.json();
      context.grafana.notifyError(['OpenDT', typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; ')]);
    }
  };
  document.body.append(big);
};
// before the twin's first window, a box has no levers yet
if (levers.length) {
  box.onclick = ({ target }) => {
    if (!target.href) open();
  };
}
