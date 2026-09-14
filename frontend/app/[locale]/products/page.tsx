import {setRequestLocale} from "next-intl/server";
import {NavBar} from "@/components/NavBar";
import {ProductsClient} from "./ProductsClient";

export default async function ProductsPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  setRequestLocale(locale);
  return (
    <div className="min-h-screen">
      <NavBar locale={locale} />
      <main className="max-w-7xl mx-auto px-4 py-6">
        <ProductsClient />
      </main>
    </div>
  );
}