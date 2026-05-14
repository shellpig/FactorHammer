"use client";

import { CircleHelp } from "lucide-react";

interface HelpTooltipProps {
  text: string;
}

export function HelpTooltip({ text }: HelpTooltipProps) {
  return (
    <span className="inline-flex align-middle" title={text} aria-label={text}>
      <CircleHelp className="h-3.5 w-3.5 text-slate-400" />
    </span>
  );
}
