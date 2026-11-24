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