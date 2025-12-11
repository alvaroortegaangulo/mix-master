import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Support | Piroola",
  description: "Get help with Piroola. Browse docs, FAQ, or contact support for AI mixing and mastering questions.",
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
