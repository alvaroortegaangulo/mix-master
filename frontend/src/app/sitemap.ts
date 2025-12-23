import type { MetadataRoute } from "next";
import { routing } from "../i18n/routing";
import { blogPostSlugs } from "../content/blogPosts";

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

  const staticRoutes = [
    { path: "", changeFrequency: "weekly", priority: 1.0 },
    { path: "/examples", changeFrequency: "monthly", priority: 0.8 },
    { path: "/pricing", changeFrequency: "monthly", priority: 0.9 },
    { path: "/docs", changeFrequency: "weekly", priority: 0.8 },
    { path: "/blog", changeFrequency: "weekly", priority: 0.8 },
    { path: "/support", changeFrequency: "monthly", priority: 0.7 },
    { path: "/faq", changeFrequency: "monthly", priority: 0.7 },
    { path: "/terms-of-service", changeFrequency: "yearly", priority: 0.3 },
    { path: "/privacy-policy", changeFrequency: "yearly", priority: 0.3 },
    { path: "/cookie-policy", changeFrequency: "yearly", priority: 0.3 },
  ] as const;

  const blogRoutes = blogPostSlugs.map((slug) => ({
    path: `/blog/${slug}`,
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  return routing.locales.flatMap((locale) => {
    const baseUrl = `${siteUrl}/${locale}`;
    const staticEntries = staticRoutes.map((route) => ({
      url: `${baseUrl}${route.path}`,
      lastModified,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
    }));
    const blogEntries = blogRoutes.map((route) => ({
      url: `${baseUrl}${route.path}`,
      lastModified,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
    }));
    return [...staticEntries, ...blogEntries];
  });
}
