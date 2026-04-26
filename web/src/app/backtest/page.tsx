import { fetchBacktestRuns } from "@/lib/api";
import BacktestPageClient from "./BacktestPageClient";

export const dynamic = "force-dynamic";

export default async function BacktestPage() {
  const runs = await fetchBacktestRuns(20).catch(() => []);
  return <BacktestPageClient initialRuns={runs} />;
}
