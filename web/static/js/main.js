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

// Table sorting
document.querySelectorAll('table.sortable').forEach(table => {
  const ths = Array.from(table.querySelectorAll('thead th'));
  const tbody = table.querySelector('tbody');
  if (!tbody) return;

  // Index of the rank column to re-number after sort (optional)
  const rankTh = table.querySelector('thead th[data-sort-rank]');
  const rankIdx = rankTh ? ths.indexOf(rankTh) : -1;

  ths.forEach((th, colIdx) => {
    th.classList.add('th-sortable');
    let dir = 1; // 1 = asc, -1 = desc

    th.addEventListener('click', () => {
      ths.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));

      const rows = Array.from(tbody.querySelectorAll('tr'));

      rows.sort((a, b) => {
        const aText = (a.cells[colIdx]?.textContent ?? '').trim();
        const bText = (b.cells[colIdx]?.textContent ?? '').trim();

        // Dashes (null values) always sort to the bottom
        const aBlank = aText === '–' || aText === '' || aText === '-';
        const bBlank = bText === '–' || bText === '' || bText === '-';
        if (aBlank && bBlank) return 0;
        if (aBlank) return 1;
        if (bBlank) return -1;

        // Numeric sort (handles +5, 0.923, plain integers)
        const aNum = parseFloat(aText.replace(/^\+/, ''));
        const bNum = parseFloat(bText.replace(/^\+/, ''));
        if (!isNaN(aNum) && !isNaN(bNum)) return dir * (aNum - bNum);

        // Fallback: alphabetical
        return dir * aText.localeCompare(bText);
      });

      rows.forEach(row => tbody.appendChild(row));

      // Re-number rank column if present
      if (rankIdx >= 0) {
        tbody.querySelectorAll('tr').forEach((row, i) => {
          if (row.cells[rankIdx]) row.cells[rankIdx].textContent = i + 1;
        });
      }

      th.classList.add(dir === 1 ? 'sort-asc' : 'sort-desc');
      dir = -dir;
    });
  });
});
