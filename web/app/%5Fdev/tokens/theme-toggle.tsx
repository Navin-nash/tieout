"use client";

import { useTheme } from "next-themes";

// Tiny client island so the proof page can flip light/dark and verify the
// DESIGN.md §12.2 dark overrides live in the same token slots.
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="rounded-sm border border-border-interactive px-3 py-1.5 font-ui text-body-sm font-medium text-ink transition-colors duration-fast ease-standard hover:bg-paper-inset"
    >
      {dark ? "Light theme" : "Dark theme"}
    </button>
  );
}