# jobs-retrieval-bot

A weekly email of up to 25 high-quality roles, plus companies worth reaching out to, matched to one
person's resume and preferences. Roles are limited to NYC and the SF Bay Area for now.

Phase 0 (this state of the repo) is the foundation only:
- the `jobs` command with stub subcommands and shared flags
- layered config with safety rules
- record/replay for API calls
- spending caps
- run logging
- the full database schema
- CI

None of the subcommands fetches jobs, ranks or sends digests yet; each one tells you which phase builds it.

## Local setup

You need Python 3.12, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync
cp .env.example .env              # then edit: JOBBOT_ALLOWED_EMAILS, JOBBOT_EMAIL_TEST_TO
docker compose up -d db           # Postgres 16 + pgvector on localhost:5432
uv run alembic upgrade head       # creates the app schema and seeds the allowed emails
uv run pytest                     # creates a separate jobbot_test database automatically
uv run pre-commit install
uv run jobs --help
```

## Supabase (production database)

1. Create a project in the same region you'll deploy to (for example US West).
2. **Database → Extensions:** enable `vector`.
3. **Project Settings → Database → Connection string:**
   - Copy the **Transaction pooler** string (port 6543) into `JOBBOT_DATABASE_URL`.
   - Copy the **Direct connection** string (port 5432) into `JOBBOT_DATABASE_URL_DIRECT`.
4. Run the migrations against Supabase from your machine:
   ```bash
   JOBBOT_ENV=prod uv run alembic upgrade head
   ```

Tables live in the `app` schema, which Supabase's REST API does not expose. Row-level security is on
for every table with no policies, so the public API roles can't read anything even if the schema is
exposed later.

## Resend (email)

1. Add a sending subdomain such as `mail.yourdomain.com` in Resend.
2. Add the SPF, DKIM and DMARC DNS records Resend shows, and wait for the domain to show as verified.
3. Put the API key in `JOBBOT_RESEND_API_KEY` and set `JOBBOT_EMAIL_FROM`, for example
   `Shortlist <digest@mail.yourdomain.com>`.
4. Check the setup with `uv run jobs admin test-email`.

## The `jobs` command

Every pipeline subcommand accepts the same shared flags:

| Flag | Effect |
|---|---|
| `--dry-run` | No database writes, no emails, no paid lookups; prints what happened |
| `--no-llm` | Rules only; any AI call is refused |
| `--fixtures DIR` / `--record-fixtures DIR` | Replay saved API responses, or record live ones (secrets stripped) |
| `--database-url URL` | Use another database, e.g. a test project |
| `--llm-budget USD` / `--max-paid-lookups N` | Spending caps for this run |
| `--sample N --seed S` | Process a reproducible random subset |
| `--output table\|json` | Output format |
| `--yes` | Skip the confirmation when a non-prod run points at a remote database |

Commands also take their own limit flags, such as `--limit-companies`, `--limit-jobs`,
`--jobs-per-company`, `--max-roles` and `--max-prospects`. `digest` also accepts `--to` and `--preview`.

```bash
uv run jobs ingest --company ramp.com --jobs-per-company 5 --dry-run
uv run jobs admin allow-email you@example.com
uv run jobs admin test-email --preview previews/test.html
uv run jobs runs list --last 10
```

## Safety rules

- Outside `JOBBOT_ENV=prod`, email only goes to `JOBBOT_EMAIL_TEST_TO`, the `--to` address, or an
  HTML preview file.
- Paid lookups default to 0. Only `config.prod.toml` raises the cap.
- `--dry-run` overrides everything: no writes, no emails, no paid calls.
- Running with a non-prod `JOBBOT_ENV` against a remote database asks for confirmation first.

## Config precedence

Highest first:
1. command flags
2. environment variables
3. `.env`
4. `config.<env>.toml`
5. `config.toml`

Secrets only go in environment variables or `.env`, never in the toml files.
