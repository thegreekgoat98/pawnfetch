# pawnfetch

A command-line tool to fetch and compare chess.com player profiles and stats,
built on chess.com's public [PubAPI](https://www.chess.com/news/view/published-data-api).

## Installation

Install the latest release from PyPI with [pipx](https://pipx.pypa.io/) or
[uv](https://docs.astral.sh/uv/) to use the CLI in an isolated environment:

```bash
pipx install pawnfetch
# or
uv tool install pawnfetch
```

To install into an existing Python environment instead:

```bash
pip install pawnfetch
```

## Usage

### Look up a profile
```bash
pawnfetch profile hikaru
```

### Check ratings and win/loss record
```bash
pawnfetch stats hikaru
```

### Compare two players
```bash
pawnfetch compare hikaru magnuscarlsen
```

The `pftch` command is also available as a shorter alias. For example:

```bash
pftch profile hikaru
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/thegreekgoat98/pawnfetch.git
cd pawnfetch
uv sync
uv run pawnfetch profile hikaru
```

Chess.com PubAPI data may be cached for up to 12 hours and may not reflect
recent changes immediately. Avoid parallel requests; Chess.com may rate-limit
them with HTTP 429.

Run tests:
```bash
uv sync --all-groups   # includes the web dependencies; web tests are skipped without them
uv run pytest
```

Lint:
```bash
uv run ruff check .
```

### Website (work in progress)

The repo also contains a FastAPI + Jinja2 + HTMX + Tailwind site in `web/`. It is not
part of the PyPI package. To run it locally:

```bash
uv sync --group web
uv run uvicorn web.app.main:app --reload
```

Then open http://127.0.0.1:8000. Styles are built with the
[Tailwind standalone CLI](https://github.com/tailwindlabs/tailwindcss/releases) into
`web/app/static/css/app.css`, which is committed:

```bash
tailwindcss -i web/app/static/css/input.css -o web/app/static/css/app.css --minify
```

## Disclaimer

pawnfetch is an independent project and is not affiliated with or endorsed by Chess.com.

## License

MIT