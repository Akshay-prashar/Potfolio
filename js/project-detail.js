// ============================================================
// PROJECT DETAIL — Brutalist page interactions
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Section reveal on scroll ─────────────────────────────
  const sections = document.querySelectorAll('.detail-section, .outcome-block, .detail-hero__category, .detail-hero__summary, .detail-hero__meta');

  if (!prefersReducedMotion) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    sections.forEach(el => {
      el.classList.add('reveal');
      observer.observe(el);
    });
  } else {
    sections.forEach(el => el.classList.add('is-visible'));
  }

  // ── Feature items stagger ────────────────────────────────
  const featureItems = document.querySelectorAll('.feature-list__item');

  if (!prefersReducedMotion && featureItems.length > 0) {
    const featureObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          const items = entry.target.querySelectorAll ? [entry.target] : [];
          setTimeout(() => {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateX(0)';
          }, i * 80);
          featureObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });

    featureItems.forEach((item, i) => {
      item.style.opacity = '0';
      item.style.transform = 'translateX(-20px)';
      item.style.transition = `all 0.4s cubic-bezier(0.22, 1, 0.36, 1) ${i * 0.08}s`;
      featureObserver.observe(item);
    });
  }
});
