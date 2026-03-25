// Mobile navigation toggle
const toggle = document.getElementById('navToggle');
const nav = document.getElementById('mainNav');

if (toggle && nav) {
  toggle.addEventListener('click', () => {
    nav.classList.toggle('open');
  });

  // Close nav when a link is clicked (but not the Teams toggle on mobile)
  nav.querySelectorAll('a').forEach(link => {
    if (!link.closest('.nav-dropdown') || link.closest('.dropdown-menu')) {
      link.addEventListener('click', () => nav.classList.remove('open'));
    }
  });
}

// Teams dropdown
document.querySelectorAll('.nav-dropdown').forEach(item => {
  // Desktop: open/close on mouse hover
  item.addEventListener('mouseenter', () => {
    if (window.innerWidth > 768) item.classList.add('open');
  });
  item.addEventListener('mouseleave', () => {
    if (window.innerWidth > 768) item.classList.remove('open');
  });

  // Mobile: tap the Teams link to toggle the submenu
  item.querySelector(':scope > a').addEventListener('click', e => {
    if (window.innerWidth <= 768) {
      e.preventDefault();
      item.classList.toggle('open');
    }
  });
});

// Close dropdown when clicking elsewhere on the page
document.addEventListener('click', e => {
  if (!e.target.closest('.nav-dropdown')) {
    document.querySelectorAll('.nav-dropdown').forEach(item => item.classList.remove('open'));
  }
});
