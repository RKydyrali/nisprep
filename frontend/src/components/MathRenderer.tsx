"use client";

import { useEffect, useMemo, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface MathRendererProps {
  text: string;
  className?: string;
}

const MATH_SPAN = /(\$\$[\s\S]+?\$\$|\\\([\s\S]+?\\\))/g;

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderInline(tex: string): string {
  try {
    return katex.renderToString(tex, {
      displayMode: false,
      throwOnError: false,
    });
  } catch {
    return escapeHtml(tex);
  }
}

function renderBlock(tex: string): string {
  try {
    return katex.renderToString(tex, {
      displayMode: true,
      throwOnError: false,
    });
  } catch {
    return escapeHtml(tex);
  }
}

export function renderMathToHtml(text: string): string {
  const segments = text.split(MATH_SPAN);
  return segments
    .map((segment) => {
      if (!segment) return "";
      if (segment.startsWith("$$") && segment.endsWith("$$")) {
        return renderBlock(segment.slice(2, -2));
      }
      if (segment.startsWith("\\(") && segment.endsWith("\\)")) {
        return renderInline(segment.slice(2, -2));
      }
      return escapeHtml(segment);
    })
    .join("");
}

/**
 * Клиентский рендер формул (KaTeX): блоки $$...$$ и инлайн \(...\).
 * Обычный текст — как есть. Контейнер с min-height против layout shift.
 */
export default function MathRenderer({ text, className }: MathRendererProps) {
  const [html, setHtml] = useState("");
  const raw = useMemo(() => text, [text]);

  useEffect(() => {
    setHtml(renderMathToHtml(raw));
  }, [raw]);

  return (
    <div
      className={className}
      style={{ minHeight: "1.6em" }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
