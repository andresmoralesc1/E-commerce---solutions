import {setRequestLocale} from "next-intl/server";
import {NavBar} from "@/components/NavBar";
import {TenantsClient} from "./TenantsClient";

export default async function TenantsPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  setRequestLocale(locale);
  return (
    <div className="min-h-screen">
      <NavBar locale={locale} />
      <main className="max-w-3xl mx-auto px-4 py-6">
        <TenantsClient />
      </main>
    </div>
  );
}