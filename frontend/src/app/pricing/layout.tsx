import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing | Audio Alchemy",
  description: "Compare Audio Alchemy plans and choose the AI mixing and mastering tier that fits your releases.",
  alternates: {
    canonical: "/pricing",
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
