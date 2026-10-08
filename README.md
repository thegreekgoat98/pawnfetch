# pawnfetch

A command-line tool to fetch and compare chess.com player profiles and stats,
built on chess.com's public [PubAPI](https://www.chess.com/news/view/published-data-api).

## Installation

Once the first release is available on PyPI, install `pawnfetch` with
[pipx](https://pipx.pypa.io/) or [uv](https://docs.astral.sh/uv/):

```bash
pipx install pawnfetch
# or
uv tool install pawnfetch
```

Until then, install the current version directly from GitHub:

```bash
uv tool install git+https://github.com/thegreekgoat98/pawnfetch.git
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
uv run pytest
```

Lint:
```bash
uv run ruff check .
```

## License

MIT