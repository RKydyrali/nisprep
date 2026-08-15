import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#047857",
          hover: "#065F46",
          soft: "#D1FAE5",
        },
        accent: {
          DEFAULT: "#F59E0B",
          soft: "#FEF3C7",
        },
        danger: {
          DEFAULT: "#DC2626",
          soft: "#FEE2E2",
        },
        surface: "#F8FAFC",
        ink: "#0F172A",
        muted: "#64748B",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      keyframes: {
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-soft": "pulse-soft 1s ease-in-out infinite",
        "fade-in-up": "fade-in-up 0.25s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
