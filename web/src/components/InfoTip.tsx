"use client";

import { useId } from "react";
import { Info } from "lucide-react";

export default function InfoTip({ text }: { text: string }) {
  const id = useId();
  return (
    <span className="relative inline-flex items-center group">
      <button
        type="button"
        aria-describedby={id}
        className="inline-flex items-center justify-center rounded p-0.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/60"
      >
        <Info size={14} />
      </button>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-64 -translate-x-1/2 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-[11px] normal-case tracking-normal text-zinc-200 shadow-lg opacity-0 translate-y-1 transition group-hover:opacity-100 group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:translate-y-0"
      >
        {text}
      </span>
    </span>
  );
}

