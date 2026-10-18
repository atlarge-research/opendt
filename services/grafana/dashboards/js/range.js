// the time a window shows: Week, the SURF week; Day or 6 h, the twin's last ones, within the week
const range = (window, twin) => {
  const hours = { day: 24, hours: 6 }[window];
  if (!hours) return week;
  const from = Math.max(new Date(twin).getTime() - hours * 3600000, new Date(week.from).getTime());
  return { from, to: from + hours * 3600000 };
};
