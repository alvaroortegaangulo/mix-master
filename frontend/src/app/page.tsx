import type { Metadata } from "next";
import { HomeClient } from "../components/HomeClient";
import { LandingPage } from "../components/landing/LandingPage";

export const metadata: Metadata = {
  alternates: {
    canonical: "/",
  },
};

export default function Page() {
  return (
    <HomeClient>
      <LandingPage />
    </HomeClient>
  );
}
