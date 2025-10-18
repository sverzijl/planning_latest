# Documentation Archive

## Purpose
This directory contains archived troubleshooting documentation, implementation reports, investigation summaries, and test development notes from the project's development history.

## Directory Structure

- **implementation_reports/** - Feature implementation deep-dives (2 reports)
  - Integration test timeout fix (2025-10-17)
  - Piecewise labor cost implementation (2025-10-17)

- **investigations/** - Forensic analysis and troubleshooting investigations (1 report)
  - State forensics: end-of-horizon inventory analysis (2025-10-16)

- **testing/** - Test development and validation documentation (3 reports)
  - Parameter parsing test suite (2025-10-17)

- **bug_fixes/** - Bug resolution documentation (empty - reserved for future use)

- **migration_guides/** - One-time migration documentation (empty - reserved for future use)

- **performance_analysis/** - Performance investigation reports (empty - reserved for future use)

## How to Use This Archive

**Each subdirectory contains:**
1. `index.md` - Comprehensive catalog with metadata, key insights, and cross-references
2. Archived markdown files with original content preserved
3. Related code references and diagnostic script locations

**When to reference:**
- Understanding historical design decisions
- Troubleshooting similar issues (forensic methodologies)
- Learning from past investigations (what worked, what didn't)
- Reference implementations for new features
- Test development patterns and best practices

## Active Documentation

Core documentation remains in:
- `/home/sverzijl/planning_latest/CLAUDE.md` - Primary development guide
- `/home/sverzijl/planning_latest/README.md` - User-facing documentation
- `/home/sverzijl/planning_latest/docs/features/` - Active feature documentation
- `/home/sverzijl/planning_latest/data/examples/` - Excel format specifications

## Archive Policy

**What gets archived:**
- ✅ Implementation reports after feature completion
- ✅ Investigation reports after issue resolution
- ✅ Test development documentation after test creation
- ✅ Bug fix summaries after deployment
- ✅ Migration guides after migration completion

**What stays active:**
- ❌ Ongoing feature development documentation
- ❌ Current test suite documentation (tests/README_*.md)
- ❌ Active troubleshooting guides
- ❌ Excel template specifications
- ❌ Main project documentation (CLAUDE.md, README.md)

## Historical Files (Pre-2025-10-18)

The archive also contains 81 markdown files from earlier development phases (2025-10-16 and earlier):
- Batch tracking implementation reports
- Daily snapshot feature development
- Cohort tracking implementation
- Performance optimization investigations
- CI/CD setup documentation
- UI enhancement summaries

These files document the evolution of the UnifiedNodeModel and optimization framework.

---
*Archive structure created: 2025-10-18*
*Total archived documentation: 87 files (81 legacy + 6 recent)*
