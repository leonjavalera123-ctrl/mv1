// Client-side animation layer. This file is the ONLY JavaScript the page
// ships (until the YouTube facades arrive), and it is pure enhancement:
// the site renders complete and readable before this runs, so users with
// JS disabled — or prefers-reduced-motion — get the full static site.
//
// Hidden-then-revealed states are set from JS (gsap.set / gsap.from),
// never in CSS. If this script fails to load, nothing is ever hidden.

import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (!reducedMotion) {
  gsap.registerPlugin(ScrollTrigger);
  initHero();
  initOrigin();
  initSeasons();
}

/* ---------------------------------------------------------------- hero */

function initHero() {
  // Entrance: the whole hero block rises into place.
  gsap.from('.hero-inner', { opacity: 0, y: 44, duration: 0.9, ease: 'power2.out' });

  // Stat counters count up from 0 to their real (already-rendered) values.
  document.querySelectorAll<HTMLElement>('[data-count]').forEach((el, i) => {
    const target = Number(el.dataset.count);
    const counter = { n: 0 };
    gsap.to(counter, {
      n: target,
      duration: 1.6,
      delay: 0.4 + i * 0.18,
      ease: 'power2.out',
      onUpdate: () => (el.textContent = String(Math.round(counter.n))),
    });
  });

  // Speed lines drift slower than the page: cheap parallax depth.
  gsap.to('.speedlines', {
    yPercent: 18,
    ease: 'none',
    scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true },
  });
}

/* -------------------------------------------------------------- origin */

function initOrigin() {
  gsap.from('.origin .kicker, .origin h2, .origin .lede', {
    opacity: 0,
    y: 32,
    duration: 0.8,
    ease: 'power2.out',
    stagger: 0.18,
    scrollTrigger: { trigger: '.origin', start: 'top 72%', once: true },
  });
}

/* ------------------------------------------------------------- seasons */

function initSeasons() {
  document.querySelectorAll<HTMLElement>('.season').forEach((section) => {
    // The big year numeral slides in from the left, the summary follows.
    gsap.from(section.querySelector('.year'), {
      x: -70,
      opacity: 0,
      duration: 0.7,
      ease: 'power3.out',
      scrollTrigger: { trigger: section, start: 'top 70%', once: true },
    });
    gsap.from(section.querySelector('.head-info'), {
      y: 24,
      opacity: 0,
      duration: 0.7,
      delay: 0.15,
      ease: 'power2.out',
      scrollTrigger: { trigger: section, start: 'top 70%', once: true },
    });

    // Champion seasons: banner pops and gold confetti falls. Once only.
    const banner = section.querySelector<HTMLElement>('.champion-banner');
    if (banner) {
      gsap.from(banner, {
        scale: 0,
        rotation: -6,
        duration: 0.55,
        ease: 'back.out(2.2)',
        scrollTrigger: {
          trigger: section,
          start: 'top 60%',
          once: true,
          onEnter: () => confettiBurst(section, banner),
        },
      });
    }
  });

  // Race cards rise in small staggered batches as they enter the viewport.
  const cards = gsap.utils.toArray<HTMLElement>('.race-grid .card');
  gsap.set(cards, { y: 26, opacity: 0 });
  ScrollTrigger.batch(cards, {
    start: 'top 88%',
    once: true,
    onEnter: (batch) =>
      gsap.to(batch, {
        y: 0,
        opacity: 1,
        duration: 0.5,
        stagger: 0.05,
        ease: 'power2.out',
        // Release inline transforms afterwards so the CSS :hover lift works.
        clearProps: 'transform,opacity',
      }),
  });
}

/* ------------------------------------------------------------ confetti */

// Tiny hand-rolled confetti: ~90 gold/orange flakes on a throwaway canvas.
// A library would be 10× the bytes for the same two seconds of joy.
function confettiBurst(section: HTMLElement, origin: HTMLElement) {
  const canvas = document.createElement('canvas');
  const rect = section.getBoundingClientRect();
  const originRect = origin.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = Math.min(rect.height, 700);
  Object.assign(canvas.style, {
    position: 'absolute',
    inset: '0',
    width: '100%',
    pointerEvents: 'none',
  } as CSSStyleDeclaration);
  section.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const startX = originRect.left - rect.left + originRect.width / 2;
  const startY = originRect.top - rect.top + originRect.height / 2;
  const colors = ['#f0b323', '#ffd968', '#ff7900', '#eef0fb', '#d21f2c'];

  const flakes = Array.from({ length: 90 }, () => ({
    x: startX,
    y: startY,
    vx: (Math.random() - 0.5) * 11,
    vy: -(Math.random() * 8 + 3),
    w: Math.random() * 7 + 4,
    h: Math.random() * 4 + 2,
    rot: Math.random() * Math.PI,
    vr: (Math.random() - 0.5) * 0.3,
    color: colors[Math.floor(Math.random() * colors.length)],
  }));

  const started = performance.now();
  const DURATION = 2200;

  function frame(now: number) {
    const t = now - started;
    ctx!.clearRect(0, 0, canvas.width, canvas.height);
    ctx!.globalAlpha = t > DURATION - 500 ? Math.max(0, (DURATION - t) / 500) : 1;
    for (const f of flakes) {
      f.vy += 0.16; // gravity
      f.x += f.vx;
      f.y += f.vy;
      f.rot += f.vr;
      ctx!.save();
      ctx!.translate(f.x, f.y);
      ctx!.rotate(f.rot);
      ctx!.fillStyle = f.color;
      ctx!.fillRect(-f.w / 2, -f.h / 2, f.w, f.h);
      ctx!.restore();
    }
    if (t < DURATION) requestAnimationFrame(frame);
    else canvas.remove();
  }
  requestAnimationFrame(frame);
}
