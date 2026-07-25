# Map frontend

## Local development

1. Start Vite in this directory:

   ```bash
   npm run dev
   ```

2. In a second terminal, start Django with the explicitly enabled local Vite URL:

   ```bash
   VITE_DEV_SERVER_URL=http://127.0.0.1:5173 python manage.py runserver
   ```

The Django tag uses the Vite server only while `DEBUG=True`. Production ignores
`VITE_DEV_SERVER_URL` and loads the built assets from Django static storage.

## Production build

```bash
npm ci
npm run lint
npm test
npm run build
python manage.py collectstatic --noinput
```

`npm run build` writes ignored generated files to `static/map-app/`, including
`manifest.json`, which must exist before `collectstatic`.
