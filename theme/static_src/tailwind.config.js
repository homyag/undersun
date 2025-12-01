module.exports = {
    content: [
        '../templates/**/*.html',
        '../../templates/**/*.html',
        '../../apps/**/templates/**/*.html',
        '../../static/js/**/*.js',
        '../../staticfiles/js/**/*.js',
    ],
    theme: {
        extend: {
            colors: {
                primary: '#474B57',
                primaryDark: '#333847',
                secondary: '#f8f9fa',
                accent: '#F1B400',
                tertiary: '#616677',
            },
            fontFamily: {
                sans: ['Gilroy', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
                gilroy: ['Gilroy', 'sans-serif'],
            },
        },
    },
    plugins: [
        require('@tailwindcss/forms'),
        require('@tailwindcss/typography'),
        require('@tailwindcss/aspect-ratio'),
    ],
}
