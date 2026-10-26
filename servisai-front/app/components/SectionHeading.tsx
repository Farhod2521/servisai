export default function SectionHeading({
  badge,
  title,
  subtitle,
}: {
  badge: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="text-center">
      <span className="inline-block rounded-full bg-brand-soft px-4 py-1 text-xs font-semibold text-brand">
        {badge}
      </span>
      <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2>
      {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
    </div>
  );
}
