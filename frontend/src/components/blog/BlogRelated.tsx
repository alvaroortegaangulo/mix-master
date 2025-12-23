import React from "react";
import { Link } from "../../i18n/routing";

interface RelatedPost {
  title: string;
  slug: string;
  category: string;
}

// Mock related posts for now, ideally passed via props
const relatedPosts: RelatedPost[] = [
  {
    title: "Guía completa de LUFS para Spotify",
    slug: "lufs-true-peak-loudness",
    category: "Mastering",
  },
  {
    title: "Cómo limpiar tus stems antes de mezclar",
    slug: "como-eliminar-dc-offset-en-stems",
    category: "Preparation",
  },
  {
    title: "Compresión de Bus: El secreto del Glue",
    slug: "compresion-bus-bateria-punch-glue",
    category: "Mixing",
  },
];

export default function BlogRelated({ currentSlug }: { currentSlug: string }) {
  const filtered = relatedPosts.filter((p) => p.slug !== currentSlug);

  return (
    <div className="mt-16 border-t border-slate-800 pt-16">
      <h3 className="mb-8 text-2xl font-bold text-white">
        Sigue aprendiendo
      </h3>
      <div className="grid gap-6 sm:grid-cols-2">
        {filtered.slice(0, 2).map((post) => (
          <Link
            key={post.slug}
            href={`/blog/${post.slug}`}
            className="group block rounded-2xl border border-slate-800 bg-slate-900/40 p-6 transition hover:border-teal-500/30 hover:bg-slate-900"
          >
            <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-teal-500">
              {post.category}
            </span>
            <h4 className="text-lg font-bold text-slate-200 transition group-hover:text-white">
              {post.title}
            </h4>
          </Link>
        ))}
      </div>
    </div>
  );
}
