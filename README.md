# Meeting Notes Agent

Extract structured meeting notes from transcripts with a CLI or FastAPI.

## Docker

Build:

```bash
docker build -t meeting-notes-agent .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env meeting-notes-agent
```

Open Swagger at [http://localhost:8000/docs](http://localhost:8000/docs).
