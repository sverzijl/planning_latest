# MIP Modeling Expert - Reference Documentation

This directory contains detailed reference documentation for Mixed Integer Programming (MIP) modeling techniques.

## Contents

### Core Techniques

1. **[indicator_variables.md](indicator_variables.md)**
   - Discontinuous variables (0 or within bounds [l,u])
   - Fixed costs and setup costs
   - Big-M formulation fundamentals

2. **[either_or_conditional.md](either_or_conditional.md)**
   - Either-or constraints (at least one must hold)
   - Conditional constraints (if-then relationships)
   - Logical equivalences for constraint modeling

3. **[sos_sets.md](sos_sets.md)**
   - Special Ordered Sets Type 1 (SOS1)
   - Special Ordered Sets Type 2 (SOS2)
   - Branching strategies and performance

4. **[piecewise_linear.md](piecewise_linear.md)**
   - λ-formulation for approximating nonlinear functions
   - Separable functions
   - Convex vs. non-convex cases
   - When MIP is required vs. pure LP

5. **[product_elimination.md](product_elimination.md)**
   - Linearizing binary × binary products
   - Linearizing binary × continuous products
   - Linearizing continuous × continuous products
   - Special cases and shortcuts

6. **[examples.md](examples.md)**
   - Complete worked examples from AIMMS guide
   - Application scenarios
   - Step-by-step formulations

## Quick Navigation

- **Beginner?** Start with `indicator_variables.md` to understand the foundation
- **Need logical constraints?** See `either_or_conditional.md`
- **Nonlinear functions?** Check `piecewise_linear.md`
- **Performance issues?** Review `sos_sets.md` for solver efficiency
- **Products of variables?** Go to `product_elimination.md`

## Source

All content is derived from Chapter 7 "Integer Linear Programming Tricks" of the AIMMS Modeling Guide (AIMMS 4, 1993-2018).
