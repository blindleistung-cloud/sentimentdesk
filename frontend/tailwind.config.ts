import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}", "./node_modules/@tremor/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "oklch(var(--sd-ink) / <alpha-value>)",
        paper: "oklch(var(--sd-paper) / <alpha-value>)",
        accent: "oklch(var(--sd-accent) / <alpha-value>)",
        accentSoft: "oklch(var(--sd-accent-soft) / <alpha-value>)",
        fog: "oklch(var(--sd-fog) / <alpha-value>)",
        warning: "oklch(var(--sd-warning) / <alpha-value>)",
      },
      fontFamily: {
        display: ["\"Space Grotesk\"", "\"IBM Plex Sans\"", "sans-serif"],
        body: ["\"Work Sans\"", "\"IBM Plex Sans\"", "sans-serif"],
      },
      boxShadow: {
        glow: "0 20px 60px -30px rgba(16, 64, 96, 0.6)",
        card: "0 20px 40px -32px rgba(15, 23, 42, 0.55)",
      },
      borderRadius: {
        xl: "20px",
      },
    },
  },
  plugins: [],
};

export default config;
