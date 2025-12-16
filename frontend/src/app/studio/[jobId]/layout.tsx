import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mix Studio | Piroola",
  description: "Interactive AI mixing studio. Adjust levels, apply corrections, and finalize your mix.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function StudioLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
