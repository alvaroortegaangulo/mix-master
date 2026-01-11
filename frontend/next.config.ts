import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');
const isFastBuild = true;

const nextConfig = {
  reactCompiler: true,
  compress: true,
  typescript: {
    ignoreBuildErrors: isFastBuild,
  },
  experimental: {
    optimizePackageImports: ['@heroicons/react', 'lucide-react', 'date-fns', 'lodash'],
    optimizeCss: !isFastBuild, // Enable CSS optimization (critters)
  },

  async headers() {
    return [
      {
        // API: no-store for authenticated/dynamic data
        source: "/api/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "no-store",
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
              "connect-src 'self' blob: https://api.music-mix-master.com wss://api.music-mix-master.com https://www.google-analytics.com https://region1.google-analytics.com https://www.googletagmanager.com https://accounts.google.com https://oauth2.googleapis.com ws://localhost:* ws://127.0.0.1:*",
              "media-src 'self' blob: https://api.music-mix-master.com",
              "frame-ancestors 'none'",
              "frame-src 'self' https://accounts.google.com",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
      {
        // Pages: allow BFCache (avoid no-store)
        source: "/((?!_next/|api/|favicon.ico|.*\\.(?:jpg|jpeg|gif|png|webp|svg|css|js|map|txt|xml|ico|woff2|woff|ttf|otf)).*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=0, must-revalidate",
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
              "connect-src 'self' blob: https://api.music-mix-master.com wss://api.music-mix-master.com https://www.google-analytics.com https://region1.google-analytics.com https://www.googletagmanager.com https://accounts.google.com https://oauth2.googleapis.com ws://localhost:* ws://127.0.0.1:*",
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

export default withNextIntl(nextConfig);
