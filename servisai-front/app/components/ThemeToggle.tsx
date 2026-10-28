"use client";

import { Moon, Sun } from "./icons";

export const THEME_KEY = "servisai_theme";

/** Sahifa chizilishidan oldin ishlaydi (layout <head>): saqlangan mavzuni qo‘llaydi, oq-qora “miltillash” bo‘lmaydi */
export const themeInitScript = `try{if(localStorage.getItem("${THEME_KEY}")==="dark")document.documentElement.classList.add("dark")}catch(e){}`;

/** Oq / qora rejim tugmasi. Holat <html class="dark"> da, ikonka CSS orqali almashadi */
export default function ThemeToggle({ className = "", withLabel = false }: { className?: string; withLabel?: boolean }) {
  const toggle = () => {
    const dark = document.documentElement.classList.toggle("dark");
    try {
      localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
    } catch {
      /* private rejim — faqat shu tashrif uchun */
    }
  };

  return (
    <button
      onClick={toggle}
      aria-label="Oq / qora rejim"
      title="Oq / qora rejim"
      className={
        withLabel
          ? `flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-brand-soft hover:text-brand ${className}`
          : `size-10 place-items-center rounded-lg text-slate-700 hover:bg-slate-100 ${className || "grid"}`
      }
    >
      <Moon className={`dark:hidden ${withLabel ? "size-4.5" : "size-5"}`} />
      <Sun className={`hidden dark:block ${withLabel ? "size-4.5" : "size-5"}`} />
      {withLabel && (
        <>
          <span className="dark:hidden">Qorong‘i rejim</span>
          <span className="hidden dark:inline">Yorug‘ rejim</span>
        </>
      )}
    </button>
  );
}
