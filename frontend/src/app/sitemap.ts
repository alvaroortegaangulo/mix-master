import type { MetadataRoute } from "next";

const fallbackSiteUrl = "https://music-mix-master.com";
const siteUrl = (() => {
  const envUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!envUrl) return fallbackSiteUrl;
  try {
    return new URL(envUrl).origin;
  } catch {
    return fallbackSiteUrl;
  }
})();

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return [
    {
      url: `${siteUrl}/`,
      lastModified,
    },
    {
      url: `${siteUrl}/terms-of-service`,
      lastModified,
    },
    {
      url: `${siteUrl}/privacy-policy`,
      lastModified,
    },
    {
      url: `${siteUrl}/cookie-policy`,
      lastModified,
    },
  ];
}
