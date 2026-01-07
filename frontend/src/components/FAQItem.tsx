"use client";

import { useState } from "react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";

interface FAQItemProps {
  question: string;
  answer: string;
}

export default function FAQItem({ question, answer }: FAQItemProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div
      className={`rounded-2xl border transition-all duration-200 ${
        isOpen
          ? "border-teal-500/50 bg-slate-900 shadow-teal-900/10"
          : "border-slate-800/60 bg-slate-900/50 hover:border-teal-500/30"
      } shadow-lg overflow-hidden cursor-pointer`}
      onClick={() => setIsOpen(!isOpen)}
    >
      <div className="p-6 flex items-center justify-between gap-4">
        <h3 className={`text-lg font-semibold transition-colors ${isOpen ? "text-teal-400" : "text-slate-200"}`}>
          {question}
        </h3>
        <ChevronDownIcon
          className={`h-5 w-5 text-slate-400 min-w-5 transition-transform duration-300 ${
            isOpen ? "rotate-180 text-teal-400" : ""
          }`}
        />
      </div>
      <div
        className={`grid transition-all duration-300 ease-in-out ${
          isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <p className="px-6 pb-6 text-slate-400 leading-relaxed border-t border-slate-800/50 pt-4 mt-2">
            {answer}
          </p>
        </div>
      </div>
    </div>
  );
}
