#!/bin/bash
# List recent markdown files that might document Phase 1 work

echo "Recent markdown files (last 7 days):"
find . -name "*.md" -mtime -7 -type f 2>/dev/null | head -20

echo ""
echo "Files containing 'labor' and 'calendar':"
find . -name "*.md" -type f -exec grep -l "labor.*calendar\|calendar.*labor" {} \; 2>/dev/null | head -10

echo ""
echo "Files containing 'Phase 1' or 'PHASE 1':"
find . -name "*.md" -type f -exec grep -l "Phase 1\|PHASE 1" {} \; 2>/dev/null | head -10
