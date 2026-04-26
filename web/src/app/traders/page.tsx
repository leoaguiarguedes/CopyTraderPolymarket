import { fetchWallets } from "@/lib/api";
import TradersPageClient from "./TradersPageClient";

export const dynamic = "force-dynamic";

export default async function TradersPage() {
  const wallets = await fetchWallets(200).catch(() => []);
  return <TradersPageClient initialWallets={wallets} />;
}
