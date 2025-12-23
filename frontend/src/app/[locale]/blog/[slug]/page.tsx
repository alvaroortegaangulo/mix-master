import type { Metadata } from "next";
import Script from "next/script";
import { notFound } from "next/navigation";
import { Link } from "../../../../i18n/routing";
import { blogPostSlugs, getBlogPost } from "../../../../content/blogPosts";
import { blogPostContent } from "../../../../content/blogPostContent";

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
  return blogPostSlugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = getBlogPost(slug);
  if (!post) {
    return {
      title: "Blog técnico",
      description: "Artículos técnicos de mezcla y mastering con IA.",
    };
  }

  return {
    title: post.title,
    description: post.description,
    keywords: post.keywords,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      title: post.title,
      description: post.description,
      url: `${siteUrl}/blog/${post.slug}`,
      type: "article",
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = getBlogPost(slug);
  const content = blogPostContent[slug];

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
        url: `${siteUrl}/logo.webp`,
      },
    },
    mainEntityOfPage: `${siteUrl}/blog/${post.slug}`,
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-5xl px-4 pb-16 pt-24">
        <Link
          href="/blog"
          className="text-sm font-medium text-slate-400 transition hover:text-teal-300"
        >
          ← Volver al blog
        </Link>

        <div className="mt-6">
          <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-teal-300">
            Guía técnica
          </p>
          <h1 className="text-4xl font-bold text-white md:text-5xl">
            {post.title}
          </h1>
          <p className="mt-4 text-lg text-slate-300">{post.description}</p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-400">
            <span>{post.dateLabel}</span>
            <span>·</span>
            <span>{post.readingTime}</span>
            <span>·</span>
            <span className="text-teal-300">{post.tags.join(" · ")}</span>
          </div>
        </div>

        <div className="mt-10 grid gap-10 lg:grid-cols-[1fr_240px]">
          <article className="prose prose-invert max-w-none prose-headings:text-white prose-a:text-teal-300 prose-a:no-underline hover:prose-a:text-teal-200">
            {content}
          </article>

          <aside className="hidden lg:block">
            <div className="sticky top-24 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
                En este artículo
              </h2>
              <ul className="mt-4 space-y-2 text-sm text-slate-400">
                {post.toc.map((item) => (
                  <li key={item.id}>
                    <a
                      href={`#${item.id}`}
                      className="transition hover:text-teal-300"
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>

        <div className="mt-12 rounded-2xl border border-slate-800 bg-slate-900/60 p-8">
          <h2 className="text-2xl font-semibold text-white">
            ¿Quieres ver esto aplicado a tus stems?
          </h2>
          <p className="mt-3 max-w-2xl text-slate-300">
            Piroola ejecuta estos pasos dentro del pipeline y entrega un informe
            técnico con métricas antes y después.
          </p>
          <div className="mt-6 flex flex-wrap gap-4">
            <Link
              href="/mix"
              className="inline-flex items-center justify-center rounded-full bg-teal-500 px-6 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition hover:bg-teal-400"
            >
              Probar Piroola
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center justify-center rounded-full border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-100 transition hover:border-teal-400 hover:text-teal-200"
            >
              Ver cómo funciona
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
