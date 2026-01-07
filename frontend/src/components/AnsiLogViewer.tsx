import React from "react";

interface AnsiLogViewerProps {
  text: string;
  className?: string;
}

const colorMap: Record<string, string> = {
  "30": "text-slate-500",
  "31": "text-red-400",
  "32": "text-green-400",
  "33": "text-amber-400",
  "34": "text-blue-400",
  "35": "text-fuchsia-400",
  "36": "text-cyan-400",
  "37": "text-slate-200",
  "90": "text-slate-500", // Bright Black (Gray)
};

const styleMap: Record<string, string> = {
  "1": "font-bold",
  "3": "italic",
  "4": "underline",
};

export const AnsiLogViewer: React.FC<AnsiLogViewerProps> = ({ text, className = "" }) => {
  if (!text) return null;

  const lines = text.split("\n");

  return (
    <div className={`font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words ${className}`}>
      {lines.map((line, i) => (
        <div key={i} className="min-h-[1.2em]">
          <AnsiLine line={line} />
        </div>
      ))}
    </div>
  );
};

const AnsiLine = ({ line }: { line: string }) => {
  if (!line) return null;

  const parts: React.ReactNode[] = [];
  const ansiRegex = /\u001b\[(\d+(?:;\d+)*)m/g;

  let lastIndex = 0;
  let match;

  // Default style
  let currentClasses: Set<string> = new Set(["text-slate-300"]);

  while ((match = ansiRegex.exec(line)) !== null) {
    const textSegment = line.substring(lastIndex, match.index);
    if (textSegment) {
      parts.push(
        <span key={lastIndex} className={Array.from(currentClasses).join(" ")}>
          {textSegment}
        </span>
      );
    }

    const codes = match[1].split(";");
    for (const code of codes) {
      if (code === "0") {
        currentClasses.clear();
        currentClasses.add("text-slate-300");
      } else if (colorMap[code]) {
        for (const c of currentClasses) {
          if (c.startsWith("text-")) currentClasses.delete(c);
        }
        currentClasses.add(colorMap[code]);
      } else if (styleMap[code]) {
        currentClasses.add(styleMap[code]);
      }
    }

    lastIndex = ansiRegex.lastIndex;
  }

  if (lastIndex < line.length) {
     parts.push(
        <span key={lastIndex} className={Array.from(currentClasses).join(" ")}>
          {line.substring(lastIndex)}
        </span>
      );
  }

  return <>{parts}</>;
};
