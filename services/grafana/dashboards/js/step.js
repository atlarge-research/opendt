// Hint and Solution unfold theirs; a choice says if it is right or wrong (in green or red, the right one in green)
// and unfolds the solution; another choice takes the last one's place
const card = context.element;
const solution = card.querySelector('.solution');
card.onclick = ({ target }) => {
  const { show, choice } = target.dataset;
  if (show) card.querySelector('.' + show).hidden = false;
  if (!choice) return;
  card.querySelectorAll('[data-choice]').forEach((c) => (c.style.borderColor = colors.none));
  target.style.borderColor = colors[choice];
  if (choice === 'guess') return;
  card.querySelector('[data-choice="right"]').style.borderColor = colors.right;
  solution.querySelector('strong').textContent = (choice === 'right' ? 'Right. ' : 'Wrong. ') + 'Solution:';
  solution.hidden = false;
};
