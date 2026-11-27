type IconProps = { className?: string };

function base(className: string | undefined) {
  return className ?? "h-5 w-5";
}

export function LogoMark({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M8 40c8-2 14-10 24-10s16 8 24 10c2 6-2 16-8 18H16C8 56 6 46 8 40z" fill="#7dcea0" />
      <path d="M32 14 14 30v18h12V36h12v12h12V30L32 14z" fill="#1f8a45" />
      <path d="M28 40h8v8h-8z" fill="#f4faf6" />
    </svg>
  );
}

export function UserIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 19.2c1.4-3 3.6-4.4 6.5-4.4s5.1 1.4 6.5 4.4" strokeLinecap="round" />
    </svg>
  );
}

export function LogoutIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M10 7V6a2 2 0 0 1 2-2h6v16h-6a2 2 0 0 1-2-2v-1" strokeLinecap="round" />
      <path d="M4 12h10M11 8l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HouseIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M4 11.5 12 4l8 7.5V20a1 1 0 0 1-1 1h-5.2v-6.2H10.2V21H5a1 1 0 0 1-1-1v-8.5z" strokeLinejoin="round" />
    </svg>
  );
}

export function MegaphoneIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M4 10v4a2 2 0 0 0 2 2h1.2L14 19.5V4.5L7.2 8H6a2 2 0 0 0-2 2z" strokeLinejoin="round" />
      <path d="M14 8.5c2 .6 3.2 2 3.2 3.5S16 15 14 15.6M17.5 6.2a6 6 0 0 1 0 11.6" strokeLinecap="round" />
    </svg>
  );
}

export function PencilIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M4 20h4.2L19 9.2 14.8 5 4 15.8V20z" strokeLinejoin="round" />
      <path d="M13.2 6.6 17.4 10.8" strokeLinecap="round" />
    </svg>
  );
}

export function RefreshIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M19 12a7 7 0 1 1-2-4.9" strokeLinecap="round" />
      <path d="M19 4.5V8h-3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CalendarIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="4" y="5" width="16" height="15" rx="2" />
      <path d="M8 3.5V7M16 3.5V7M4 10h16" strokeLinecap="round" />
    </svg>
  );
}

export function ChartIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M5 19V10M12 19V5M19 19v-7" strokeLinecap="round" />
    </svg>
  );
}

export function ChevronIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M6 14.5 12 8.5l6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <path d="M8.5 12.2 11 14.7l4.6-5.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ListIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M9 7h11M9 12h11M9 17h11" strokeLinecap="round" />
      <path d="M5 7h.01M5 12h.01M5 17h.01" strokeLinecap="round" />
    </svg>
  );
}

export function SwapIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M7 7h11l-2.5-2.5M17 17H6l2.5 2.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="8" cy="7" r="2" />
      <circle cx="16" cy="17" r="2" />
    </svg>
  );
}

export function SpecIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M5 6h14M5 12h14M5 18h8" strokeLinecap="round" />
      <circle cx="16" cy="6" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="10" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="14" cy="18" r="1.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function AlertIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 4.5 3.8 19h16.4L12 4.5z" strokeLinejoin="round" />
      <path d="M12 10v4.2" strokeLinecap="round" />
      <path d="M12 16.8h.01" strokeLinecap="round" />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg className={base(className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8.5v7M8.5 12h7" strokeLinecap="round" />
    </svg>
  );
}
