import type { Metadata } from "next";
import { HomeClient } from "../../components/HomeClient";

export const metadata: Metadata = {
  alternates: {
    canonical: "/",
  },
};

export default function Page() {
  return <HomeClient />;
}
