import type { Metadata } from "next";
import { Link } from "../../../i18n/routing";
import { blogPosts } from "../../../content/blogPosts";

export const metadata: Metadata = {
  title: "Blog técnico de mezcla y mastering con IA",
  description:
    "Guías técnicas sobre problemas reales de audio: DC offset, compresión de bus, dinámica y preparación de stems.",
  alternates: { canonical: "/blog" },
};

export default function BlogPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-24">
        <div className="mb-12">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-teal-300">
            Blog técnico
          </p>
          <h1 className="text-4xl font-bold text-white md:text-5xl">
            Soluciones específicas para problemas reales de mezcla
          </h1>
          <p className="mt-4 max-w-3xl text-lg text-slate-300">
            En lugar de competir por keywords genéricas, aquí atacamos búsquedas
            técnicas que los productores hacen todos los días: limpieza de DC
            offset, compresión de bus, control dinámico y preparación de stems.
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-2">
          {blogPosts.map((post) => (
            <article
              key={post.slug}
              className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 transition hover:border-teal-500/40 hover:bg-slate-900/60"
            >
              <div className="flex flex-wrap gap-2 text-xs uppercase tracking-wide text-slate-300">
                {post.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-slate-700/80 bg-slate-950/40 px-2 py-1"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <h2 className="mt-4 text-2xl font-semibold text-white">
                {post.title}
              </h2>
              <p className="mt-3 text-slate-300">{post.excerpt}</p>
              <div className="mt-4 flex items-center gap-4 text-sm text-slate-400">
                <span>{post.dateLabel}</span>
                <span>·</span>
                <span>{post.readingTime}</span>
              </div>
              <div className="mt-6">
                <Link
                  href={`/blog/${post.slug}`}
                  className="inline-flex items-center gap-2 text-sm font-semibold text-teal-300 transition hover:text-teal-200"
                >
                  Leer artículo
                  <span aria-hidden="true">→</span>
                </Link>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-16 rounded-2xl border border-slate-800 bg-slate-900/60 p-8">
          <h2 className="text-2xl font-semibold text-white">
            ¿Quieres aplicar estos ajustes automáticamente?
          </h2>
          <p className="mt-3 max-w-2xl text-slate-300">
            Piroola analiza tus stems, detecta problemas técnicos y aplica
            correcciones de forma consistente en cada etapa del pipeline.
          </p>
          <div className="mt-6">
            <Link
              href="/mix"
              className="inline-flex items-center justify-center rounded-full bg-teal-500 px-6 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition hover:bg-teal-400"
            >
              Probar Piroola
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
