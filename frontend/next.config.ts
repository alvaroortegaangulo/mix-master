import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  compress: true,

  async headers() {
    return [
      {
        // Aplica a TODO: páginas, API routes y estáticos de Next
        source: "/((?!_next/|favicon.ico).*)",
        headers: [
          {
            key: "Cache-Control",
            value:
              "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0",
          },
          {
            key: "Pragma",
            value: "no-cache",
          },
          {
            key: "Expires",
            value: "0",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains; preload",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com https://cdn.cookie-script.com https://accounts.google.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https://api.music-mix-master.com https://www.google-analytics.com https://region1.google-analytics.com https://www.googletagmanager.com",
              "font-src 'self'",
              "connect-src 'self' blob: https://api.music-mix-master.com https://www.google-analytics.com https://region1.google-analytics.com https://www.googletagmanager.com https://accounts.google.com https://oauth2.googleapis.com",
              "media-src 'self' blob: https://api.music-mix-master.com",
              "frame-ancestors 'none'",
              "frame-src 'self' https://accounts.google.com",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
