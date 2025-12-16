import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Support - Piroola",
  description: "Get help with Piroola's AI mixing and mastering service. Contact support or find answers in our documentation.",
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
