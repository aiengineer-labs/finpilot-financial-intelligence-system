import type { SVGProps } from "react";

const paths = {
  overview: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  ledger: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  forecast: "M3 20h18M5 16l4-5 4 3 6-8M15 6h4v4",
  advice: "M12 3l1.8 4.6L18 9.5l-4.2 1.9L12 16l-1.8-4.6L6 9.5l4.2-1.9zM19 15l.8 2 2 .8-2 .8L19 21l-.8-2.4-2-.8 2-.8z",
  audit: "M9 5h10M9 12h10M9 19h10M4.5 5.5l1 1 2-2M4.5 12.5l1 1 2-2M4.5 19.5l1 1 2-2",
  digests: "M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0",
  governance: "M12 3l7.5 3v5.5c0 4.6-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.9-7.5-9.5V6zM8.8 12l2.2 2.2 4.4-4.4",
  system: "M3.5 5.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0M15.5 5.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0M9.5 18.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0M7.2 7.7l3.6 8.6M16.8 7.7l-3.6 8.6M8.5 5.5h7",
  search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.5 15.5L20 20",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  monitor: "M3.5 5h17v11h-17zM9 20h6M12 16v4",
  upload: "M12 15V4M7.5 8.5L12 4l4.5 4.5M5 15v4h14v-4",
  download: "M12 4v11M7.5 10.5L12 15l4.5-4.5M5 15v4h14v-4",
  play: "M7 4.5v15l12-7.5z",
  plus: "M12 5v14M5 12h14",
  check: "M5 12.5l4.5 4.5L19 7.5",
  close: "M6 6l12 12M18 6L6 18",
  chevronRight: "M9 5l7 7-7 7",
  chevronLeft: "M15 5l-7 7 7 7",
  chevronDown: "M5 9l7 7 7-7",
  logout: "M14 4h5v16h-5M10 8l-4 4 4 4M6 12h10",
  sidebar: "M3.5 5h17v14h-17zM9 5v14",
  alert: "M12 4l9 16H3zM12 10v4.5M12 17.5h.01",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5.5M12 7.5h.01",
  refresh: "M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4h-4",
  repeat: "M4 11V9a3 3 0 0 1 3-3h12M16 3l3 3-3 3M20 13v2a3 3 0 0 1-3 3H5M8 21l-3-3 3-3",
  bolt: "M13 3L5 13.5h6L10 21l8-10.5h-6z",
  lock: "M6 11h12v9.5H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3",
  bank: "M3 9.5L12 4l9 5.5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3.5 20.5h17",
  doc: "M6 3.5h8l4 4v13H6zM14 3.5v4h4M9 13h6M9 16.5h6",
  command: "M9 9V6.5A2.5 2.5 0 1 0 6.5 9H9zm0 0h6m-6 0v6m6-6V6.5A2.5 2.5 0 1 1 17.5 9H15zm0 0v6m0 0h-6m6 0v2.5a2.5 2.5 0 1 0 2.5-2.5H15zm-6 0v2.5A2.5 2.5 0 1 1 6.5 15H9z",
  filter: "M4 6h16M7 12h10M10 18h4",
  copy: "M9 9h11v11H9zM15 9V4H4v11h5",
  calendar: "M4 6h16v14H4zM4 10h16M8.5 3.5v4M15.5 3.5v4",
  cpu: "M7 7h10v10H7zM10 10h4v4h-4zM9.5 3.5V7M14.5 3.5V7M9.5 17v3.5M14.5 17v3.5M3.5 9.5H7M3.5 14.5H7M17 9.5h3.5M17 14.5h3.5",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7.5V12l3 2",
  inbox: "M3.5 13.5l3-8.5h11l3 8.5v6h-17zM3.5 13.5h5l1.5 2.5h4l1.5-2.5h5",
  sparkline: "M3 17l5-6 4 3 8-9",
  wallet: "M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3M4 7.5V18a2 2 0 0 0 2 2h14V8H6.5A2.5 2.5 0 0 1 4 5.5M16 14h.01",
  arrowUpRight: "M7 17L17 7M8.5 7H17v8.5",
  arrowDownRight: "M7 7l10 10M17 8.5V17H8.5",
  flask: "M9.5 3.5h5M10.5 3.5v6L5 19.5h14l-5.5-10v-6M7.5 15h9",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 20.5a7.5 7.5 0 0 1 15 0",
  terminal: "M4 5h16v14H4zM7.5 9.5l3 2.5-3 2.5M12.5 15h4"
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18, ...props }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>
      <path d={paths[name]} />
    </svg>
  );
}
