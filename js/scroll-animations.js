// ============================================================
// SCROLL ANIMATIONS — Intersection Observer reveal system
// Lightweight alternative to GSAP for basic reveals. Uses only
// transform + opacity (GPU-accelerated per UX guidelines).
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  // ── Reduced motion check ─────────────────────────────────
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (prefersReducedMotion) {
    // Make everything visible immediately
    document.querySelectorAll('.reveal').forEach(el => {
      el.classList.add('is-visible');
    });
    return;
  }

  // ── Intersection Observer for reveals ────────────────────
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -60px 0px'
  });

  document.querySelectorAll('.reveal').forEach(el => {
    revealObserver.observe(el);
  });

  // ── Parallax effect for decorated elements ───────────────
  const parallaxElements = document.querySelectorAll('[data-parallax]');

  if (parallaxElements.length > 0) {
    let ticking = false;

    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const scrollY = window.scrollY;

          parallaxElements.forEach(el => {
            const speed = parseFloat(el.dataset.parallax) || 0.1;
            const rect = el.getBoundingClientRect();
            const centerY = rect.top + rect.height / 2;
            const viewportCenter = window.innerHeight / 2;
            const offset = (centerY - viewportCenter) * speed;

            el.style.transform = `translateY(${offset}px)`;
          });

          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // ── Loading animation ────────────────────────────────────
  const loader = document.querySelector('.loader');
  if (loader) {
    window.addEventListener('load', () => {
      setTimeout(() => {
        loader.classList.add('loaded');
        document.body.classList.add('page-enter');
      }, 1300);
    });
  }

  // ── Counter animation for metrics ────────────────────────
  const counters = document.querySelectorAll('[data-counter]');

  if (counters.length > 0) {
    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const target = parseInt(el.dataset.counter, 10);
          const duration = 1500;
          const start = Date.now();

          function updateCounter() {
            const elapsed = Date.now() - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            const current = Math.floor(eased * target);
            el.textContent = current.toLocaleString();

            if (progress < 1) {
              requestAnimationFrame(updateCounter);
            } else {
              el.textContent = target.toLocaleString();
            }
          }

          updateCounter();
          counterObserver.unobserve(el);
        }
      });
    }, { threshold: 0.5 });

    counters.forEach(el => counterObserver.observe(el));
  }
});
