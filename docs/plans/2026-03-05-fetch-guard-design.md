# RLM Fetch Guard Design

## Problem
WebFetch dumps raw fetched content into context, defeating RLM's purpose. No interception exists.

## Solution

### 1. Hook expansion (`pretooluse-rlm.mjs`)
- Add `WebFetch` to matcher: `"Read|Bash|WebFetch"`
- Block WebFetch with `decision: "block"` + pre-built Python fetch command
- Node 12+ compatibility: no optional chaining, no top-level await, classic syntax

### 2. Python fetch utility (`src/fetch.py`)
- `fetch.py <url> [-o output_path] [--headers key:val]`
- Uses `requests` with fallback to `urllib.request`
- Saves response to temp file, prints only metadata (status, content-type, size, path)

### 3. Hook block output format
```json
{
  "decision": "block",
  "reason": "[RLM] WebFetch dumps raw content into context. Use Python fetch instead:\n\npython fetch.py <url> -o /tmp/rlm_fetch.json\n\nThen process the file with python3 -c and print only what you need."
}
```

### 4. Version bump to 0.2.0

## Files
- `hooks/hooks.json` — add WebFetch to matcher
- `hooks/pretooluse-rlm.mjs` — add handleWebFetch(), Node 12+ compat rewrite
- `src/fetch.py` — new file
- `pyproject.toml` — version 0.2.0
