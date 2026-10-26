import type { Metadata } from "next";
import Footer from "../components/Footer";
import Catalog from "./Catalog";

export const metadata: Metadata = {
  title: "Barcha servislar — servisai.uz",
  description: "ChatGPT, Claude, Gemini, CapCut, Midjourney va boshqa premium servislar katalogi.",
};

export default function ProductsPage() {
  return (
    <>
      <Catalog />
      <Footer />
    </>
  );
}
