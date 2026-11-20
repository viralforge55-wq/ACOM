import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { fetchProductBySlug } from "@/lib/server/catalog_repository";

type RouteContext = {
  params: Promise<{ slug: string }>;
};

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const correlationId = request.headers.get("x-correlation-id") || crypto.randomUUID();
  const { slug } = await context.params;

  try {
    const result = await fetchProductBySlug(slug, correlationId);
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
          message: "Unable to load product.",
          details: {},
        },
        meta: { correlation_id: correlationId },
      },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
