import { BlogLocale, defaultBlogLocale } from "./blogPosts";

type BlogIndexCopy = {
  metaTitle: string;
  metaDescription: string;
  badge: string;
  title: string;
  subtitle: string;
  readArticleLabel: string;
  ctaTitle: string;
  ctaBody: string;
  ctaButton: string;
};

type BlogPostCopy = {
  metaFallbackTitle: string;
  metaFallbackDescription: string;
  backLink: string;
  badge: string;
  tocTitle: string;
  ctaTitle: string;
  ctaBody: string;
  ctaPrimary: string;
  ctaSecondary: string;
};

type BlogRssCopy = {
  title: string;
  description: string;
};

export const blogCopy: Record<
  BlogLocale,
  { index: BlogIndexCopy; post: BlogPostCopy; rss: BlogRssCopy }
> = {
  en: {
    index: {
      metaTitle: "Technical AI Mixing & Mastering Blog",
      metaDescription:
        "Technical guides on real audio problems: DC offset, drum bus compression, dynamics, and stem preparation.",
      badge: "Technical blog",
      title: "Your Music Deserves to Sound Professional",
      subtitle:
        "Stop fighting your mix and start creating with confidence. Discover the technical strategies top engineers use to achieve clarity, power, and emotion in every track.",
      readArticleLabel: "Read article",
      ctaTitle: "Want these fixes applied automatically?",
      ctaBody:
        "Piroola analyzes your stems, detects technical issues, and applies consistent corrections at every pipeline stage.",
      ctaButton: "Try Piroola",
    },
    post: {
      metaFallbackTitle: "Technical blog",
      metaFallbackDescription:
        "Technical mixing and mastering articles powered by AI.",
      backLink: "← Back to blog",
      badge: "Technical guide",
      tocTitle: "In this article",
      ctaTitle: "Want this applied to your stems?",
      ctaBody:
        "Piroola runs these steps inside the pipeline and delivers a technical report with before/after metrics.",
      ctaPrimary: "Try Piroola",
      ctaSecondary: "See how it works",
    },
    rss: {
      title: "Piroola | Technical Blog",
      description:
        "Technical guides on real audio problems: DC offset, drum bus compression, dynamics, and stem preparation.",
    },
  },
  es: {
    index: {
      metaTitle: "Blog técnico de mezcla y mastering con IA",
      metaDescription:
        "Guías técnicas sobre problemas reales de audio: DC offset, compresión de bus, dinámica y preparación de stems.",
      badge: "Blog técnico",
      title: "Tu Música Merece Sonar Profesional",
      subtitle:
        "Deja de luchar con tu mezcla y empieza a crear con confianza. Descubre las estrategias técnicas que utilizan los ingenieros top para lograr claridad, potencia y emoción en cada track.",
      readArticleLabel: "Leer artículo",
      ctaTitle: "¿Quieres aplicar estos ajustes automáticamente?",
      ctaBody:
        "Piroola analiza tus stems, detecta problemas técnicos y aplica correcciones de forma consistente en cada etapa del pipeline.",
      ctaButton: "Probar Piroola",
    },
    post: {
      metaFallbackTitle: "Blog técnico",
      metaFallbackDescription:
        "Artículos técnicos de mezcla y mastering con IA.",
      backLink: "← Volver al blog",
      badge: "Guía técnica",
      tocTitle: "En este artículo",
      ctaTitle: "¿Quieres ver esto aplicado a tus stems?",
      ctaBody:
        "Piroola ejecuta estos pasos dentro del pipeline y entrega un informe técnico con métricas antes y después.",
      ctaPrimary: "Probar Piroola",
      ctaSecondary: "Ver cómo funciona",
    },
    rss: {
      title: "Piroola | Blog técnico",
      description:
        "Guías técnicas sobre problemas reales de audio: DC offset, compresión de bus, dinámica y preparación de stems.",
    },
  },
  fr: {
    index: {
      metaTitle: "Blog technique de mixage et mastering IA",
      metaDescription:
        "Guides techniques sur des problèmes audio réels : DC offset, compression de bus, dynamique et préparation de stems.",
      badge: "Blog technique",
      title: "Solutions précises pour des problèmes réels de mix",
      subtitle:
        "Au lieu de viser des mots-clés génériques, on cible les recherches techniques que les producteurs font chaque jour : nettoyage du DC offset, compression de bus, contrôle dynamique et préparation de stems.",
      readArticleLabel: "Lire l’article",
      ctaTitle: "Envie d’appliquer ces réglages automatiquement ?",
      ctaBody:
        "Piroola analyse vos stems, détecte les problèmes techniques et applique des corrections cohérentes à chaque étape du pipeline.",
      ctaButton: "Tester Piroola",
    },
    post: {
      metaFallbackTitle: "Blog technique",
      metaFallbackDescription:
        "Articles techniques de mixage et mastering avec IA.",
      backLink: "← Retour au blog",
      badge: "Guide technique",
      tocTitle: "Dans cet article",
      ctaTitle: "Vous voulez l’appliquer à vos stems ?",
      ctaBody:
        "Piroola exécute ces étapes dans le pipeline et livre un rapport technique avec métriques avant/après.",
      ctaPrimary: "Tester Piroola",
      ctaSecondary: "Voir comment ça marche",
    },
    rss: {
      title: "Piroola | Blog technique",
      description:
        "Guides techniques sur des problèmes audio réels : DC offset, compression de bus, dynamique et préparation de stems.",
    },
  },
  de: {
    index: {
      metaTitle: "Technischer Blog für KI-Mixing & Mastering",
      metaDescription:
        "Technische Guides zu echten Audio-Problemen: DC Offset, Drum-Bus-Kompression, Dynamik und Stem-Vorbereitung.",
      badge: "Technik-Blog",
      title: "Konkrete Lösungen für echte Mixing-Probleme",
      subtitle:
        "Statt generische Keywords zu bekämpfen, adressieren wir technische Suchen, die Producer täglich stellen: DC-Offset-Bereinigung, Bus-Kompression, Dynamik-Kontrolle und Stem-Vorbereitung.",
      readArticleLabel: "Artikel lesen",
      ctaTitle: "Willst du diese Fixes automatisch anwenden?",
      ctaBody:
        "Piroola analysiert deine Stems, erkennt technische Probleme und wendet konsistente Korrekturen in jeder Pipeline-Stufe an.",
      ctaButton: "Piroola testen",
    },
    post: {
      metaFallbackTitle: "Technik-Blog",
      metaFallbackDescription:
        "Technische Mixing- und Mastering-Artikel mit KI.",
      backLink: "← Zurück zum Blog",
      badge: "Technik-Guide",
      tocTitle: "In diesem Artikel",
      ctaTitle: "Willst du das auf deine Stems anwenden?",
      ctaBody:
        "Piroola führt diese Schritte in der Pipeline aus und liefert einen technischen Bericht mit Vorher/Nachher-Metriken.",
      ctaPrimary: "Piroola testen",
      ctaSecondary: "So funktioniert’s",
    },
    rss: {
      title: "Piroola | Technik-Blog",
      description:
        "Technische Guides zu echten Audio-Problemen: DC Offset, Drum-Bus-Kompression, Dynamik und Stem-Vorbereitung.",
    },
  },
  it: {
    index: {
      metaTitle: "Blog tecnico di mixing e mastering con IA",
      metaDescription:
        "Guide tecniche su problemi audio reali: DC offset, compressione del bus, dinamica e preparazione degli stem.",
      badge: "Blog tecnico",
      title: "Soluzioni specifiche per problemi reali di mix",
      subtitle:
        "Invece di competere su keyword generiche, puntiamo alle ricerche tecniche che i producer fanno ogni giorno: pulizia del DC offset, compressione del bus, controllo dinamico e preparazione degli stem.",
      readArticleLabel: "Leggi l’articolo",
      ctaTitle: "Vuoi applicare questi interventi automaticamente?",
      ctaBody:
        "Piroola analizza i tuoi stem, rileva problemi tecnici e applica correzioni coerenti in ogni fase della pipeline.",
      ctaButton: "Prova Piroola",
    },
    post: {
      metaFallbackTitle: "Blog tecnico",
      metaFallbackDescription:
        "Articoli tecnici di mixing e mastering con IA.",
      backLink: "← Torna al blog",
      badge: "Guida tecnica",
      tocTitle: "In questo articolo",
      ctaTitle: "Vuoi applicarlo ai tuoi stem?",
      ctaBody:
        "Piroola esegue questi passaggi nella pipeline e consegna un report tecnico con metriche prima/dopo.",
      ctaPrimary: "Prova Piroola",
      ctaSecondary: "Guarda come funziona",
    },
    rss: {
      title: "Piroola | Blog tecnico",
      description:
        "Guide tecniche su problemi audio reali: DC offset, compressione del bus, dinamica e preparazione degli stem.",
    },
  },
  pt: {
    index: {
      metaTitle: "Blog técnico de mixagem e masterização com IA",
      metaDescription:
        "Guias técnicos sobre problemas reais de áudio: DC offset, compressão de bus, dinâmica e preparação de stems.",
      badge: "Blog técnico",
      title: "Soluções específicas para problemas reais de mix",
      subtitle:
        "Em vez de disputar keywords genéricas, atacamos buscas técnicas que produtores fazem todo dia: limpeza de DC offset, compressão de bus, controle dinâmico e preparação de stems.",
      readArticleLabel: "Ler artigo",
      ctaTitle: "Quer aplicar esses ajustes automaticamente?",
      ctaBody:
        "A Piroola analisa seus stems, detecta problemas técnicos e aplica correções consistentes em cada etapa do pipeline.",
      ctaButton: "Testar Piroola",
    },
    post: {
      metaFallbackTitle: "Blog técnico",
      metaFallbackDescription:
        "Artigos técnicos de mixagem e masterização com IA.",
      backLink: "← Voltar ao blog",
      badge: "Guia técnico",
      tocTitle: "Neste artigo",
      ctaTitle: "Quer aplicar isso aos seus stems?",
      ctaBody:
        "A Piroola executa esses passos na pipeline e entrega um relatório técnico com métricas antes/depois.",
      ctaPrimary: "Testar Piroola",
      ctaSecondary: "Ver como funciona",
    },
    rss: {
      title: "Piroola | Blog técnico",
      description:
        "Guias técnicos sobre problemas reais de áudio: DC offset, compressão de bus, dinâmica e preparação de stems.",
    },
  },
  ja: {
    index: {
      metaTitle: "AIミキシング/マスタリング技術ブログ",
      metaDescription:
        "DCオフセット、ドラムバス圧縮、ダイナミクス、ステム準備など実務的な技術ガイド。",
      badge: "テクニカルブログ",
      title: "ミックスの実問題に効く具体的ソリューション",
      subtitle:
        "一般的なキーワードではなく、プロデューサーが日々検索する技術課題に答えます：DCオフセット除去、バス圧縮、ダイナミクス管理、ステム準備。",
      readArticleLabel: "記事を読む",
      ctaTitle: "これらを自動で適用したいですか？",
      ctaBody:
        "Piroolaはステムを解析し、技術的な問題を検出して各ステージで一貫した補正を行います。",
      ctaButton: "Piroolaを試す",
    },
    post: {
      metaFallbackTitle: "テクニカルブログ",
      metaFallbackDescription: "AIによるミキシング/マスタリングの技術記事。",
      backLink: "← ブログに戻る",
      badge: "技術ガイド",
      tocTitle: "この記事の内容",
      ctaTitle: "ステムに適用してみませんか？",
      ctaBody:
        "Piroolaはパイプライン内でこれらのステップを実行し、前後の指標を含む技術レポートを提供します。",
      ctaPrimary: "Piroolaを試す",
      ctaSecondary: "仕組みを見る",
    },
    rss: {
      title: "Piroola | テクニカルブログ",
      description:
        "DCオフセット、ドラムバス圧縮、ダイナミクス、ステム準備など実務的な技術ガイド。",
    },
  },
  zh: {
    index: {
      metaTitle: "AI混音与母带技术博客",
      metaDescription:
        "聚焦真实音频问题的技术指南：DC偏移、鼓组总线压缩、动态控制与干声道准备。",
      badge: "技术博客",
      title: "面向真实混音问题的具体解决方案",
      subtitle:
        "我们不与泛关键词竞争，而是覆盖制作人每天搜索的技术问题：DC偏移清理、总线压缩、动态控制与干声道准备。",
      readArticleLabel: "阅读文章",
      ctaTitle: "想自动应用这些调整吗？",
      ctaBody:
        "Piroola 会分析你的 stems，检测技术问题，并在每个流程阶段进行一致的修正。",
      ctaButton: "试用 Piroola",
    },
    post: {
      metaFallbackTitle: "技术博客",
      metaFallbackDescription: "AI 混音与母带的技术文章。",
      backLink: "← 返回博客",
      badge: "技术指南",
      tocTitle: "本文内容",
      ctaTitle: "想把这些应用到你的 stems 吗？",
      ctaBody:
        "Piroola 在流程中执行这些步骤，并提供包含前后指标的技术报告。",
      ctaPrimary: "试用 Piroola",
      ctaSecondary: "了解原理",
    },
    rss: {
      title: "Piroola | 技术博客",
      description:
        "聚焦真实音频问题的技术指南：DC偏移、鼓组总线压缩、动态控制与干声道准备。",
    },
  },
};

export function getBlogCopy(locale: BlogLocale) {
  return blogCopy[locale] ?? blogCopy[defaultBlogLocale];
}
