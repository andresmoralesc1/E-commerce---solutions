import {setRequestLocale} from "next-intl/server";
import {NavBar} from "@/components/NavBar";
import {OnboardingWizard} from "@/components/OnboardingWizard";
import {DashboardClient} from "./DashboardClient";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  setRequestLocale(locale);
  return (
    <div className="min-h-screen">
      <NavBar locale={locale} />
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <OnboardingWizard locale={locale} />
        <DashboardClient />
      </main>
    </div>
  );
}