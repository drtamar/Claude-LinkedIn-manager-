/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        linkedin: {
          blue: "#0077B5",
          dark: "#004471",
          light: "#E8F4FD",
        },
      },
    },
  },
  plugins: [],
}

