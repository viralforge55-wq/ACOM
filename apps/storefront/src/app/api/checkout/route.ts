import { NextRequest } from "next/server";
import { checkoutProxy } from "@/lib/server/checkout_proxy";
export const runtime = "nodejs";
export function POST(request: NextRequest) { return checkoutProxy(request, "create_checkout"); }
