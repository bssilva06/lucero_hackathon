# Lucero Frontend

Professional, citation-first bilingual immigration research interface.

## Running

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173. Backend must be running on port 8080.

## Environment

Copy `.env.example` to `.env.local` to override the API base:

```
VITE_API_BASE_URL=http://127.0.0.1:8080
```

## Layout

- **Left pane** — chat transcript and composer (Enter to send, Shift+Enter for newline)
- **Right pane** — source detail panel; click any citation chip to open
- **Tool trace** — collapsible accordion above the composer showing per-turn tool calls
- **Footer** — persistent practitioner disclaimer

## Build

```bash
npm run build    # production bundle → dist/
npm run preview  # serve dist/ locally
```
