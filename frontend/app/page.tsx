import {redirect} from "next/navigation";
import {routing} from "@/i18n";

export default function RootPage() {
  redirect(`/${routing.defaultLocale}`);
}