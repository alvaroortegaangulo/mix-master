import type { Metadata } from "next";
import Script from "next/script";
import { notFound } from "next/navigation";
import { Link } from "../../../../i18n/routing";
import {
  blogLocales,
  blogPostSlugs,
  getBlogPost,
  resolveBlogLocale,
} from "../../../../content/blogPosts";
import { getBlogPostContent } from "../../../../content/blogPostContent";
import { getBlogCopy } from "../../../../content/blogCopy";
import BlogAuthor from "../../../../components/blog/BlogAuthor";
import BlogRelated from "../../../../components/blog/BlogRelated";
import { ArrowRightIcon } from "@heroicons/react/24/solid";

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

type Props = {
  params: Promise<{ slug: string; locale: string }>;
};

export function generateStaticParams() {
  return blogLocales.flatMap((locale) =>
    blogPostSlugs.map((slug) => ({ locale, slug }))
  );
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug, locale } = await params;
  const blogLocale = resolveBlogLocale(locale);
  const post = getBlogPost(slug, blogLocale);
  const copy = getBlogCopy(blogLocale).post;

  if (!post) {
    return {
      title: copy.metaFallbackTitle,
      description: copy.metaFallbackDescription,
    };
  }

  return {
    title: post.title,
    description: post.description,
    keywords: post.keywords,
    alternates: { canonical: `/${blogLocale}/blog/${post.slug}` },
    openGraph: {
      title: post.title,
      description: post.description,
      url: `${siteUrl}/${blogLocale}/blog/${post.slug}`,
      type: "article",
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug, locale } = await params;
  const blogLocale = resolveBlogLocale(locale);
  const post = getBlogPost(slug, blogLocale);
  const content = getBlogPostContent(slug, blogLocale);
  const copy = getBlogCopy(blogLocale).post;

  if (!post || !content) {
    notFound();
  }

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.description,
    datePublished: post.publishedAt,
    dateModified: post.publishedAt,
    author: {
      "@type": "Organization",
      name: "Piroola",
    },
    publisher: {
      "@type": "Organization",
      name: "Piroola",
      logo: {
        "@type": "ImageObject",
        url: `${siteUrl}/brand/logo.webp`,
      },
    },
    mainEntityOfPage: `${siteUrl}/${blogLocale}/blog/${post.slug}`,
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-24">
        {/* Navigation */}
        <Link
          href="/blog"
          className="mb-8 inline-flex items-center text-sm font-medium text-slate-400 transition hover:text-teal-300"
        >
          ← {copy.backLink}
        </Link>

        {/* Header Section */}
        <header className="mx-auto max-w-4xl text-center">
          <div className="mb-6 flex justify-center">
            <span className="rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-teal-300 shadow-[0_0_10px_rgba(20,184,166,0.2)]">
              {copy.badge}
            </span>
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl md:text-6xl lg:leading-tight">
            {post.title}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-300 md:text-xl">
            {post.description}
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-4 text-sm font-medium text-slate-400">
             <div className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-teal-500"></span>
                {post.publishedAtLabel}
             </div>
             <div className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-teal-500"></span>
                {post.readingTime}
             </div>
             <div className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-teal-500"></span>
                <span className="text-teal-300">{post.tags.join(" • ")}</span>
             </div>
          </div>
        </header>

        {/* Main Layout: Content + Sidebar */}
        <div className="mt-16 grid gap-12 lg:grid-cols-[1fr_300px]">
          {/* Main Content Column */}
          <main>
            <article className="prose prose-lg prose-invert max-w-none
              prose-headings:scroll-mt-24 prose-headings:font-bold prose-headings:text-white
              prose-a:text-teal-300 prose-a:no-underline hover:prose-a:text-teal-200
              prose-strong:text-white prose-li:text-slate-300 prose-p:text-slate-300 prose-p:leading-relaxed
              [&>p]:mb-6 [&>ul]:mb-6 [&>ol]:mb-6">
              {content}
            </article>

            {/* Post-Article Components */}
            <BlogAuthor />
            <BlogRelated currentSlug={slug} />
          </main>

          {/* Sidebar Column */}
          <aside className="hidden lg:block">
            <div className="sticky top-24 space-y-8">
              {/* Table of Contents */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-sm">
                <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-slate-400">
                  {copy.tocTitle}
                </h2>
                <nav>
                  <ul className="space-y-3">
                    {post.toc.map((item) => (
                      <li key={item.id}>
                        <a
                          href={`#${item.id}`}
                          className="block text-sm text-slate-400 transition hover:text-teal-300 hover:translate-x-1"
                        >
                          {item.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                </nav>
              </div>

              {/* Utility Plugin CTA (Simulated) */}
              <div className="relative overflow-hidden rounded-2xl border border-teal-500/30 bg-gradient-to-br from-slate-900 to-slate-800 p-6 shadow-xl">
                 <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-teal-500/20 blur-3xl"></div>
                 <h3 className="relative z-10 text-lg font-bold text-white">
                   ¿Mezclas opacas?
                 </h3>
                 <p className="relative z-10 mt-2 text-sm text-slate-300">
                   Prueba nuestro motor de masterización gratuito y dale vida a tus stems.
                 </p>
                 <Link
                   href="/mix"
                   className="relative z-10 mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-bold text-slate-900 transition hover:bg-teal-400"
                 >
                   Probar ahora <ArrowRightIcon className="h-4 w-4" />
                 </Link>
              </div>
            </div>
          </aside>
        </div>

        {/* Bottom CTA (Mobile/Desktop Backup) */}
        <div className="mt-20 rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-950 p-8 text-center md:p-12">
          <h2 className="text-3xl font-bold text-white md:text-4xl">
            {copy.ctaTitle}
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-300">
            {copy.ctaBody}
          </p>
          <div className="mt-8 flex flex-col justify-center gap-4 sm:flex-row">
            <Link
              href="/mix"
              className="inline-flex items-center justify-center rounded-full bg-teal-500 px-8 py-4 text-base font-bold text-slate-950 shadow-[0_0_20px_rgba(20,184,166,0.3)] transition hover:scale-105 hover:bg-teal-400 hover:shadow-[0_0_30px_rgba(20,184,166,0.5)]"
            >
              {copy.ctaPrimary}
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center justify-center rounded-full border border-slate-700 bg-slate-800/50 px-8 py-4 text-base font-semibold text-slate-200 transition hover:border-teal-400 hover:text-white"
            >
              {copy.ctaSecondary}
            </Link>
          </div>
        </div>
      </div>

      <Script
        id={`ld-blog-${post.slug}`}
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
    </div>
  );
}
