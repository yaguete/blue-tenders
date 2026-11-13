export type ThemeMode = "system" | "light" | "dark";

export const THEME_KEY = "blue-tender-theme";

export const THEME_BOOT_SCRIPT = `(function(){try{var k=localStorage.getItem("${THEME_KEY}");var dark=k==="dark"||(k!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",dark);}catch(e){}})();`;

export function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system";
}

export function applyTheme(mode: ThemeMode) {
  const dark =
    mode === "dark" ||
    (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function setTheme(mode: ThemeMode) {
  window.localStorage.setItem(THEME_KEY, mode);
  applyTheme(mode);
  window.dispatchEvent(new Event("blue-tender-theme"));
}
