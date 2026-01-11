export const blogLocales = [
  "en",
  "es",
  "fr",
  "de",
  "it",
  "pt",
  "ja",
  "zh",
] as const;

export type BlogLocale = (typeof blogLocales)[number];

export const defaultBlogLocale: BlogLocale = "en";

export type BlogPostTocItem = {
  id: string;
  label: string;
};

export type BlogPostTranslation = {
  title: string;
  description: string;
  excerpt: string;
  publishedAtLabel: string;
  readingTime: string;
  tags: string[];
  keywords: string[];
  toc: BlogPostTocItem[];
};

export type BlogPost = {
  slug: string;
  image?: string;
  publishedAt: string;
  translations: Record<BlogLocale, BlogPostTranslation>;
};

export type LocalizedBlogPost = BlogPostTranslation & {
  slug: string;
  image?: string;
  publishedAt: string;
};

const createLocalizedTranslations = (
  base: BlogPostTranslation,
  overrides: Partial<Record<BlogLocale, BlogPostTranslation>> = {},
): Record<BlogLocale, BlogPostTranslation> => {
  return blogLocales.reduce((acc, locale) => {
    acc[locale] = overrides[locale] ?? base;
    return acc;
  }, {} as Record<BlogLocale, BlogPostTranslation>);
};

const IA_PRODUCTION_EN: BlogPostTranslation = {
  title: "AI in Music Production: Ally or Adversary?",
  description:
    "We analyze the latest AI-assisted mastering copilots and how to integrate them into your workflow without losing human oversight.",
  excerpt:
    "AI promises to fix everything with a click. We map the guardrails that keep your mixes sounding intentional rather than auto-generated.",
  publishedAtLabel: "Jan 20, 2025",
  readingTime: "8 min read",
  tags: ["AI", "Production", "Mastering", "Stems"],
  keywords: [
    "AI mastering",
    "automatic mixing",
    "stems workflow",
    "machine learning audio",
    "human oversight",
    "mix prep",
  ],
  toc: [
    { id: "new-tools", label: "New AI mastering copilots" },
    { id: "trust-boundaries", label: "Trust boundaries with automation" },
    { id: "hybrid-workflow", label: "Designing a hybrid workflow" },
    { id: "ready-checklist", label: "Checklist before uploading stems" },
  ],
};

const IA_PRODUCTION_ES: BlogPostTranslation = {
  title: "IA en la Producción Musical: ¿Aliado o Enemigo?",
  description:
    "Analizamos las nuevas herramientas de mastering asistido por IA y cómo integrarlas en tu flujo sin perder el control creativo.",
  excerpt:
    "Estas herramientas prometen solucionar todo al instante. Descubre cuándo confiar y cuándo seguir supervisando manualmente.",
  publishedAtLabel: "20 Ene 2025",
  readingTime: "8 min",
  tags: ["IA", "Producción Musical", "Mastering", "Flujo de trabajo"],
  keywords: [
    "IA en mezcla",
    "mastering asistido",
    "preparación de stems",
    "flujo creativo",
    "control humano",
    "herramientas inteligentes",
  ],
  toc: [
    { id: "nuevas-herramientas", label: "Nuevas herramientas asistidas por IA" },
    { id: "limites-de-confianza", label: "Límites de confianza con la automatización" },
    { id: "flujo-hibrido", label: "Diseñar un flujo híbrido" },
    { id: "checklist", label: "Checklist antes de subir stems" },
  ],
};

const DSP_CALIBRATION_EN: BlogPostTranslation = {
  title: "Acoustic Treatment vs. DSP Calibration: Can Software Fix Your Room?",
  description:
    "We test the leading DSP suites against physical treatment to understand where software can save the day and where it can't compete.",
  excerpt:
    "Before buying foam or repositioning monitors, learn when DSP delivers and when real acoustic panels are still required.",
  publishedAtLabel: "Jan 22, 2025",
  readingTime: "15 min read",
  tags: ["Acoustics", "DSP", "Monitoring", "Studio"],
  keywords: [
    "acoustic treatment",
    "DSP calibration",
    "room correction",
    "monitoring",
    "bass traps",
    "acoustic measurements",
  ],
  toc: [
    { id: "physical-vs-dsp", label: "Physical panels vs. DSP tricks" },
    { id: "dsp-limitations", label: "Where DSP calibration helps" },
    { id: "monitoring-strategies", label: "Real monitoring strategies on a budget" },
    { id: "hybrid-plan", label: "Hybrid correction road map" },
  ],
};

const DSP_CALIBRATION_ES: BlogPostTranslation = {
  title: "Tratamiento Acústico vs. Calibración DSP",
  description:
    "¿Realmente puedes arreglar tu sala con software? Probamos las soluciones líderes del mercado para entender sus límites y garantías.",
  excerpt:
    "A veces la calibración DSP rescata una sala doméstica; otras veces los paneles acústicos siguen siendo la respuesta. Te contamos cómo decidir.",
  publishedAtLabel: "22 Ene 2025",
  readingTime: "15 min",
  tags: ["Acústica", "DSP", "Sala", "Monitoreo"],
  keywords: [
    "tratamiento acústico",
    "calibración dsp",
    "paneles acústicos",
    "trap bass",
    "ecualización de sala",
    "monitoreo crítico",
  ],
  toc: [
    { id: "fisica-vs-dsp", label: "Paneles físicos vs. trucos digitales" },
    { id: "limitaciones-dsp", label: "Dónde la calibración DSP ayuda" },
    { id: "casos-practicos", label: "Casos reales con salas domésticas" },
    { id: "plan-hibrido", label: "Hoja de ruta híbrida" },
  ],
};

export const blogPosts: BlogPost[] = [
  {
    slug: "como-eliminar-dc-offset-en-stems",
    image: "/blog/covers/blog_eliminarDC.png",
    publishedAt: "2025-01-10",
    translations: {
      en: {
        title: "How to remove DC offset from stems automatically",
        description:
          "Technical step-by-step guide to detect DC offset, recover headroom, and avoid compression and clipping issues before mixing.",
        excerpt:
          "DC offset is inaudible, but it steals headroom and makes compressors react the wrong way. Learn how to detect and fix it safely.",
        publishedAtLabel: "Jan 10, 2025",
        readingTime: "10 min read",
        tags: ["DC offset", "Stems", "Headroom", "Technical prep"],
        keywords: [
          "dc offset",
          "remove dc offset",
          "dc offset stems",
          "dc offset correction",
          "mix headroom",
          "stem preparation",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "What is DC offset" },
          { id: "por-que-importa", label: "Why it matters on stems" },
          { id: "como-detectarlo", label: "How to detect it quickly" },
          { id: "como-lo-hace-piroola", label: "How Piroola handles it" },
          { id: "solucion-manual", label: "Safe manual fix" },
          {
            id: "checklist",
            label: "Checklist before uploading stems",
          },
          { id: "faq", label: "FAQs" },
        ],
      },
      es: {
        title: "Cómo eliminar el DC offset en tus stems automáticamente",
        description:
          "Guía técnica paso a paso para detectar DC offset, recuperar headroom y evitar problemas de compresión y clipping antes de mezclar.",
        excerpt:
          "El DC offset no se oye, pero roba headroom y hace que los compresores reaccionen mal. Aprende a detectarlo y corregirlo de forma segura.",
        publishedAtLabel: "10 Ene 2025",
        readingTime: "10 min",
        tags: ["DC offset", "Stems", "Headroom", "Preparación técnica"],
        keywords: [
          "dc offset",
          "eliminar dc offset",
          "dc offset stems",
          "corrección dc offset",
          "headroom mezcla",
          "preparación de stems",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "Qué es el DC offset" },
          { id: "por-que-importa", label: "Por qué importa en los stems" },
          { id: "como-detectarlo", label: "Cómo detectarlo rápido" },
          { id: "como-lo-hace-piroola", label: "Cómo lo hace Piroola" },
          { id: "solucion-manual", label: "Solución manual segura" },
          {
            id: "checklist",
            label: "Checklist antes de subir stems",
          },
          { id: "faq", label: "Preguntas frecuentes" },
        ],
      },
      fr: {
        title: "Comment supprimer le DC offset sur vos stems automatiquement",
        description:
          "Guide technique étape par étape pour détecter le DC offset, récupérer du headroom et éviter les problèmes de compression ou clipping avant le mix.",
        excerpt:
          "Le DC offset est inaudible, mais il réduit le headroom et fausse la réaction des compresseurs. Voici comment le corriger.",
        publishedAtLabel: "10 janv. 2025",
        readingTime: "10 min",
        tags: ["DC offset", "Stems", "Headroom", "Préparation technique"],
        keywords: [
          "dc offset",
          "supprimer dc offset",
          "dc offset stems",
          "correction dc offset",
          "headroom mix",
          "préparation des stems",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "Qu’est-ce que le DC offset" },
          { id: "por-que-importa", label: "Pourquoi c’est important" },
          { id: "como-detectarlo", label: "Comment le détecter" },
          { id: "como-lo-hace-piroola", label: "Comment Piroola le traite" },
          { id: "solucion-manual", label: "Correction manuelle sûre" },
          {
            id: "checklist",
            label: "Checklist avant d’envoyer les stems",
          },
          { id: "faq", label: "FAQ" },
        ],
      },
      de: {
        title: "DC Offset in deinen Stems automatisch entfernen",
        description:
          "Technischer Schritt-für-Schritt-Guide zum Erkennen von DC Offset, mehr Headroom und weniger Kompressions- oder Clipping-Probleme.",
        excerpt:
          "DC Offset ist nicht hörbar, kostet aber Headroom und stört Kompressoren. So findest und entfernst du es sicher.",
        publishedAtLabel: "10. Jan. 2025",
        readingTime: "10 Min.",
        tags: ["DC Offset", "Stems", "Headroom", "Technische Vorbereitung"],
        keywords: [
          "dc offset",
          "dc offset entfernen",
          "dc offset stems",
          "dc offset korrigieren",
          "mix headroom",
          "stem vorbereiten",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "Was ist DC Offset" },
          { id: "por-que-importa", label: "Warum es wichtig ist" },
          { id: "como-detectarlo", label: "So erkennst du es" },
          { id: "como-lo-hace-piroola", label: "So löst es Piroola" },
          { id: "solucion-manual", label: "Sichere manuelle Lösung" },
          {
            id: "checklist",
            label: "Checklist vor dem Upload",
          },
          { id: "faq", label: "FAQ" },
        ],
      },
      it: {
        title: "Come eliminare il DC offset nei tuoi stem automaticamente",
        description:
          "Guida tecnica passo per passo per rilevare il DC offset, recuperare headroom ed evitare problemi di compressione o clipping.",
        excerpt:
          "Il DC offset non si sente, ma ruba headroom e fa reagire male i compressori. Ecco come risolverlo.",
        publishedAtLabel: "10 gen 2025",
        readingTime: "10 min",
        tags: ["DC offset", "Stem", "Headroom", "Preparazione tecnica"],
        keywords: [
          "dc offset",
          "rimuovere dc offset",
          "dc offset stem",
          "correzione dc offset",
          "headroom mix",
          "preparazione stem",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "Cos’è il DC offset" },
          { id: "por-que-importa", label: "Perché è importante" },
          { id: "como-detectarlo", label: "Come rilevarlo" },
          { id: "como-lo-hace-piroola", label: "Come lo gestisce Piroola" },
          { id: "solucion-manual", label: "Correzione manuale sicura" },
          {
            id: "checklist",
            label: "Checklist prima di caricare gli stem",
          },
          { id: "faq", label: "FAQ" },
        ],
      },
      pt: {
        title: "Como remover DC offset nos seus stems automaticamente",
        description:
          "Guia técnico passo a passo para detectar DC offset, recuperar headroom e evitar problemas de compressão e clipping.",
        excerpt:
          "DC offset não é audível, mas rouba headroom e faz compressores reagirem mal. Veja como corrigir.",
        publishedAtLabel: "10 jan 2025",
        readingTime: "10 min",
        tags: ["DC offset", "Stems", "Headroom", "Preparação técnica"],
        keywords: [
          "dc offset",
          "remover dc offset",
          "dc offset stems",
          "correção dc offset",
          "headroom mix",
          "preparação de stems",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "O que é DC offset" },
          { id: "por-que-importa", label: "Por que isso importa" },
          { id: "como-detectarlo", label: "Como detectar rápido" },
          { id: "como-lo-hace-piroola", label: "Como a Piroola faz" },
          { id: "solucion-manual", label: "Correção manual segura" },
          {
            id: "checklist",
            label: "Checklist antes de enviar stems",
          },
          { id: "faq", label: "FAQ" },
        ],
      },
      ja: {
        title: "ステムのDCオフセットを自動で除去する方法",
        description:
          "DCオフセットの検出、ヘッドルームの回復、圧縮やクリッピング問題の回避までを解説する技術ガイド。",
        excerpt:
          "DCオフセットは聴こえませんが、ヘッドルームを奪いコンプレッサーの挙動を乱します。安全な対処法を学びましょう。",
        publishedAtLabel: "2025年1月10日",
        readingTime: "10分",
        tags: ["DCオフセット", "ステム", "ヘッドルーム", "技術準備"],
        keywords: [
          "DCオフセット",
          "DCオフセット除去",
          "ステム DCオフセット",
          "ヘッドルーム",
          "ミックス前処理",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "DCオフセットとは" },
          { id: "por-que-importa", label: "ステムで問題になる理由" },
          { id: "como-detectarlo", label: "素早い検出方法" },
          { id: "como-lo-hace-piroola", label: "Piroolaでの処理" },
          { id: "solucion-manual", label: "安全な手動修正" },
          { id: "checklist", label: "アップロード前チェック" },
          { id: "faq", label: "FAQ" },
        ],
      },
      zh: {
        title: "如何自动去除分轨中的DC偏移",
        description:
          "一步步讲解如何检测DC偏移、恢复余量，并避免混音前的压缩和削波问题。",
        excerpt:
          "DC偏移听不见，但会占用余量并让压缩器反应异常。这里教你如何安全修正。",
        publishedAtLabel: "2025年1月10日",
        readingTime: "10分钟",
        tags: ["DC偏移", "分轨", "余量", "技术准备"],
        keywords: [
          "DC偏移",
          "去除DC偏移",
          "分轨DC偏移",
          "余量",
          "混音前准备",
        ],
        toc: [
          { id: "que-es-el-dc-offset", label: "什么是DC偏移" },
          { id: "por-que-importa", label: "为什么分轨会受影响" },
          { id: "como-detectarlo", label: "如何快速检测" },
          { id: "como-lo-hace-piroola", label: "Piroola的处理方式" },
          { id: "solucion-manual", label: "手动安全修复" },
          { id: "checklist", label: "上传前检查清单" },
          { id: "faq", label: "常见问题" },
        ],
      },
    },
  },
  {
    slug: "compresion-bus-bateria-punch-glue",
    image: "/blog/covers/blog_compresionBus.png",
    publishedAt: "2025-01-10",
    translations: {
      en: {
        title: "The definitive guide to drum bus compression",
        description:
          "How to get punch and glue without killing transients: crest factor, ratio, attack, and release, and when to apply bus compression.",
        excerpt:
          "Drum bus compression can save or ruin your mix. Here is a technical, repeatable method.",
        publishedAtLabel: "Jan 10, 2025",
        readingTime: "12 min read",
        tags: ["Drum bus", "Compression", "Dynamics", "Mixbus"],
        keywords: [
          "drum bus compression",
          "glue drums",
          "crest factor",
          "bus dynamics drums",
          "mixbus compression",
        ],
        toc: [
          { id: "por-que-bus", label: "Why compress the drum bus" },
          { id: "crest-factor", label: "Crest factor and useful dynamics" },
          { id: "ajustes-base", label: "Recommended base settings" },
          { id: "como-lo-hace-piroola", label: "How Piroola does it" },
          { id: "paso-a-paso", label: "Manual step-by-step" },
          { id: "errores-comunes", label: "Common mistakes" },
          { id: "checklist", label: "Quick checklist" },
        ],
      },
      es: {
        title: "La guía definitiva para la compresión de bus de batería",
        description:
          "Cómo conseguir punch y glue sin destruir transientes: cresta, ratio, attack y release, y cuándo aplicar compresión de bus.",
        excerpt:
          "La compresión de bus de batería puede salvar o arruinar tu mezcla. Aquí tienes un método técnico y reproducible.",
        publishedAtLabel: "10 Ene 2025",
        readingTime: "12 min",
        tags: ["Bus de batería", "Compresión", "Dinámica", "Mixbus"],
        keywords: [
          "compresión bus batería",
          "drum bus compression",
          "glue batería",
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
      fr: {
        title: "Le guide ultime de la compression de bus batterie",
        description:
          "Punch et glue sans tuer les transitoires : crest factor, ratio, attack, release et quand compresser le bus.",
        excerpt:
          "La compression de bus batterie peut sauver ou ruiner un mix. Voici une méthode technique et reproductible.",
        publishedAtLabel: "10 janv. 2025",
        readingTime: "12 min",
        tags: ["Bus batterie", "Compression", "Dynamique", "Mixbus"],
        keywords: [
          "compression bus batterie",
          "drum bus compression",
          "glue batterie",
          "crest factor",
          "mixbus compression",
        ],
        toc: [
          { id: "por-que-bus", label: "Pourquoi compresser le bus batterie" },
          { id: "crest-factor", label: "Crest factor et dynamique utile" },
          { id: "ajustes-base", label: "Réglages de base" },
          { id: "como-lo-hace-piroola", label: "Comment Piroola procède" },
          { id: "paso-a-paso", label: "Étapes manuelles" },
          { id: "errores-comunes", label: "Erreurs fréquentes" },
          { id: "checklist", label: "Checklist rapide" },
        ],
      },
      de: {
        title: "Der ultimative Guide zur Drum-Bus-Kompression",
        description:
          "Punch und Glue ohne Transienten zu zerstören: Crest Factor, Ratio, Attack, Release und wann Bus-Kompression sinnvoll ist.",
        excerpt:
          "Drum-Bus-Kompression kann deinen Mix retten oder ruinieren. Hier ist eine reproduzierbare Methode.",
        publishedAtLabel: "10. Jan. 2025",
        readingTime: "12 Min.",
        tags: ["Drum-Bus", "Kompression", "Dynamik", "Mixbus"],
        keywords: [
          "drum bus kompression",
          "glue drums",
          "crest factor",
          "bus dynamics drums",
          "mixbus kompression",
        ],
        toc: [
          { id: "por-que-bus", label: "Warum Drum-Bus-Kompression" },
          { id: "crest-factor", label: "Crest Factor und Dynamik" },
          { id: "ajustes-base", label: "Empfohlene Basiswerte" },
          { id: "como-lo-hace-piroola", label: "So macht es Piroola" },
          { id: "paso-a-paso", label: "Manuelles Vorgehen" },
          { id: "errores-comunes", label: "Häufige Fehler" },
          { id: "checklist", label: "Kurze Checklist" },
        ],
      },
      it: {
        title: "La guida definitiva alla compressione del bus batteria",
        description:
          "Punch e glue senza distruggere i transienti: crest factor, ratio, attack, release e quando usare la compressione di bus.",
        excerpt:
          "La compressione del bus batteria può salvare o rovinare il mix. Ecco un metodo tecnico e ripetibile.",
        publishedAtLabel: "10 gen 2025",
        readingTime: "12 min",
        tags: ["Bus batteria", "Compressione", "Dinamica", "Mixbus"],
        keywords: [
          "compressione bus batteria",
          "drum bus compression",
          "glue batteria",
          "crest factor",
          "mixbus compression",
        ],
        toc: [
          { id: "por-que-bus", label: "Perché comprimere il bus batteria" },
          { id: "crest-factor", label: "Crest factor e dinamica utile" },
          { id: "ajustes-base", label: "Settaggi di base" },
          { id: "como-lo-hace-piroola", label: "Come lo fa Piroola" },
          { id: "paso-a-paso", label: "Passo dopo passo" },
          { id: "errores-comunes", label: "Errori comuni" },
          { id: "checklist", label: "Checklist rapida" },
        ],
      },
      pt: {
        title: "O guia definitivo de compressão no bus de bateria",
        description:
          "Punch e glue sem destruir transientes: crest factor, ratio, attack, release e quando aplicar compressão de bus.",
        excerpt:
          "A compressão no bus de bateria pode salvar ou arruinar a mix. Aqui vai um método técnico e repetível.",
        publishedAtLabel: "10 jan 2025",
        readingTime: "12 min",
        tags: ["Bus de bateria", "Compressão", "Dinâmica", "Mixbus"],
        keywords: [
          "compressão bus bateria",
          "drum bus compression",
          "glue bateria",
          "crest factor",
          "mixbus compression",
        ],
        toc: [
          { id: "por-que-bus", label: "Por que comprimir o bus de bateria" },
          { id: "crest-factor", label: "Crest factor e dinâmica útil" },
          { id: "ajustes-base", label: "Ajustes base" },
          { id: "como-lo-hace-piroola", label: "Como a Piroola faz" },
          { id: "paso-a-paso", label: "Passo a passo manual" },
          { id: "errores-comunes", label: "Erros comuns" },
          { id: "checklist", label: "Checklist rápido" },
        ],
      },
      ja: {
        title: "ドラムバス・コンプレッション完全ガイド",
        description:
          "パンチとグルー感を保ちながらトランジェントを潰さないための基礎設定と判断基準を解説します。",
        excerpt:
          "ドラムバスのコンプレッションはミックスの成否を左右します。再現性のある方法を紹介します。",
        publishedAtLabel: "2025年1月10日",
        readingTime: "12分",
        tags: ["ドラムバス", "コンプレッション", "ダイナミクス", "ミックスバス"],
        keywords: [
          "ドラムバス コンプレッション",
          "glue",
          "crest factor",
          "bus dynamics drums",
          "ミックスバス",
        ],
        toc: [
          { id: "por-que-bus", label: "なぜドラムバスを圧縮するのか" },
          { id: "crest-factor", label: "クレストファクターと動的レンジ" },
          { id: "ajustes-base", label: "おすすめ基本設定" },
          { id: "como-lo-hace-piroola", label: "Piroolaでの処理" },
          { id: "paso-a-paso", label: "手動の手順" },
          { id: "errores-comunes", label: "よくあるミス" },
          { id: "checklist", label: "クイックチェック" },
        ],
      },
      zh: {
        title: "鼓组总线压缩终极指南",
        description:
          "如何在不破坏瞬态的情况下获得 punch 与 glue：crest factor、ratio、attack、release 以及何时压缩。",
        excerpt:
          "鼓组总线压缩可以拯救或毁掉混音。这里是可复现的技术方法。",
        publishedAtLabel: "2025年1月10日",
        readingTime: "12分钟",
        tags: ["鼓组总线", "压缩", "动态", "Mixbus"],
        keywords: [
          "鼓组总线压缩",
          "drum bus compression",
          "glue 鼓组",
          "crest factor",
          "mixbus compression",
        ],
        toc: [
          { id: "por-que-bus", label: "为什么压缩鼓组总线" },
          { id: "crest-factor", label: "Crest factor 与动态" },
          { id: "ajustes-base", label: "推荐基础设置" },
          { id: "como-lo-hace-piroola", label: "Piroola如何处理" },
          { id: "paso-a-paso", label: "手动操作步骤" },
          { id: "errores-comunes", label: "常见错误" },
          { id: "checklist", label: "快速检查清单" },
        ],
      },
    },
  },
  {
    slug: "alineacion-fase-bateria-multimic",
    image: "/blog/covers/blog_alineacionFase.png",
    publishedAt: "2025-01-12",
    translations: {
      en: {
        title: "Phase alignment for multi-mic drums: punch without cancellations",
        description:
          "Detect phase problems, fix polarity, and recover low-end impact on multi-mic drum recordings.",
        excerpt:
          "If your kick loses weight or your snare sounds hollow, phase is usually the reason.",
        publishedAtLabel: "Jan 12, 2025",
        readingTime: "9 min read",
        tags: ["Phase", "Drums", "Multi-mic", "Polarity"],
        keywords: [
          "phase alignment drums",
          "polarity drums",
          "phase cancellation",
          "multi mic drums",
          "drum phase alignment",
        ],
        toc: [
          { id: "sintomas-fase", label: "Symptoms of phase issues" },
          { id: "por-que-se-pierde", label: "Why phase shifts happen" },
          { id: "como-medir", label: "How to measure and align" },
          { id: "como-lo-hace-piroola", label: "How Piroola handles it" },
          { id: "paso-a-paso", label: "Manual workflow" },
          { id: "errores-comunes", label: "Common mistakes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      es: {
        title: "Alineación de fase en baterías multi‑mic: punch sin cancelaciones",
        description:
          "Detecta problemas de fase, corrige polaridad y recupera el low‑end en grabaciones de batería con múltiples micrófonos.",
        excerpt:
          "Si el kick pierde peso o la caja suena hueca, la fase suele ser la causa.",
        publishedAtLabel: "12 Ene 2025",
        readingTime: "9 min",
        tags: ["Fase", "Batería", "Multi-mic", "Polaridad"],
        keywords: [
          "alineación de fase",
          "fase batería",
          "cancelación de fase",
          "batería multi micrófono",
          "polaridad batería",
        ],
        toc: [
          { id: "sintomas-fase", label: "Síntomas de fase" },
          { id: "por-que-se-pierde", label: "Por qué se pierde la fase" },
          { id: "como-medir", label: "Cómo medir y alinear" },
          { id: "como-lo-hace-piroola", label: "Cómo lo hace Piroola" },
          { id: "paso-a-paso", label: "Paso a paso manual" },
          { id: "errores-comunes", label: "Errores comunes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      fr: {
        title: "Alignement de phase en batterie multi‑mic : punch sans annulation",
        description:
          "Détectez les problèmes de phase, corrigez la polarité et récupérez le grave sur des prises batterie multi‑mic.",
        excerpt:
          "Si le kick perd du poids ou la caisse sonne creuse, la phase est souvent la cause.",
        publishedAtLabel: "12 janv. 2025",
        readingTime: "9 min",
        tags: ["Phase", "Batterie", "Multi-mic", "Polarité"],
        keywords: [
          "alignement de phase batterie",
          "polarité batterie",
          "annulation de phase",
          "batterie multi micro",
          "phase drums",
        ],
        toc: [
          { id: "sintomas-fase", label: "Signes de problèmes de phase" },
          { id: "por-que-se-pierde", label: "Pourquoi la phase bouge" },
          { id: "como-medir", label: "Mesurer et aligner" },
          { id: "como-lo-hace-piroola", label: "Méthode Piroola" },
          { id: "paso-a-paso", label: "Workflow manuel" },
          { id: "errores-comunes", label: "Erreurs fréquentes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      de: {
        title: "Phasenabgleich bei Multi‑Mic‑Drums: Punch ohne Auslöschungen",
        description:
          "Phasenprobleme erkennen, Polarität korrigieren und Low‑End‑Impact bei Multi‑Mic‑Drums zurückholen.",
        excerpt:
          "Wenn Kick an Gewicht verliert oder die Snare hohl klingt, ist die Phase oft der Grund.",
        publishedAtLabel: "12. Jan. 2025",
        readingTime: "9 Min.",
        tags: ["Phase", "Drums", "Mehrfachmikro", "Polarität"],
        keywords: [
          "phasenabgleich drums",
          "polarität drums",
          "phasenauslöschung",
          "multi mic drums",
          "drum phase alignment",
        ],
        toc: [
          { id: "sintomas-fase", label: "Symptome von Phasenproblemen" },
          { id: "por-que-se-pierde", label: "Warum Phase verloren geht" },
          { id: "como-medir", label: "Messen und ausrichten" },
          { id: "como-lo-hace-piroola", label: "So macht es Piroola" },
          { id: "paso-a-paso", label: "Manueller Ablauf" },
          { id: "errores-comunes", label: "Häufige Fehler" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      it: {
        title: "Allineamento di fase nelle batterie multi‑mic: punch senza cancellazioni",
        description:
          "Rileva problemi di fase, correggi la polarità e recupera il low‑end nelle registrazioni multi‑mic.",
        excerpt:
          "Se il kick perde peso o lo snare suona vuoto, spesso è colpa della fase.",
        publishedAtLabel: "12 gen 2025",
        readingTime: "9 min",
        tags: ["Fase", "Batteria", "Multi-mic", "Polarità"],
        keywords: [
          "allineamento fase batteria",
          "polarità batteria",
          "cancellazione di fase",
          "batteria multi mic",
          "drum phase alignment",
        ],
        toc: [
          { id: "sintomas-fase", label: "Sintomi di fase" },
          { id: "por-que-se-pierde", label: "Perché si perde la fase" },
          { id: "como-medir", label: "Come misurare e allineare" },
          { id: "como-lo-hace-piroola", label: "Come lo fa Piroola" },
          { id: "paso-a-paso", label: "Workflow manuale" },
          { id: "errores-comunes", label: "Errori comuni" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      pt: {
        title: "Alinhamento de fase em bateria multi‑mic: punch sem cancelamentos",
        description:
          "Detecte problemas de fase, corrija a polaridade e recupere o low‑end em gravações multi‑mic.",
        excerpt:
          "Se o kick perde peso ou a caixa soa oca, a fase costuma ser o motivo.",
        publishedAtLabel: "12 jan 2025",
        readingTime: "9 min",
        tags: ["Fase", "Bateria", "Multi-mic", "Polaridade"],
        keywords: [
          "alinhamento de fase bateria",
          "polaridade bateria",
          "cancelamento de fase",
          "bateria multi mic",
          "drum phase alignment",
        ],
        toc: [
          { id: "sintomas-fase", label: "Sintomas de fase" },
          { id: "por-que-se-pierde", label: "Por que a fase se perde" },
          { id: "como-medir", label: "Como medir e alinhar" },
          { id: "como-lo-hace-piroola", label: "Como a Piroola faz" },
          { id: "paso-a-paso", label: "Workflow manual" },
          { id: "errores-comunes", label: "Erros comuns" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      ja: {
        title: "マルチマイクのドラム位相合わせ：打撃感を失わない方法",
        description:
          "位相問題の検出、極性補正、マルチマイク録音の低域インパクト回復を解説します。",
        excerpt:
          "キックの重さが消える、スネアが薄い…その原因は位相の可能性が高いです。",
        publishedAtLabel: "2025年1月12日",
        readingTime: "9分",
        tags: ["位相", "ドラム", "マルチマイク", "極性"],
        keywords: [
          "ドラム 位相",
          "極性 反転",
          "位相キャンセル",
          "マルチマイク ドラム",
          "位相合わせ",
        ],
        toc: [
          { id: "sintomas-fase", label: "位相問題の症状" },
          { id: "por-que-se-pierde", label: "位相ずれの原因" },
          { id: "como-medir", label: "測定と整列方法" },
          { id: "como-lo-hace-piroola", label: "Piroolaでの処理" },
          { id: "paso-a-paso", label: "手動ワークフロー" },
          { id: "errores-comunes", label: "よくあるミス" },
          { id: "checklist", label: "チェックリスト" },
        ],
      },
      zh: {
        title: "多麦鼓组相位对齐：不牺牲冲击力",
        description:
          "检测相位问题、纠正极性、恢复多麦鼓组的低频冲击力。",
        excerpt:
          "如果踢鼓没了重量或军鼓发空，通常就是相位问题。",
        publishedAtLabel: "2025年1月12日",
        readingTime: "9分钟",
        tags: ["相位", "鼓组", "多麦", "极性"],
        keywords: [
          "鼓组相位对齐",
          "极性反转",
          "相位抵消",
          "多麦鼓组",
          "phase alignment",
        ],
        toc: [
          { id: "sintomas-fase", label: "相位问题的症状" },
          { id: "por-que-se-pierde", label: "相位偏移的原因" },
          { id: "como-medir", label: "如何测量与对齐" },
          { id: "como-lo-hace-piroola", label: "Piroola如何处理" },
          { id: "paso-a-paso", label: "手动流程" },
          { id: "errores-comunes", label: "常见错误" },
          { id: "checklist", label: "检查清单" },
        ],
      },
    },
  },
  {
    slug: "control-resonancias-stems",
    image: "/blog/covers/blog_resonancias.png",
    publishedAt: "2025-01-14",
    translations: {
      en: {
        title: "Resonance control on stems: remove harshness without killing tone",
        description:
          "Find and tame resonant peaks with narrow cuts or dynamic EQ to keep mixes clean and smooth.",
        excerpt:
          "Resonances add harshness and fatigue. Fix them surgically instead of over‑EQing.",
        publishedAtLabel: "Jan 14, 2025",
        readingTime: "11 min read",
        tags: ["Resonances", "EQ", "Stems", "Spectral cleanup"],
        keywords: [
          "resonance control",
          "stem resonance",
          "notch eq",
          "dynamic eq",
          "harsh frequencies",
        ],
        toc: [
          { id: "que-son-resonancias", label: "What resonances are" },
          { id: "por-que-problema", label: "Why they are a problem" },
          { id: "como-detectar", label: "How to detect them" },
          { id: "como-lo-hace-piroola", label: "How Piroola does it" },
          { id: "workflow-manual", label: "Manual workflow" },
          { id: "errores-comunes", label: "Common mistakes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      es: {
        title: "Control de resonancias en stems: limpia sin matar el tono",
        description:
          "Detecta y atenúa picos resonantes con cortes estrechos o EQ dinámica para mantener la mezcla limpia.",
        excerpt:
          "Las resonancias vuelven la mezcla áspera y fatigante. Corrígelas de forma quirúrgica.",
        publishedAtLabel: "14 Ene 2025",
        readingTime: "11 min",
        tags: ["Resonancias", "EQ", "Stems", "Limpieza espectral"],
        keywords: [
          "control de resonancias",
          "resonancias en stems",
          "ecualización notch",
          "eq dinámica",
          "frecuencias ásperas",
        ],
        toc: [
          { id: "que-son-resonancias", label: "Qué son las resonancias" },
          { id: "por-que-problema", label: "Por qué son un problema" },
          { id: "como-detectar", label: "Cómo detectarlas" },
          { id: "como-lo-hace-piroola", label: "Cómo lo hace Piroola" },
          { id: "workflow-manual", label: "Workflow manual" },
          { id: "errores-comunes", label: "Errores comunes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      fr: {
        title: "Contrôle des résonances sur les stems : nettoyer sans tuer le son",
        description:
          "Repérez et atténuez les pics de résonance avec des coupes étroites ou une EQ dynamique.",
        excerpt:
          "Les résonances rendent le mix agressif et fatigant. Corrigez‑les de façon chirurgicale.",
        publishedAtLabel: "14 janv. 2025",
        readingTime: "11 min",
        tags: ["Résonances", "EQ", "Stems", "Nettoyage spectral"],
        keywords: [
          "contrôle des résonances",
          "résonances stems",
          "eq notch",
          "eq dynamique",
          "fréquences agressives",
        ],
        toc: [
          { id: "que-son-resonancias", label: "Que sont les résonances" },
          { id: "por-que-problema", label: "Pourquoi c’est un problème" },
          { id: "como-detectar", label: "Comment les détecter" },
          { id: "como-lo-hace-piroola", label: "Méthode Piroola" },
          { id: "workflow-manual", label: "Workflow manuel" },
          { id: "errores-comunes", label: "Erreurs fréquentes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      de: {
        title: "Resonanzen in Stems kontrollieren: sauber ohne Klangverlust",
        description:
          "Resonanzspitzen finden und mit schmalen Cuts oder dynamischem EQ zähmen.",
        excerpt:
          "Resonanzen machen den Mix hart und ermüdend. Entferne sie chirurgisch statt brutal.",
        publishedAtLabel: "14. Jan. 2025",
        readingTime: "11 Min.",
        tags: ["Resonanzen", "EQ", "Stems", "Spektrale Bereinigung"],
        keywords: [
          "resonanzen kontrollieren",
          "stem resonanzen",
          "notch eq",
          "dynamischer eq",
          "harte frequenzen",
        ],
        toc: [
          { id: "que-son-resonancias", label: "Was Resonanzen sind" },
          { id: "por-que-problema", label: "Warum sie problematisch sind" },
          { id: "como-detectar", label: "So findest du sie" },
          { id: "como-lo-hace-piroola", label: "Piroola‑Methode" },
          { id: "workflow-manual", label: "Manueller Workflow" },
          { id: "errores-comunes", label: "Häufige Fehler" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      it: {
        title: "Controllo delle risonanze negli stem: pulizia senza perdere tono",
        description:
          "Individua e attenua i picchi di risonanza con tagli stretti o EQ dinamica.",
        excerpt:
          "Le risonanze rendono il mix aspro e affaticante. Correggile in modo chirurgico.",
        publishedAtLabel: "14 gen 2025",
        readingTime: "11 min",
        tags: ["Risonanze", "EQ", "Stem", "Pulizia spettrale"],
        keywords: [
          "controllo risonanze",
          "risonanze stem",
          "eq notch",
          "eq dinamica",
          "frequenze aspre",
        ],
        toc: [
          { id: "que-son-resonancias", label: "Cosa sono le risonanze" },
          { id: "por-que-problema", label: "Perché sono un problema" },
          { id: "como-detectar", label: "Come individuarle" },
          { id: "como-lo-hace-piroola", label: "Come lo fa Piroola" },
          { id: "workflow-manual", label: "Workflow manuale" },
          { id: "errores-comunes", label: "Errori comuni" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      pt: {
        title: "Controle de ressonâncias em stems: limpe sem matar o timbre",
        description:
          "Encontre e atenue picos de ressonância com cortes estreitos ou EQ dinâmica.",
        excerpt:
          "Ressonâncias deixam o mix áspero e cansativo. Corrija de forma cirúrgica.",
        publishedAtLabel: "14 jan 2025",
        readingTime: "11 min",
        tags: ["Ressonâncias", "EQ", "Stems", "Limpeza espectral"],
        keywords: [
          "controle de ressonâncias",
          "ressonâncias em stems",
          "eq notch",
          "eq dinâmica",
          "frequências ásperas",
        ],
        toc: [
          { id: "que-son-resonancias", label: "O que são ressonâncias" },
          { id: "por-que-problema", label: "Por que é um problema" },
          { id: "como-detectar", label: "Como detectar" },
          { id: "como-lo-hace-piroola", label: "Como a Piroola faz" },
          { id: "workflow-manual", label: "Workflow manual" },
          { id: "errores-comunes", label: "Erros comuns" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      ja: {
        title: "ステムの共振コントロール：音色を殺さずに整える",
        description:
          "狭いカットやダイナミックEQで共振ピークを抑え、ミックスを滑らかに保つ方法。",
        excerpt:
          "共振はミックスを耳疲れさせます。過度なEQではなく外科的に処理しましょう。",
        publishedAtLabel: "2025年1月14日",
        readingTime: "11分",
        tags: ["共振", "EQ", "ステム", "スペクトル整理"],
        keywords: [
          "共振 コントロール",
          "ステム 共振",
          "ノッチEQ",
          "ダイナミックEQ",
          "耳疲れ",
        ],
        toc: [
          { id: "que-son-resonancias", label: "共振とは" },
          { id: "por-que-problema", label: "問題になる理由" },
          { id: "como-detectar", label: "検出方法" },
          { id: "como-lo-hace-piroola", label: "Piroolaでの処理" },
          { id: "workflow-manual", label: "手動ワークフロー" },
          { id: "errores-comunes", label: "よくあるミス" },
          { id: "checklist", label: "チェックリスト" },
        ],
      },
      zh: {
        title: "分轨共振控制：清理刺耳而不伤音色",
        description:
          "通过窄带削减或动态EQ压制共振峰，保持混音干净顺滑。",
        excerpt:
          "共振会让混音刺耳、疲劳。用外科式处理而不是过度EQ。",
        publishedAtLabel: "2025年1月14日",
        readingTime: "11分钟",
        tags: ["共振", "EQ", "分轨", "频谱清理"],
        keywords: [
          "共振控制",
          "分轨共振",
          "陷波EQ",
          "动态EQ",
          "刺耳频段",
        ],
        toc: [
          { id: "que-son-resonancias", label: "什么是共振" },
          { id: "por-que-problema", label: "为什么是问题" },
          { id: "como-detectar", label: "如何检测" },
          { id: "como-lo-hace-piroola", label: "Piroola如何处理" },
          { id: "workflow-manual", label: "手动流程" },
          { id: "errores-comunes", label: "常见错误" },
          { id: "checklist", label: "检查清单" },
        ],
      },
    },
  },
  {
    slug: "lufs-true-peak-loudness",
    image: "/blog/covers/mastering.webp",
    publishedAt: "2025-01-16",
    translations: {
      en: {
        title: "LUFS and true peak: reach loudness without destroying dynamics",
        description:
          "Streaming targets, true peak safety, and a clean way to hit loudness without pumping or distortion.",
        excerpt:
          "Getting loud is easy. Getting loud and clean takes method.",
        publishedAtLabel: "Jan 16, 2025",
        readingTime: "10 min read",
        tags: ["LUFS", "True peak", "Mastering", "Loudness"],
        keywords: [
          "lufs",
          "true peak",
          "streaming loudness",
          "loudness targets",
          "mastering limiter",
        ],
        toc: [
          { id: "que-son-lufs", label: "What LUFS actually means" },
          { id: "targets-streaming", label: "Streaming targets" },
          { id: "true-peak", label: "True peak and intersample peaks" },
          { id: "como-lo-hace-piroola", label: "How Piroola handles it" },
          { id: "paso-a-paso", label: "Manual step-by-step" },
          { id: "errores-comunes", label: "Common mistakes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      es: {
        title: "LUFS y true peak: loudness sin destruir la dinámica",
        description:
          "Objetivos de streaming, seguridad de true peak y un método limpio para llegar al loudness sin bombeo ni distorsión.",
        excerpt:
          "Subir volumen es fácil. Hacerlo limpio y controlado requiere método.",
        publishedAtLabel: "16 Ene 2025",
        readingTime: "10 min",
        tags: ["LUFS", "True peak", "Mastering", "Loudness"],
        keywords: [
          "lufs",
          "true peak",
          "loudness streaming",
          "objetivos lufs",
          "limitador mastering",
        ],
        toc: [
          { id: "que-son-lufs", label: "Qué son los LUFS" },
          { id: "targets-streaming", label: "Targets de streaming" },
          { id: "true-peak", label: "True peak e intersample peaks" },
          { id: "como-lo-hace-piroola", label: "Cómo lo hace Piroola" },
          { id: "paso-a-paso", label: "Paso a paso manual" },
          { id: "errores-comunes", label: "Errores comunes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      fr: {
        title: "LUFS et true peak : atteindre le loudness sans détruire la dynamique",
        description:
          "Targets streaming, true peak safety et méthode propre pour atteindre le loudness sans pompage.",
        excerpt:
          "Monter le volume est facile. Le faire proprement demande une méthode.",
        publishedAtLabel: "16 janv. 2025",
        readingTime: "10 min",
        tags: ["LUFS", "True peak", "Mastering", "Loudness"],
        keywords: [
          "lufs",
          "true peak",
          "loudness streaming",
          "targets loudness",
          "limiteur mastering",
        ],
        toc: [
          { id: "que-son-lufs", label: "Que signifie LUFS" },
          { id: "targets-streaming", label: "Targets streaming" },
          { id: "true-peak", label: "True peak et intersample" },
          { id: "como-lo-hace-piroola", label: "Comment Piroola procède" },
          { id: "paso-a-paso", label: "Étapes manuelles" },
          { id: "errores-comunes", label: "Erreurs fréquentes" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      de: {
        title: "LUFS und True Peak: Lautheit ohne zerstörte Dynamik",
        description:
          "Streaming‑Ziele, True‑Peak‑Sicherheit und ein sauberer Weg zu mehr Loudness ohne Pumpen.",
        excerpt:
          "Laut machen ist leicht. Sauber laut machen braucht Methode.",
        publishedAtLabel: "16. Jan. 2025",
        readingTime: "10 Min.",
        tags: ["LUFS", "True Peak", "Mastering", "Loudness"],
        keywords: [
          "lufs",
          "true peak",
          "streaming loudness",
          "loudness ziele",
          "mastering limiter",
        ],
        toc: [
          { id: "que-son-lufs", label: "Was LUFS bedeutet" },
          { id: "targets-streaming", label: "Streaming‑Ziele" },
          { id: "true-peak", label: "True Peak und Intersample" },
          { id: "como-lo-hace-piroola", label: "Piroola‑Ansatz" },
          { id: "paso-a-paso", label: "Manueller Ablauf" },
          { id: "errores-comunes", label: "Häufige Fehler" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      it: {
        title: "LUFS e true peak: loudness senza distruggere la dinamica",
        description:
          "Target streaming, sicurezza true peak e un metodo pulito per arrivare al loudness senza pumping.",
        excerpt:
          "Fare volume è facile. Farlo in modo pulito richiede metodo.",
        publishedAtLabel: "16 gen 2025",
        readingTime: "10 min",
        tags: ["LUFS", "True peak", "Mastering", "Loudness"],
        keywords: [
          "lufs",
          "true peak",
          "loudness streaming",
          "target loudness",
          "limiter mastering",
        ],
        toc: [
          { id: "que-son-lufs", label: "Cosa significa LUFS" },
          { id: "targets-streaming", label: "Target streaming" },
          { id: "true-peak", label: "True peak e intersample" },
          { id: "como-lo-hace-piroola", label: "Come lo fa Piroola" },
          { id: "paso-a-paso", label: "Passo a passo" },
          { id: "errores-comunes", label: "Errori comuni" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      pt: {
        title: "LUFS e true peak: loudness sem destruir a dinâmica",
        description:
          "Targets de streaming, segurança de true peak e um método limpo para atingir loudness sem pumping.",
        excerpt:
          "Ficar alto é fácil. Ficar alto e limpo exige método.",
        publishedAtLabel: "16 jan 2025",
        readingTime: "10 min",
        tags: ["LUFS", "True peak", "Mastering", "Loudness"],
        keywords: [
          "lufs",
          "true peak",
          "loudness streaming",
          "targets loudness",
          "limiter mastering",
        ],
        toc: [
          { id: "que-son-lufs", label: "O que significa LUFS" },
          { id: "targets-streaming", label: "Targets de streaming" },
          { id: "true-peak", label: "True peak e intersample" },
          { id: "como-lo-hace-piroola", label: "Como a Piroola faz" },
          { id: "paso-a-paso", label: "Passo a passo" },
          { id: "errores-comunes", label: "Erros comuns" },
          { id: "checklist", label: "Checklist" },
        ],
      },
      ja: {
        title: "LUFSとTrue Peak：ダイナミクスを壊さずにラウド化する",
        description:
          "配信の目標値、True Peakの安全域、ポンピングなしでラウド化する方法を解説。",
        excerpt:
          "音量を上げるのは簡単。きれいに上げるのは難しい。",
        publishedAtLabel: "2025年1月16日",
        readingTime: "10分",
        tags: ["LUFS", "True Peak", "マスタリング", "ラウドネス"],
        keywords: [
          "LUFS",
          "True Peak",
          "ラウドネス 目標",
          "配信 ラウドネス",
          "マスタリング リミッター",
        ],
        toc: [
          { id: "que-son-lufs", label: "LUFSとは" },
          { id: "targets-streaming", label: "配信の目標値" },
          { id: "true-peak", label: "True Peakとインターサンプル" },
          { id: "como-lo-hace-piroola", label: "Piroolaでの処理" },
          { id: "paso-a-paso", label: "手動手順" },
          { id: "errores-comunes", label: "よくあるミス" },
          { id: "checklist", label: "チェックリスト" },
        ],
      },
      zh: {
        title: "LUFS 与 True Peak：不破坏动态的响度目标",
        description:
          "流媒体目标、True Peak 安全值，以及无泵音的响度提升方法。",
        excerpt:
          "变大声很容易，干净而有控制地变大声才需要方法。",
        publishedAtLabel: "2025年1月16日",
        readingTime: "10分钟",
        tags: ["LUFS", "True Peak", "母带", "响度"],
        keywords: [
          "LUFS",
          "True Peak",
          "流媒体响度",
          "响度目标",
          "母带限制器",
        ],
        toc: [
          { id: "que-son-lufs", label: "什么是LUFS" },
          { id: "targets-streaming", label: "流媒体目标" },
          { id: "true-peak", label: "True Peak与插值峰值" },
          { id: "como-lo-hace-piroola", label: "Piroola如何处理" },
          { id: "paso-a-paso", label: "手动步骤" },
          { id: "errores-comunes", label: "常见错误" },
          { id: "checklist", label: "检查清单" },
        ],
      },
    },
  },
  {
    slug: "ia-en-produccion-musical-aliado-enemigo",
    image: "/blog/covers/blog_ia.png",
    publishedAt: "2025-01-20",
    translations: {
      en: {
        title: "AI in Music Production: Friend or Foe?",
        description:
          "Analyzing the emerging batch of AI-assisted mastering and how to decide whether they become a creative ally or a runaway compressor.",
        excerpt:
          "As machine listening matures, production teams need to understand where to let AI automate and when to keep the human ear in charge.",
        publishedAtLabel: "Jan 20, 2025",
        readingTime: "9 min read",
        tags: ["AI", "Music production", "Mastering"],
        keywords: [
          "ai mastering",
          "ai music production",
          "creative workflow ai",
          "ai assisted mastering",
          "automated mixing tools",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "The AI echo chamber today" },
          { id: "freedoms-and-limitations", label: "What freedom the AI tools really give you" },
          { id: "matching-vision-to-output", label: "Matching production intent to AI output" },
          { id: "quality-control-checklist", label: "Quality control checklist" },
          { id: "keeping-human-tone", label: "Keeping the human tonal compass" },
          { id: "workflow-sprint", label: "Workflow sprint with AI" },
          { id: "glimpses-future", label: "What we expect next" },
        ],
      },
      es: {
        title: "IA en la Producción Musical: ¿Aliado o Enemigo?",
        description:
          "Analizamos las nuevas herramientas de mastering asistidas por IA y cómo integrarlas para que sumen sin reemplazar al ingeniero.",
        excerpt:
          "La escucha automática evoluciona rápido; aquí te ayudamos a decidir qué dejar en manos de la IA y qué debe seguir siendo humano.",
        publishedAtLabel: "20 Ene 2025",
        readingTime: "9 min",
        tags: ["IA", "Producción", "Mastering"],
        keywords: [
          "mastering ai",
          "producción musical ai",
          "flujo creativo ai",
          "mastering asistido",
          "automatización mix",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "El ecosistema de IA hoy" },
          { id: "freedoms-and-limitations", label: "Qué libertades reales ofrece la IA" },
          { id: "matching-vision-to-output", label: "Alineando intención y resultado" },
          { id: "quality-control-checklist", label: "Checklist de control de calidad" },
          { id: "keeping-human-tone", label: "Manteniendo el tono humano" },
          { id: "workflow-sprint", label: "Sprint de flujo con IA" },
          { id: "glimpses-future", label: "Qué viene después" },
        ],
      },
      fr: {
        title: "L’IA en production musicale : alliée ou ennemie ?",
        description:
          "Nous décortiquons les dernières fonctions de mastering assisté par IA pour garder le contrôle créatif sans perdre en efficacité.",
        excerpt:
          "Quand l’écoute machine s’améliore, il faut savoir quand lui confier des tâches et quand garder l’oreille humaine.",
        publishedAtLabel: "20 janv. 2025",
        readingTime: "9 min",
        tags: ["IA", "Production musicale", "Mastering"],
        keywords: [
          "mastering ai",
          "production musicale ai",
          "workflow créatif ai",
          "mastering assisté",
          "outils de mix automatisés",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "L’écosystème IA actuel" },
          { id: "freedoms-and-limitations", label: "Les vraies libertés de l’IA" },
          { id: "matching-vision-to-output", label: "Aligner intention et rendu" },
          { id: "quality-control-checklist", label: "Checklist qualité" },
          { id: "keeping-human-tone", label: "Conserver l’oreille humaine" },
          { id: "workflow-sprint", label: "Sprint de workflow IA" },
          { id: "glimpses-future", label: "Ce qui arrive" },
        ],
      },
      de: {
        title: "KI in der Musikproduktion: Verbündeter oder Feind?",
        description:
          "Wir analysieren die neuesten KI-gestützten Mastering-Tools und zeigen, wann sie kreative Hilfe leisten dürfen.",
        excerpt:
          "Maschinelles Hören wird besser – es gilt zu entscheiden, wann wir es einsetzen und wann der Mensch das letzte Wort behält.",
        publishedAtLabel: "20. Jan. 2025",
        readingTime: "9 Min.",
        tags: ["KI", "Musikproduktion", "Mastering"],
        keywords: [
          "ki mastering",
          "musikproduktion ai",
          "kreativer workflow ai",
          "assistiertes mastering",
          "automatisierte mix tools",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "Das KI-Ökosystem heute" },
          { id: "freedoms-and-limitations", label: "Was KI wirklich erlaubt" },
          { id: "matching-vision-to-output", label: "Intention mit Ergebnis abgleichen" },
          { id: "quality-control-checklist", label: "Qualitätscheckliste" },
          { id: "keeping-human-tone", label: "Das menschliche Ohr behalten" },
          { id: "workflow-sprint", label: "Workflow-Sprint mit KI" },
          { id: "glimpses-future", label: "Blick in die Zukunft" },
        ],
      },
      it: {
        title: "IA nella produzione musicale: alleata o nemica?",
        description:
          "Scomponiamo le novità nel mastering assistito da IA per usarle senza perdere controllo creativo.",
        excerpt:
          "L’ascolto automatico migliora: è ora di decidere quando affidarsi alla macchina e quando mantenere l’orecchio umano.",
        publishedAtLabel: "20 gen 2025",
        readingTime: "9 min",
        tags: ["IA", "Produzione", "Mastering"],
        keywords: [
          "mastering ai",
          "produzione musicale ai",
          "workflow creativo ai",
          "mastering assistito",
          "strumenti mix automatizzati",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "Il panorama IA oggi" },
          { id: "freedoms-and-limitations", label: "Cosa permette davvero l’IA" },
          { id: "matching-vision-to-output", label: "Allineare intenzione e resa" },
          { id: "quality-control-checklist", label: "Checklist qualità" },
          { id: "keeping-human-tone", label: "Mantenere l’orecchio umano" },
          { id: "workflow-sprint", label: "Sprint di workflow con IA" },
          { id: "glimpses-future", label: "Cosa viene dopo" },
        ],
      },
      pt: {
        title: "IA na produção musical: aliada ou inimiga?",
        description:
          "Analisamos as últimas funções de masterização assistida por IA para manter o controle artístico acompanhado da eficiência.",
        excerpt:
          "A escuta automática evolui rápido – descubra o que deixar com a IA e o que manter sob supervisão humana.",
        publishedAtLabel: "20 jan 2025",
        readingTime: "9 min",
        tags: ["IA", "Produção musical", "Mastering"],
        keywords: [
          "mastering ai",
          "produção musical ai",
          "workflow criativo ai",
          "mastering assistido",
          "ferramentas de mix automatizadas",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "O ecossistema de IA hoje" },
          { id: "freedoms-and-limitations", label: "O que a IA realmente deixa fazer" },
          { id: "matching-vision-to-output", label: "Alinhar intenção com resultado" },
          { id: "quality-control-checklist", label: "Checklist de qualidade" },
          { id: "keeping-human-tone", label: "Manter o ouvido humano" },
          { id: "workflow-sprint", label: "Sprint de workflow com IA" },
          { id: "glimpses-future", label: "O que vem por aí" },
        ],
      },
      ja: {
        title: "音楽制作におけるAI：味方か敵か？",
        description:
          "AI支援マスタリングの新機能を紐解き、創造的コントロールを保ちながら生産性を得る方法を探ります。",
        excerpt:
          "機械的なリスニングが進化すると、どこまで任せるか、人間の耳をいつ残すかの判断が重要になります。",
        publishedAtLabel: "2025年1月20日",
        readingTime: "9分",
        tags: ["AI", "音楽制作", "マスタリング"],
        keywords: [
          "ai マスタリング",
          "音楽制作 ai",
          "クリエイティブワークフロー ai",
          "ai支援マスタリング",
          "自動ミックスツール",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "最新のAIエコシステム" },
          { id: "freedoms-and-limitations", label: "AIが本当に与える自由" },
          { id: "matching-vision-to-output", label: "意図と出力を揃える" },
          { id: "quality-control-checklist", label: "品質チェックリスト" },
          { id: "keeping-human-tone", label: "人間の耳を残す" },
          { id: "workflow-sprint", label: "AIとのワークフロースプリント" },
          { id: "glimpses-future", label: "これからの展望" },
        ],
      },
      zh: {
        title: "音乐制作中的 AI：盟友还是敌人？",
        description:
          "解读最新 AI 辅助母带功能，在保持创作掌控的同时提高效率的实践建议。",
        excerpt:
          "机器听觉不断进化，现在是时候界定哪些任务交给 AI，哪些需要人耳终审。",
        publishedAtLabel: "2025年1月20日",
        readingTime: "9分钟",
        tags: ["AI", "音乐制作", "母带"],
        keywords: [
          "ai 母带",
          "音乐制作 ai",
          "创意流程 ai",
          "ai 辅助母带",
          "自动混音工具",
        ],
        toc: [
          { id: "today-s-ia-echoes", label: "当前的 AI 生态" },
          { id: "freedoms-and-limitations", label: "AI 实际赋予的自由" },
          { id: "matching-vision-to-output", label: "对齐创作意图与输出" },
          { id: "quality-control-checklist", label: "质量检查表" },
          { id: "keeping-human-tone", label: "保留人类听觉" },
          { id: "workflow-sprint", label: "与 AI 的工作流加速" },
          { id: "glimpses-future", label: "未来展望" },
        ],
      },
    },
  },
  {
    slug: "tratamiento-acustico-vs-calibracion-dsp",
    image: "/blog/covers/blog_dsp.png",
    publishedAt: "2025-01-22",
    translations: {
      en: {
        title: "Acoustic Treatment vs. DSP Calibration",
        description:
          "Testing whether software EQ, convolution, and room correction can replace physical traps — and where real acoustics still win.",
        excerpt:
          "We compare in-room absorption, bass trapping, and measurements against the latest calibration suites to understand the trade-offs.",
        publishedAtLabel: "Jan 22, 2025",
        readingTime: "15 min read",
        tags: ["Acoustics", "DSP", "Studios"],
        keywords: [
          "acoustic treatment",
          "dsp calibration",
          "room treatment vs dsp",
          "calibrating studio room",
          "room correction software",
        ],
        toc: [
          { id: "physical-vs-digital", label: "Physical control vs. digital correction" },
          { id: "what-dsp-tools-make", label: "What today's DSP tools actually do" },
          { id: "room-measurements", label: "Room measurement methodology" },
          { id: "treatment-checkpoints", label: "Treatment checkpoints and budget" },
          { id: "hybrid-recipe", label: "A hybrid recipe for mixing rooms" },
          { id: "when-to-rent", label: "When to rent a treated room" },
        ],
      },
      es: {
        title: "Tratamiento Acústico vs. Calibración DSP",
        description:
          "Comparamos si el EQ de software y la corrección con convolución pueden reemplazar trampas y paneles físicos.",
        excerpt:
          "Contraste entre absorción en sala, trampas de graves y las últimas suites de calibración para entender las compensaciones.",
        publishedAtLabel: "22 Ene 2025",
        readingTime: "15 min",
        tags: ["Acústica", "Sala", "DSP"],
        keywords: [
          "tratamiento acústico",
          "calibración dsp",
          "sala tratada vs dsp",
          "calibrar sala",
          "software de corrección de sala",
        ],
        toc: [
          { id: "physical-vs-digital", label: "Físico vs digital" },
          { id: "what-dsp-tools-make", label: "Qué hacen hoy las herramientas DSP" },
          { id: "room-measurements", label: "Metodología de medición" },
          { id: "treatment-checkpoints", label: "Puntos clave de tratamiento" },
          { id: "hybrid-recipe", label: "Receta híbrida para salas" },
          { id: "when-to-rent", label: "Cuándo alquilar una sala tratada" },
        ],
      },
      fr: {
        title: "Traitement acoustique vs calibration DSP",
        description:
          "Nous testons si l’équalisation logicielle et la convolution peuvent remplacer les panneaux physiques.",
        excerpt:
          "Comparatif entre absorption réelle, piégeage des basses et suites de calibration modernes pour apprécier les compromis.",
        publishedAtLabel: "22 janv. 2025",
        readingTime: "15 min",
        tags: ["Acoustique", "DSP", "Studios"],
        keywords: [
          "traitement acoustique",
          "calibration dsp",
          "salle traitée vs dsp",
          "calibrer une salle",
          "correction de pièce logicielle",
        ],
        toc: [
          { id: "physical-vs-digital", label: "Contrôle physique vs correction digitale" },
          { id: "what-dsp-tools-make", label: "Ce que font vraiment les outils DSP" },
          { id: "room-measurements", label: "Méthodologie de mesure" },
          { id: "treatment-checkpoints", label: "Points de traitement" },
          { id: "hybrid-recipe", label: "Recette hybride" },
          { id: "when-to-rent", label: "Quand louer une salle traitée" },
        ],
      },
      de: {
        title: "Akustikbehandlung vs. DSP-Kalibrierung",
        description:
          "Wir testen, ob Software-EQ und Raumkorrektur Hardware-Panels ersetzen können und wo echte Akustik punktet.",
        excerpt:
          "Vergleich von Absorption, Bassfallen und Kalibrierungssuites, um die richtigen Kompromisse zu verstehen.",
        publishedAtLabel: "22. Jan. 2025",
        readingTime: "15 Min.",
        tags: ["Akustik", "DSP", "Studios"],
        keywords: [
          "akustikbehandlung",
          "dsp kalibrierung",
          "raum akustik vs dsp",
          "studio kalibrierung",
          "raumnormierung software",
        ],
        toc: [
          { id: "physical-vs-digital", label: "Physisch vs digital" },
          { id: "what-dsp-tools-make", label: "Was DSP-Tools tatsächlich tun" },
          { id: "room-measurements", label: "Raum-Messmethodik" },
          { id: "treatment-checkpoints", label: "Behandlungs-Checkpoints" },
          { id: "hybrid-recipe", label: "Hybrides Rezept" },
          { id: "when-to-rent", label: "Wann man behandelte Räume mieten sollte" },
        ],
      },
      it: {
        title: "Trattamento acustico vs calibrazione DSP",
        description:
          "Valutiamo se l’EQ software e la correzione possono sostituire pannelli e pannelli bass trap fisici.",
        excerpt:
          "Mettiamo a confronto assorbimento reale, trap per bassi e suite di calibrazione per capire i compromessi.",
        publishedAtLabel: "22 gen 2025",
        readingTime: "15 min",
        tags: ["Acustica", "Sala", "DSP"],
        keywords: [
          "trattamento acustico",
          "calibrazione dsp",
          "sala trattata vs dsp",
          "calibrare sala",
          "correzione stanza software",
        ],
        toc: [
          { id: "physical-vs-digital", label: "Fisico vs digitale" },
          { id: "what-dsp-tools-make", label: "Cosa fanno veramente gli strumenti DSP" },
          { id: "room-measurements", label: "Metodologia di misurazione" },
          { id: "treatment-checkpoints", label: "Checkpoint di trattamento" },
          { id: "hybrid-recipe", label: "Ricetta ibrida" },
          { id: "when-to-rent", label: "Quando affittare una sala trattata" },
        ],
      },
      pt: {
        title: "Tratamento acústico vs calibração DSP",
        description:
          "Testamos se equalização e convolução podem substituir fofos físicos e quando a acústica real ainda manda.",
        excerpt:
          "Comparamos absorção na sala, armadilhas de graves e as últimas suítes de calibração para entender trocas.",
        publishedAtLabel: "22 jan 2025",
        readingTime: "15 min",
        tags: ["Acústica", "Sala", "DSP"],
        keywords: [
          "tratamento acústico",
          "calibração dsp",
          "sala tratada vs dsp",
          "calibrar sala",
          "correção de sala software",
        ],
        toc: [
          { id: "physical-vs-digital", label: "Físico vs digital" },
          { id: "what-dsp-tools-make", label: "O que os DSPs fazem" },
          { id: "room-measurements", label: "Método de medição" },
          { id: "treatment-checkpoints", label: "Pontos de tratamento" },
          { id: "hybrid-recipe", label: "Receita híbrida" },
          { id: "when-to-rent", label: "Quando alugar uma sala tratada" },
        ],
      },
      ja: {
        title: "アコースティック処理 vs DSP校正",
        description:
          "EQやルーム補正ソフトが物理的な吸音と置き換えられるか、どこで本物のアコースティックが勝つかを検証します。",
        excerpt:
          "吸音とベーストラップ、最新キャリブレーションツールを比較して妥協点を探ります。",
        publishedAtLabel: "2025年1月22日",
        readingTime: "15分",
        tags: ["アコースティック", "DSP", "スタジオ"],
        keywords: [
          "アコースティック処理",
          "DSP 校正",
          "ルーム処理 vs dsp",
          "スタジオ キャリブレーション",
          "ルームコレクション ソフト",
        ],
        toc: [
          { id: "physical-vs-digital", label: "物理 vs デジタル" },
          { id: "what-dsp-tools-make", label: "DSPが実際に行うこと" },
          { id: "room-measurements", label: "ルーム計測" },
          { id: "treatment-checkpoints", label: "処理チェック" },
          { id: "hybrid-recipe", label: "ハイブリッドレシピ" },
          { id: "when-to-rent", label: "処理済みルームを借りるタイミング" },
        ],
      },
      zh: {
        title: "声学处理 vs DSP 校准",
        description:
          "我们检验软件 EQ 能否替代物理吸音、什么时候真正的声学安排才是胜出者。",
        excerpt:
          "比较吸收、低频陷阱与最新校准套件，厘清哪种策略适合混音室。",
        publishedAtLabel: "2025年1月22日",
        readingTime: "15分钟",
        tags: ["声学", "DSP", "工作室"],
        keywords: [
          "声学处理",
          "DSP 校准",
          "处理 vs dsp",
          "校准工作室",
          "房间校正软件",
        ],
        toc: [
          { id: "physical-vs-digital", label: "实体 vs 数字" },
          { id: "what-dsp-tools-make", label: "DSP 工具能做什么" },
          { id: "room-measurements", label: "房间测量方法" },
          { id: "treatment-checkpoints", label: "处理检查点" },
          { id: "hybrid-recipe", label: "混合方案" },
          { id: "when-to-rent", label: "何时租用处理房" },
        ],
      },
    },
  },
{
slug: "stems-vs-stereo-mezcla",
image: "/blog/covers/stems_vs_stereo.webp",
publishedAt: "2025-01-25",
translations: {
  en: {
    title: "Stems vs. Stereo: Why Stem Mixing Changes the Game",
    description: "Discover why separating your tracks into stems gives you more control, better clarity, and superior mastering results.",
    excerpt: "Stereo mastering is good, but stem mastering is transformative. Learn how grouping your tracks unlocks a new level of polish.",
    publishedAtLabel: "Jan 25, 2025",
    readingTime: "7 min read",
    tags: ["Stems", "Mixing", "Mastering", "Workflow"],
    keywords: ["stem mastering", "stems vs stereo", "mixing stems", "audio separation", "mastering control"],
    toc: [
      { id: "intro", label: "Introduction" },
      { id: "what-are-stems", label: "What are Stems?" },
      { id: "benefits-of-stems", label: "Benefits of Stem Mixing" },
      { id: "common-stem-groups", label: "Common Stem Groups" },
      { id: "preparing-stems", label: "Preparing Your Stems" },
    ],
  },
  es: {
    title: "Stems vs. Stereo: Por qué mezclar por grupos cambia el juego",
    description: "Descubre por qué separar tus pistas en stems te da más control, mejor claridad y resultados de mastering superiores.",
    excerpt: "El mastering estéreo es bueno, pero el mastering por stems es transformador. Aprende cómo agrupar tus pistas desbloquea un nuevo nivel de pulido.",
    publishedAtLabel: "25 Ene 2025",
    readingTime: "7 min",
    tags: ["Stems", "Mezcla", "Mastering", "Flujo de trabajo"],
    keywords: ["mastering por stems", "stems vs stereo", "mezcla de stems", "separación de audio", "control de mastering"],
    toc: [
      { id: "intro", label: "Introducción" },
      { id: "what-are-stems", label: "¿Qué son los Stems?" },
      { id: "benefits-of-stems", label: "Beneficios de la Mezcla por Stems" },
      { id: "common-stem-groups", label: "Grupos de Stems Comunes" },
      { id: "preparing-stems", label: "Preparando tus Stems" },
    ],
  },
  fr: {
    title: "Stems vs. Stereo: Pourquoi le mixage par stems change la donne",
    description: "Découvrez pourquoi séparer vos pistes en stems vous donne plus de contrôle, une meilleure clarté et des résultats de mastering supérieurs.",
    excerpt: "Le mastering stéréo est bien, mais le mastering par stems est transformateur. Apprenez comment grouper vos pistes débloque un nouveau niveau de finition.",
    publishedAtLabel: "25 janv. 2025",
    readingTime: "7 min",
    tags: ["Stems", "Mixage", "Mastering", "Workflow"],
    keywords: ["mastering par stems", "stems vs stereo", "mixage de stems", "séparation audio", "contrôle de mastering"],
    toc: [
      { id: "intro", label: "Introduction" },
      { id: "what-are-stems", label: "Que sont les Stems ?" },
      { id: "benefits-of-stems", label: "Avantages du Mixage par Stems" },
      { id: "common-stem-groups", label: "Groupes de Stems Communs" },
      { id: "preparing-stems", label: "Préparer vos Stems" },
    ],
  },
  de: {
    title: "Stems vs. Stereo: Warum Stem-Mixing das Spiel verändert",
    description: "Entdecken Sie, warum das Aufteilen Ihrer Tracks in Stems mehr Kontrolle, bessere Klarheit und überlegene Mastering-Ergebnisse bietet.",
    excerpt: "Stereo-Mastering ist gut, aber Stem-Mastering ist transformativ. Erfahren Sie, wie das Gruppieren Ihrer Tracks ein neues Niveau an Politur freischaltet.",
    publishedAtLabel: "25. Jan. 2025",
    readingTime: "7 Min.",
    tags: ["Stems", "Mixing", "Mastering", "Workflow"],
    keywords: ["stem mastering", "stems vs stereo", "mixing stems", "audio trennung", "mastering kontrolle"],
    toc: [
      { id: "intro", label: "Einführung" },
      { id: "what-are-stems", label: "Was sind Stems?" },
      { id: "benefits-of-stems", label: "Vorteile von Stem-Mixing" },
      { id: "common-stem-groups", label: "Häufige Stem-Gruppen" },
      { id: "preparing-stems", label: "Vorbereitung Ihrer Stems" },
    ],
  },
  it: {
    title: "Stems vs. Stereo: Perché il mixaggio per stem cambia il gioco",
    description: "Scopri perché separare le tue tracce in stem ti dà più controllo, migliore chiarezza e risultati di mastering superiori.",
    excerpt: "Il mastering stereo è buono, ma il mastering per stem è trasformativo. Impara come raggruppare le tue tracce sblocca un nuovo livello di finitura.",
    publishedAtLabel: "25 gen 2025",
    readingTime: "7 min",
    tags: ["Stems", "Mixaggio", "Mastering", "Workflow"],
    keywords: ["mastering per stem", "stems vs stereo", "mixaggio di stem", "separazione audio", "controllo di mastering"],
    toc: [
      { id: "intro", label: "Introduzione" },
      { id: "what-are-stems", label: "Cosa sono gli Stems?" },
      { id: "benefits-of-stems", label: "Benefici del Mixaggio per Stems" },
      { id: "common-stem-groups", label: "Gruppi di Stems Comuni" },
      { id: "preparing-stems", label: "Preparare i tuoi Stems" },
    ],
  },
  pt: {
    title: "Stems vs. Stereo: Por que mixar por grupos muda o jogo",
    description: "Descubra por que separar suas faixas em stems oferece mais controle, melhor clareza e resultados de masterização superiores.",
    excerpt: "A masterização estéreo é boa, mas a masterização por stems é transformadora. Aprenda como agrupar suas faixas desbloqueia um novo nível de polimento.",
    publishedAtLabel: "25 jan 2025",
    readingTime: "7 min",
    tags: ["Stems", "Mixagem", "Mastering", "Workflow"],
    keywords: ["mastering por stems", "stems vs stereo", "mixagem de stems", "separação de áudio", "controle de mastering"],
    toc: [
      { id: "intro", label: "Introdução" },
      { id: "what-are-stems", label: "O que são Stems?" },
      { id: "benefits-of-stems", label: "Benefícios da Mixagem por Stems" },
      { id: "common-stem-groups", label: "Grupos de Stems Comuns" },
      { id: "preparing-stems", label: "Preparando seus Stems" },
    ],
  },
  ja: {
    title: "ステム vs ステレオ：ステムミキシングがゲームを変える理由",
    description: "トラックをステムに分割することで、より多くのコントロール、優れた透明度、そして優れたマスタリング結果が得られる理由を発見してください。",
    excerpt: "ステレオマスタリングも良いですが、ステムマスタリングは革新的です。トラックをグループ化することで、新しいレベルの洗練さが解き放たれます。",
    publishedAtLabel: "2025年1月25日",
    readingTime: "7分",
    tags: ["ステム", "ミキシング", "マスタリング", "ワークフロー"],
    keywords: ["ステムマスタリング", "ステム vs ステレオ", "ステムミキシング", "オーディオ分離", "マスタリングコントロール"],
    toc: [
      { id: "intro", label: "はじめに" },
      { id: "what-are-stems", label: "ステムとは？" },
      { id: "benefits-of-stems", label: "ステムミキシングの利点" },
      { id: "common-stem-groups", label: "一般的なステムグループ" },
      { id: "preparing-stems", label: "ステムの準備" },
    ],
  },
  zh: {
    title: "分轨 vs 立体声：为什么分轨混音改变了游戏规则",
    description: "了解为什么将音轨分成 stems 可以提供更多控制、更好的清晰度和优越的母带效果。",
    excerpt: "立体声母带很好，但分轨母带是变革性的。了解分组音轨如何解锁新的打磨水平。",
    publishedAtLabel: "2025年1月25日",
    readingTime: "7分钟",
    tags: ["分轨", "混音", "母带", "工作流"],
    keywords: ["分轨母带", "分轨 vs 立体声", "分轨混音", "音频分离", "母带控制"],
    toc: [
      { id: "intro", label: "介绍" },
      { id: "what-are-stems", label: "什么是 Stems？" },
      { id: "benefits-of-stems", label: "分轨混音的好处" },
      { id: "common-stem-groups", label: "常见的分轨组" },
      { id: "preparing-stems", label: "准备你的 Stems" },
    ],
  },
},
},
{
slug: "guia-mastering-lufs-true-peak",
image: "/blog/covers/lufs_guide.webp",
publishedAt: "2025-01-27",
translations: {
  en: {
    title: "Mastering LUFS: The Ultimate Loudness Guide",
    description: "Demystifying Loudness Units Full Scale (LUFS) and True Peak. Learn how to hit competitive levels without sacrificing dynamics.",
    excerpt: "Confused by -14 LUFS vs -9 LUFS? We explain what really matters for Spotify, Apple Music, and the dancefloor.",
    publishedAtLabel: "Jan 27, 2025",
    readingTime: "9 min read",
    tags: ["LUFS", "Mastering", "Loudness", "True Peak"],
    keywords: ["lufs guide", "mastering loudness", "spotify lufs", "true peak explained", "dynamic range"],
    toc: [
      { id: "intro", label: "Introduction" },
      { id: "what-is-lufs", label: "What is LUFS?" },
      { id: "true-peak-explained", label: "True Peak Explained" },
      { id: "streaming-standards", label: "Streaming Standards" },
      { id: "how-loud", label: "How Loud Should You Go?" },
    ],
  },
  es: {
    title: "Dominando los LUFS: La guía definitiva de sonoridad",
    description: "Desmitificando Loudness Units Full Scale (LUFS) y True Peak. Aprende a alcanzar niveles competitivos sin sacrificar la dinámica.",
    excerpt: "¿Confundido por -14 LUFS vs -9 LUFS? Explicamos lo que realmente importa para Spotify, Apple Music y la pista de baile.",
    publishedAtLabel: "27 Ene 2025",
    readingTime: "9 min",
    tags: ["LUFS", "Mastering", "Sonoridad", "True Peak"],
    keywords: ["guía lufs", "sonoridad mastering", "spotify lufs", "true peak explicado", "rango dinámico"],
    toc: [
      { id: "intro", label: "Introducción" },
      { id: "what-is-lufs", label: "¿Qué son los LUFS?" },
      { id: "true-peak-explained", label: "True Peak Explicado" },
      { id: "streaming-standards", label: "Estándares de Streaming" },
      { id: "how-loud", label: "¿Qué tan fuerte deberías ir?" },
    ],
  },
  fr: {
    title: "Maîtriser les LUFS : Le guide ultime de la sonie",
    description: "Démystifier les Loudness Units Full Scale (LUFS) et le True Peak. Apprenez à atteindre des niveaux compétitifs sans sacrifier la dynamique.",
    excerpt: "Confus par -14 LUFS vs -9 LUFS ? Nous expliquons ce qui compte vraiment pour Spotify, Apple Music et le dancefloor.",
    publishedAtLabel: "27 janv. 2025",
    readingTime: "9 min",
    tags: ["LUFS", "Mastering", "Sonie", "True Peak"],
    keywords: ["guide lufs", "sonie mastering", "spotify lufs", "true peak expliqué", "plage dynamique"],
    toc: [
      { id: "intro", label: "Introduction" },
      { id: "what-is-lufs", label: "Qu'est-ce que le LUFS ?" },
      { id: "true-peak-explained", label: "True Peak Expliqué" },
      { id: "streaming-standards", label: "Standards de Streaming" },
      { id: "how-loud", label: "Jusqu'où aller ?" },
    ],
  },
  de: {
    title: "LUFS Meistern: Der ultimative Lautheits-Guide",
    description: "Entmystifizierung von Loudness Units Full Scale (LUFS) und True Peak. Lernen Sie, wettbewerbsfähige Pegel zu erreichen, ohne Dynamik zu opfern.",
    excerpt: "Verwirrt von -14 LUFS vs -9 LUFS? Wir erklären, was für Spotify, Apple Music und den Dancefloor wirklich zählt.",
    publishedAtLabel: "27. Jan. 2025",
    readingTime: "9 Min.",
    tags: ["LUFS", "Mastering", "Lautheit", "True Peak"],
    keywords: ["lufs guide", "mastering lautheit", "spotify lufs", "true peak erklärt", "dynamikbereich"],
    toc: [
      { id: "intro", label: "Einführung" },
      { id: "what-is-lufs", label: "Was ist LUFS?" },
      { id: "true-peak-explained", label: "True Peak Erklärt" },
      { id: "streaming-standards", label: "Streaming-Standards" },
      { id: "how-loud", label: "Wie laut sollten Sie gehen?" },
    ],
  },
  it: {
    title: "Padroneggiare i LUFS: La guida definitiva al loudness",
    description: "Demistificare Loudness Units Full Scale (LUFS) e True Peak. Impara a raggiungere livelli competitivi senza sacrificare la dinamica.",
    excerpt: "Confuso da -14 LUFS vs -9 LUFS? Spieghiamo cosa conta davvero per Spotify, Apple Music e la pista da ballo.",
    publishedAtLabel: "27 gen 2025",
    readingTime: "9 min",
    tags: ["LUFS", "Mastering", "Loudness", "True Peak"],
    keywords: ["guida lufs", "loudness mastering", "spotify lufs", "true peak spiegato", "range dinamico"],
    toc: [
      { id: "intro", label: "Introduzione" },
      { id: "what-is-lufs", label: "Cos'è LUFS?" },
      { id: "true-peak-explained", label: "True Peak Spiegato" },
      { id: "streaming-standards", label: "Standard di Streaming" },
      { id: "how-loud", label: "Quanto alto dovresti andare?" },
    ],
  },
  pt: {
    title: "Dominando LUFS: O guia definitivo de volume",
    description: "Desmistificando Loudness Units Full Scale (LUFS) e True Peak. Aprenda a atingir níveis competitivos sem sacrificar a dinâmica.",
    excerpt: "Confuso com -14 LUFS vs -9 LUFS? Explicamos o que realmente importa para Spotify, Apple Music e a pista de dança.",
    publishedAtLabel: "27 jan 2025",
    readingTime: "9 min",
    tags: ["LUFS", "Mastering", "Volume", "True Peak"],
    keywords: ["guia lufs", "volume mastering", "spotify lufs", "true peak explicado", "faixa dinâmica"],
    toc: [
      { id: "intro", label: "Introdução" },
      { id: "what-is-lufs", label: "O que é LUFS?" },
      { id: "true-peak-explained", label: "True Peak Explicado" },
      { id: "streaming-standards", label: "Padrões de Streaming" },
      { id: "how-loud", label: "Quão alto você deve ir?" },
    ],
  },
  ja: {
    title: "LUFSをマスターする：究極のラウドネスガイド",
    description: "Loudness Units Full Scale (LUFS) と True Peak の謎を解明します。ダイナミクスを犠牲にすることなく競争力のあるレベルに到達する方法を学びます。",
    excerpt: "-14 LUFS と -9 LUFS で混乱していませんか？Spotify、Apple Music、ダンスフロアにとって何が重要かを説明します。",
    publishedAtLabel: "2025年1月27日",
    readingTime: "9分",
    tags: ["LUFS", "マスタリング", "ラウドネス", "True Peak"],
    keywords: ["LUFSガイド", "マスタリングラウドネス", "Spotify LUFS", "True Peak解説", "ダイナミックレンジ"],
    toc: [
      { id: "intro", label: "はじめに" },
      { id: "what-is-lufs", label: "LUFSとは？" },
      { id: "true-peak-explained", label: "True Peakの解説" },
      { id: "streaming-standards", label: "ストリーミング基準" },
      { id: "how-loud", label: "どれくらいの音量にするべきか？" },
    ],
  },
  zh: {
    title: "掌握 LUFS：终极响度指南",
    description: "揭秘响度单位满刻度 (LUFS) 和真实峰值 (True Peak)。学习如何在不牺牲动态的情况下达到有竞争力的电平。",
    excerpt: "对 -14 LUFS 和 -9 LUFS 感到困惑？我们解释了对于 Spotify、Apple Music 和舞池来说真正重要的是什么。",
    publishedAtLabel: "2025年1月27日",
    readingTime: "9分钟",
    tags: ["LUFS", "母带", "响度", "True Peak"],
    keywords: ["lufs 指南", "母带响度", "spotify lufs", "true peak 解释", "动态范围"],
    toc: [
      { id: "intro", label: "介绍" },
      { id: "what-is-lufs", label: "什么是 LUFS？" },
      { id: "true-peak-explained", label: "真实峰值解释" },
      { id: "streaming-standards", label: "流媒体标准" },
      { id: "how-loud", label: "你应该多大声？" },
    ],
  },
},
},
{
slug: "flujo-trabajo-inteligencia-artificial",
image: "/blog/covers/workflow_ai.webp",
publishedAt: "2025-01-30",
translations: {
  en: {
    title: "The Piroola Workflow: From Demo to Master in Minutes",
    description: "See how our AI-driven pipeline analyzes, corrects, and masters your tracks. A deep dive into the technology behind the sound.",
    excerpt: "Understand the three-stage process: Analysis, Correction, and Mastering. How our AI hears your music and enhances it without losing your vibe.",
    publishedAtLabel: "Jan 30, 2025",
    readingTime: "8 min read",
    tags: ["AI", "Workflow", "Piroola", "Technology"],
    keywords: ["piroola workflow", "ai mastering process", "audio analysis", "automated mastering", "music production ai"],
    toc: [
      { id: "intro", label: "Introduction" },
      { id: "stage-1-analysis", label: "Stage 1: Deep Analysis" },
      { id: "stage-2-correction", label: "Stage 2: Surgical Correction" },
      { id: "stage-3-mastering", label: "Stage 3: Creative Mastering" },
      { id: "human-control", label: "Where You Have Control" },
    ],
  },
  es: {
    title: "El flujo de trabajo de Piroola: De la demo al master en minutos",
    description: "Mira cómo nuestro pipeline impulsado por IA analiza, corrige y masteriza tus pistas. Una inmersión profunda en la tecnología detrás del sonido.",
    excerpt: "Entiende el proceso de tres etapas: Análisis, Corrección y Mastering. Cómo nuestra IA escucha tu música y la mejora sin perder tu vibra.",
    publishedAtLabel: "30 Ene 2025",
    readingTime: "8 min",
    tags: ["IA", "Flujo de trabajo", "Piroola", "Tecnología"],
    keywords: ["flujo piroola", "proceso mastering ai", "análisis de audio", "mastering automatizado", "producción musical ai"],
    toc: [
      { id: "intro", label: "Introducción" },
      { id: "stage-1-analysis", label: "Etapa 1: Análisis Profundo" },
      { id: "stage-2-correction", label: "Etapa 2: Corrección Quirúrgica" },
      { id: "stage-3-mastering", label: "Etapa 3: Mastering Creativo" },
      { id: "human-control", label: "Dónde tienes el control" },
    ],
  },
  fr: {
    title: "Le workflow Piroola : De la démo au master en quelques minutes",
    description: "Découvrez comment notre pipeline piloté par IA analyse, corrige et masterise vos pistes. Une plongée au cœur de la technologie.",
    excerpt: "Comprenez le processus en trois étapes : Analyse, Correction et Mastering. Comment notre IA écoute votre musique et l'améliore.",
    publishedAtLabel: "30 janv. 2025",
    readingTime: "8 min",
    tags: ["IA", "Workflow", "Piroola", "Technologie"],
    keywords: ["workflow piroola", "processus mastering ai", "analyse audio", "mastering automatisé", "production musicale ai"],
    toc: [
      { id: "intro", label: "Introduction" },
      { id: "stage-1-analysis", label: "Étape 1 : Analyse Approfondie" },
      { id: "stage-2-correction", label: "Étape 2 : Correction Chirurgicale" },
      { id: "stage-3-mastering", label: "Étape 3 : Mastering Créatif" },
      { id: "human-control", label: "Où vous avez le contrôle" },
    ],
  },
  de: {
    title: "Der Piroola-Workflow: Von der Demo zum Master in Minuten",
    description: "Sehen Sie, wie unsere KI-gesteuerte Pipeline Ihre Tracks analysiert, korrigiert und mastert. Ein tiefer Einblick in die Technologie.",
    excerpt: "Verstehen Sie den dreistufigen Prozess: Analyse, Korrektur und Mastering. Wie unsere KI Ihre Musik hört und verbessert.",
    publishedAtLabel: "30. Jan. 2025",
    readingTime: "8 Min.",
    tags: ["KI", "Workflow", "Piroola", "Technologie"],
    keywords: ["piroola workflow", "ki mastering prozess", "audio analyse", "automatisiertes mastering", "musikproduktion ki"],
    toc: [
      { id: "intro", label: "Einführung" },
      { id: "stage-1-analysis", label: "Stufe 1: Tiefenanalyse" },
      { id: "stage-2-correction", label: "Stufe 2: Chirurgische Korrektur" },
      { id: "stage-3-mastering", label: "Stufe 3: Kreatives Mastering" },
      { id: "human-control", label: "Wo Sie die Kontrolle haben" },
    ],
  },
  it: {
    title: "Il workflow Piroola: Dalla demo al master in minuti",
    description: "Guarda come la nostra pipeline guidata dall'IA analizza, corregge e masterizza le tue tracce. Un'immersione nella tecnologia.",
    excerpt: "Comprendi il processo in tre fasi: Analisi, Correzione e Mastering. Come la nostra IA ascolta la tua musica e la migliora.",
    publishedAtLabel: "30 gen 2025",
    readingTime: "8 min",
    tags: ["IA", "Workflow", "Piroola", "Tecnologia"],
    keywords: ["workflow piroola", "processo mastering ai", "analisi audio", "mastering automatizzato", "produzione musicale ai"],
    toc: [
      { id: "intro", label: "Introduzione" },
      { id: "stage-1-analysis", label: "Fase 1: Analisi Profonda" },
      { id: "stage-2-correction", label: "Fase 2: Correzione Chirurgica" },
      { id: "stage-3-mastering", label: "Fase 3: Mastering Creativo" },
      { id: "human-control", label: "Dove hai il controllo" },
    ],
  },
  pt: {
    title: "O fluxo de trabalho Piroola: Da demo ao master em minutos",
    description: "Veja como nosso pipeline impulsionado por IA analisa, corrige e masteriza suas faixas. Um mergulho na tecnologia.",
    excerpt: "Entenda o processo de três etapas: Análise, Correção e Masterização. Como nossa IA ouve sua música e a aprimora.",
    publishedAtLabel: "30 jan 2025",
    readingTime: "8 min",
    tags: ["IA", "Workflow", "Piroola", "Tecnologia"],
    keywords: ["workflow piroola", "processo mastering ai", "análise de áudio", "mastering automatizado", "produção musical ai"],
    toc: [
      { id: "intro", label: "Introdução" },
      { id: "stage-1-analysis", label: "Etapa 1: Análise Profunda" },
      { id: "stage-2-correction", label: "Etapa 2: Correção Cirúrgica" },
      { id: "stage-3-mastering", label: "Etapa 3: Mastering Criativo" },
      { id: "human-control", label: "Onde você tem o controle" },
    ],
  },
  ja: {
    title: "Piroolaワークフロー：デモからマスターまで数分で",
    description: "AI駆動のパイプラインがトラックを分析、修正、マスタリングする方法をご覧ください。サウンドの背後にある技術への深い探求。",
    excerpt: "分析、修正、マスタリングの3段階のプロセスを理解しましょう。当社のAIがあなたの音楽をどのように聴き、強化するか。",
    publishedAtLabel: "2025年1月30日",
    readingTime: "8分",
    tags: ["AI", "ワークフロー", "Piroola", "技術"],
    keywords: ["piroola ワークフロー", "ai マスタリング プロセス", "オーディオ分析", "自動マスタリング", "音楽制作 ai"],
    toc: [
      { id: "intro", label: "はじめに" },
      { id: "stage-1-analysis", label: "ステージ 1: 深層分析" },
      { id: "stage-2-correction", label: "ステージ 2: 外科的修正" },
      { id: "stage-3-mastering", label: "ステージ 3: クリエイティブマスタリング" },
      { id: "human-control", label: "コントロールできる場所" },
    ],
  },
  zh: {
    title: "Piroola 工作流：几分钟内从 Demo 到 Master",
    description: "了解我们的 AI 驱动管道如何分析、修正和母带处理您的音轨。深入了解声音背后的技术。",
    excerpt: "了解三个阶段的过程：分析、修正和母带处理。我们的 AI 如何聆听您的音乐并在不丢失氛围的情况下增强它。",
    publishedAtLabel: "2025年1月30日",
    readingTime: "8分钟",
    tags: ["AI", "工作流", "Piroola", "技术"],
    keywords: ["piroola 工作流", "ai 母带流程", "音频分析", "自动母带", "音乐制作 ai"],
    toc: [
      { id: "intro", label: "介绍" },
      { id: "stage-1-analysis", label: "第一阶段：深度分析" },
      { id: "stage-2-correction", label: "第二阶段：手术式修正" },
      { id: "stage-3-mastering", label: "第三阶段：创意母带" },
      { id: "human-control", label: "您掌控的地方" },
    ],
  },
},
},
];

export const blogPostSlugs = blogPosts.map((post) => post.slug);

export function resolveBlogLocale(locale: string): BlogLocale {
  return blogLocales.includes(locale as BlogLocale)
    ? (locale as BlogLocale)
    : defaultBlogLocale;
}

export function getBlogPost(
  slug: string,
  locale: BlogLocale
): LocalizedBlogPost | null {
  const post = blogPosts.find((entry) => entry.slug === slug);
  if (!post) return null;

  const translation =
    post.translations[locale] ?? post.translations[defaultBlogLocale];
  return {
    slug: post.slug,
    image: post.image,
    publishedAt: post.publishedAt,
    ...translation,
  };
}

export function getBlogPosts(locale: BlogLocale): LocalizedBlogPost[] {
  return blogPosts.map((post) => ({
    slug: post.slug,
    image: post.image,
    publishedAt: post.publishedAt,
    ...(post.translations[locale] ?? post.translations[defaultBlogLocale]),
  }));
}

export function getBlogTags(locale: BlogLocale): string[] {
  const posts = getBlogPosts(locale);
  const tags = new Set<string>();
  posts.forEach((post) => {
    post.tags.forEach((tag) => tags.add(tag));
  });
  return Array.from(tags);
}
