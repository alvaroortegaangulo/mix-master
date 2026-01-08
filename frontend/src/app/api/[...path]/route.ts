import { NextRequest } from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";
const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
]);

function getBackendBaseUrl(): string {
  const envUrl =
    process.env.BACKEND_URL?.trim() ||
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (envUrl) {
    return envUrl.replace(/\/+$/, "");
  }
  return DEFAULT_BACKEND_URL;
}

function buildProxyHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const apiKey = process.env.MIXMASTER_API_KEY?.trim();
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  return headers;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const { path } = await context.params;
  const pathParts = path ?? [];
  const backendBase = getBackendBaseUrl();
  const targetUrl = new URL(backendBase);
  targetUrl.pathname = `/${pathParts.join("/")}`;
  targetUrl.search = request.nextUrl.search;

  const headers = buildProxyHeaders(request);
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }

  const res = await fetch(targetUrl.toString(), init);
  const responseHeaders = new Headers(res.headers);

  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: responseHeaders,
  });
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
