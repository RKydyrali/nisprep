"use client";

import { useEffect, useRef, useState } from "react";

interface MicroTimerProps {
  seconds: number;
  onExpire: () => void;
}

/**
 * Круговой SVG-таймер: зелёный (>=60% времени), жёлтый (30–60%),
 * красный (<30%) с пульсацией. Вызывает onExpire один раз по истечении.
 */
export default function MicroTimer({ seconds, onExpire }: MicroTimerProps) {
  const [remainingMs, setRemainingMs] = useState(seconds * 1000);
  const expiredRef = useRef(false);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    setRemainingMs(seconds * 1000);
    expiredRef.current = false;
  }, [seconds]);

  useEffect(() => {
    const startedAt = Date.now();
    const totalMs = seconds * 1000;

    const interval = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const left = Math.max(0, totalMs - elapsed);
      setRemainingMs(left);

      if (left <= 0 && !expiredRef.current) {
        expiredRef.current = true;
        window.clearInterval(interval);
        onExpireRef.current();
      }
    }, 100);

    return () => window.clearInterval(interval);
  }, [seconds]);

  const ratio = remainingMs / (seconds * 1000);
  const secondsLeft = Math.ceil(remainingMs / 1000);

  const color =
    ratio >= 0.6 ? "#059669" : ratio >= 0.3 ? "#F59E0B" : "#DC2626";

  const size = 120;
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - ratio);

  return (
    <div className="relative inline-flex items-center justify-center" aria-live="polite">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.1s linear, stroke 0.3s ease" }}
        />
      </svg>
      <span
        className={`absolute text-2xl font-bold tabular-nums ${
          ratio < 0.3 ? "animate-pulse-soft text-danger" : "text-ink"
        }`}
        style={{ color: ratio < 0.3 ? undefined : color }}
      >
        {secondsLeft}
      </span>
    </div>
  );
}
