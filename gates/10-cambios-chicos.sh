#!/usr/bin/env bash
# Máximo 120 líneas agregadas + borradas.
total="$(git diff --numstat "$FACTORY_BASE" -- . | awk '{ if ($1 != "-") n += $1 + $2 } END { print n + 0 }')"
if [ "$total" -gt 120 ]; then echo "El cambio tiene $total líneas; el máximo es 120."; exit 1; fi
