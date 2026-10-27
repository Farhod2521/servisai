import { Fragment } from "react";

const URL_RE = /(https?:\/\/[^\s<>"']+)/g;

/** Matndagi http(s) havolalarni bosiladigan qiladi (yetkazilgan ma’lumotlar uchun). Qator ko‘chishlari saqlanadi. */
export default function Linkify({ text }: { text: string }) {
  return (
    <>
      {text.split(URL_RE).map((part, i) =>
        i % 2 === 1 ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="font-semibold underline underline-offset-2 break-all">
            {part}
          </a>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}
