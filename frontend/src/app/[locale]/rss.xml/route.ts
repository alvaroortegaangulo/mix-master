import { buildBlogRssXml } from "../../../lib/blogRss";
import type { NextRequest } from "next/server";
import { resolveBlogLocale } from "../../../content/blogPosts";

export const revalidate = 3600;

type Props = {
  params: Promise<{ locale: string }>;
};

export async function GET(_request: NextRequest, { params }: Props) {
  const { locale } = await params;
  const blogLocale = resolveBlogLocale(locale);
  const xml = buildBlogRssXml(blogLocale, `/${blogLocale}/rss.xml`);
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
    },
  });
}
