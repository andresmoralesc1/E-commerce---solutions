"use client";
import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {useTranslations} from "next-intl";
import {useAuth} from "@/lib/auth";

export function NavBar({locale}: {locale: string}) {
  const t = useTranslations("nav");
  const path = usePathname();
  const router = useRouter();
  const {setToken} = useAuth();

  const items = [
    {href: `/${locale}`, label: t("dashboard")},
    {href: `/${locale}/products`, label: t("products")},
    {href: `/${locale}/pending`, label: t("pending")},
    {href: `/${locale}/tenants`, label: t("tenants")},
  ];

  const altLocale = locale === "es" ? "en" : "es";
  const altHref = path.replace(`/${locale}`, `/${altLocale}`);

  return (
    <nav className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center gap-4">
      <Link href={`/${locale}`} className="font-semibold text-emerald-400">
        🧠 Ecommerce Brain
      </Link>
      <div className="flex gap-1">
        {items.map((it) => (
          <Link
            key={it.href}
            href={it.href}
            className={`px-3 py-1 rounded text-sm hover:bg-slate-800 ${
              path === it.href ? "bg-slate-800 text-white" : "text-slate-300"
            }`}
          >
            {it.label}
          </Link>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-3 text-sm">
        <Link href={altHref} className="text-slate-400 hover:text-white uppercase">
          {altLocale}
        </Link>
        <button
          onClick={() => {
            setToken(null);
            router.push(`/${locale}/login`);
          }}
          className="text-slate-400 hover:text-rose-400"
        >
          {t("logout")}
        </button>
      </div>
    </nav>
  );
}