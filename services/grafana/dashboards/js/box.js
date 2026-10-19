// ✎ Change opens an editor in place; Apply, once confirmed, sends the change to the twin. The screen's refreshes
// draw the box anew, so an open editor is kept in window.opendtEditing and opened again
const box = context.element.querySelector('.lever');
const editing = (window.opendtEditing ??= {});
const { key, name, value, choices } = box?.dataset ?? {};
if (key) {
  const shown = box.querySelector('b');
  if (!choices) shown.textContent = Number(value).toLocaleString('en');
  const open = () => {
    const draft = editing[key];
    shown.innerHTML = choices
      ? '<select>' + choices.split(',').map((c) => '<option' + (c === draft ? ' selected' : '') + '>' + c + '</option>').join('') + '</select>'
      : '<input type="number" min="1" value="' + draft + '">';
    box.querySelector('.edit').outerHTML = '<a class="apply">Apply</a><a class="cancel">Cancel</a>';
    const input = shown.querySelector('select, input');
    input.oninput = () => (editing[key] = input.value);
    box.querySelector('.cancel').onclick = () => {
      delete editing[key];
      context.grafana.refresh();
    };
    box.querySelector('.apply').onclick = async () => {
      if (input.value === value) return box.querySelector('.cancel').click();
      if (!confirm(name + ': ' + value + ' to ' + input.value + '? The twin follows from its next window.')) return;
      const change = { [key]: choices ? input.value : Number(input.value) };
      const response = await fetch(control, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(change) });
      if (response.ok) {
        delete editing[key];
        context.grafana.notifySuccess(['OpenDT', 'Applied']);
        context.grafana.refresh();
      } else {
        const { detail } = await response.json();
        context.grafana.notifyError(['OpenDT', typeof detail === 'string' ? detail : detail.map((d) => d.msg).join('; ')]);
      }
    };
  };
  if (key in editing) open();
  else box.querySelector('.edit').onclick = () => {
    editing[key] = value;
    open();
  };
}
