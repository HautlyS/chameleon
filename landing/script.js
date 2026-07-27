/* ============================================
   CHAMELEON — LANDING PAGE SCRIPT
   Scroll reveal + nav behavior
   ============================================ */

document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  // --- Scroll Reveal ---
  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -60px 0px'
  });

  // Observe all section containers + bento cells + steps + quote cards
  var targets = document.querySelectorAll(
    '.features, .steps, .testimonials, .cta-section, ' +
    '.bento-cell, .step, .quote-card, .trusted'
  );

  targets.forEach(function (el) {
    el.classList.add('reveal');
    observer.observe(el);
  });

  // Hero elements reveal immediately with stagger
  var heroEls = document.querySelectorAll(
    '.hero-headline, .hero-sub, .hero-actions, .hero-footnote, .hero-visual'
  );

  heroEls.forEach(function (el, i) {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    el.style.transitionDelay = (i * 120) + 'ms';

    requestAnimationFrame(function () {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });
  });

  // --- Reduced Motion: skip all animations ---
  var motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (motionQuery.matches) {
    targets.forEach(function (el) {
      el.classList.remove('reveal');
      el.style.opacity = '1';
      el.style.transform = 'none';
      el.style.transition = 'none';
    });

    heroEls.forEach(function (el) {
      el.style.opacity = '1';
      el.style.transform = 'none';
      el.style.transition = 'none';
    });
  }
});
