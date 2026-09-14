import {defineRouting} from "next-intl/routing";
import {getRequestConfig} from "next-intl/server";

export const routing = defineRouting({
  locales: ["es", "en"],
  defaultLocale: "es",
  localePrefix: "always",
});

export default getRequestConfig(async ({requestLocale}) => {
  let locale = await requestLocale;
  if (!locale || !routing.locales.includes(locale as (typeof routing.locales)[number])) {
    locale = routing.defaultLocale;
  }
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});