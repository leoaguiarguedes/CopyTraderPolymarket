"use client";

import { useEffect } from "react";

export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 max-w-xl w-full shadow-2xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 transition text-xl leading-none w-6 h-6 flex items-center justify-center rounded hover:bg-zinc-800"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function DetailRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex gap-3 py-1.5 border-b border-zinc-800 last:border-0">
      <span className="text-xs text-zinc-500 w-36 shrink-0">{label}</span>
      <span className={`text-xs text-zinc-200 break-all ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}
