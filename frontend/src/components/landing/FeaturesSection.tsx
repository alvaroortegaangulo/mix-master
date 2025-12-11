import { BeakerIcon, AdjustmentsHorizontalIcon, SparklesIcon } from "@heroicons/react/24/outline";

export function FeaturesSection() {
  const features = [
    {
      title: "Intelligent Analysis",
      description: "Our AI scans your tracks to understand key, tempo, genre, and instrumentation, creating a custom mixing strategy.",
      icon: BeakerIcon,
      color: "text-purple-400",
      bg: "bg-purple-400/10",
    },
    {
      title: "Precision Mixing",
      description: "Applies surgical EQ, dynamic compression, and spatial enhancements tailored to each stem's role in the mix.",
      icon: AdjustmentsHorizontalIcon,
      color: "text-teal-400",
      bg: "bg-teal-400/10",
    },
    {
      title: "Mastering Grade Polish",
      description: "Finalizes your track with industry-standard loudness matching, stereo widening, and limiter safety.",
      icon: SparklesIcon,
      color: "text-amber-400",
      bg: "bg-amber-400/10",
    },
  ];

  return (
    <section id="features" className="py-24 bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Under the Hood
          </h2>
          <p className="mt-4 text-lg text-slate-400">
            A complete audio engineering team in the cloud.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          {features.map((feature, idx) => (
            <div
              key={idx}
              className="relative rounded-2xl border border-slate-800 bg-slate-950/50 p-8 transition hover:border-slate-700 hover:bg-slate-950"
            >
              <div className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl ${feature.bg}`}>
                <feature.icon className={`h-6 w-6 ${feature.color}`} />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-white">
                {feature.title}
              </h3>
              <p className="text-slate-400 leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
