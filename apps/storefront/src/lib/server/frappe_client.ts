import crypto from "node:crypto";
import http from "node:http";
import https from "node:https";
import type { ApiEnvelope, ApiMeta } from "@/types/catalog";

const DEFAULT_BASE_URL = "http://127.0.0.1:8080";
const DEFAULT_SITE_HOST = "acom.localhost";
const DEFAULT_TIMEOUT_MS = 8000;

export function getFrappeConfig(): {
  baseUrl: string;
  siteHost: string;
  timeoutMs: number;
} {
  const baseUrl = (process.env.FRAPPE_API_BASE_URL || DEFAULT_BASE_URL).replace(/\/+$/, "");
  const siteHost = (process.env.FRAPPE_SITE_HOST || DEFAULT_SITE_HOST).trim();
  const parsedTimeout = Number.parseInt(process.env.FRAPPE_API_TIMEOUT_MS || "", 10);
  const timeoutMs =
    Number.isFinite(parsedTimeout) && parsedTimeout > 0 ? parsedTimeout : DEFAULT_TIMEOUT_MS;
  return { baseUrl, siteHost, timeoutMs };
}

export type FrappeCallResult<T, M extends ApiMeta = ApiMeta> = {
  status: number;
  envelope: ApiEnvelope<T, M>;
  retryAfter?: string;
};

type FrappeCallOptions = {
  method: "GET" | "POST";
  endpoint: string;
  query?: Record<string, string | number | undefined>;
  body?: Record<string, unknown>;
  userAgent?: string | null;
  correlationId?: string;
  sessionId?: string;
  csrfToken?: string;
  idempotencyKey?: string;
};

type RawHttpResponse = {
  status: number;
  headers: http.IncomingHttpHeaders;
  body: string;
};

export function performNodeHttpRequest(
  targetUrl: URL,
  method: "GET" | "POST",
  headers: Record<string, string>,
  bodyStr: string | undefined,
  timeoutMs: number,
): Promise<RawHttpResponse> {
  return new Promise((resolve, reject) => {
    const transport = targetUrl.protocol === "https:" ? https : http;
    const req = transport.request(
      {
        protocol: targetUrl.protocol,
        hostname: targetUrl.hostname,
        port: targetUrl.port || (targetUrl.protocol === "https:" ? 443 : 80),
        path: `${targetUrl.pathname}${targetUrl.search}`,
        method,
        headers,
        timeout: timeoutMs,
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk: Buffer | string) => {
          chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
        });
        res.on("end", () => {
          resolve({
            status: res.statusCode ?? 502,
            headers: res.headers,
            body: Buffer.concat(chunks).toString("utf-8"),
          });
        });
      },
    );

    req.on("timeout", () => {
      req.destroy(new Error("Upstream request timed out"));
    });
    req.on("error", reject);

    if (bodyStr !== undefined) {
      req.write(bodyStr);
    }
    req.end();
  });
}

/**
 * Server-only HTTP client for acom_core whitelisted Frappe methods.
 *
 * Uses node:http / node:https instead of WHATWG fetch because fetch/undici
 * silently drops the `Host` header (forbidden header name in the Fetch spec).
 * Sending an explicit `Host: <FRAPPE_SITE_HOST>` header against 127.0.0.1:8080
 * ensures Frappe nginx resolves `acom.localhost` reliably on Windows hosts.
 */
export async function callFrappeMethod<T, M extends ApiMeta = ApiMeta>(
  options: FrappeCallOptions,
): Promise<FrappeCallResult<T, M>> {
  const { baseUrl, siteHost, timeoutMs } = getFrappeConfig();
  const correlationId = options.correlationId || crypto.randomUUID();

  const url = new URL(`/api/method/${options.endpoint}`, baseUrl);
  if (options.query) {
    for (const [key, val] of Object.entries(options.query)) {
      if (val !== undefined && val !== "") {
        url.searchParams.set(key, String(val));
      }
    }
  }

  let bodyStr: string | undefined;
  const headers: Record<string, string> = {
    Accept: "application/json",
    Host: siteHost,
    "X-Correlation-Id": correlationId,
  };
  if (options.userAgent) {
    headers["User-Agent"] = options.userAgent;
  }
  if (options.sessionId) headers.Cookie = `sid=${options.sessionId}`;
  if (options.csrfToken) headers["X-Frappe-CSRF-Token"] = options.csrfToken;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  if (options.method === "POST") {
    bodyStr = JSON.stringify(options.body ?? {});
    headers["Content-Type"] = "application/json";
    headers["Content-Length"] = String(Buffer.byteLength(bodyStr, "utf-8"));
  }

  let response: RawHttpResponse;
  try {
    response = await performNodeHttpRequest(url, options.method, headers, bodyStr, timeoutMs);
  } catch {
    return {
      status: 502,
      envelope: {
        ok: false,
        error: {
          code: "UPSTREAM_UNAVAILABLE",
          message: "Catalog service is temporarily unavailable.",
          details: {},
        },
        meta: { correlation_id: correlationId },
      },
    };
  }

  const retryAfterRaw = response.headers["retry-after"];
  const retryAfter = Array.isArray(retryAfterRaw) ? retryAfterRaw[0] : retryAfterRaw;

  let rawJson: unknown;
  try {
    rawJson = JSON.parse(response.body);
  } catch {
    return {
      status: 502,
      envelope: {
        ok: false,
        error: {
          code: "UPSTREAM_INVALID_RESPONSE",
          message: "Received an invalid response from catalog service.",
          details: {},
        },
        meta: { correlation_id: correlationId },
      },
      retryAfter,
    };
  }

  const unwrapped =
    rawJson !== null &&
    typeof rawJson === "object" &&
    "message" in (rawJson as Record<string, unknown>) &&
    typeof (rawJson as Record<string, unknown>).message === "object" &&
    (rawJson as Record<string, unknown>).message !== null
      ? (rawJson as { message: unknown }).message
      : rawJson;

  if (
    unwrapped !== null &&
    typeof unwrapped === "object" &&
    "ok" in (unwrapped as Record<string, unknown>)
  ) {
    return {
      status: response.status,
      envelope: unwrapped as ApiEnvelope<T, M>,
      retryAfter,
    };
  }

  return {
    status: response.status >= 400 ? response.status : 502,
    envelope: {
      ok: false,
      error: {
        code: response.status === 403 ? "FORBIDDEN" : "INTERNAL_ERROR",
        message: "Request could not be completed.",
        details: {},
      },
      meta: { correlation_id: correlationId },
    },
    retryAfter,
  };
}
