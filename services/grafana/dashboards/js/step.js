// Hint and Solution unfold theirs; a choice says if it is right or wrong (in green or red, the right one in green)
// and unfolds the solution; another choice takes the last one's place
const card = context.element;
const solution = card.querySelector('.solution');
card.onclick = ({ target }) => {
  const { show } = target.dataset;
  if (show) card.querySelector('.' + show).hidden = false;
  const option = target.closest('[data-choice]');
  if (!option) return;
  const { choice } = option.dataset;
  card.querySelectorAll('[data-choice]').forEach((c) => (c.style.borderColor = colors.none));
  option.style.borderColor = colors[choice];
  card.querySelector('[data-choice="right"]').style.borderColor = colors.right;
  solution.querySelector('strong').textContent = (choice === 'right' ? 'Right. ' : 'Wrong. ') + 'Solution:';
  solution.hidden = false;
  solution.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
};
