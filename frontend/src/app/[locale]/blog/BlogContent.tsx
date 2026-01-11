"use client";

import { useState, useMemo } from "react";
import { Link } from "../../../i18n/routing";
import type { LocalizedBlogPost } from "../../../content/blogPosts";
import Image from "next/image";

interface BlogContentProps {
  posts: LocalizedBlogPost[];
  allTags: string[];
  copy: any;
  locale: string;
}

export default function BlogContent({ posts, allTags, copy, locale }: BlogContentProps) {
  const [activeTag, setActiveTag] = useState<string>("All");

  const filteredPosts = useMemo(() => {
    if (activeTag === "All") return posts;
    return posts.filter((post) => post.tags.includes(activeTag));
  }, [posts, activeTag]);

  const featuredPost = filteredPosts[0];
  const recentPosts = filteredPosts.slice(1);

  // Function to get a color for the tag (optional, can be improved or removed)
  const getTagColor = (tag: string) => {
    // Just a simple rotation or fixed style.
    // For now, consistent with the dark/teal theme.
    return "border-teal-500/30 bg-teal-500/10 text-teal-300";
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
      <div className="mx-auto max-w-7xl px-4 pb-16 pt-24 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="mb-12 text-center">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-teal-300">
            {copy.badge}
          </p>
          <h1 className="text-4xl font-bold text-white md:text-5xl lg:text-6xl tracking-tight">
            {copy.title}
          </h1>
          <p className="mt-6 max-w-2xl mx-auto text-lg text-slate-400">
            {copy.subtitle}
          </p>
        </div>

        {/* Filter Tags */}
        <div className="mb-12 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => setActiveTag("All")}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
              activeTag === "All"
                ? "bg-teal-500 text-slate-950 shadow-lg shadow-teal-500/20"
                : "bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white border border-slate-800"
            }`}
          >
            {/* We might need a translation for "All" or just use a generic icon/text.
                Using "Todos" / "All" based on locale if possible, or defaulting.
                For now, let's assume 'All' or a fixed string, or we can add it to copy.
                I'll use a safe default and maybe the copy has a 'allTags' label?
                No, checking copy structure, it doesn't. I will stick to 'View All' or just a star icon.
                Let's use a localized string if I can find one, or hardcode common ones or just "All".
             */}
            View All
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setActiveTag(tag)}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
                activeTag === tag
                  ? "bg-teal-500 text-slate-950 shadow-lg shadow-teal-500/20"
                  : "bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white border border-slate-800"
              }`}
            >
              {tag}
            </button>
          ))}
        </div>

        {/* Featured Post (Hero) */}
        {featuredPost && (
          <div className="mb-16">
             <Link href={`/blog/${featuredPost.slug}`} className="group relative block overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/40 transition-all hover:border-teal-500/40 hover:shadow-2xl hover:shadow-teal-900/20">
              <div className="grid lg:grid-cols-5 gap-0 h-full">
                {/* Image Section */}
                <div className="lg:col-span-3 relative h-64 lg:h-auto min-h-[400px] overflow-hidden">
                    {/* Placeholder Logic: If we had real images, they'd go here.
                        Using a gradient fallback or a localized image path.
                    */}
                    <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-slate-800">
                        <Image
                           src={featuredPost.image || `/blog/covers/${featuredPost.slug}.webp`}
                           alt={featuredPost.title}
                           fill
                           className="object-cover transition-transform duration-700 group-hover:scale-105"
                           onError={(e) => {
                               // Fallback logic could go here, but next/image handles errors gracefully usually if configured
                               const target = e.target as HTMLImageElement;
                               target.style.display = 'none';
                           }}
                        />
                        {/* Overlay for text readability if needed */}
                        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent lg:bg-gradient-to-r lg:from-transparent lg:via-slate-950/20 lg:to-slate-950/90" />
                    </div>
                     <div className="absolute top-4 left-4 flex flex-wrap gap-2">
                        {featuredPost.tags.map(tag => (
                            <span key={tag} className="backdrop-blur-md bg-slate-950/50 border border-white/10 rounded-full px-3 py-1 text-xs font-semibold text-white uppercase tracking-wider">
                                {tag}
                            </span>
                        ))}
                    </div>
                </div>

                {/* Content Section */}
                <div className="lg:col-span-2 p-8 lg:p-12 flex flex-col justify-center relative bg-slate-900/40 backdrop-blur-sm lg:bg-transparent">
                  <div className="flex items-center gap-3 text-sm text-teal-400 font-medium mb-4">
                     <span>{featuredPost.publishedAtLabel}</span>
                     <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                     <span>{featuredPost.readingTime}</span>
                  </div>

                  <h2 className="text-3xl md:text-4xl font-bold text-white mb-6 group-hover:text-teal-300 transition-colors leading-tight">
                    {featuredPost.title}
                  </h2>

                  <p className="text-slate-300 text-lg leading-relaxed mb-8 line-clamp-4">
                    {featuredPost.excerpt}
                  </p>

                  <div className="mt-auto">
                    <span className="inline-flex items-center gap-2 text-base font-bold text-teal-400 group-hover:translate-x-1 transition-transform">
                      {copy.readArticleLabel}
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path></svg>
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          </div>
        )}

        {/* Recent Posts Grid */}
        {recentPosts.length > 0 && (
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {recentPosts.map((post) => (
              <article
                key={post.slug}
                className="group flex flex-col h-full rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden transition-all hover:border-teal-500/30 hover:bg-slate-900/60 hover:-translate-y-1 hover:shadow-xl hover:shadow-black/20"
              >
                {/* Card Image */}
                <Link href={`/blog/${post.slug}`} className="relative h-48 w-full overflow-hidden bg-slate-800">
                     <Image
                           src={post.image || `/blog/covers/${post.slug}.webp`}
                           alt={post.title}
                           fill
                           className="object-cover transition-transform duration-500 group-hover:scale-110"
                        />
                    <div className="absolute top-3 left-3">
                         <span className="backdrop-blur-md bg-slate-950/60 border border-white/10 rounded-full px-2 py-1 text-[10px] font-bold text-white uppercase tracking-wider">
                            {post.tags[0]}
                        </span>
                    </div>
                </Link>

                {/* Card Content */}
                <div className="flex flex-1 flex-col p-6">
                    <div className="flex items-center gap-2 text-xs text-slate-400 mb-3">
                        <span>{post.publishedAtLabel}</span>
                        <span>•</span>
                        <span>{post.readingTime}</span>
                    </div>

                    <Link href={`/blog/${post.slug}`}>
                        <h3 className="text-xl font-bold text-white mb-3 group-hover:text-teal-300 transition-colors line-clamp-2">
                            {post.title}
                        </h3>
                    </Link>

                    <p className="text-sm text-slate-300 line-clamp-3 mb-6 flex-1">
                        {post.excerpt}
                    </p>

                     <div className="pt-4 border-t border-slate-800/50 mt-auto">
                        <Link
                        href={`/blog/${post.slug}`}
                        className="inline-flex items-center gap-2 text-sm font-semibold text-teal-400 transition hover:text-teal-300"
                        >
                        {copy.readArticleLabel}
                         <svg className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                        </Link>
                    </div>
                </div>
              </article>
            ))}
          </div>
        )}

         {/* Empty State */}
        {filteredPosts.length === 0 && (
            <div className="text-center py-20">
                <p className="text-slate-400 text-lg">No posts found for "{activeTag}".</p>
                <button onClick={() => setActiveTag('All')} className="mt-4 text-teal-400 hover:underline">View all posts</button>
            </div>
        )}

        {/* CTA Section */}
        <div className="mt-24 relative overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/60 p-8 md:p-12 text-center">
            <div className="absolute inset-0 bg-gradient-to-r from-teal-500/5 via-transparent to-purple-500/5" />
          <h2 className="relative text-3xl font-bold text-white md:text-4xl">
            {copy.ctaTitle}
          </h2>
          <p className="relative mt-4 max-w-2xl mx-auto text-lg text-slate-300">
            {copy.ctaBody}
          </p>
          <div className="relative mt-8">
            <Link
              href="/mix"
              className="inline-flex items-center justify-center rounded-full bg-teal-500 px-8 py-4 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all hover:bg-teal-400 hover:scale-105"
            >
              {copy.ctaButton}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
