"use client";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import type { EquityCurve } from "@/lib/api";
import { fmtUsd, fmtTime } from "@/lib/utils";

interface Props {
  data: EquityCurve;
}

export default function EquityCurveChart({ data }: Props) {
  const points = data.points.map((p) => ({
    ...p,
    tsLabel: fmtTime(p.ts),
  }));

  const min = Math.min(...points.map((p) => p.cumulative));
  const max = Math.max(...points.map((p) => p.cumulative));

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="tsLabel"
            tick={{ fontSize: 10, fill: "#71717a" }}
            interval="preserveStartEnd"
            tickLine={false}
          />
          <YAxis
            domain={[Math.floor(min * 0.95), Math.ceil(max * 1.05)]}
            tickFormatter={(v) => fmtUsd(v)}
            tick={{ fontSize: 10, fill: "#71717a" }}
            tickLine={false}
            axisLine={false}
            width={80}
          />
          <Tooltip
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              fontSize: 12,
            }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(v: any) => [
              typeof v === "number" ? fmtUsd(v as number) : String(v ?? ""),
              "Cumulative PnL",
            ]}
            labelStyle={{ color: "#a1a1aa" }}
          />
          <Area
            type="monotone"
            dataKey="cumulative"
            stroke="#22d3ee"
            strokeWidth={2}
            fill="url(#eq)"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
