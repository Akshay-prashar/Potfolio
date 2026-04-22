// ============================================================
// SPLINE HERO — Load Spline 3D scene via @splinetool/runtime
// Uses latest runtime (1.12.87) matching the exported .splinecode
//
// The canvas has pointer-events:none so the page can scroll
// freely. We forward mousemove events to the Spline app so the
// 3D scene still reacts to cursor position.
// ============================================================

import { Application } from 'https://unpkg.com/@splinetool/runtime@1.12.87/build/runtime.js';

(async function () {
  const canvas = document.getElementById('canvas3d');
  if (!canvas) return;

  // Skip on mobile — CSS hides the container anyway
  if (window.innerWidth <= 768) return;

  const app = new Application(canvas);

  try {
    await app.load('https://prod.spline.design/Et7xG9kjJm8XGCEj/scene.splinecode');
  } catch (err) {
    console.warn('[Spline Hero] Failed to load scene:', err);
    return;
  }

  // ── Prevent Spline from blocking scroll ────────────────────
  // The canvas has pointer-events:auto to receive mouse interaction,
  // but Spline internally calls e.preventDefault() on scroll/wheel
  // events. By intercepting wheel/touchmove events in the capturing 
  // phase and stopping propagation to the canvas, we allow native scroll.
  const preventSplineScrollBlock = (e) => {
    if (e.target === canvas) {
      e.stopPropagation(); // Stop Spline from seeing the scroll event
    }
  };
  
  window.addEventListener('wheel', preventSplineScrollBlock, { capture: true, passive: false });
  window.addEventListener('touchmove', preventSplineScrollBlock, { capture: true, passive: false });

  // Note: The Spline branding watermark is physically covered 
  // by the .spline-watermark-hider div in the HTML/CSS as requested,
  // avoiding the need to hack the DOM or break Spline's runtime state.
})();
