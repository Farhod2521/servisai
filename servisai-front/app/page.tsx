import Header from "./components/Header";
import Hero from "./components/Hero";
import Products from "./components/Products";
import { CallToAction, Features, HowItWorks, PromoBanner } from "./components/Sections";
import Testimonials from "./components/Testimonials";
import Faq from "./components/Faq";
import Footer from "./components/Footer";
import AnnouncementPopup from "./components/AnnouncementPopup";

export default function Home() {
  return (
    <>
      <Header />
      <main className="flex-1">
        <Hero />
        <Products />
        <PromoBanner />
        <HowItWorks />
        <Features />
        <Testimonials />
        <Faq />
        <CallToAction />
      </main>
      <Footer />
      <AnnouncementPopup />
    </>
  );
}
