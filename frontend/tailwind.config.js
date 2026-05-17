import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      typography: ({ theme }) => ({
        slate: {
          css: {
            "--tw-prose-body": theme("colors.slate.200"),
            "--tw-prose-headings": theme("colors.white"),
            "--tw-prose-lead": theme("colors.slate.300"),
            "--tw-prose-links": theme("colors.blue.400"),
            "--tw-prose-bold": theme("colors.white"),
            "--tw-prose-counters": theme("colors.slate.400"),
            "--tw-prose-bullets": theme("colors.slate.500"),
            "--tw-prose-hr": theme("colors.slate.800"),
            "--tw-prose-quotes": theme("colors.slate.100"),
            "--tw-prose-quote-borders": theme("colors.slate.700"),
            "--tw-prose-captions": theme("colors.slate.400"),
            "--tw-prose-code": theme("colors.amber.200"),
            "--tw-prose-pre-code": theme("colors.slate.100"),
            "--tw-prose-pre-bg": theme("colors.slate.900"),
            "--tw-prose-th-borders": theme("colors.slate.700"),
            "--tw-prose-td-borders": theme("colors.slate.800"),
          },
        },
      }),
    },
  },
  plugins: [typography],
};
