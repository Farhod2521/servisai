import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Base({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const ArrowRight = (p: IconProps) => (
  <Base {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Base>
);
export const ChevronDown = (p: IconProps) => (
  <Base {...p}>
    <path d="m6 9 6 6 6-6" />
  </Base>
);
export const ChevronLeft = (p: IconProps) => (
  <Base {...p}>
    <path d="m15 18-6-6 6-6" />
  </Base>
);
export const ChevronRight = (p: IconProps) => (
  <Base {...p}>
    <path d="m9 18 6-6-6-6" />
  </Base>
);
export const Search = (p: IconProps) => (
  <Base {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Base>
);
export const Cart = (p: IconProps) => (
  <Base {...p}>
    <circle cx="9" cy="20" r="1.4" />
    <circle cx="18" cy="20" r="1.4" />
    <path d="M2 3h3l2.6 12.4a2 2 0 0 0 2 1.6h8.3a2 2 0 0 0 2-1.5L22 8H6" />
  </Base>
);
export const Menu = (p: IconProps) => (
  <Base {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </Base>
);
export const Close = (p: IconProps) => (
  <Base {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Base>
);
export const Play = (p: IconProps) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="m10 8 6 4-6 4z" fill="currentColor" />
  </Base>
);
export const Bolt = (p: IconProps) => (
  <Base {...p}>
    <path d="M13 2 4 14h7l-1 8 9-12h-7z" fill="currentColor" />
  </Base>
);
export const Shield = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="m9 12 2 2 4-4" />
  </Base>
);
export const Headset = (p: IconProps) => (
  <Base {...p}>
    <path d="M3 14v-2a9 9 0 0 1 18 0v2" />
    <path d="M21 15a2 2 0 0 1-2 2h-1v-6h1a2 2 0 0 1 2 2zM3 15a2 2 0 0 0 2 2h1v-6H5a2 2 0 0 0-2 2z" />
    <path d="M18 17v1a3 3 0 0 1-3 3h-3" />
  </Base>
);
export const Grid = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="3" width="7" height="7" rx="2" />
    <rect x="14" y="3" width="7" height="7" rx="2" />
    <rect x="3" y="14" width="7" height="7" rx="2" />
    <rect x="14" y="14" width="7" height="7" rx="2" />
  </Base>
);
export const Bot = (p: IconProps) => (
  <Base {...p}>
    <rect x="4" y="8" width="16" height="12" rx="3" />
    <path d="M12 8V4M9 4h6" />
    <circle cx="9" cy="14" r="1" fill="currentColor" />
    <circle cx="15" cy="14" r="1" fill="currentColor" />
  </Base>
);
export const Video = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <path d="m10 9 5 3-5 3z" fill="currentColor" />
  </Base>
);
export const Code = (p: IconProps) => (
  <Base {...p}>
    <path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" />
  </Base>
);
export const Cap = (p: IconProps) => (
  <Base {...p}>
    <path d="M2 9 12 4l10 5-10 5z" />
    <path d="M6 11v5c3 2.5 9 2.5 12 0v-5M22 9v6" />
  </Base>
);
export const Dots = (p: IconProps) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="10" />
    <circle cx="8" cy="12" r=".6" fill="currentColor" />
    <circle cx="12" cy="12" r=".6" fill="currentColor" />
    <circle cx="16" cy="12" r=".6" fill="currentColor" />
  </Base>
);
export const CartFilled = (p: IconProps) => (
  <Base {...p}>
    <path d="M2 3h3l2.6 12.4a2 2 0 0 0 2 1.6h8.3a2 2 0 0 0 2-1.5L22 8H6z" fill="currentColor" />
    <circle cx="9" cy="20" r="1.4" fill="currentColor" />
    <circle cx="18" cy="20" r="1.4" fill="currentColor" />
  </Base>
);
export const Wallet = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="5" width="18" height="15" rx="3" />
    <path d="M3 10h18" />
    <path d="M15 15h3" />
  </Base>
);
export const Send = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M21.9 3.3 18.6 19a1 1 0 0 1-1.5.6l-4.6-3.4-2.3 2.2a.6.6 0 0 1-1-.4l.2-3.6 8-7.3c.3-.3 0-.5-.4-.3l-9.9 6.2-4.3-1.4c-.9-.3-.9-1 .2-1.4l16.6-6.4c.8-.3 1.5.2 1.3 1.5z" />
  </svg>
);
export const Tag = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M3 4a1 1 0 0 1 1-1h7.6a2 2 0 0 1 1.4.6l8.4 8.4a2 2 0 0 1 0 2.8l-6.6 6.6a2 2 0 0 1-2.8 0L3.6 13A2 2 0 0 1 3 11.6zm5 5.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z" />
  </svg>
);
export const ShieldFilled = (p: IconProps) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="currentColor" />
    <path d="m8.5 12 2.5 2.5 4.5-5" fill="none" stroke="#fff" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const Star = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z" />
  </svg>
);
export const Mail = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </Base>
);
export const Phone = (p: IconProps) => (
  <Base {...p}>
    <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z" />
  </Base>
);
export const Clock = (p: IconProps) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 6v6l4 2" />
  </Base>
);
export const Instagram = (p: IconProps) => (
  <Base {...p}>
    <rect x="3" y="3" width="18" height="18" rx="5" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="17.5" cy="6.5" r=".6" fill="currentColor" />
  </Base>
);
export const Youtube = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12a31 31 0 0 0 .5 4.8 3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-4.8 31 31 0 0 0-.5-4.8zM9.7 15.1V8.9l5.8 3.1z" />
  </svg>
);

export const Heart = (p: IconProps) => (
  <Base {...p}>
    <path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 1 1 12 6.1a5 5 0 1 1 7.5 6.5z" />
  </Base>
);
export const Filter = (p: IconProps) => (
  <Base {...p}>
    <path d="M4 6h16M7 12h10M10 18h4" />
  </Base>
);
export const ListIcon = (p: IconProps) => (
  <Base {...p}>
    <path d="M9 6h11M9 12h11M9 18h11" />
    <circle cx="4.5" cy="6" r=".8" fill="currentColor" />
    <circle cx="4.5" cy="12" r=".8" fill="currentColor" />
    <circle cx="4.5" cy="18" r=".8" fill="currentColor" />
  </Base>
);
export const Users = (p: IconProps) => (
  <Base {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6.5 6.5 0 0 1 3.5 5.5" />
  </Base>
);
export const Box = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 2 3 7v10l9 5 9-5V7z" />
    <path d="m3 7 9 5 9-5M12 12v10" />
  </Base>
);

/* ---------- Brand logos (soddalashtirilgan) ---------- */

export const Logo = (p: IconProps) => (
  <svg viewBox="0 0 32 32" aria-hidden="true" {...p}>
    <circle cx="16" cy="16" r="16" fill="#1557ff" />
    <path
      d="M20.5 10.5c-1.2-1-2.8-1.5-4.6-1.5-3 0-5 1.6-5 3.9 0 4.9 9.3 3 9.3 6.6 0 1.3-1.3 2.2-3.5 2.2-2 0-3.6-.7-4.8-1.8"
      fill="none"
      stroke="#fff"
      strokeWidth={2.8}
      strokeLinecap="round"
    />
  </svg>
);

export const OpenAILogo = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...p}>
    <path d="M22.3 9.8a5.9 5.9 0 0 0-.5-4.9 6 6 0 0 0-6.5-2.9A6 6 0 0 0 4.9 4.2a5.9 5.9 0 0 0-4 2.9 6 6 0 0 0 .8 7 5.9 5.9 0 0 0 .5 4.9 6 6 0 0 0 6.5 2.9 5.9 5.9 0 0 0 4.4 2A6 6 0 0 0 19 19.8a5.9 5.9 0 0 0 4-2.9 6 6 0 0 0-.7-7.1zm-9 12.6a4.4 4.4 0 0 1-2.8-1l.1-.1 4.7-2.7a.8.8 0 0 0 .4-.7v-6.6l2 1.1v5.5a4.5 4.5 0 0 1-4.4 4.5zM3.6 18.3a4.4 4.4 0 0 1-.5-3l.1.1 4.7 2.7a.8.8 0 0 0 .8 0l5.8-3.3v2.3l-4.8 2.8a4.5 4.5 0 0 1-6.1-1.6zM2.3 7.9a4.4 4.4 0 0 1 2.4-2v5.6a.8.8 0 0 0 .4.7l5.7 3.3-2 1.2-4.8-2.8a4.5 4.5 0 0 1-1.7-6zm16.6 3.8-5.8-3.4 2-1.1 4.8 2.7a4.5 4.5 0 0 1-.7 8.1v-5.6a.8.8 0 0 0-.3-.7zm2-3-.2-.1-4.7-2.7a.8.8 0 0 0-.8 0L9.4 9.2V6.9l4.8-2.8a4.5 4.5 0 0 1 6.7 4.6zM8.3 12.9l-2-1.1V6.2a4.5 4.5 0 0 1 7.3-3.4l-.1.1-4.7 2.7a.8.8 0 0 0-.4.7zm1.1-2.4L12 9l2.6 1.5v3L12 15l-2.6-1.5z" />
  </svg>
);

export const GeminiLogo = ({ gradientId = "gem", ...p }: IconProps & { gradientId?: string }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" {...p}>
    <defs>
      <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#4f7cff" />
        <stop offset="1" stopColor="#9b5cff" />
      </linearGradient>
    </defs>
    <path d="M12 2c.6 5.3 4.7 9.4 10 10-5.3.6-9.4 4.7-10 10-.6-5.3-4.7-9.4-10-10 5.3-.6 9.4-4.7 10-10z" fill={`url(#${gradientId})`} />
  </svg>
);

export const CapCutLogo = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinejoin="round" aria-hidden="true" {...p}>
    <path d="M3 5h18v3L5 16v3h16v-3L5 8V5" />
  </svg>
);

export const MidjourneyLogo = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" aria-hidden="true" {...p}>
    <path d="M11 3 4 17h7zM12.5 5l6 12h-6zM13 8l3 5" />
    <path d="M2 19c3 1.5 5 1.5 7 0s4-1.5 6 0 4 1.5 7 0" />
  </svg>
);
