import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Support | Audio Alchemy",
  description: "Get help with Audio Alchemy. Browse docs, FAQ, or contact support for AI mixing and mastering questions.",
  alternates: {
    canonical: "/support",
  },
};

export default function SupportLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
