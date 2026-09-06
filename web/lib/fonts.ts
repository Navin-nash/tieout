// DESIGN.md §3.1 — families, licensing, hosting. Values and structure come
// verbatim from DESIGN.md; all three families are SIL OFL 1.1 and self-hosted
// via next/font/google (woff2 downloaded at build time, served from this
// origin — no runtime request to fonts.googleapis.com).
import { Source_Serif_4, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";

export const statement = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-statement",
  display: "swap",
});

export const ui = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ui",
  display: "swap",
});

export const numeral = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-numeral",
  display: "swap",
});