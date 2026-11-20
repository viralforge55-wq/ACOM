import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF9F6",
        surface: "#FFFFFF",
        ink: "#141413",
        muted: "#57554F",
        line: "#E5E2DC",
        accent: "#1F4E3D",
        "accent-hover": "#163B2E",
        callout: "#F4EFE4",
      },
    },
  },
  plugins: [],
};

export default config;
