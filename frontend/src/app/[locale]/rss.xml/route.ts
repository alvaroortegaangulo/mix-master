import { buildBlogRssXml } from "../../../lib/blogRss";
import type { NextRequest } from "next/server";
import { resolveBlogLocale } from "../../../content/blogPosts";

export const revalidate = 3600;

type Props = {
  params: { locale: string };
};

export async function GET(_request: NextRequest, { params }: Props) {
  const locale = resolveBlogLocale(params.locale);
  const xml = buildBlogRssXml(locale, `/${locale}/rss.xml`);
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
    },
  });
}
