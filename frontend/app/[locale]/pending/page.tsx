import {setRequestLocale} from "next-intl/server";
import {NavBar} from "@/components/NavBar";
import {PendingClient} from "./PendingClient";

export default async function PendingPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  setRequestLocale(locale);
  return (
    <div className="min-h-screen">
      <NavBar locale={locale} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        <PendingClient />
      </main>
    </div>
  );
}