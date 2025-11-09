# HiGHS Solver Options Analysis

**Source:** https://ergo-code.github.io/HiGHS/dev/options/definitions/
**Date:** 2025-10-19

## Key MIP Options Extracted

### Current Configuration Issues Found

| Option | HiGHS Default | Our Setting | Issue |
|--------|---------------|-------------|-------|
| `mip_heuristic_effort` | 0.05 (5%) | 0.5 (50%) normal | ✅ Good |
| `mip_lp_age_limit` | 10 | 20 | ⚠️ Too high (keeps old cuts longer) |
| `simplex_strategy` | 1 (Dual serial) | 4 (Primal) | ⚠️ Wrong - should use 1 or 2 |
| `mip_heuristic_run_zi_round` | false | Not set | Could enable |
| `mip_heuristic_run_shifting` | false | Not set | Could enable |
| `mip_allow_restart` | true | Not set | ✅ Default OK |
| `mip_max_nodes` | unlimited | Not set | ✅ OK |

### Critical Findings

#### 1. **simplex_strategy = 4 is WRONG!** ⚠️
```
simplex_strategy values:
0 => Choose (auto-select)
1 => Dual (serial) - DEFAULT, best for MIP
2 => Dual (SIP) - Parallel dual simplex
3 => Dual (PAMI) - Another parallel variant
4 => Primal - Usually slower for MIP!
```

**Issue:** We're setting `simplex_strategy=4` (Primal), but HiGHS default is `1` (Dual serial), which is faster for MIP!
**Fix:** Use `simplex_strategy=1` or `2` (dual simplex variants)

#### 2. **mip_lp_age_limit Too High**
- **Default:** 10
- **Our setting:** 20
- **Impact:** Keeps old LP cuts longer, slowing down LP resolves
- **Fix:** Use default (10) or even lower (5-8) for aggressive cut removal

#### 3. **Missing Additional Heuristics**
- `mip_heuristic_run_zi_round`: Default false (we could enable)
- `mip_heuristic_run_shifting`: Default false (we could enable)

#### 4. **Default mip_heuristic_effort is Only 5%!**
- HiGHS default: 0.05 (very conservative!)
- Our setting: 0.5 (10x better) ✅
- This was a good change

