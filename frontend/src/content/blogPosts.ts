export type BlogPostTocItem = {
  id: string;
  label: string;
};

export type BlogPost = {
  slug: string;
  title: string;
  description: string;
  excerpt: string;
  publishedAt: string;
  dateLabel: string;
  readingTime: string;
  tags: string[];
  keywords: string[];
  toc: BlogPostTocItem[];
};

export const blogPosts: BlogPost[] = [
  {
    slug: "como-eliminar-dc-offset-en-stems",
    title: "Cómo eliminar el DC offset en tus stems automáticamente",
    description:
      "Guía técnica paso a paso para detectar DC offset, recuperar headroom y evitar problemas de compresión y clipping antes de mezclar.",
    excerpt:
      "El DC offset no se oye, pero roba headroom y hace que los compresores reaccionen mal. Aprende a detectarlo y corregirlo de forma segura.",
    publishedAt: "2025-01-10",
    dateLabel: "10 Ene 2025",
    readingTime: "10 min",
    tags: ["DC offset", "Stems", "Headroom", "Preparación técnica"],
    keywords: [
      "dc offset",
      "eliminar dc offset",
      "dc offset stems",
      "correccion dc offset",
      "headroom mezcla",
      "preparacion de stems",
    ],
    toc: [
      { id: "que-es-el-dc-offset", label: "Qué es el DC offset" },
      { id: "por-que-importa", label: "Por qué importa en los stems" },
      { id: "como-detectarlo", label: "Cómo detectarlo rápido" },
      { id: "como-lo-hace-piroola", label: "Cómo lo hace Piroola" },
      { id: "solucion-manual", label: "Solución manual segura" },
      { id: "checklist", label: "Checklist antes de subir stems" },
      { id: "faq", label: "Preguntas frecuentes" },
    ],
  },
  {
    slug: "compresion-bus-bateria-punch-glue",
    title: "La guía definitiva para la compresión de bus de batería",
    description:
      "Cómo conseguir punch y glue sin destruir transientes: cresta, ratio, attack y release, y cuándo aplicar compresión de bus.",
    excerpt:
      "La compresión de bus de batería puede salvar o arruinar tu mezcla. Aquí tienes un método técnico y reproducible.",
    publishedAt: "2025-01-10",
    dateLabel: "10 Ene 2025",
    readingTime: "12 min",
    tags: ["Drum bus", "Compresión", "Dinámica", "Mixbus"],
    keywords: [
      "compresion bus bateria",
      "drum bus compression",
      "glue bateria",
      "crest factor",
      "bus dynamics drums",
    ],
    toc: [
      { id: "por-que-bus", label: "Por qué comprimir el bus de batería" },
      { id: "crest-factor", label: "Crest factor y dinámica útil" },
      { id: "ajustes-base", label: "Ajustes base recomendados" },
      { id: "como-lo-hace-piroola", label: "Cómo lo hace Piroola" },
      { id: "paso-a-paso", label: "Paso a paso manual" },
      { id: "errores-comunes", label: "Errores comunes" },
      { id: "checklist", label: "Checklist rápido" },
    ],
  },
];

export const blogPostSlugs = blogPosts.map((post) => post.slug);

export function getBlogPost(slug: string) {
  return blogPosts.find((post) => post.slug === slug);
}
