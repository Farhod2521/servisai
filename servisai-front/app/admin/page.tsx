import type { Metadata } from "next";
import { Suspense } from "react";
import Header from "../components/Header";
import AdminPanel from "./AdminPanel";

export const metadata: Metadata = {
  title: "Admin panel — servisai.uz",
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <Suspense fallback={<div className="h-96 animate-pulse rounded-3xl bg-white" />}>
          <AdminPanel />
        </Suspense>
      </main>
    </>
  );
}
