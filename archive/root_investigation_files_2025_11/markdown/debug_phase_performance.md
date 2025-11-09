# Phase Performance Investigation

## Observed Behavior

| Phase | Fixed Vars | Binary Vars | Solve Time | Status | Cost | Gap |
|-------|-----------|-------------|------------|---------|------|-----|
| 1 | 140 (all) | 0 | 13.1s | optimal | $773,853 | - |
| 2 | 121 | 19 | 13.5s | optimal | $716,488 | 0.54% |
| 3 | 101 | 39 | 13.3s | optimal | $679,788 | 3.79% |
| 4 | 83 | 57 | **48.1s** | optimal | $654,875 | 2.61% |
| 5 | 65 | 75 | **65.8s** | optimal | $649,684 | 2.90% |
| 6 | 61 | 79 | **72.3s** | maxTimeLimit | $662,279 | 4.65% |

## Key Observations

1. **Performance cliff at Phase 4:**
   - Phase 3: 39 binary vars → 13.3s
   - Phase 4: 57 binary vars → 48.1s (**3.6× slower!**)

2. **Continued degradation:**
   - Phase 5: 75 binary vars → 65.8s
   - Phase 6: 79 binary vars → 72.3s + timeout

3. **Model structure identical:**
   - Same number of constraints
   - Same total variables (140 product_produced)
   - Only difference: which ones are fixed vs binary

4. **MIP gap tolerance:**
   - All phases use same gap (6% = mip_gap × 2)
   - Gap achieved varies: 0.54%, 3.79%, 2.61%, 2.90%, 4.65%

## Hypothesis 1: Binary Variable Count Threshold

MIP complexity grows exponentially with binary variables. There may be a threshold around 50-60 binary vars where:
- Search space becomes significantly larger
- LP relaxation becomes weaker
- More branch-and-bound nodes required

## Hypothesis 2: Problem Becomes Harder (Tighter Constraints)

As we remove SKUs, remaining SKUs must satisfy all demand:
- More routing/timing constraints become active
- Less flexibility in production scheduling
- Solver must work harder to find feasible solutions

## Hypothesis 3: Warmstart Not Applied Between Phases

Each phase solves from scratch (no warmstart between iterations):
- Phase 1: Cold start (but trivial - all fixed)
- Phase 2-6: Cold start with increasing binary complexity
- Could benefit from using previous phase solution as warmstart

## Hypothesis 4: LP Relaxation Quality

With more binary variables free:
- LP relaxation bound may be weaker
- More branching required to reach integer solution
- Fixed variables provide strong bounds; binary variables don't

## Investigation Plan

1. Check actual number of branch-and-bound nodes (solver statistics)
2. Check LP relaxation quality (root node bound vs final objective)
3. Verify variables are actually being fixed (inspect Pyomo model)
4. Test warmstart between phases (use Phase N-1 as warmstart for Phase N)
