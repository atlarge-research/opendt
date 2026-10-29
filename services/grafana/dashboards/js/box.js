// a click opens Grafana's dialog with what the box's levers take; Apply, once confirmed in Grafana's confirm dialog,
// sends the changes to the twin. On the page, the dialog outlives the box's refreshes
const box = context.element.querySelector('.lever');
const rows = [...box.querySelectorAll('[data-name]')];
const levers = [...box.querySelectorAll('[data-key]')];
// a choice by its label, a number with its thousands separators
const label = ({ dataset: { choices, labels } }, value) =>
  choices ? labels.split('|')[choices.split(',').indexOf(value)] ?? value : Number(value).toLocaleString('en');
// a change sent, shown (old → new, pulsing in white on blue) until the twin follows it: the hosts and the CO2 zone
// from its next window, which takes longer with more hosts; kept over page reloads, for 10 minutes at most (a
// restarted twin may never follow it), and shared by the boxes of every screen
const PENDING = 'opendt-pending';
const load = () => JSON.parse(sessionStorage.getItem(PENDING) || '{}');
const save = (sent) => sessionStorage.setItem(PENDING, JSON.stringify(sent));
const same = ({ dataset: { choices } }, a, b) => (choices ? a === b : Number(a) === Number(b));
const pending = load();
levers.forEach((lever) => {
  const { key, value } = lever.dataset;
  const done = pending[key] && (same(lever, pending[key].value, value) || Date.now() - pending[key].at > 600000);
  if (done) delete pending[key];
  const sent = key in pending;
  lever.textContent = label(lever, value) + (sent ? ' → ' + label(lever, pending[key].value) : '');
  lever.classList.toggle('pending', sent);
  lever.title = sent ? 'Sent; the twin follows from its next window' : '';
});
save(pending);
const open = () => {
  // on a node of the page, shared by the four boxes
  document.getElementById('opendt-lever') || document.body.insertAdjacentHTML('beforeend', '<div id="opendt-lever"></div>');
  const node = document.getElementById('opendt-lever');
  const draft = Object.fromEntries(levers.map(({ dataset: { key, value } }) => [key, value]));
  const changed = () => levers.filter(({ dataset }) => draft[dataset.key] !== dataset.value);
  const close = () => render(node, () => null);
  // e.g., Hosts: 277 to 300; Range of r: 3-9 to 3-10
  const question = () => rows.filter((row) => changed().some((l) => row.contains(l))).map((row) => {
    const mine = [...row.querySelectorAll('[data-key]')];
    const values = (value) => mine.map((l) => label(l, value(l))).join('-');
    return row.dataset.name + ': ' + values((l) => l.dataset.value) + ' to ' + values((l) => draft[l.dataset.key]);
  }).join('; ') + '? The twin follows from its next window.';
  const send = async () => {
    const change = Object.fromEntries(changed().map(({ dataset: { key, choices } }) => [key, choices ? draft[key] : Number(draft[key])]));
    try {
      const response = await fetch(control, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) });
      if (!response.ok) {
        const { detail } = await response.json();
        return warn(typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; '));
      }
    } catch {
      return warn('The twin did not answer; try again');
    }
    const sent = load();  // other boxes may have changed it since this one rendered
    changed().forEach(({ dataset: { key } }) => (sent[key] = { value: draft[key], at: Date.now() }));
    save(sent);
    close();
    context.grafana.notifySuccess(['OpenDT', 'Applied']);
    context.grafana.refresh();
  };
  // the levers, or, after Apply with a change, the question; drawn anew after each click
  const draw = (confirming) => render(node, (h, ui) => {
    if (confirming) {
      return h(ui.ConfirmModal, { isOpen: true, title, body: question(), confirmText: 'Apply', confirmButtonVariant: 'primary', onConfirm: send, onDismiss: () => draw() });
    }
    // a lever's choices as buttons, the draft's in blue, or its number
    const edit = ({ dataset: { key, choices, labels, min, max, step } }) => choices
      ? h(ui.ButtonGroup, null, ...choices.split(',').map((choice, i) =>
        h(ui.Button, { variant: choice === draft[key] ? 'primary' : 'secondary', onClick: () => { draft[key] = choice; draw(); } }, labels.split('|')[i])))
      : h(ui.Input, { type: 'number', min, max, step, defaultValue: draft[key], onChange: ({ target }) => (draft[key] = target.value) });
    const fields = rows.map((row) => {
      const [first, second] = [...row.querySelectorAll('[data-key]')].map(edit);
      return h(ui.Field, { label: row.dataset.name, description: row.dataset.info }, h(ui.Stack, { alignItems: 'center' }, first, second && 'to', second));
    });
    const apply = () => (changed().length ? draw(true) : close());
    return h(ui.Modal, { title, isOpen: true, onDismiss: close }, ...fields,
      h(ui.Modal.ButtonRow, null, h(ui.Button, { variant: 'secondary', onClick: close }, 'Cancel'), h(ui.Button, { onClick: apply }, 'Apply')));
  });
  draw();
};
// before the twin's first window, a box has no levers yet
if (levers.length) {
  box.onclick = ({ target }) => {
    if (!target.href) open();
  };
}
