# Warmstart Implementation Context Repository

**Last Updated:** 2025-10-19
**Status:** INITIALIZATION
**Primary Objective:** Implement CBC warmstart functionality to reduce solve time by 20-40% for 4-week planning horizons

---

## Repository Structure

```
context/
├── README.md (this file)              # Overview and navigation
├── design/                            # Design specifications
│   ├── cbc_warmstart_mechanism.md     # Technical design for CBC warmstart
│   ├── campaign_pattern_algorithm.md  # Production campaign algorithm
│   └── integration_design.md          # Integration architecture
├── code/                              # Code artifacts
│   ├── base_model_changes.md          # Changes to base_model.py
│   ├── warmstart_generator.py         # Draft implementation
│   └── unified_model_changes.md       # Changes to unified_node_model.py
├── tests/                             # Test specifications
│   ├── test_plan.md                   # Test strategy and requirements
│   └── test_warmstart.py              # Draft test implementation
└── progress/                          # Progress tracking
    ├── agent_status.json              # Agent task status
    ├── validation_checklist.md        # Implementation validation
    └── decisions_log.md               # Design decisions and rationale
```

---

## Quick Reference

### Key Files to Modify

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `src/optimization/base_model.py` | 187-332 | Add warmstart integration point (line 283) | NOT STARTED |
| `src/optimization/unified_node_model.py` | 599-603, 922-949 | Add warmstart parameter + call generator | NOT STARTED |

### New Files to Create

| File | Purpose | Status |
|------|---------|--------|
| `src/optimization/warmstart_generator.py` | Campaign pattern warmstart generation | NOT STARTED |
| `tests/test_warmstart.py` | Warmstart functionality tests | NOT STARTED |

---

## Context Categories

### 1. Business Context
- **Problem:** 4-week planning horizon takes >300s to solve with CBC (exceeds timeout)
- **Solution:** Provide initial feasible solution (warmstart) to accelerate CBC
- **Expected Outcome:** 20-40% reduction in solve time (target: <120s)
- **Products:** 5 SKUs in example dataset
- **Production Rate:** 1,400 units/hour
- **Daily Capacity:** 16,800 units (regular), 19,600 units (with overtime)
- **Shelf Life:** 17 days ambient
- **Changeover Time:** 1.0 hour per SKU

### 2. Technical Context
- **Solver:** CBC 2.10.12 (open-source MIP solver)
- **Framework:** Pyomo 6.x
- **Warmstart Mechanism:** Set `variable.value = initial_value` before solve
- **Warmstart Data Structure:** `{(var_name, index_tuple): value}`
- **Example:** `{('production', ('6122', 'PROD_001', date(2025,10,20))): 5000.0}`

### 3. Design Context
- **Campaign Pattern:** Group 2-3 SKUs per production day to minimize changeovers
- **Weekly Rotation:** Ensure all 5 SKUs produced at least once per week
- **Demand Allocation:** Distribute total weekly demand across production days
- **Strategy:** DEMAND_WEIGHTED (proportional to demand)
- **Fallback:** Graceful degradation if warmstart fails (log warning, continue)

### 4. Implementation Context
- **Approach:** Automatic warmstart with opt-out capability
- **Default Behavior:** `use_warmstart=True`
- **Opt-out:** `use_warmstart=False` parameter
- **Integration Point:** base_model.py line 283 (before solver.solve())
- **Backward Compatibility:** ZERO breaking changes required

---

## Agent Communication Protocol

### Agent Roles

| Agent | Responsibility | Input From | Output To |
|-------|----------------|------------|-----------|
| pyomo-modeling-expert | CBC warmstart API design | context-manager | python-pro |
| production-planner | Campaign algorithm specification | context-manager | python-pro |
| python-pro | Code implementation (3 files) | experts | test-automator |
| test-automator | Test suite + performance validation | python-pro | code-reviewer |
| code-reviewer | Code quality review | python-pro, test-automator | context-manager |
| context-manager | Knowledge synchronization | all | all |

### Communication Flow

```
context-manager (initialization)
    ↓
pyomo-modeling-expert (warmstart API design)
    ↓
production-planner (campaign algorithm)
    ↓
python-pro (implementation)
    ↓
test-automator (validation)
    ↓
code-reviewer (quality review)
    ↓
context-manager (final integration)
```

---

## Access Points

### For Expert Agents (Design Phase)
- **Read:** Business constraints, technical requirements
- **Write:** Design documents (`context/design/*.md`)
- **Update:** `context/progress/decisions_log.md`

### For Implementation Agents (Code Phase)
- **Read:** Design specifications, code snippets
- **Write:** Code drafts (`context/code/*.py`, `context/tests/*.py`)
- **Update:** `context/progress/agent_status.json`

### For Validation Agents (Test Phase)
- **Read:** Implementation artifacts, test requirements
- **Write:** Test results, performance reports
- **Update:** `context/progress/validation_checklist.md`

---

## Current Status

**Phase:** INITIALIZATION
**Next Step:** pyomo-modeling-expert to design CBC warmstart mechanism
**Blockers:** None
**Completion:** 0% (0/6 agents)

---

## Navigation

- **Design Documents:** [context/design/](./design/)
- **Code Artifacts:** [context/code/](./code/)
- **Test Specifications:** [context/tests/](./tests/)
- **Progress Tracking:** [context/progress/](./progress/)

---

## Contact

**Context Manager Agent:** Maintains this repository
**Update Frequency:** After each agent completion
**Sync Protocol:** All agents read context before starting work
