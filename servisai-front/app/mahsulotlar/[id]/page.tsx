import type { Metadata } from "next";
import Footer from "../../components/Footer";
import Header from "../../components/Header";
import { HowItWorks } from "../../components/Sections";
import { knownProductIds } from "../catalog-data";
import ProductDetail from "./ProductDetail";

// Mahsulotlar backenddan brauzerda yuklanadi (admin o‘zgartirsa darhol ko‘rinadi).
// Ma’lum sahifalar build vaqtida tayyorlanadi, admin qo‘shgan yangilari birinchi so‘rovda.
export function generateStaticParams() {
  return knownProductIds.map((id) => ({ id }));
}

export const metadata: Metadata = {
  title: "Servis — servisai.uz",
};

export default async function ProductPage({ params }: PageProps<"/mahsulotlar/[id]">) {
  const { id } = await params;

  return (
    <>
      <Header />
      <ProductDetail id={id}>
        <HowItWorks />
      </ProductDetail>
      <Footer />
    </>
  );
}
