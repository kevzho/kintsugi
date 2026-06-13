# Kintsugi — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind + shadcn-style UI + Recharts.

## Local development

```bash
npm install
cp .env.example .env.local   # point NEXT_PUBLIC_API_URL at your backend
npm run dev                  # http://localhost:3000
```

The backend base URL is read from `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

## Build

```bash
npm run build
npm start
```

## Deploy (Vercel)

1. Import the repo into Vercel and set the project root to `frontend/`.
2. Add an environment variable `NEXT_PUBLIC_API_URL` = your Render backend URL.
3. Deploy. `vercel.json` already configures the Next.js framework preset.
