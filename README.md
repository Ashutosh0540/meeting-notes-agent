# Meeting Notes Agent

Extract structured meeting notes from transcripts with a CLI or FastAPI.

## Docker

Build:

```bash
docker build -t meeting-notes-agent .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env -e PORT=8000 meeting-notes-agent
```

Open Swagger at [http://localhost:8000/docs](http://localhost:8000/docs).

## Render

Create a new Web Service, connect `Ashutosh0540/meeting-notes-agent`, and use its
Dockerfile. Set `GROQ_API_KEY`, `GROQ_MODEL`, and `LLM_PROVIDER` in Render's
environment configuration, then deploy. Render uses `/health` for health checks.

## Supabase PostgreSQL

Create a Supabase project, copy its PostgreSQL connection string, and set it as
`DATABASE_URL` in your local `.env`. Set the same environment variable in Render
when you are ready to deploy persistence.

For Docker environments without IPv6 connectivity, use Supabase's Session Pooler
connection URI for `DATABASE_URL`; direct database URIs remain suitable for local
development when reachable.
