import { fetchSignals } from "@/lib/api";
import SignalsPageClient from "./SignalsPageClient";

export const dynamic = "force-dynamic";

export default async function SignalsPage() {
  const signals = await fetchSignals(200).catch(() => []);
  return <SignalsPageClient initialSignals={signals} />;
}
