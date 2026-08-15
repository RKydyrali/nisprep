"use client";

import type { GraphEdge, GraphNode, Readiness } from "@/lib/api";

/* ---------------------------------- ThetaBars ---------------------------------- */

const THETA_SERIES: { key: keyof Readiness["theta"]; color: string }[] = [
  { key: "math", color: "#047857" },
  { key: "quant", color: "#F59E0B" },
  { key: "nat_sci", color: "#2563EB" },
  { key: "lang", color: "#7C3AED" },
];

export function ThetaBars({
  theta,
  labels,
}: {
  theta: Readiness["theta"];
  labels: Record<string, string>;
}) {
  const maxAbs = Math.max(
    0.5,
    ...THETA_SERIES.map((s) => Math.abs(theta[s.key])),
  );

  return (
    <div className="space-y-3">
      {THETA_SERIES.map((s) => {
        const value = theta[s.key];
        const width = Math.max(4, (Math.abs(value) / maxAbs) * 100);
        return (
          <div key={s.key} className="flex items-center gap-3">
            <span className="w-40 shrink-0 truncate text-sm text-slate-600 sm:w-48">
              {labels[s.key]}
            </span>
            <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${width}%`,
                  backgroundColor: s.color,
                  opacity: value < 0 ? 0.45 : 0.9,
                }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-sm font-semibold tabular-nums text-ink">
              {value >= 0 ? "+" : ""}
              {value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------------- HistoryChart --------------------------------- */

const HISTORY_COLORS: Record<string, string> = {
  math: "#047857",
  quant: "#F59E0B",
  nat_sci: "#2563EB",
  lang: "#7C3AED",
};

export function HistoryChart({
  history,
}: {
  history: Readiness["history"];
}) {
  const { dates, series } = history;
  const keys = Object.keys(series) as (keyof typeof series)[];

  const allValues = keys.flatMap((k) => series[k]);
  if (allValues.length === 0) return null;

  const min = Math.min(...allValues, 0);
  const max = Math.max(...allValues, 1);
  const range = max - min || 1;
  const n = Math.max(2, dates.length);
  const W = 720;
  const H = 240;
  const PAD_X = 36;
  const PAD_Y = 24;

  const x = (i: number) => PAD_X + (i / (n - 1)) * (W - PAD_X * 2);
  const y = (v: number) => H - PAD_Y - ((v - min) / range) * (H - PAD_Y * 2);

  const pathFor = (values: number[]) =>
    values
      .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`)
      .join(" ");

  const gridLines = [0, 0.5, 1].map((f) => ({
    value: min + f * range,
    y: PAD_Y + (1 - f) * (H - PAD_Y * 2),
  }));

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {gridLines.map((g) => (
          <line
            key={g.y}
            x1={PAD_X}
            x2={W - PAD_X}
            y1={g.y}
            y2={g.y}
            stroke="#E2E8F0"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        ))}
        {keys.map((k) => (
          <path
            key={k}
            d={pathFor(series[k])}
            fill="none"
            stroke={HISTORY_COLORS[k]}
            strokeWidth={2.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        {keys.map((k) =>
          series[k].map((v, i) => (
            <circle
              key={`${k}-${i}`}
              cx={x(i)}
              cy={y(v)}
              r={3}
              fill="#fff"
              stroke={HISTORY_COLORS[k]}
              strokeWidth={2}
            />
          )),
        )}
      </svg>
      <div className="mt-1 flex flex-wrap items-center justify-center gap-4">
        {keys.map((k) => (
          <span key={k} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span
              className="h-2 w-4 rounded-full"
              style={{ backgroundColor: HISTORY_COLORS[k] }}
            />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ----------------------------------- SkillGraph ----------------------------------- */

function accuracyColor(accuracy: number): string {
  if (accuracy < 0.5) return "#DC2626";
  if (accuracy < 0.7) return "#F59E0B";
  return "#047857";
}

export function SkillGraph({
  nodes,
  edges,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
}) {
  if (nodes.length === 0) return null;

  const W = 560;
  const H = 460;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(cx, cy) - 46;

  const positions = new Map<number, { x: number; y: number }>();
  nodes.forEach((node, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI - Math.PI / 2;
    positions.set(node.id, {
      x: cx + R * Math.cos(angle),
      y: cy + R * Math.sin(angle),
    });
  });

  const maxWeight = Math.max(1, ...nodes.map((n) => n.weight));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img">
      {edges.map((edge, i) => {
        const from = positions.get(edge.from_id);
        const to = positions.get(edge.to_id);
        if (!from || !to) return null;
        return (
          <line
            key={`e-${i}`}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            stroke="#94A3B8"
            strokeWidth={1 + edge.value * 2.5}
            opacity={0.25 + edge.value * 0.5}
          />
        );
      })}
      {nodes.map((node) => {
        const pos = positions.get(node.id);
        if (!pos) return null;
        const r = 8 + (node.weight / maxWeight) * 10;
        const color = accuracyColor(node.accuracy);
        return (
          <g key={node.id}>
            <circle
              cx={pos.x}
              cy={pos.y}
              r={r + 3}
              fill="#fff"
              stroke={color}
              strokeWidth={2}
            />
            <circle cx={pos.x} cy={pos.y} r={r} fill={color} />
            <text
              x={pos.x}
              y={pos.y + r + 14}
              textAnchor="middle"
              fontSize={11}
              fontWeight={600}
              fill="#0F172A"
            >
              {node.name_ru.length > 18 ? `${node.name_ru.slice(0, 17)}…` : node.name_ru}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ----------------------------------- WeakSkills ----------------------------------- */

export function WeakSkills({
  skills,
  locale,
}: {
  skills: Readiness["weak_skills"];
  locale: string;
}) {
  const name = (ru: string, kk: string) => (locale === "kk" ? kk : ru);

  return (
    <div className="space-y-3">
      {skills.map((skill) => {
        const accuracyPct = Math.round(skill.accuracy * 100);
        const color = accuracyColor(skill.accuracy);
        return (
          <div
            key={skill.micro_skill_id}
            className="rounded-2xl border border-slate-200 bg-white p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-ink">
                {name(skill.name_ru, skill.name_kk)}
              </span>
              <span
                className="rounded-full px-2 py-0.5 text-xs font-bold tabular-nums"
                style={{ backgroundColor: `${color}1A`, color }}
              >
                {accuracyPct}%
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full"
                style={{ width: `${accuracyPct}%`, backgroundColor: color }}
              />
            </div>
            <div className="mt-1.5 flex items-center justify-between text-xs text-muted">
              <span>
                {skill.count} {skill.count === 1 ? "попытка" : skill.count < 5 ? "попытки" : "попыток"}
              </span>
              <span className="font-mono">{skill.code}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
