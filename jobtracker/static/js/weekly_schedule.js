/**
 * Auto-centers the weekly schedule on the current day and ensures
 * the highlighted date matches the displayed header.
 */
document.addEventListener('DOMContentLoaded', () => {
  const schedule = document.querySelector('.weekly-schedule');
  if (!schedule) return;

  const today = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };

  const header = document.querySelector('.weekly-schedule-date');
  if (header) {
    header.textContent = today.toLocaleDateString(undefined, options);
  }

  let activeDay = null;
  schedule.querySelectorAll('[data-date]').forEach((day) => {
    const dayDate = new Date(day.dataset.date);
    if (dayDate.toDateString() === today.toDateString()) {
      day.classList.add('active');
      activeDay = day;
    } else {
      day.classList.remove('active');
    }
  });

  if (activeDay) {
    activeDay.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }
});
