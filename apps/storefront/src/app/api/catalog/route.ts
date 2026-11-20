import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { fetchCatalog } from "@/lib/server/catalog_repository";
import type { CatalogSort } from "@/types/catalog";

const ALLOWED_QUERY_KEYS = new Set(["page", "page_size", "category", "sales_type", "sort", "q"]);
const ALLOWED_SORTS = new Set<CatalogSort>(["newest", "popular", "price_asc", "price_desc"]);

export async function GET(request: NextRequest): Promise<NextResponse> {
  const correlationId = request.headers.get("x-correlation-id") || crypto.randomUUID();
  const params = request.nextUrl.searchParams;

  const unknownKeys = Array.from(params.keys()).filter((k) => !ALLOWED_QUERY_KEYS.has(k));
  if (unknownKeys.length > 0) {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Unknown query parameters are not permitted.",
          details: { fields: unknownKeys.sort() },
        },
        meta: { correlation_id: correlationId },
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const pageRaw = params.get("page") ?? "1";
  const sizeRaw = params.get("page_size") ?? "20";
  const page = Number.parseInt(pageRaw, 10);
  const pageSize = Number.parseInt(sizeRaw, 10);

  if (!Number.isFinite(page) || page < 1 || !Number.isFinite(pageSize) || pageSize < 1 || pageSize > 100) {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "page must be >= 1 and page_size must be between 1 and 100.",
          details: { fields: ["page", "page_size"] },
        },
        meta: { correlation_id: correlationId },
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const sortParam = (params.get("sort") || "newest").trim().toLowerCase() as CatalogSort;
  if (!ALLOWED_SORTS.has(sortParam)) {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid sort parameter.",
          details: { fields: ["sort"] },
        },
        meta: { correlation_id: correlationId },
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  const salesTypeRaw = params.get("sales_type")?.trim().toUpperCase();
  if (salesTypeRaw && salesTypeRaw !== "AFFILIATE" && salesTypeRaw !== "DROPSHIP") {
    return NextResponse.json(
      {
        ok: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "sales_type must be AFFILIATE or DROPSHIP.",
          details: { fields: ["sales_type"] },
        },
        meta: { correlation_id: correlationId },
      },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  try {
    const result = await fetchCatalog(
      {
        page,
        page_size: pageSize,
        category: params.get("category") ?? undefined,
        sales_type: salesTypeRaw as "AFFILIATE" | "DROPSHIP" | undefined,
        sort: sortParam,
        q: params.get("q") ?? undefined,
      },
      correlationId,
    );

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
          message: "Unable to load catalog.",
          details: {},
        },
        meta: { correlation_id: correlationId },
      },
      { status: 500, headers: { "Cache-Control": "no-store" } },
    );
  }
}
