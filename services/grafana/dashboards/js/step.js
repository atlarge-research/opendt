// Hint and Solution unfold theirs; a choice turns green if right (and the solution unfolds), red if wrong
const card = context.element;
card.onclick = ({ target }) => {
  const { show, choice } = target.dataset;
  if (show) card.querySelector('.' + show).hidden = false;
  if (choice) target.style.borderColor = colors[choice];
  if (choice === 'right') card.querySelector('.solution').hidden = false;
};
