import React from "react";
import {
  LightBulbIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  AcademicCapIcon,
} from "@heroicons/react/24/outline";

type CalloutType = "tip" | "warning" | "info" | "concept";

interface BlogCalloutProps {
  type: CalloutType;
  title?: string;
  children: React.ReactNode;
}

export default function BlogCallout({
  type,
  title,
  children,
}: BlogCalloutProps) {
  const styles = {
    tip: {
      container: "border-teal-500/30 bg-teal-500/10",
      icon: "text-teal-400",
      title: "text-teal-200",
      body: "text-teal-100",
      IconComponent: LightBulbIcon,
      defaultTitle: "Pro Tip",
    },
    warning: {
      container: "border-amber-500/30 bg-amber-500/10",
      icon: "text-amber-400",
      title: "text-amber-200",
      body: "text-amber-100",
      IconComponent: ExclamationTriangleIcon,
      defaultTitle: "Warning",
    },
    info: {
      container: "border-blue-500/30 bg-blue-500/10",
      icon: "text-blue-400",
      title: "text-blue-200",
      body: "text-blue-100",
      IconComponent: InformationCircleIcon,
      defaultTitle: "Note",
    },
    concept: {
      container: "border-purple-500/30 bg-purple-500/10",
      icon: "text-purple-400",
      title: "text-purple-200",
      body: "text-purple-100",
      IconComponent: AcademicCapIcon,
      defaultTitle: "Key Concept",
    },
  };

  const style = styles[type];
  const Icon = style.IconComponent;

  return (
    <div
      className={`not-prose my-8 rounded-xl border p-5 ${style.container} relative overflow-hidden`}
    >
      <div className="relative z-10 flex gap-4">
        <div className="shrink-0">
          <Icon className={`h-6 w-6 ${style.icon}`} aria-hidden="true" />
        </div>
        <div>
          <h4 className={`mb-1 text-sm font-bold uppercase tracking-wider ${style.title}`}>
            {title || style.defaultTitle}
          </h4>
          <div className={`text-base leading-relaxed ${style.body}`}>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
