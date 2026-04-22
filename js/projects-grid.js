// ============================================================
// PROJECTS GRID — Card tilt effect, filter chips
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Card tilt on hover ───────────────────────────────────
  const cards = document.querySelectorAll('.glass-card');

  if (!prefersReducedMotion) {
    cards.forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const rotateX = ((y - centerY) / centerY) * -4;
        const rotateY = ((x - centerX) / centerX) * 4;

        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-6px) scale(1.01)`;
      });

      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
      });
    });
  }

  // ── Filter chips ─────────────────────────────────────────
  const filterChips = document.querySelectorAll('.filter-chip');
  const projectCards = document.querySelectorAll('.glass-card');

  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      // Update active state
      filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');

      const category = chip.dataset.filter;

      projectCards.forEach(card => {
        if (category === 'all' || card.dataset.category === category) {
          card.style.display = '';
          // Re-trigger reveal animation
          setTimeout(() => card.classList.add('is-visible'), 50);
        } else {
          card.style.display = 'none';
          card.classList.remove('is-visible');
        }
      });
    });
  });

  // ── Staggered entrance ───────────────────────────────────
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry, index) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.classList.add('is-visible');
        }, index * 100);
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.05 });

  cards.forEach(card => {
    card.classList.add('reveal');
    revealObserver.observe(card);
  });
});
