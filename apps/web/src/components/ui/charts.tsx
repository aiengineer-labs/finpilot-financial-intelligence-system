"use client";

import { type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { addDays, compactMoney, money, shortDate } from "@/lib/format";

/* Charts are hand-built SVG so the bundle stays dependency-free. Labels are rendered
   through React text nodes (never innerHTML) because merchant and category names come
   from uploaded CSV data. */

function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

function niceTicks(min: number, max: number, count = 4) {
  const span = max - min || Math.abs(max) || 1;
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const ratio = raw / magnitude;
  const step = (ratio <= 1 ? 1 : ratio <= 2 ? 2 : ratio <= 5 ? 5 : 10) * magnitude;
  const low = Math.floor(min / step) * step;
  const high = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let value = low; value <= high + step / 2; value += step) ticks.push(Math.round(value));
  return { low, high, ticks };
}

function roundedColumn(x: number, y: number, width: number, height: number, radius = 4) {
  const r = Math.min(radius, width / 2, height);
  return `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
}

/* ---------- Sparkline ---------- */

export function Sparkline({ values, width = 84, height = 28 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const range = high - low || 1;
  const points = values.map((value, index) => [
    2 + (index / (values.length - 1)) * (width - 6),
    3 + (1 - (value - low) / range) * (height - 6)
  ]);
  const [lastX, lastY] = points[points.length - 1];
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")} />
      <circle cx={lastX} cy={lastY} r={2.6} />
    </svg>
  );
}

/* ---------- Line / area chart with crosshair ---------- */

export type LineSeries = { id: string; label: string; values: number[]; color: string; area?: boolean };
export type ChartMarker = { index: number; label: string; tone: "bad" | "accent" };

export function LineChart({ days, series, height = 300, markers = [], ariaLabel, valueFormat = money }: {
  days: string[]; series: LineSeries[]; height?: number; markers?: ChartMarker[]; ariaLabel: string;
  valueFormat?: (minor: number) => string;
}) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const pad = { left: 58, right: 18, top: 18, bottom: 30 };
  const plotWidth = Math.max(width - pad.left - pad.right, 10);
  const plotHeight = height - pad.top - pad.bottom;
  const count = days.length;

  const scale = useMemo(() => {
    const values = series.flatMap((item) => item.values);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const padding = (rawMax - rawMin) * 0.12 || Math.abs(rawMax) * 0.1 || 100;
    return niceTicks(rawMin < 0 ? rawMin - padding : Math.max(0, rawMin - padding), rawMax + padding, 4);
  }, [series]);

  const x = (index: number) => pad.left + (count <= 1 ? plotWidth / 2 : (index / (count - 1)) * plotWidth);
  const y = (value: number) => pad.top + ((scale.high - value) / (scale.high - scale.low || 1)) * plotHeight;
  const xTicks = count > 1 ? [...new Set([0, 1, 2, 3, 4].map((step) => Math.round((step * (count - 1)) / 4)))] : [0];

  function locate(event: PointerEvent<SVGRectElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const offset = event.clientX - bounds.left;
    setActive(Math.min(count - 1, Math.max(0, Math.round((offset / Math.max(bounds.width, 1)) * (count - 1)))));
  }

  function step(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setActive((current) => {
      const base = current ?? (event.key === "ArrowLeft" ? count : -1);
      return Math.min(count - 1, Math.max(0, base + (event.key === "ArrowRight" ? 1 : -1)));
    });
  }

  const tooltipLeft = active === null ? 0 : x(active);
  const flip = tooltipLeft > width - 200;

  return (
    <div className="chart" ref={ref} tabIndex={0} role="group" aria-label={`${ariaLabel}. Use left and right arrow keys to inspect days.`} onKeyDown={step} onBlur={() => setActive(null)} style={{ height }}>
      {width > 0 && count > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          <defs>
            {series.filter((item) => item.area).map((item) => (
              <linearGradient key={item.id} id={`wash-${item.id}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" style={{ stopColor: item.color, stopOpacity: 0.22 }} />
                <stop offset="100%" style={{ stopColor: item.color, stopOpacity: 0 }} />
              </linearGradient>
            ))}
          </defs>
          {scale.ticks.map((tick) => (
            <g key={tick}>
              <line className={tick === 0 ? "grid zero" : "grid"} x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} />
              <text className="axis-label" x={pad.left - 10} y={y(tick)} dy="0.32em" textAnchor="end">{compactMoney(tick)}</text>
            </g>
          ))}
          {xTicks.map((index) => (
            <text key={index} className="axis-label" x={x(index)} y={height - 8} textAnchor={index === 0 ? "start" : index === count - 1 ? "end" : "middle"}>{shortDate(days[index])}</text>
          ))}
          {series.map((item) => {
            const line = item.values.map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join("");
            return (
              <g key={item.id}>
                {item.area && <path d={`${line}L${x(item.values.length - 1).toFixed(1)},${pad.top + plotHeight}L${x(0).toFixed(1)},${pad.top + plotHeight}Z`} fill={`url(#wash-${item.id})`} />}
                <path d={line} className="series-line" style={{ stroke: item.color }} />
                <circle className="end-dot" cx={x(item.values.length - 1)} cy={y(item.values[item.values.length - 1])} r={4} style={{ fill: item.color }} />
              </g>
            );
          })}
          {markers.map((marker) => (
            <g key={`${marker.tone}-${marker.index}`} className={`marker marker-${marker.tone}`}>
              <line x1={x(marker.index)} x2={x(marker.index)} y1={pad.top} y2={pad.top + plotHeight} />
              <text x={x(marker.index)} y={pad.top - 6} textAnchor={x(marker.index) > width - 80 ? "end" : "middle"}>{marker.label}</text>
            </g>
          ))}
          {active !== null && (
            <g className="crosshair">
              <line x1={x(active)} x2={x(active)} y1={pad.top} y2={pad.top + plotHeight} />
              {series.map((item) => <circle key={item.id} cx={x(active)} cy={y(item.values[active])} r={4.5} style={{ fill: item.color }} />)}
            </g>
          )}
          <rect className="hit-area" x={pad.left} y={pad.top} width={plotWidth} height={plotHeight} onPointerMove={locate} onPointerDown={locate} onPointerLeave={() => setActive(null)} />
        </svg>
      )}
      {active !== null && (
        <div className="chart-tooltip glass-strong" style={{ left: tooltipLeft, top: pad.top, transform: flip ? "translateX(calc(-100% - 14px))" : "translateX(14px)" }}>
          <span className="tooltip-title">{shortDate(days[active])}</span>
          {series.map((item) => (
            <div key={item.id} className="tooltip-row"><i style={{ background: item.color }} /><b>{valueFormat(item.values[active])}</b><span>{item.label}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Grouped columns ---------- */

export function ColumnChart({ groups, series, height = 230, ariaLabel }: {
  groups: Array<{ key: string; label: string; values: number[] }>;
  series: Array<{ label: string; color: string }>;
  height?: number; ariaLabel: string;
}) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const pad = { left: 52, right: 8, top: 14, bottom: 28 };
  const plotWidth = Math.max(width - pad.left - pad.right, 10);
  const plotHeight = height - pad.top - pad.bottom;
  const scale = niceTicks(0, Math.max(...groups.flatMap((group) => group.values), 1), 4);
  const band = plotWidth / Math.max(groups.length, 1);
  const barWidth = Math.max(6, Math.min(24, (band * 0.62 - 2 * (series.length - 1)) / series.length));
  const groupWidth = barWidth * series.length + 2 * (series.length - 1);
  const y = (value: number) => pad.top + (1 - value / (scale.high || 1)) * plotHeight;

  return (
    <div className="chart" ref={ref} style={{ height }} role="group" aria-label={ariaLabel}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {scale.ticks.map((tick) => (
            <g key={tick}>
              <line className={tick === 0 ? "grid zero" : "grid"} x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} />
              <text className="axis-label" x={pad.left - 10} y={y(tick)} dy="0.32em" textAnchor="end">{compactMoney(tick)}</text>
            </g>
          ))}
          {groups.map((group, groupIndex) => {
            const start = pad.left + groupIndex * band + (band - groupWidth) / 2;
            return (
              <g key={group.key} className={active !== null && active !== groupIndex ? "dimmed" : ""}>
                {group.values.map((value, seriesIndex) => {
                  const top = y(value);
                  return <path key={seriesIndex} d={roundedColumn(start + seriesIndex * (barWidth + 2), top, barWidth, Math.max(pad.top + plotHeight - top, 0))} style={{ fill: series[seriesIndex].color }} />;
                })}
                <text className="axis-label" x={pad.left + groupIndex * band + band / 2} y={height - 8} textAnchor="middle">{group.label}</text>
                <rect className="hit-area" x={pad.left + groupIndex * band} y={pad.top} width={band} height={plotHeight} tabIndex={0} aria-label={`${group.label}: ${group.values.map((value, index) => `${series[index].label} ${money(value)}`).join(", ")}`} onPointerEnter={() => setActive(groupIndex)} onPointerLeave={() => setActive(null)} onFocus={() => setActive(groupIndex)} onBlur={() => setActive(null)} />
              </g>
            );
          })}
        </svg>
      )}
      {active !== null && groups[active] && (
        <div className="chart-tooltip glass-strong" style={{ left: pad.left + active * band + band / 2, top: pad.top, transform: active > groups.length / 2 ? "translateX(calc(-100% - 18px))" : "translateX(18px)" }}>
          <span className="tooltip-title">{groups[active].label}</span>
          {series.map((item, index) => (
            <div key={item.label} className="tooltip-row"><i style={{ background: item.color }} /><b>{money(groups[active].values[index])}</b><span>{item.label}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Donut with linked legend ---------- */

function sector(cx: number, cy: number, inner: number, outer: number, start: number, end: number) {
  const sweep = Math.min(end - start, Math.PI * 2 - 0.0001);
  const finish = start + sweep;
  const large = sweep > Math.PI ? 1 : 0;
  const point = (radius: number, angle: number) => `${(cx + radius * Math.sin(angle)).toFixed(2)} ${(cy - radius * Math.cos(angle)).toFixed(2)}`;
  return `M${point(outer, start)}A${outer} ${outer} 0 ${large} 1 ${point(outer, finish)}L${point(inner, finish)}A${inner} ${inner} 0 ${large} 0 ${point(inner, start)}Z`;
}

export function Donut({ slices, centerLabel, size = 184 }: {
  slices: Array<{ key: string; label: string; value: number; color: string; detail?: string }>;
  centerLabel: string; size?: number;
}) {
  const [active, setActive] = useState<string | null>(null);
  const total = slices.reduce((sum, slice) => sum + slice.value, 0) || 1;
  const outer = size / 2 - 4;
  const inner = outer - 22;
  const gap = 2.4 / outer;
  const ends = slices.reduce<number[]>((acc, slice) => [...acc, (acc[acc.length - 1] ?? 0) + (slice.value / total) * Math.PI * 2], []);
  const arcs = slices.map((slice, index) => {
    const start = ends[index - 1] ?? 0;
    const end = ends[index];
    const padded = end - start > gap * 2 ? gap / 2 : 0;
    return { ...slice, d: sector(size / 2, size / 2, inner, active === slice.key ? outer + 3 : outer, start + padded, end - padded) };
  });
  const focus = slices.find((slice) => slice.key === active);

  return (
    <div className="donut-wrap">
      <div className="donut" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${centerLabel}: ${slices.map((slice) => `${slice.label} ${money(slice.value)}`).join(", ")}`}>
          {arcs.map((arc) => (
            <path key={arc.key} d={arc.d} style={{ fill: arc.color }} className={active && active !== arc.key ? "dimmed" : ""} onPointerEnter={() => setActive(arc.key)} onPointerLeave={() => setActive(null)} />
          ))}
        </svg>
        <div className="donut-center">
          <small>{focus ? focus.label : centerLabel}</small>
          <strong>{compactMoney(focus ? focus.value : total)}</strong>
          <span>{focus ? `${Math.round((focus.value / total) * 100)}% of spend` : `${slices.length} groups`}</span>
        </div>
      </div>
      <ul className="legend-list">
        {slices.map((slice) => (
          <li key={slice.key} className={active === slice.key ? "active" : ""} onPointerEnter={() => setActive(slice.key)} onPointerLeave={() => setActive(null)} tabIndex={0} onFocus={() => setActive(slice.key)} onBlur={() => setActive(null)}>
            <i style={{ background: slice.color }} />
            <span>{slice.label}{slice.detail && <small>{slice.detail}</small>}</span>
            <b>{money(slice.value)}</b>
            <em>{Math.round((slice.value / total) * 100)}%</em>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------- Calendar heatmap (sequential, one hue) ---------- */

export function CalendarHeatmap({ start, end, values, footer }: { start: string; end: string; values: Map<string, number>; footer?: ReactNode }) {
  const [frame, available] = useElementWidth<HTMLDivElement>();
  const [active, setActive] = useState<{ day: string; x: number; y: number } | null>(null);
  const gapSize = 3;
  const startDate = new Date(`${start}T00:00:00Z`);
  const mondayOffset = (startDate.getUTCDay() + 6) % 7;
  const first = addDays(start, -mondayOffset);
  const totalDays = Math.round((new Date(`${end}T00:00:00Z`).getTime() - new Date(`${first}T00:00:00Z`).getTime()) / 86_400_000) + 1;
  const weeks = Math.ceil(totalDays / 7);
  const cell = available ? Math.max(10, Math.min(22, Math.floor((available - 28) / weeks) - gapSize)) : 13;
  const nonZero = [...values.values()].filter((value) => value > 0).sort((a, b) => a - b);
  const quantile = (q: number) => nonZero[Math.min(nonZero.length - 1, Math.floor(q * nonZero.length))] ?? 0;
  const thresholds = [quantile(0.25), quantile(0.5), quantile(0.75)];
  const level = (value: number) => (value <= 0 ? 0 : value <= thresholds[0] ? 1 : value <= thresholds[1] ? 2 : value <= thresholds[2] ? 3 : 4);
  const left = 28;
  const top = 18;
  const width = left + weeks * (cell + gapSize);
  const height = top + 7 * (cell + gapSize);
  const cells: Array<{ day: string; col: number; row: number; value: number; inRange: boolean }> = [];
  const monthLabels: Array<{ col: number; label: string }> = [];
  for (let index = 0; index < weeks * 7; index += 1) {
    const day = addDays(first, index);
    const col = Math.floor(index / 7);
    const row = index % 7;
    const inRange = day >= start && day <= end;
    if (day.endsWith("-01") || (index === mondayOffset && !monthLabels.length)) {
      monthLabels.push({ col, label: new Date(`${day}T00:00:00Z`).toLocaleDateString("en-IN", { month: "short", timeZone: "UTC" }) });
    }
    cells.push({ day, col, row, value: values.get(day) ?? 0, inRange });
  }

  return (
    <div className="heatmap" ref={frame}>
      <div className="heatmap-scroll">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Daily spending calendar">
          {monthLabels.map((month) => <text key={`${month.col}-${month.label}`} className="axis-label" x={left + month.col * (cell + gapSize)} y={10}>{month.label}</text>)}
          {["Mon", "Wed", "Fri"].map((label, index) => <text key={label} className="axis-label" x={0} y={top + (index * 2) * (cell + gapSize) + cell - 2}>{label}</text>)}
          {cells.filter((item) => item.inRange).map((item) => (
            <rect
              key={item.day}
              x={left + item.col * (cell + gapSize)}
              y={top + item.row * (cell + gapSize)}
              width={cell}
              height={cell}
              rx={cell > 16 ? 5 : 3.5}
              className={`heat heat-${level(item.value)} ${active?.day === item.day ? "active" : ""}`}
              tabIndex={0}
              aria-label={`${shortDate(item.day)}: ${money(item.value)} spent`}
              onPointerEnter={() => setActive({ day: item.day, x: left + item.col * (cell + gapSize) + cell / 2, y: top + item.row * (cell + gapSize) })}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive({ day: item.day, x: left + item.col * (cell + gapSize) + cell / 2, y: top + item.row * (cell + gapSize) })}
              onBlur={() => setActive(null)}
            />
          ))}
        </svg>
        {active && (
          <div className="chart-tooltip glass-strong heat-tooltip" style={{ left: `${(active.x / width) * 100}%`, top: `${(active.y / height) * 100}%` } as CSSProperties}>
            <span className="tooltip-title">{shortDate(active.day)}</span>
            <div className="tooltip-row"><b>{money(values.get(active.day) ?? 0)}</b><span>spent</span></div>
          </div>
        )}
      </div>
      <div className="heatmap-legend"><span>Less</span>{[0, 1, 2, 3, 4].map((step) => <i key={step} className={`heat-${step}`} />)}<span>More</span>{footer}</div>
    </div>
  );
}
