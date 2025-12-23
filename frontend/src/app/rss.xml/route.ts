import { buildBlogRssXml } from "../../lib/blogRss";
import { defaultBlogLocale } from "../../content/blogPosts";

export const revalidate = 3600;

export async function GET() {
  const xml = buildBlogRssXml(defaultBlogLocale, "/rss.xml");
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
    },
  });
}
