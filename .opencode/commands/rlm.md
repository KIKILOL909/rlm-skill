Use the RLM 6-step structured protocol for this task. Instead of reading large data into context, explore it programmatically through: METADATA -> PEEK -> SEARCH -> ANALYZE -> SYNTHESIZE -> SUBMIT.

Key principle: **Tokens are CPU, not storage.** Never dump raw data into context.

For the user's request "$ARGUMENTS":

1. **METADATA**: Assess file — type, size, lines, 200-char preview via `python3 -c` (or `python -c` on Windows). Use **glob** for file discovery (never `find`). **WebFetch is blocked** — download via python urllib instead. Prefer python over PowerShell for data processing.
2. **PEEK**: Sample head/tail/random slices to understand structure
3. **SEARCH**: Targeted extraction (regex, AST, JSON keys) based on PEEK findings

If file is 500KB+, continue with:

4. **ANALYZE**: Decomposition — spawn @explore sub-agents per chunk (up to 15 sub-queries). Pass only the chunk + specific question to each sub-agent.
5. **SYNTHESIZE**: Combine findings, cross-reference, resolve conflicts
6. **SUBMIT**: End with explicit SUBMIT block:

```
=== RLM SUBMIT ===
Query: [question]
Confidence: [high/medium/low]
Protocol: [steps executed]
Sub-queries: [N spawned, N completed]
Data processed: [size]

[Answer]
=== END ===
```

If data is 50MB+ — use `rlm-cli query "..." --file <path> --stats`

Budget: 20 iterations max, 15K chars/step, 15 sub-queries max. Always SUBMIT.
