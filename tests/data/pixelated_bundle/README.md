# Sanitized Pixelated adapter fixture

This directory contains a minimal, synthetic-shaped export that follows the
real Pixelated Studio Edition research-bundle filenames and columns. It is a
software-test input, not an experimental result. Identifiers are deliberately
anonymous and no user agent, URL, credential, device identity or personal path
is retained.

`context.json` is intentionally separate from `valid/`: Pixelated's browser
bundle cannot declare the complete comparison context required by the research
contract, so callers must provide that context explicitly.
