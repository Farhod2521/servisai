import type { Metadata } from "next";
import { Suspense } from "react";
import Footer from "../components/Footer";
import Header from "../components/Header";
import Profile from "./Profile";

export const metadata: Metadata = {
  title: "Profil — servisai.uz",
};

export default function ProfilePage() {
  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-8 sm:px-6">
        <Suspense fallback={<div className="h-96 animate-pulse rounded-3xl bg-white" />}>
          <Profile />
        </Suspense>
      </main>
      <Footer />
    </>
  );
}
