# Token Usage Analytics

Token usage analytics for the local Hermes database. Reads `~/.hermes/state.db` and renders session, model, and aggregate token reports.

## Language

**Session**:
A single conversation session in Hermes, identified by a unique session ID. Contains aggregated token counts across all models used in that session.
_Avoid_: Conversation, chat, thread

**Model Usage**:
Aggregated token statistics for a specific model within a time window or session. Includes input, output, cache read/write, and reasoning tokens.
_Avoid_: Model stats, model metrics

**Cache Multiplier**:
Ratio of cache-read tokens to model tokens (input + output), expressed as a percentage. Values > 100% indicate cache reads exceed fresh model tokens.
_Avoid_: Cache ratio (ambiguous)

**Cache Hit Rate**:
Percentage of total token interactions served from cache: `cache_read / (cache_read + input_tokens) * 100%`. Range 0–100%.
_Avoid_: Cache efficiency, cache percentage

**Timeline Bucket**:
A time-slice aggregation (hour/day/month) of token usage across all sessions in that period.
_Avoid_: Time bucket, period

**Pricing Entry**:
Per-1M-token cost configuration for a specific model or model prefix. Used to estimate USD cost. Absence means cost is unknown (`n/a`).
_Avoid_: Price config, rate card

**Total Tokens**:
Sum of input tokens and output tokens only. Excludes cache read, cache write, and reasoning tokens.
_Avoid_: All tokens, aggregate tokens

**Current Session**:
The most recent active session by `last_activity_at`. Pinned at the top of the sessions table with a "◂ current" marker in the Current column.
_Avoid_: Active session, latest session

**Period**:
A time grouping for usage analytics: day (daily heatmap), month (6-month bar chart), or year (3-year bar chart). Selected via `--by day|month|year`.
_Avoid_: Granularity, time window, interval

**Heatmap**:
GitHub-style 12-week contribution grid (Monday–Sunday) showing daily token totals with 4 green intensity levels. Cells after today are blank. Month labels above never overlap.
_Avoid_: Calendar grid, activity map

**Pagination**:
Sessions table split into pages of configurable size (default 10). Footer shows "Page N of M · rows a–b of T · next: --page N+1". Current session pinned to page 1. Zero-token sessions excluded from pagination and counted in footer.
_Avoid_: Paging, page splitting