// Mobile navigation toggle
const toggle = document.getElementById('navToggle');
const nav = document.getElementById('mainNav');

if (toggle && nav) {
  toggle.addEventListener('click', () => {
    nav.classList.toggle('open');
  });

  // Close nav when a non-dropdown link is clicked
  nav.querySelectorAll('a').forEach(link => {
    if (!link.closest('.nav-dropdown') || link.closest('.dropdown-menu')) {
      link.addEventListener('click', () => nav.classList.remove('open'));
    }
  });
}

// Teams dropdown: click-toggle on mobile, hover on desktop (CSS handles hover)
document.querySelectorAll('.nav-dropdown').forEach(item => {
  const topLink = item.querySelector(':scope > a');
  topLink.addEventListener('click', e => {
    // On narrow screens the dropdown is toggled by click
    if (window.innerWidth <= 768) {
      e.preventDefault();
      item.classList.toggle('open');
    }
    // On desktop, clicking the top-level link navigates normally (href)
  });
});
