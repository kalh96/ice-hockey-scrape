// Mobile navigation toggle
const toggle = document.getElementById('navToggle');
const nav = document.getElementById('mainNav');

if (toggle && nav) {
  toggle.addEventListener('click', () => {
    nav.classList.toggle('open');
  });

  // Close nav when a link is clicked
  nav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => nav.classList.remove('open'));
  });
}
