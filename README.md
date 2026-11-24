# Hermes Token Usage Plugin

## Purpose

Surface token usage from the local Hermes database directly in the CLI.
Produces lifetime totals, a per-model breakdown, and a per-session breakdown,
all filterable by time window, model, profile, and session. All user-facing
labels are config-driven; nothing is hardcoded.

## CLI Interface

Install:

```bash
hermes plugins install priyankarpal/hermes-agent-token-usages --enable
```

If you already had the plugin installed, update it so Hermes picks up the new CLI arguments:

```bash
hermes plugins update token-usage
```

Invoke:

```bash
hermes tokens [--window 7d|30d|90d|lifetime] [--model <model>] [--session <id>] [--format table|json] [--profile <profile>] [--timeline hour|day|month]
```

| Argument | Values | Meaning |
|----------|--------|---------|
| `--window` | `lifetime`, `7d`, `30d`, `90d` | Time window for aggregation |
| `--model` | <model name> | Filter to a specific model |
| `--session` | <session id> | Drill down into one session's model/billing rows |
| `--profile` | <profile_name> | Filter to a specific profile |
| `--format` | `table`, `json` | Output format |
| `--timeline` | `hour`, `day`, `month` | Show usage timeline grouped by time bucket with a simple bar chart |

## Feature 1: Current session

Every normal report identifies the **current session** — the most recent
active session by `last_activity_at`. It appears:

* In the report header/meta section (`Current Session` row).
* In the per-session table, pinned at the top with a `●` prefix on the session id.
* In JSON output under the `current_session` key.

## Feature 2: Token Usage Timeline

`--timeline hour|day|month` groups sessions into time buckets and renders a
simple ASCII bar chart of total tokens per bucket, ordered chronologically.
Use it to spot usage patterns over time:

```bash
hermes tokens --timeline day     # usage per day
hermes tokens --timeline hour    # usage per hour
hermes tokens --timeline month   # usage per month
```

In JSON output, the timeline appears under `timeline_granularity` and
`timeline_buckets`.

## Configuration

All configuration lives under `token_plugin:` in `~/.hermes/config.yaml`
(or `TOKEN_PLUGIN_*` environment variables):

| Config key | Env var | Default | Description |
|------------|---------|---------|-------------|
| `token_plugin.db_path` | `TOKEN_PLUGIN_DB_PATH` | `~/.hermes/state.db` | Path to the Hermes state SQLite database (read-only). |
| `token_plugin.default_window` | `TOKEN_PLUGIN_DEFAULT_WINDOW` | `lifetime` | Default time window. |
| `token_plugin.include_archived` | `TOKEN_PLUGIN_INCLUDE_ARCHIVED` | `false` | Include archived sessions in totals. |
| `token_plugin.output_format` | `TOKEN_PLUGIN_OUTPUT_FORMAT` | `table` | `table` or `json`. |
| `token_plugin.max_sessions` | `TOKEN_PLUGIN_MAX_SESSIONS` | `50` | Max sessions to list in the per-session breakdown. |
| `token_plugin.profile` | `TOKEN_PLUGIN_PROFILE` | `` | Optional `profile_name` filter applied to all queries. |
| `token_plugin.currency_label` | `TOKEN_PLUGIN_CURRENCY_LABEL` | `USD` | Currency label for cost columns (USD only; no FX conversion). |

Labels and column headers are config-driven under `token_plugin.labels:*`; unset
labels fall back to the key name itself.

## Pricing

The DB stores claimed cost **totals**, not per-token **rates**, so the plugin
never fabricates a `USD 0.0000` price:

* When `token_plugin.pricing` has an entry for the model (exact match, else the
  longest configured prefix match), estimated cost is computed per model as
  `(input_tokens / 1M) × input_per_1m + (output_tokens / 1M) × output_per_1m`,
  and per-model costs sum exactly to the window total.
* When no pricing entry exists for a model, its cost shows `—` (em dash) — honest
  rather than a fabricated `USD 0.0000`. The window total shows `—` if any
  model in it lacks pricing.

| Config key | Env var | Default | Description |
|------------|---------|---------|-------------|
| `token_plugin.pricing.<model>.input_per_1m` | `TOKEN_PLUGIN_PRICING_<MODEL>_INPUT_PER_1M` | — | Estimated USD per 1M input tokens for `<model>`. |
| `token_plugin.pricing.<model>.output_per_1m` | `TOKEN_PLUGIN_PRICING_<MODEL>_OUTPUT_PER_1M` | — | Estimated USD per 1M output tokens for `<model>`. |

Model names match exactly, or by longest configured prefix (e.g.
`nvidia/nemotron-3.5` covers all that provider's models). Pricing is per-user
config; there is no shared price list. Add pricing only for the models you
actually want priced — everything else stays `—`.

### Future: opt-in provider API (not implemented)

A future option is an opt-in `token_plugin.pricing_source` config pointing at a
billing endpoint the plugin polls for per-model rates. That is deliberately
**not** implemented here: it breaks the plugin's no-network guarantee, and the
DB holds no rates to derive them from. Leave `token_plugin.pricing` unset and
cost columns will show `—` until you opt in.

## Database

Reads only from `~/.hermes/state.db`. Two independent safety layers guarantee
the Hermes state database is never written, locked, or modified:

1. **URI `mode=ro`** — the database is opened with a read-only file descriptor,
   so SQLite cannot write at the OS level.
2. **`PRAGMA query_only = ON`** — SQLite rejects every INSERT/UPDATE/DELETE/
   CREATE/DROP/ALTER statement at runtime.

Only `SELECT` statements are executed. Tables used: `sessions` and
`session_model_usage`. Never writes to the database.

## Example output

Running `hermes tokens` (default `lifetime` window, `table` format):

```text
┌─────────────────────┬──────────────────────────────────────────────────────────────┐
│ Key                 │ Value                                                        │
├─────────────────────┼──────────────────────────────────────────────────────────────┤
│ Database            │ ~/.hermes/state.db                                           │
│ Window              │ Lifetime                                                     │
│ Profile             │ —                                                            │
│ Format              │ table                                                        │
│ Current Session     │ local-35698ebdf3020f2cb… (nvidia/nemotron-3-ultra-550b-a55b) │
└─────────────────────┴──────────────────────────────────────────────────────────────┘

Sessions:           33
Input Tokens:       22.4M
Output Tokens:      1.7M
Cache Read:         773.3M
Cache Multiplier:   3204.3%
Cache Hit Rate:     97.2%
Cache Write:        0
Reasoning:          792.6K
Total Tokens:       24.1M
API Calls:          4.3K
Est. Cost (USD):    —
Actual Cost (USD):  —

┌─────────────────────────────────────────────┬──────────┬──────────────┬──────────────┬──────────────────┐
│ Model                                       │ Sessions │ Input Tokens │ Total Tokens │ Share %          │
├─────────────────────────────────────────────┼──────────┼──────────────┼──────────────┼──────────────────┤
│ nvidia/nemotron-3-ultra-550b-a55b           │ 22       │ 14.4M        │ 15.1M        │ ██████░░░░ 62.4% │
│ nvidia/nemotron-3.5-super-vl-120b-a12b      │ 14       │ 6.6M         │ 7.6M         │ ███░░░░░░░ 31.5% │
│ upstage/solar-mini4:free                    │ 2        │ 1.4M         │ 1.4M         │ ░░░░░░░░░░ 5.9%  │
│ private/nvidia/nemotron-3.5-super-120b-a12b │ 6        │ 38.6K        │ 38.9K        │ ░░░░░░░░░░ 0.2%  │
│ m1                                          │ 1        │ 1.0K         │ 1.5K         │ ░░░░░░░░░░ 0.0%  │
└─────────────────────────────────────────────┴──────────┴──────────────┴──────────────┴──────────────────┘

┌──────────────────────────┬────────────────────────────────────────┬──────────────────┬──────────────────┬──────────────┬───────────┐
│ Session ID               │ Model                                  │ Started At       │ Last Activity    │ Input Tokens │ Reasoning │
├──────────────────────────┼────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────┼───────────┤
│ ● local-35698ebdf3020f2… │ nvidia/nemotron-3-ultra-550b-a55b      │ 2026-11-24 19:27 │ 2026-11-24 20:46 │ 1.7M         │ 23.6K     │
│ local-4dab01080b6ed33eb… │ nvidia/nemotron-3-ultra-550b-a55b      │ 2026-11-24 11:38 │ 2026-11-24 16:09 │ 6.5M         │ 77.3K     │
│ local-77de9ef9933610a25… │ nvidia/nemotron-3-ultra-550b-a55b      │ 2026-11-23 14:38 │ 2026-11-23 16:59 │ 4.5M         │ 199.1K    │
│ local-142e773f7065e7e62… │ nvidia/nemotron-3-ultra-550b-a55b      │ 2026-11-20 16:46 │ 2026-11-20 17:53 │ 2.5M         │ 68.8K     │
│ local-47f25150e14fb6ad2… │ nvidia/nemotron-3.5-super-vl-120b-a12b │ 2026-11-21 11:58 │ 2026-11-21 13:15 │ 2.4M         │ 94.8K     │
│ local-2ed2adad81bd09d55… │ nvidia/nemotron-3.5-super-vl-120b-a12b │ 2026-11-19 15:59 │ 2026-11-19 16:58 │ 1.0M         │ 182.5K    │
│ local-19bd2f52f4b69a032… │ nvidia/nemotron-3.5-super-vl-120b-a12b │ 2026-11-19 13:46 │ 2026-11-19 15:01 │ 880.4K       │ 63.6K     │
└──────────────────────────┴────────────────────────────────────────┴──────────────────┴──────────────────┴──────────────┴───────────┘
```

The per-session table lists the top sessions by total token count, capped at
`max_sessions` (default 50). The **current session is pinned at the top** with a `●` prefix.

The report surfaces two cache metrics:
- **Cache Multiplier** = `cache_read / (input + output) × 100%` — shows scale (can exceed 100%)
- **Cache Hit Rate** = `cache_read / (cache_read + input) × 100%` — shows efficiency (0–100%)

The per-model table includes **Share %** with visual bars (`██████░░░░ 62.4%`) showing each model's share of total tokens.

## Colour & Responsive Layout

* **Colours** appear only when stdout is a TTY and `NO_COLOR` is not set. Piped output stays clean for scripts/logs.
* **Responsive tables** automatically drop lower-priority columns to fit your terminal width (tested at 80/100/120/140/160/180/200 columns).

## Configuration (labels)

All labels and column headers are config-driven under `token_plugin.labels:*` in `~/.hermes/config.yaml` (or `TOKEN_PLUGIN_LABELS_*` env vars). Unset labels fall back to the key name.

## Module layout

| Module | Responsibility |
|--------|----------------|
| `__init__.py` | Package entry; exports `register(ctx)` |
| `plugin.py` | Hermes plugin registration (`register_cli_command`) |
| `config.py` | Config loading (`config.yaml` / `TOKEN_PLUGIN_*` env) |
| `db.py` | Read-only SQLite connection (`mode=ro`) |
| `domain.py` | Entities + value objects (Session, ModelUsage, Window, Currency, UsageReport) |
| `service.py` | Report use case: DB queries + `TokenUsageService` |
| `render.py` | Formatters + text/JSON rendering (pure functions, testable in isolation) |
| `cli.py` | Argparse + CLI handler + backward-compatible `run(ns, cfg)` |

## Requirements

* Python stdlib only (`sqlite3`, `argparse`, `json`, `shutil`).
* PyYAML is used when available (already a Hermes dependency); a small
  built-in fallback parser handles simple config files.