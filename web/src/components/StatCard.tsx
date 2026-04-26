import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  negative?: boolean;
  className?: string;
}

export default function StatCard({
  label,
  value,
  sub,
  positive,
  negative,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        "bg-zinc-900 rounded-xl border border-zinc-800 p-4 flex flex-col gap-1",
        className
      )}
    >
      <p className="text-xs text-zinc-500 uppercase tracking-wider">{label}</p>
      <p
        className={cn(
          "text-2xl font-bold",
          positive && "text-green-400",
          negative && "text-red-400",
          !positive && !negative && "text-zinc-100"
        )}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-zinc-500">{sub}</p>}
    </div>
  );
}
