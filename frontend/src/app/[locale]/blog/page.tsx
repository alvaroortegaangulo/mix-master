import type { Metadata } from "next";
import { getBlogPosts, resolveBlogLocale, getBlogTags } from "../../../content/blogPosts";
import { getBlogCopy } from "../../../content/blogCopy";
import BlogContent from "./BlogContent";

type Props = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const blogLocale = resolveBlogLocale(locale);
  const copy = getBlogCopy(blogLocale).index;

  return {
    title: copy.metaTitle,
    description: copy.metaDescription,
    alternates: { canonical: `/${blogLocale}/blog` },
    openGraph: {
      title: copy.metaTitle,
      description: copy.metaDescription,
      url: `/${blogLocale}/blog`,
      type: "website",
    },
  };
}

export default async function BlogPage({ params }: Props) {
  const { locale } = await params;
  const blogLocale = resolveBlogLocale(locale);
  const copy = getBlogCopy(blogLocale).index;
  const posts = getBlogPosts(blogLocale);
  const allTags = getBlogTags(blogLocale);

  return (
    <BlogContent
      posts={posts}
      allTags={allTags}
      copy={copy}
      locale={locale}
    />
  );
}
