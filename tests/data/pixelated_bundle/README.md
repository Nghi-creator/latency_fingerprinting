# Sanitized Pixelated adapter fixture

This directory contains minimal, synthetic-shaped v1 and v2 exports that follow
the real Pixelated Studio Edition research-bundle filenames and columns. They
are software-test inputs, not experimental results. Identifiers are deliberately
anonymous and no URL, credential, device identity or personal path is retained.

`context.json` and `context-v2.json` are intentionally separate from their
bundle directories: Pixelated cannot declare the complete comparison context
required by the research contract, so callers must provide it explicitly.
