import { NextRequest } from "next/server";
import { checkoutProxy } from "@/lib/server/checkout_proxy";
export const runtime = "nodejs";
export async function GET(request: NextRequest, { params }: { params: Promise<{ order_id: string }> }) {
  return checkoutProxy(request, "get_customer_order", { order_id: (await params).order_id });
}
