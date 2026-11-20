import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { submitAffiliateClick } from "@/lib/server/affiliate_service";
import { validateClickPayload } from "@/lib/server/security";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const correlationId = request.headers.get("x-correlation-id") || crypto.randomUUID();

  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Request body must be valid JSON.",
          details: {},
        },
        meta: { correlation_id: correlationId },
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const validated = validateClickPayload(rawBody);
  if (!validated.ok) {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: validated.code,
          message: validated.message,
          details: { fields: validated.fields },
        },
        meta: { correlation_id: correlationId },
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const upstream = await submitAffiliateClick(validated.value, {
    userAgent: request.headers.get("user-agent"),
    correlationId,
  });

  const headers: Record<string, string> = {
    "Cache-Control": "no-store",
  };
  if (upstream.retryAfter) {
    headers["Retry-After"] = upstream.retryAfter;
  }

  return NextResponse.json(upstream.envelope, {
    status: upstream.status,
    headers,
  });
}
