"use client";

import { useEffect, useState } from "react";

interface ReadinessGaugeProps {
  /** Вероятность 0–100 */
  value: number;
  band: "high" | "medium" | "low";
  bandLabel: string;
  caption?: string;
}

const SIZE = 220;
const CENTER = 110;
const RADIUS = 84;
const STROKE = 14;

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 180) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

function arcPath(fromAngle: number, toAngle: number): string {
  const start = polar(CENTER, CENTER, RADIUS, fromAngle);
  const end = polar(CENTER, CENTER, RADIUS, toAngle);
  const large = toAngle - fromAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${RADIUS} ${RADIUS} 0 ${large} 1 ${end.x} ${end.y}`;
}

function bandColor(band: "high" | "medium" | "low"): string {
  switch (band) {
    case "high":
      return "#047857";
    case "medium":
      return "#F59E0B";
    case "low":
      return "#DC2626";
  }
}

/**
 * Спидометр готовности к гранту «Өркен»: полукруглая шкала 0–100%,
 * зоны красная/янтарная/зелёная, стрелка с плавным переходом.
 */
export default function ReadinessGauge({
  value,
  band,
  bandLabel,
  caption,
}: ReadinessGaugeProps) {
  const [needleAngle, setNeedleAngle] = useState(180);

  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const angle = 180 - (clamped / 100) * 180;
  const tip = polar(CENTER, CENTER, RADIUS - 14, angle);
  const color = bandColor(band);

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      setNeedleAngle(angle);
    });
    return () => cancelAnimationFrame(raf);
  }, [angle]);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: SIZE, height: SIZE / 2 + 18 }}>
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE / 2 + 18}`}
          className="w-full overflow-visible"
          role="img"
          aria-label={`${caption ?? "P(grant)"}: ${clamped}%`}
        >
          <path
            d={arcPath(0, 40)}
            stroke="#DC2626"
            strokeWidth={STROKE}
            strokeLinecap="butt"
            fill="none"
            opacity={0.85}
          />
          <path
            d={arcPath(40, 70)}
            stroke="#F59E0B"
            strokeWidth={STROKE}
            strokeLinecap="butt"
            fill="none"
            opacity={0.85}
          />
          <path
            d={arcPath(70, 100)}
            stroke="#047857"
            strokeWidth={STROKE}
            strokeLinecap="butt"
            fill="none"
            opacity={0.85}
          />
          {[0, 20, 40, 60, 80, 100].map((tick) => {
            const p = polar(CENTER, CENTER, RADIUS + STROKE / 2 + 4, 180 - tick * 1.8);
            return (
              <text
                key={tick}
                x={p.x}
                y={p.y + 4}
                textAnchor="middle"
                fontSize={10}
                fill="#64748B"
                className="select-none"
              >
                {tick}
              </text>
            );
          })}
          <line
            x1={CENTER}
            y1={CENTER}
            x2={tip.x}
            y2={tip.y}
            stroke="#0F172A"
            strokeWidth={4}
            strokeLinecap="round"
            style={{
              transformOrigin: `${CENTER}px ${CENTER}px`,
              transform: `rotate(${needleAngle}deg)`,
              transition: "transform 0.9s cubic-bezier(0.34, 1.3, 0.64, 1)",
            }}
          />
          <circle cx={CENTER} cy={CENTER} r={7} fill="#0F172A" />
        </svg>
        <div className="absolute inset-x-0 bottom-0 flex flex-col items-center">
          <div className="text-3xl font-extrabold tabular-nums text-ink">
            {clamped}
            <span className="text-lg text-muted">%</span>
          </div>
          <div
            className="mt-0.5 rounded-full px-3 py-0.5 text-xs font-semibold"
            style={{ backgroundColor: `${color}1A`, color }}
          >
            {bandLabel}
          </div>
        </div>
      </div>
    </div>
  );
}
