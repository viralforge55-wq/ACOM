import { NextRequest, NextResponse } from "next/server";
import { getFrappeConfig, performNodeHttpRequest, callFrappeMethod } from "@/lib/server/frappe_client";
import { sameOrigin, failure } from "@/lib/server/checkout_proxy";
export const runtime = "nodejs";
export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return failure(403, "Same-origin request required.");
  try {
    const input = await request.json();
    if (!input || Object.keys(input).some((key) => !["usr", "pwd"].includes(key)) || typeof input.usr !== "string" || typeof input.pwd !== "string") return failure(400, "Email and password required.");
    const { baseUrl, siteHost, timeoutMs } = getFrappeConfig();
    const body = JSON.stringify(input);
    const upstream = await performNodeHttpRequest(new URL("/api/method/login", baseUrl), "POST", {
      Host: siteHost, "Content-Type": "application/json", "Content-Length": String(Buffer.byteLength(body)),
    }, body, timeoutMs);
    const sid = upstream.headers["set-cookie"]?.find((cookie) => cookie.startsWith("sid="))?.split(";")[0].slice(4);
    if (upstream.status !== 200 || !sid || sid === "Guest") return failure(403, "Sign-in failed.");
    const session = await callFrappeMethod<{ csrf_token: string }>({ method: "GET", endpoint: "acom_core.api.dropship.session_info", sessionId: sid });
    if (!session.envelope.ok) return failure(403, "Sign-in failed.");
    const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
    const options = { httpOnly: true, sameSite: "lax" as const, secure: new URL(request.url).protocol === "https:", path: "/", maxAge: 3600 };
    response.cookies.set("acom_sid", sid, options);
    response.cookies.set("acom_csrf", session.envelope.data.csrf_token, options);
    return response;
  } catch { return failure(400, "Sign-in could not be completed."); }
}
