import { NextRequest, NextResponse } from "next/server";
import { callFrappeMethod } from "./frappe_client";
import { assertNoBannedFields } from "./security";

export function sameOrigin(request: NextRequest): boolean {
  return request.headers.get("origin") === new URL(request.url).origin;
}

export function failure(status: number, message: string) {
  return NextResponse.json({ ok: false, error: { code: status === 403 ? "FORBIDDEN" : "VALIDATION_ERROR", message, details: {} }, meta: { correlation_id: crypto.randomUUID() } }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function checkoutProxy(request: NextRequest, method: string, query?: Record<string, string>) {
  if (request.method === "POST" && !sameOrigin(request)) return failure(403, "Same-origin request required.");
  try {
    const body = request.method === "POST" ? await request.json() : undefined;
    if (body && (typeof body !== "object" || Array.isArray(body))) return failure(400, "JSON object required.");
    const result = await callFrappeMethod({ method: request.method === "POST" ? "POST" : "GET",
      endpoint: `acom_core.api.dropship.${method}`, body, query,
      sessionId: request.cookies.get("acom_sid")?.value,
      csrfToken: request.cookies.get("acom_csrf")?.value,
      idempotencyKey: request.headers.get("idempotency-key") || undefined,
    });
    assertNoBannedFields(result.envelope);
    return NextResponse.json(result.envelope, { status: result.status, headers: { "Cache-Control": "no-store" } });
  } catch { return failure(400, "Request could not be processed."); }
}
