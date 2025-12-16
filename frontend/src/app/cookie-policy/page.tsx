import type { Metadata } from "next";
import Link from "next/link";

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
const canonicalUrl = `${siteUrl}/cookie-policy`;

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Home",
      item: siteUrl,
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "Cookie Policy",
      item: canonicalUrl,
    },
  ],
};

const webPageJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "Cookie Policy",
  url: canonicalUrl,
  isPartOf: {
    "@type": "WebSite",
    url: siteUrl,
    name: "Piroola",
  },
  inLanguage: "en",
};

export const metadata: Metadata = {
  title: "Cookie Policy",
  description:
    "Understand how Piroola uses cookies and similar technologies to improve your AI mixing and mastering experience.",
  alternates: { canonical: "/cookie-policy" },
  robots: { index: true, follow: true },
};

export default function CookiePolicyPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(webPageJsonLd) }}
      />
      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl prose prose-invert prose-slate">
          <h1 className="text-3xl font-bold mb-8 text-teal-400">Cookie Policy</h1>

          <p className="text-slate-300 mb-6">Last updated: {new Date().toLocaleDateString()}</p>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">1. What Are Cookies</h2>
            <p className="text-slate-400 leading-relaxed">
              Cookies are small text files that are placed on your computer or mobile device when you browse websites.
              They are widely used to make websites work, or work more efficiently, as well as to provide information to the owners of the site.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">2. How We Use Cookies</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              We use cookies for a variety of reasons detailed below. Unfortunately, in most cases there are no industry standard options
              for disabling cookies without completely disabling the functionality and features they add to this site.
              It is recommended that you leave on all cookies if you are not sure whether you need them or not in case they are used to provide a service that you use.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">3. The Cookies We Set</h2>
            <ul className="list-disc pl-5 text-slate-400 space-y-2">
              <li>
                <strong>Essential Cookies:</strong> These cookies are necessary for the website to function and cannot be switched off in our systems.
                They are usually only set in response to actions made by you which amount to a request for services, such as setting your privacy preferences, logging in or filling in forms.
              </li>
              <li>
                <strong>Functionality Cookies:</strong> These cookies enable the website to provide enhanced functionality and personalization.
                They may be set by us or by third party providers whose services we have added to our pages.
              </li>
              <li>
                <strong>Analytics Cookies:</strong> We use Google Analytics to understand how our visitors interact with the website.
                This helps us improve the user experience. These cookies track things such as how long you spend on the site and the pages that you visit.
              </li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">4. Third Party Cookies</h2>
            <p className="text-slate-400 leading-relaxed">
              In some special cases we also use cookies provided by trusted third parties.
              The following section details which third party cookies you might encounter through this site.
            </p>
            <p className="text-slate-400 leading-relaxed mt-2">
              This site uses Google Analytics which is one of the most widespread and trusted analytics solutions on the web for helping us
              to understand how you use the site and ways that we can improve your experience. These cookies may track things such as how long you spend on the site and the pages that you visit so we can continue to produce engaging content.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">5. Managing Cookies</h2>
            <p className="text-slate-400 leading-relaxed">
              You can prevent the setting of cookies by adjusting the settings on your browser (see your browser Help for how to do this).
              Be aware that disabling cookies will affect the functionality of this and many other websites that you visit.
              Disabling cookies will usually result in also disabling certain functionality and features of this site.
              Therefore it is recommended that you do not disable cookies.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">6. Contact Details</h2>
            <p className="text-slate-400 leading-relaxed">
              If you have any questions about this cookie policy, please contact us at: <br />
              <span className="text-teal-400">privacy@audioalchemy.com</span>
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
