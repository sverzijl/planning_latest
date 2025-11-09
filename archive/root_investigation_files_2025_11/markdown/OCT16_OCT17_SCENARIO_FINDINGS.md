# Oct 16/Oct 17 Scenario Investigation

## Session Summary

**Total time:** ~4 hours

### Bugs Fixed:

1. **Disposal bug** (commit 1614047) - $326k savings
   - Circular dependency in consumption limits
   - Fix: Bound consumption against inflows

2. **Lineage state display** (commit b4c5012)
   - Thawed inventory for frozen-only nodes
   - Fix: Match thaw capability logic

### Current Investigation: 6130 Ambient Consumption

**User scenario:**
- Inventory snapshot: Oct 16, 2025
- Planning start: Oct 17, 2025
- Observation: 518 units ambient at 6130 not consumed

**Findings so far:**
1. ✅ Forecast has 615 units demand at 6130 on Oct 17
2. ✅ SAP IBP parser works correctly
3. ✅ Alias resolution works (168847 → HELGAS GFREE MIXED GRAIN)
4. ⚠️  Default DataCoordinator uses Nov 8 snapshot (not Oct 16)
5. ⚠️  Need to test with explicit Oct 16 snapshot passed through

### Next Steps:

1. Run full solve with Oct 16 inventory + Oct 17 planning
2. Check if 6130 ambient is consumed
3. If not consumed:
   - Create minimal test case
   - Prove root cause
   - Fix formulation

### Recommendation:

Given session complexity, suggest:
- Review current fixes (disposal + Lineage) - both significant improvements
- Test Oct 16/Oct 17 scenario in clean session
- May be data configuration issue rather than model bug

### Files Created:

- DISPOSAL_BUG_ROOT_CAUSE_AND_FIX.md
- LESSONS_LEARNED_DISPOSAL_BUG.md
- OPTIMIZATION_DEBUGGING_PLAYBOOK.md
- Multiple diagnostic scripts
