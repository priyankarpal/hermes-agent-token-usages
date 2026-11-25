# Hermes Token Usage Plugin

## Purpose

See your token usage from the local Hermes database in the terminal. Shows totals, per-model breakdown, and per-session breakdown — all filterable by time window, model, profile, and session.

## Install

```bash
hermes plugins install priyankarpal/hermes-agent-token-usages --enable
```

Update to get new CLI flags:

```bash
hermes plugins update token-usage
```

## Quick Start

```bash
hermes tokens                    # lifetime, daily heatmap, page 1 (10 sessions)
hermes tokens --by month         # 6-month bar chart instead of heatmap
hermes tokens --page 2 --page-size 20   # page 2, 20 sessions per page
hermes tokens --window 30d --by year    # last 3 years, 30-day window
hermes tokens --format json      # JSON output for scripts
```

## CLI Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--window` | `lifetime`, `7d`, `30d`, `90d` | `lifetime` | Time window |
| `--model` | model name | — | Filter to one model |
| `--session` | session ID | — | Drill down into one session |
| `--profile` | profile name | — | Filter to one profile |
| `--format` | `table`, `json` | `table` | Output format |
| `--by` | `day`, `month`, `year` | `day` | Timeline: heatmap / 6-month bars / 3-year bars |
| `--page` | integer | `1` | Sessions page number |
| `--page-size` | integer | `10` | Sessions per page |
| `--width` | integer | terminal | Force terminal width (min 60) |

Invalid page, page-size, or width (< 60) → exit code 2 with one-line message.

## What You See

### 1. Meta Panel
Database path, window, profile, format, and current session (most recent by `last_activity_at`).

### 2. Totals Panel
| Metric | Meaning |
|--------|---------|
| **Sessions** | Count of sessions in window |
| **Input / Output** | Tokens sent to / received from model |
| **Cache Read** | Tokens served from cache |
| **Cache Multiplier** | `cache_read / (input + output) × 100%` — scale (often 1000%+) |
| **Cache Hit Rate** | `cache_read / (cache_read + input) × 100%` — efficiency (0–100%) |
| **Total Tokens** | `input + output` only (excludes cache/read/write/reasoning) |
| **Est. Cost** | `—` if no pricing configured for any model in window |

### 3. Models Table
Per-model breakdown with share bars (`██████░░░░ 64.8%`). Columns drop responsively at narrow widths.

### 4. Timeline (`--by`)
| Mode | What you get |
|------|--------------|
| `--by day` | GitHub-style 12-week heatmap (Mon–Sun), 4 green levels, month labels, legend |
| `--by month` | Last 6 calendar months (incl. zeros) as horizontal share-bar chart |
| `--by year` | Last 3 calendar years (incl. zeros) as horizontal share-bar chart |

### 5. Sessions Table (paginated)
- Current session pinned at top of page 1 with `◂ current` marker (never truncates)
- Sorted by total tokens descending
- Zero-token sessions hidden; counted in footer
- Footer: `Page N of M · rows a–b of T · next: --page N+1 · X with no activity hidden`
- Columns drop responsively: Current (never) → Model → Session ID → others

## Cost Display: Why `—` (em dash)?

The DB stores only cost *totals*, not per-token rates. Without `token_plugin.pricing` config, the plugin shows `—` meaning "not configured" — not a bug. Add pricing for models you want cost estimates:

```yaml
token_plugin:
  pricing:
    "nvidia/nemotron-3.5":
      input_per_1m: 0.15
      output_per_1m: 0.60
```

## Cache Metrics Explained

| Metric | Formula | Range | Meaning |
|--------|---------|-------|---------|
| **Cache Multiplier** | `cache_read / (input + output) × 100%` | 0%–∞ | **Scale** — how many times larger cache reads are than fresh model tokens. Can exceed 100% (often 1000%+). |
| **Cache Hit Rate** | `cache_read / (cache_read + input) × 100%` | 0%–100% | **Efficiency** — what fraction of total token interactions (cache + input) were served from cache. |

**Total Tokens** = `input + output` only (excludes cache/read/write/reasoning).

## Configuration

All under `token_plugin:` in `~/.hermes/config.yaml` (or `TOKEN_PLUGIN_*` env vars):

| Key | Env Var | Default | Description |
|-----|---------|---------|-------------|
| `db_path` | `TOKEN_PLUGIN_DB_PATH` | `~/.hermes/state.db` | SQLite DB (read-only) |
| `default_window` | `TOKEN_PLUGIN_DEFAULT_WINDOW` | `lifetime` | Time window |
| `include_archived` | `TOKEN_PLUGIN_INCLUDE_ARCHIVED` | `false` | Include archived sessions |
| `output_format` | `TOKEN_PLUGIN_OUTPUT_FORMAT` | `table` | `table` or `json` |
| `max_sessions` | `TOKEN_PLUGIN_MAX_SESSIONS` | `50` | Max sessions in breakdown |
| `profile` | `TOKEN_PLUGIN_PROFILE` | — | Profile filter |
| `currency_label` | `TOKEN_PLUGIN_CURRENCY_LABEL` | `USD` | Currency label (no FX) |

Labels are config-driven under `token_plugin.labels:*`; unset falls back to key name.

## Safety

Two independent layers guarantee the Hermes DB is never modified:
1. **URI `mode=ro`** — read-only file descriptor
2. **`PRAGMA query_only = ON`** — SQLite rejects all writes at runtime

Only `SELECT` on `sessions` and `session_model_usage` tables.

## Example

```bash
$ hermes tokens --page 1 --page-size 5 --width 120
```

Outputs: meta panel → totals panel → models table → 12-week heatmap → sessions table (page 1) with pagination footer.