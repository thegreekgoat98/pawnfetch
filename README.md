# pawnfetch

A command-line tool to fetch and compare chess.com player profiles and stats,
built on chess.com's public [PubAPI](https://www.chess.com/news/view/published-data-api).

## Installation

```bash
pip install pawnfetch
# or
uv add pawnfetch
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

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/thegreekgoat98/pawnfetch.git
cd pawnfetch
uv sync
uv run pawnfetch profile hikaru
```

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