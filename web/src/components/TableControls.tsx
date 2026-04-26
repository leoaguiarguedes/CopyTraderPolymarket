"use client";

import type { ReactNode } from "react";

export type SortDirection = "asc" | "desc";

export function SortHeader({
  label,
  active,
  direction,
  onClick,
  align = "left",
}: {
  label: ReactNode;
  active: boolean;
  direction: SortDirection;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 hover:text-zinc-300 transition-colors ${
        align === "right" ? "justify-end w-full" : ""
      }`}
    >
      <span>{label}</span>
      <span className={active ? "text-zinc-300" : "text-zinc-600"}>
        {active ? (direction === "asc" ? "^" : "v") : "<>"}
      </span>
    </button>
  );
}

export function PaginationControls({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100, 200],
}: {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: number[];
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="flex items-center justify-between gap-3 flex-wrap text-xs text-zinc-500">
      <div>
        Exibindo {start}-{end} de {total}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <label className="flex items-center gap-2">
          <span>Por página</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-2 py-1 rounded border border-zinc-800 disabled:opacity-40 text-zinc-300"
        >
          Anterior
        </button>
        <span className="text-zinc-400">
          Página {page} de {totalPages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-2 py-1 rounded border border-zinc-800 disabled:opacity-40 text-zinc-300"
        >
          Próxima
        </button>
      </div>
    </div>
  );
}
