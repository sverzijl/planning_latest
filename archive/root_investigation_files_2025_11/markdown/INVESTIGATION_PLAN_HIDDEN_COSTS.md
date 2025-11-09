# Investigation Plan: Hidden Costs Analysis
**Question:** Why does producing LESS (271k vs 285k) cost MORE ($1,052k vs $947k)?
**Approach:** Systematic debugging + MIP expert + Pyomo expert skills

---

## The Paradox

**Natural solution (waste_mult=10):**
- Production: 285,886 units
- End inventory: 15,705 units (waste)
- Shortage: 36,118 units
- **Objective: $947,364**

**Constrained solution (end_inv <= 2,000):**
- Production: 271,756 units (-14,130 units, 5% less!)
- End inventory: 2,000 units (waste)
- Shortage: 48,848 units (+12,730 units)
- **Objective: $1,052,903 (+$105,539)**

**The Paradox:** Producing 14k FEWER units costs $105k MORE!

**Cost accounting:**
- Waste savings: $178k (13,705 fewer units × $13)
- Shortage increase: $127k (12,730 more units × $10)
- **"Other costs": +$156k**

**User's insight:** This doesn't make logical sense unless there's a bug.

---

## Investigation Phases

### Phase 1: Extract Full Cost Breakdown (Both Solutions)

**Objective:** Get COMPLETE cost breakdown for both solutions

**Extract from solution object:**
1. Production cost
2. Labor cost (total + breakdown: fixed/overtime/weekend)
3. Transport cost
4. Holding cost (frozen + ambient)
5. Shortage cost
6. Waste cost
7. Changeover cost
8. Disposal cost
9. Any other costs

**From Pyomo model objective:**
Verify solution.total_cost matches sum of components

**Output:** Side-by-side comparison table

---

### Phase 2: Identify Which Cost(s) Increased

**Hypothesis testing:**

**Hypothesis A: Labor cost increased (suspicious)**
- Natural uses cheaper labor days
- Constrained forces expensive labor days
- **Check:** Labor cost natural vs constrained
- **Expected:** Should be SAME or LOWER (producing less!)
- **If HIGHER:** Something is forcing expensive production timing

**Hypothesis B: Transport cost increased (very suspicious)**
- Shipping less should cost less
- **Check:** Transport cost natural vs constrained
- **Expected:** Should be LOWER
- **If HIGHER:** Bug in transport cost calculation or routing forced to expensive routes

**Hypothesis C: Holding cost increased (possible)**
- Producing earlier → hold inventory longer
- **Check:** Pallet-days natural vs constrained
- **Expected:** Could be higher if production shifts earlier
- **If much higher:** Need to understand why production shifted

**Hypothesis D: Changeover cost increased (possible)**
- More changeovers if production spread differently
- **Check:** Number of product starts
- **Expected:** Could vary
- **Logical bound:** Max ~$50k for reasonable changeover counts

**Hypothesis E: Cost extraction bug**
- Some cost component extracted incorrectly
- **Check:** Manually recalculate each component from Pyomo variables
- **Verify:** sum(components) = objective

---

### Phase 3: Trace Production Timing Changes

**Objective:** Understand HOW production shifts when end inventory constrained

**Compare production schedules:**

Natural vs Constrained, for Days 1-28:
- Which days have production?
- How much each day?
- Which products each day?
- What labor type (fixed/overtime/weekend)?

**Key questions:**
1. Does constrained solution use MORE expensive labor days?
2. Does it shift production to weekends (can't ship)?
3. Does it create more changeovers?
4. Does it force early production (more holding cost)?

---

### Phase 4: Verify Cost Formulation (Pyomo Expert)

**Check objective expression in Pyomo:**

```python
# Extract objective components directly from model
model.obj.expr  # Get full expression

# Manually evaluate each term:
- Production: sum(prod_cost × production[...])
- Labor: sum(rates × hours[...])
- Transport: sum(route_cost × shipments[...])
- etc.
```

**Verify each component:**
1. Is it in the objective?
2. Does the coefficient make sense?
3. Are the variables valued correctly?

**Look for:**
- Terms that shouldn't be there
- Double-counting
- Missing negative signs
- Wrong coefficients

---

### Phase 5: Test Intermediate Constraints

**If costs seem wrong, test intermediate constraints:**

**Test 1:** Constrain end_inv <= 5,000 (instead of 2,000)
- See if cost increase is proportional
- If linear relationship → real cost
- If non-linear jump → constraint forcing expensive solution

**Test 2:** Constrain only SPECIFIC products
- Force just one product to low end inventory
- See if cost increase makes sense for that product
- Isolate which product's end inventory is "expensive" to avoid

**Test 3:** Check infeasibility**
- Constrain end_inv <= 1,000
- If infeasible, identify which constraint conflicts
- This reveals the structural limit

---

### Phase 6: MIP Theory Analysis

**From MIP formulation, the "other costs" could be:**

**Real economic costs:**
1. **Labor timing cost**
   - Constrained forces production on Day X (expensive)
   - Natural allows production on Day Y (cheap)
   - Difference: Real labor cost difference

2. **Holding cost during horizon**
   - Constrained produces earlier → holds longer → more pallet-days
   - Natural produces later → holds shorter
   - Difference: Real holding cost

3. **Transport routing**
   - Constrained forces different routes (expensive)
   - Natural uses cheaper routes
   - Difference: Real transport cost

**Potential bugs:**
1. **Cost calculation bug**
   - Some cost extracted wrong
   - Double-counting
   - Wrong sign

2. **Constraint forcing expensive solution**
   - Some constraint becomes tight
   - Forces model into expensive corner
   - Not a real economic cost, but artifact of formulation

3. **Solver numerical issues**
   - With tight constraint, solver finds suboptimal solution
   - MIP gap or tolerance issues

---

## Execution Order

### Quick Wins (30 min)
1. **Phase 1:** Extract full cost breakdown (both solutions)
2. **Phase 2:** Identify which cost increased

### Deep Dive (if needed) (1-2 hours)
3. **Phase 3:** Trace production timing
4. **Phase 4:** Verify Pyomo cost formulation
5. **Phase 5:** Test intermediate constraints
6. **Phase 6:** MIP theory analysis

---

## Success Criteria

**Investigation complete when we can answer:**

**Question:** What are the "$156k other costs"?

**Possible answers:**
1. ✅ Real labor costs (model shifts to expensive days)
2. ✅ Real holding costs (earlier production = longer holding)
3. ✅ Real transport costs (different routing)
4. ❌ Bug in cost extraction
5. ❌ Bug in constraint formulation
6. ❌ Double-counting of shortage cost

**If real costs:** Model is correct, waste_mult=100 is the right fix
**If bug:** Fix the bug, then waste_mult=10 should work

---

## Deliverables

1. **Detailed cost comparison spreadsheet** (all components, both solutions)
2. **Production timing comparison** (when/where production differs)
3. **Root cause identification** (which specific cost(s) increased and why)
4. **Verdict:** Bug or feature? If bug, what's the fix?

---

**Ready to execute Phase 1?**
