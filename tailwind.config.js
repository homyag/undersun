/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./*/templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#2c5aa0',
        'secondary': '#f8f9fa',
        'accent': '#ffc107',
      },
    },
  },
  plugins: [],
}