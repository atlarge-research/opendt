// a click opens the box larger, over the screen, with what its levers take; Apply, once confirmed, sends the
// changes to the twin. Over the screen, the open box outlives the screen's refreshes
const box = context.element.querySelector('.lever');
const levers = [...box.querySelectorAll('[data-key]')];
const { name } = box.dataset;
// a choice by its label, a number with its thousands separators
const label = ({ dataset: { choices, labels } }, value) =>
  choices ? labels.split('|')[choices.split(',').indexOf(value)] : Number(value).toLocaleString('en');
levers.forEach((lever) => (lever.textContent = label(lever, lever.dataset.value)));
if (!document.getElementById('opendt-lever')) {
  document.head.insertAdjacentHTML('beforeend', '<style id="opendt-lever">' + style + '</style>');
}
const open = () => {
  document.querySelector('.opendt-lever')?.remove();
  const draft = Object.fromEntries(levers.map(({ dataset: { key, value } }) => [key, value]));
  const { left, top, width } = (box.closest('section') ?? box).getBoundingClientRect();
  const big = document.createElement('div');
  big.className = 'opendt-lever';
  big.style.cssText = 'left: ' + (left + scrollX) + 'px; top: ' + (top + scrollY) + 'px; width: ' + width + 'px';
  big.innerHTML =
    '<small>' + name + '</small>' +
    levers.map(({ dataset: { key, choices, labels, min = '', max = '', step = 'any' } }) => choices
      ? choices.split(',').map((c, i) => '<button class="choice' + (c === draft[key] ? ' on' : '') + '" data-key="' + key + '" value="' + c + '">' + labels.split('|')[i] + '</button>').join('')
      : '<input type="number" data-key="' + key + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + draft[key] + '">'
    ).join('<small>to</small>') +
    '<div><button class="apply">Apply</button><button class="cancel">Cancel</button></div>';
  big.oninput = ({ target }) => (draft[target.dataset.key] = target.value);
  big.onclick = async ({ target }) => {
    if (target.classList.contains('choice')) {
      draft[target.dataset.key] = target.value;
      big.querySelectorAll('.choice').forEach((c) => c.classList.toggle('on', c === target));
    }
    if (target.className === 'cancel') big.remove();
    if (target.className !== 'apply') return;
    const changed = levers.filter(({ dataset: { key, value } }) => draft[key] !== value);
    if (!changed.length) return big.remove();
    const was = levers.map((l) => label(l, l.dataset.value)).join('-');
    const now = levers.map((l) => label(l, draft[l.dataset.key])).join('-');
    if (!confirm(name + ': ' + was + ' to ' + now + '? The twin follows from its next window.')) return;
    const change = Object.fromEntries(changed.map(({ dataset: { key, choices } }) => [key, choices ? draft[key] : Number(draft[key])]));
    const response = await fetch(control, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) });
    if (response.ok) {
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
