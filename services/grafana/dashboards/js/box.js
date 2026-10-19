// ✎ Change opens an editor in place; Apply, once confirmed, sends the changes to the twin. The screen's refreshes
// draw the box anew, so an open editor is kept in window.opendtEditing and opened again
const box = context.element.querySelector('.lever');
const editing = (window.opendtEditing ??= {});
const levers = [...(box?.querySelectorAll('[data-key]') ?? [])];
const name = box?.dataset.name;
// a choice by its label, a number with its thousands separators
const label = ({ dataset: { choices, labels } }, value) =>
  choices ? labels.split(',')[choices.split(',').indexOf(value)] : Number(value).toLocaleString('en');
levers.forEach((lever) => (lever.textContent = label(lever, lever.dataset.value)));
const open = () => {
  const draft = editing[name];
  levers.forEach((lever) => {
    const { key, choices, labels, min = '', max = '', step = 'any' } = lever.dataset;
    lever.innerHTML = choices
      ? '<select>' + choices.split(',').map((c, i) => '<option value="' + c + '"' + (c === draft[key] ? ' selected' : '') + '>' + labels.split(',')[i] + '</option>').join('') + '</select>'
      : '<input type="number" min="' + min + '" max="' + max + '" step="' + step + '" value="' + draft[key] + '">';
    const input = lever.firstChild;
    input.oninput = () => (draft[key] = input.value);
  });
  box.querySelector('.edit').outerHTML = '<a class="apply">Apply</a><a class="cancel">Cancel</a>';
  const cancel = () => {
    delete editing[name];
    context.grafana.refresh();
  };
  box.querySelector('.cancel').onclick = cancel;
  box.querySelector('.apply').onclick = async () => {
    const changed = levers.filter(({ dataset: { key, value } }) => draft[key] !== value);
    if (!changed.length) return cancel();
    const was = levers.map((l) => label(l, l.dataset.value)).join('-');
    const now = levers.map((l) => label(l, draft[l.dataset.key])).join('-');
    if (!confirm(name + ': ' + was + ' to ' + now + '? The twin follows from its next window.')) return;
    const change = Object.fromEntries(changed.map(({ dataset: { key, choices } }) => [key, choices ? draft[key] : Number(draft[key])]));
    const response = await fetch(control, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) });
    if (response.ok) {
      delete editing[name];
      context.grafana.notifySuccess(['OpenDT', 'Applied']);
      context.grafana.refresh();
    } else {
      const { detail } = await response.json();
      context.grafana.notifyError(['OpenDT', typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; ')]);
    }
  };
};
if (name in editing) open();
else if (levers.length) {
  box.querySelector('.edit').onclick = () => {
    editing[name] = Object.fromEntries(levers.map(({ dataset: { key, value } }) => [key, value]));
    open();
  };
}
