import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { resolveAffiliateRedirect } from "@/lib/server/affiliate_service";

type RouteContext = {
  params: Promise<{ click_id: string }>;
};

const NOT_FOUND_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex, nofollow" />
  <title>Deal Link Not Found — ACOM</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; background: #FAF9F6; color: #141413; margin: 0; padding: 4rem 1.5rem; }
    main { max-width: 34rem; margin: 0 auto; }
    h1 { font-size: 1.5rem; margin: 0 0 0.75rem; }
    p { color: #57554F; line-height: 1.6; margin: 0 0 1.5rem; }
    a { color: #1F4E3D; font-weight: 600; text-decoration: none; border-bottom: 1px solid #1F4E3D; padding-bottom: 2px; }
  </style>
</head>
<body>
  <main>
    <h1>Deal link not found or no longer active</h1>
    <p>This outbound merchant link could not be resolved. The offer may have been paused or the link identifier is invalid.</p>
    <a href="/">Return to ACOM Catalog</a>
  </main>
</body>
</html>`;

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const correlationId = request.headers.get("x-correlation-id") || crypto.randomUUID();
  const { click_id: clickId } = await context.params;

  const result = await resolveAffiliateRedirect(clickId, correlationId);

  if (!result.envelope.ok) {
    const status = result.status === 422 ? 404 : result.status === 404 ? 404 : 404;
    return new NextResponse(NOT_FOUND_HTML, {
      status,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Robots-Tag": "noindex, nofollow",
      },
    });
  }

  return new NextResponse(null, {
    status: 302,
    headers: {
      Location: result.envelope.data.destination_url,
      "Cache-Control": "no-store, no-cache, must-revalidate",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}
