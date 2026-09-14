import {redirect} from "next/navigation";
import {setRequestLocale} from "next-intl/server";
import {LoginForm} from "./LoginForm";

export default async function LoginPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  setRequestLocale(locale);
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <LoginForm locale={locale} />
    </main>
  );
}