# Highs - Terminology

**Pages:** 1

---

## Terminology · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/terminology/

**Contents:**
- Terminology
- Bounds and the objective function
- Constraints and the feasible region
- The constraint matrix
- Optimization outcomes
- Primal values
- Dual values
- Basic solution
- Sensitivity
- MIP

Any linear optimization model will have decision variables, a linear or quadratic objective function, and linear constraints and bounds on the values of the decision variables. A mixed-integer optimization model will require some or all of the decision variables to take integer values. The model may require the objective function to be maximized or minimized whilst satisfying the constraints and bounds. By default, HiGHS minimizes the objective function.

The bounds on a decision variable are the least and greatest values that it may take, and infinite bounds can be specified. A linear objective function is given by a set of coefficients, one for each decision variable, and its value is the sum of products of coefficients and values of decision variables. The objective coefficients are often referred to as costs, and some may be zero. When a model has been solved, the optimal values of the decision variables are referred to as the (primal) solution.

Linear constraints require linear functions of decision variables to lie between bounds, and infinite bounds can be specified. If the bounds are equal, then the constraint is an equation. If the bounds are both finite, then the constraint is said to be boxed or two-sided. The set of points satisfying linear constraints and bounds is known as the feasible region. Geometrically, this is a multi-dimensional convex polyhedron, whose extreme points are referred to as vertices.

The coefficients of the linear constraints are naturally viewed as rows of a matrix. The constraint coefficients associated with a particular decision variable form a column of the constraint matrix. Hence constraints are sometimes referred to as rows, and decision variables as columns. Constraint matrix coefficients may be zero. Indeed, for large practical models it is typical for most of the coefficients to be zero. When this property can be exploited to computational advantage, the matrix is said to be sparse. When the constraint matrix is not sparse, the solution of large models is normally intractable computationally.

It is possible to define a set of constraints and bounds that cannot be satisfied, in which case the model is said to be infeasible. Conversely, it is possible that the value of the objective function can be improved without bound whilst satisfying the constraints and bounds, in which case the model is said to be unbounded. If a model is neither infeasible, nor unbounded, it has an optimal solution. The optimal objective 

*[Content truncated]*

---
