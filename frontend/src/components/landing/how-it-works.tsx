import { SectionKicker } from "@/components/landing/section-kicker";
import { t } from "@/lib/i18n";

const steps = [
  ["01", "landingHowFindTitle", "landingHowFindBody"],
  ["02", "landingHowCheckTitle", "landingHowCheckBody"],
  ["03", "landingHowTrackTitle", "landingHowTrackBody"],
] as const;

export function HowItWorks({ n }: { n: number }) {
  return (
    <section>
      <SectionKicker n={n} label={t("landingHowKicker")} />
      <h2 className="mt-3 max-w-xl text-3xl font-semibold tracking-[-0.03em] text-balance">{t("landingHowTitle")}</h2>
      <ol className="mt-10 grid gap-10 md:grid-cols-3">
        {steps.map(([number, title, body]) => (
          <li key={number} className="border-t-2 border-foreground pt-4">
            <p className="font-mono text-sm tabular-nums">{number}</p>
            <h3 className="mt-4 text-lg font-semibold">{t(title)}</h3>
            <p className="mt-2 text-sm leading-6 text-foreground/80">{t(body)}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
