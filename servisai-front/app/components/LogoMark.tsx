import Image from "next/image";
import mark from "@/public/logo-mark.png";

/** servisai.uz "S" belgisi (rang-barang, shaffof fonli). O‘lcham balandlik bilan beriladi: `className="h-8 w-auto"` */
export default function LogoMark({ className = "h-8 w-auto", preload }: { className?: string; preload?: boolean }) {
  return <Image src={mark} alt="" aria-hidden preload={preload} sizes="96px" className={className} />;
}
