# Root Directory Investigation Files Archive

**Archive Date:** November 9, 2025
**Purpose:** Cleanup of temporary investigation and debug files from root directory
**Total Files:** 186 markdown files

---

## Contents

This archive contains all investigation markdown files that were previously scattered in the project root directory.

### Markdown Files (186 files)

Investigation reports, session summaries, bug analyses, and debugging documentation from various development sessions during Oct-Nov 2025.

**Categories:**
- Bug investigation reports (BUG_*.md)
- Session summaries (SESSION_*.md, FINAL_*.md)
- Investigation plans and findings (INVESTIGATION_*.md, FINDINGS_*.md)
- Implementation handoffs (HANDOVER_*.md, IMPLEMENTATION_*.md)
- Debugging checklists (SYSTEMATIC_*.md)
- Next session prompts (START_NEXT_SESSION*.txt)

### Python Files (0 files)

No Python debug scripts found in root (they were likely in git staging area as deletions).

---

## Why Archived

These files were temporary artifacts from troubleshooting sessions:
- Not part of permanent documentation
- Redundant with committed code changes and formal docs
- Cluttered the root directory (186 files!)
- Made project navigation difficult
- Most findings already incorporated into code/docs

---

## File Organization

```
archive/root_investigation_files_2025_11/
├── markdown/          # 186 markdown investigation reports
│   ├── BUG_*.md      # Bug analysis reports
│   ├── SESSION_*.md  # Session summaries
│   ├── FINAL_*.md    # Final handoffs and summaries
│   ├── HANDOVER_*.md # Investigation handoffs
│   └── ...
└── python/            # (empty - no Python files in root)
```

---

## Notable Investigation Topics

Based on filenames, major investigation areas included:
- **6130 Ambient Consumption Bug** - Multiple reports on demand consumption issues
- **End Inventory Analysis** - MIP formulation analysis
- **Disposal Bug** - Investigation into disposal pathway issues
- **Labor Constraint Violations** - Capacity and labor cost debugging
- **Sliding Window Implementation** - Oct 2025 development work
- **Warmstart Performance** - Solver warmstart investigation
- **Truck Loading Fixes** - Distribution constraint debugging

---

## Relationship to Other Archives

**Related archives:**
- `archive/debug_scripts/` - 292 Python debug scripts (archived Oct 2025)
- `archive/initial_inventory_debug_2025_11/` - Initial inventory debug (Nov 2025)
- `archive/sliding_window_debug_2025_10_27/` - Sliding window debug scripts
- `archive/warmstart_investigation_2025_10/` - Warmstart research

**Difference:** This archive contains markdown **reports** from investigations.
Other archives contain the **debug scripts** themselves.

---

## If You Need These Files

**Finding specific investigations:**
```bash
# Search all markdown files in archive
grep -r "keyword" archive/root_investigation_files_2025_11/markdown/

# List all files by topic
ls archive/root_investigation_files_2025_11/markdown/ | grep "BUG"
ls archive/root_investigation_files_2025_11/markdown/ | grep "SESSION"
```

**Restoration:**
```bash
# Copy specific file back to root
cp archive/root_investigation_files_2025_11/markdown/<filename> .

# Restore all (not recommended!)
cp archive/root_investigation_files_2025_11/markdown/* .
```

---

## Cleanup Impact

**Before cleanup:**
- Root directory: 186 markdown files + code/docs
- Difficult to find actual project files
- git status showed 200+ untracked files

**After cleanup:**
- Root directory: Only essential project files (README.md, CLAUDE.md, requirements.txt, etc.)
- Clean git status
- Easier project navigation
- All investigation history preserved in archive

---

## Maintenance

**Status:** Read-only archive (no updates needed)

**Retention:** Keep indefinitely
- Historical reference for troubleshooting patterns
- Understanding of bug evolution
- Development process documentation

**Last Updated:** November 9, 2025
