// ============================================================
// NAV — Scroll state, mobile toggle, active page
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  const nav = document.querySelector('.nav');
  const toggle = document.querySelector('.nav__toggle');
  const links = document.querySelector('.nav__links');
  const navLinks = document.querySelectorAll('.nav__link');

  // ── Scroll state ─────────────────────────────────────────
  let lastScroll = 0;

  window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;
    if (scrollY > 50) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
    lastScroll = scrollY;
  }, { passive: true });

  // ── Mobile toggle ────────────────────────────────────────
  if (toggle) {
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('open');
      links.classList.toggle('open');
      document.body.style.overflow = links.classList.contains('open') ? 'hidden' : '';
    });

    // Close menu on link click
    navLinks.forEach(link => {
      link.addEventListener('click', () => {
        toggle.classList.remove('open');
        links.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  // ── Active page highlighting ─────────────────────────────
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';

  navLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (!href) return;
    const linkPage = href.split('/').pop();

    if (linkPage === currentPage ||
        (currentPage === '' && linkPage === 'index.html') ||
        (currentPage.startsWith('project-') && linkPage === 'projects.html')) {
      link.classList.add('active');
    }
  });

  // ── Keyboard navigation ──────────────────────────────────
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && links.classList.contains('open')) {
      toggle.classList.remove('open');
      links.classList.remove('open');
      document.body.style.overflow = '';
      toggle.focus();
    }
  });
});
