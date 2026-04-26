import { fetchPositions } from "@/lib/api";
import PortfolioPageClient from "./PortfolioPageClient";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const [open, closed] = await Promise.all([
    fetchPositions("open", 200),
    fetchPositions("closed", 200),
  ]);

  return <PortfolioPageClient openPositions={open} closedPositions={closed} />;
}
