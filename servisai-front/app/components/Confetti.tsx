"use client";

import { useEffect, useRef } from "react";

const COLORS = ["#1557ff", "#4f9cff", "#22c55e", "#facc15", "#f97316", "#ec4899", "#a855f7"];
const DURATION_MS = 4500;

type Piece = { x: number; y: number; vx: number; vy: number; w: number; h: number; rot: number; vr: number; color: string; round: boolean };

/** Bayramona konfetti: ekranning ikki pastki burchagidan otiladi va pastga sochiladi. Bir marta o‘ynaydi. */
export default function Confetti() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    // Harakatni kamaytirish so‘ralgan bo‘lsa animatsiya o‘ynalmaydi
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const W = window.innerWidth;
    const H = window.innerHeight;
    const burst = (fromLeft: boolean): Piece[] =>
      Array.from({ length: 90 }, () => {
        const angle = ((fromLeft ? -60 : -120) + (Math.random() - 0.5) * 40) * (Math.PI / 180);
        const speed = 12 + Math.random() * 10;
        return {
          x: fromLeft ? 0 : W,
          y: H * 0.85,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          w: 6 + Math.random() * 6,
          h: 8 + Math.random() * 8,
          rot: Math.random() * Math.PI,
          vr: (Math.random() - 0.5) * 0.3,
          color: COLORS[Math.floor(Math.random() * COLORS.length)],
          round: Math.random() < 0.3,
        };
      });
    const pieces = [...burst(true), ...burst(false)];

    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = now - start;
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = t > DURATION_MS - 1000 ? Math.max(0, (DURATION_MS - t) / 1000) : 1;
      for (const p of pieces) {
        p.vy += 0.35; // og‘irlik
        p.vx *= 0.99;
        p.vy *= 0.99;
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        if (p.round) {
          ctx.beginPath();
          ctx.arc(0, 0, p.w / 2, 0, Math.PI * 2);
          ctx.fill();
        } else {
          // Aylanayotgandek ko‘rinishi uchun eni o‘zgarib turadi
          ctx.fillRect(-p.w / 2, -p.h / 2, p.w * Math.abs(Math.cos(p.rot * 2)), p.h);
        }
        ctx.restore();
      }
      if (t < DURATION_MS) frame = requestAnimationFrame(tick);
      else ctx.clearRect(0, 0, W, H);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} aria-hidden className="pointer-events-none fixed inset-0 z-[100] size-full" />;
}
