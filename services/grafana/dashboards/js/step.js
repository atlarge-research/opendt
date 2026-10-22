// Hint and Solution unfold theirs; a wrong choice (in red) says to try another, as in the notebooks; the right one
// (in green) unfolds the solution
const card = context.element;
const solution = card.querySelector('.solution');
const retry = card.querySelector('.retry');
card.onclick = ({ target }) => {
  const { show } = target.dataset;
  if (show) card.querySelector('.' + show).hidden = false;
  const option = target.closest('[data-choice]');
  if (!option) return;
  const { choice } = option.dataset;
  card.querySelectorAll('[data-choice]').forEach((c) => (c.style.borderColor = colors.none));
  option.style.borderColor = colors[choice];
  retry.hidden = choice === 'right';
  if (choice === 'right') {
    solution.querySelector('strong').textContent = 'Right. Solution:';
    solution.hidden = false;
  }
  (choice === 'right' ? solution : retry).scrollIntoView({ block: 'nearest', behavior: 'smooth' });
};
