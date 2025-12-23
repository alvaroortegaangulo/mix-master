import React from "react";
import { CheckCircleIcon } from "@heroicons/react/24/solid";

interface BlogChecklistProps {
  items: string[];
  title?: string;
}

export default function BlogChecklist({ items, title }: BlogChecklistProps) {
  return (
    <div className="not-prose my-8 rounded-2xl border border-slate-800 bg-slate-900/50 p-6 shadow-xl shadow-black/20">
      {title && (
        <h3 className="mb-4 text-lg font-bold text-white flex items-center gap-2">
          <span className="h-6 w-1 bg-teal-500 rounded-full"></span>
          {title}
        </h3>
      )}
      <ul className="space-y-3">
        {items.map((item, idx) => (
          <li key={idx} className="flex items-start gap-3 group">
            <CheckCircleIcon className="mt-0.5 h-5 w-5 shrink-0 text-teal-500 transition group-hover:text-teal-400 group-hover:scale-110" />
            <span className="text-slate-300 group-hover:text-slate-200 transition">
              {item}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
