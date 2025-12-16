import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Profile | Piroola",
  description: "Manage your Piroola account settings, update password, or manage your subscription.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function ProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
