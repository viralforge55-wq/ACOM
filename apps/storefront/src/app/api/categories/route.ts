import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { fetchCategories } from "@/lib/server/catalog_repository";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const correlationId = request.headers.get("x-correlation-id") || crypto.randomUUID();
  try {
    const result = await fetchCategories(correlationId);
    return NextResponse.json(result.envelope, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "INTERNAL_ERROR",
          message: "Unable to load categories.",
          details: {},
        },
        meta: { correlation_id: correlationId },
      },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
