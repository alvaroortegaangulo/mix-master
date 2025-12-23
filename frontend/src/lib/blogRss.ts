import { getBlogPosts, resolveBlogLocale } from "../content/blogPosts";
import { getBlogCopy } from "../content/blogCopy";

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

const escapeXml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&apos;");

export function buildBlogRssXml(localeInput: string, feedPath: string) {
  const locale = resolveBlogLocale(localeInput);
  const copy = getBlogCopy(locale).rss;
  const posts = getBlogPosts(locale);
  const channelLink = `${siteUrl}/${locale}/blog`;
  const feedUrl = `${siteUrl}${feedPath}`;
  const lastBuildDate = new Date().toUTCString();

  const items = posts
    .map((post) => {
      const link = `${siteUrl}/${locale}/blog/${post.slug}`;
      return `
    <item>
      <title>${escapeXml(post.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${new Date(post.publishedAt).toUTCString()}</pubDate>
      <description>${escapeXml(post.excerpt)}</description>
    </item>`;
    })
    .join("");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(copy.title)}</title>
    <link>${channelLink}</link>
    <description>${escapeXml(copy.description)}</description>
    <language>${locale}</language>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <atom:link href="${feedUrl}" rel="self" type="application/rss+xml" />
    ${items}
  </channel>
</rss>
`;
}
