import type { Metadata } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import { statement, ui, numeral } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Tieout — audit-grade reconciliation",
    template: "%s · Tieout",
  },
  description:
    "Reconciliation that refuses to fake it. Deterministic matching, staged automation, and a ledger-ruled review surface.",
};

const THEME_SCRIPT = `(function(){try{var d=document.documentElement;var t=localStorage.getItem("tieout-theme");if(t==="dark"||(!t&&window.matchMedia("(prefers-color-scheme: dark)").matches))d.classList.add("dark")}catch(e){}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${statement.variable} ${ui.variable} ${numeral.variable} h-full antialiased`}
    >
      <head>
        {/* Applies the persisted/OS theme before first paint so there is no
            flash of the wrong theme. Light is the primary per DESIGN.md §4. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">
        {/* storageKey must match the key THEME_SCRIPT reads above, or the
            anti-flash script restores nothing on reload. */}
        <ThemeProvider
          attribute="class"
          storageKey="tieout-theme"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}