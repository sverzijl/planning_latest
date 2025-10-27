# Highs - Guide

**Pages:** 4

---

## GPU acceleration · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/guide/gpu/

**Contents:**
- GPU acceleration
  - PDLP: A health warning
    - Termination criteria
  - Requirements
  - Build HiGHS with GPU support

From HiGHS v1.10.0, its first order primal-dual LP (PDLP) solver cuPDLP-C can be run on an NVIDIA GPU under Linux and Windows. However, to achieve this, CUDA utilities must be installed and HiGHS must be built locally using CMake, as described below.

First order solvers for LP are still very much "work in progress". Although impressive results have been reported, these are often to lower accuracy than is achieved by simplex and interior point solvers, have been obtained using top-of-the-range GPUs, and not achieved for all problem classes. Note that, due to PDLP using relative termination conditions, a solution deemed optimal by PDLP may not be accepted as optimal by HiGHS. The user should consider the infeasibility data returned by HighsInfo to decide whether the solution is acceptable to them.

Although the PDLP solver may report that it has terminated with an optimal solution, HiGHS may identify that the solution returned by PDLP is not optimal. As discussed in HiGHS feasibility and optimality tolerances, this is due to PDLP using relative termination criteria and (unlike interior point solvers) not satisfying feasibility to high accuracy.

If you use the HiGHS PDLP solver, in the first instance it is recommended that you increase the feasibility and optimality tolerances to 1e-4, since this will result in the algorithm terminating much sooner. There are multiple feasibility and optimality tolerances, but all will be set to the value of the kkt_tolerance option (if it differs from its default value of 1e-4) so this is recommended in the first instance.

CUDA Toolkit and CMake.

A CUDA Toolkit installation is required, along with the matching NVIDIA driver. Please install both following the instructions on NVIDIA's website.

HiGHS must be build locally with CMake.

Make sure the CUDA compiler nvcc is installed by running

See Building HiGHS with NVidia GPU support.

**Examples:**

Example 1 (unknown):
```unknown
nvcc --version
```

---

## Basic features · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/guide/basic/

**Contents:**
- Basic features
  - HiGHS data structures
    - Enums
    - Classes
- Defining a model
  - Reading a model from a file
  - Building a model
  - Passing a model
- Solving the model
- Extracting results

The minimal use of HiGHS has the following three stages.

Although its default actions will be sufficient for most users, HiGHS can be controlled by setting Option values.

Intro to other basic features

There are several specialist data structures that can be used to interact with HiGHS when using C++ and highspy. These are defined in the sections on enums and classes, and are referred to below.

Enums are scalar identifier types that can take only a limited range of values.

The advantage of using the native C++ classes in HiGHS is that many fewer parameters are needed when passing data to and from HiGHS. The binding of the data members of these classes to highspy structures allows them to be used when calling HiGHS from Python, although they are not necessary for the basic use of highspy. As with the C and Fortran interfaces, there are equivalent methods that use simple scalars and vectors of data.

HiGHS has comprehensive tools for defining models. This can be done by either reading a model using a data file created elsewhere, or by passing model data to HiGHS. Once a model has been defined in HiGHS, it is referred to as the incumbent model.

The simplest way to define a model in HiGHS is to read it from a file using the method readModel. HiGHS infers the file type by the extension. Supported extensions are:

HiGHS can read compressed files that end in the .gz extension, but not (yet) files that end in the .zip extension.

The model in HiGHS can be built using a sequence of calls to add variables and constraints. This is most easily done one-by-one using the methods addCol and addRow. Alternatively, calls to addVar can be used to add variables, with calls to changeColCost used to define each objective coefficient.

Addition of multiple variables and constraints can be achieved using addCols and addRows. Alternatively, addVars can be used to add variables, with changeColsCost used to define objective coefficients. Note that defining multiple variables and constraints requires vectors of data and the specification of constraint coefficients as compressed row-wise or column-wise matrices.

If the entire definition of a model is known, then it can be passed to HiGHS via individual data arrays using the method passModel. In languages where HiGHS data structures can be used, an instance of the HighsLp class can be populated with data and then passed.

The incumbent model in HiGHS is solved by a call to the method run. By default, HiGHS minimizes the model's 

*[Content truncated]*

---

## Further features · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/guide/further/

**Contents:**
- Further features
- Model and solution management
  - Extracting model data
- Modifying model data
- Hot start
  - LP
  - MIP
- Presolve
- Multi-objective optimization
  - Methods

HiGHS has comprehensive tools for defining and extracting models. This can be done either to/from MPS or (CPLEX) format LP files, or via method calls. HiGHS also has methods that permit the incumbent model to be modified. Solutions can be supplied and extracted using either files or method calls.

The numbers of column, rows and nonzeros in the model are returned by the methods getNumCols, getNumRows, and getNumEntries respectively.

Model data can be extracted for a single column or row by specifying the index of the column or row and calling the methods getCol and getRow.

As well as returning the value of the cost and bounds, these methods also return the number of nonzeros in the corresponding column or row of the constraint matrix. The indices and values of the nonzeros can be obtained using the methods getColEntries and getRowEntries.

For multiple columns and rows defined by a set of indices, the corresponding data can be extracted using the methods getCols, getRows, getColsEntries and getRowsEntries.

Specific matrix coefficients obtained using the method getCoeff.

The most immediate model modification is to change the sense of the objective. By default, HiGHS minimizes the model's objective function. The objective sense can be set to minimize (maximize) using changeObjectiveSense.

Model data for can be changed for one column or row by specifying the index of the column or row, together with the new scalar value for the cost or bounds, the specific methods being changeColCost, changeColBounds. The corresponding method for a row is changeRowBounds. Changes for multiple columns or rows are defined by supplying a list of indices, together with arrays of new values, using the methods changeColsCost, changeColsBounds. The corresponding method for a row is changeRowsBounds. An individual matrix coefficient is changed by passing its row index, column index and new value to changeCoeff.

It may be possible for HiGHS to start solving a model using data obtained by solving a related model, or supplied by a user. Whether this is possible depends on the the class of model being solved, the solver to be used, and the modifications (if any) that have been to the incumbent model since it was last solved.

To run HiGHS from a user-defined solution or basis, this is passed to HiGHS using the methods setSolution or setBasis. The basis passed to HiGHS need not be complete

There can be more basic variables then the number of rows in the model. HiGHS will identify a

*[Content truncated]*

---

## Feasibility and optimality · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/guide/kkt/

**Contents:**
- Feasibility and optimality
  - Feasibility and optimality conditions
  - The HiGHS feasibility and optimality tolerances
  - When HiGHS yields an optimal solution
  - Solutions with a corresponding basis
  - Solutions without a corresponding basis
    - Interior point solutions
    - PDLP solutions
    - HiGHS solutions
  - Discrete optimization problems

Mathematically, continuous optimization problems have exact feasibility and optimality conditions. However, since solvers cannot always satisfy these conditions exactly when using floating-point arithmetic, they do so to within tolerances. As explored below, some solvers aim to satisfy those tolerances absolutely, and others aim to satisfy tolerances relative to problem data. When tolerances are satisfied relatively, they are generally not satisfied absolutely. The use of tolerances relative to problem data is not consistent across solvers, and can give a misleading claim of optimality. To achieve consistency, HiGHS reassesses the optimal solution claimed by such a solver in a reasonable and uniform manner.

To discuss tolerances and their use in different solvers, consider the standard form linear programming (LP) problem with $n$ variables and $m$ equations ($n\ge m$).

\[\begin{aligned} \textrm{minimize} \quad & c^T\! x \\ \textrm{subject to} \quad & Ax = b \\ & x \ge 0, \end{aligned}\]

The feasibility and optimality conditions (KKT conditions) are that, at a point $x$, there exist (row) dual values $y$ and reduced costs (column dual values) $s$ such that

\[\begin{aligned} Ax=b&\qquad\textrm{Primal~equations}\\ A^Ty+s=c&\qquad\textrm{Dual~equations}\\ x\ge0&\qquad\textrm{Primal~feasibility}\\ s\ge0&\qquad\textrm{Dual~feasibility}\\ c^Tx-b^Ty=0&\qquad\textrm{Optimality} \end{aligned}\]

The optimality condition is equivalent to the complementarity condition that $x^Ts=0$. Since any LP problem can be transformed into standard form, the following discussion loses no generality. This discussion also largely applies to quadratic programming (QP) problems, with the differences explored below.

HiGHS has separate tolerances for the following, listed with convenient mathematical notation

All are set to the same default value of $10^{-7}$. Although each can be set to different values by the user, if the user wishes to solve LPs to a general lower or higher tolerance, the value of the KKT tolerance can be changed from this default value.

When HiGHS returns a model status of optimal, the solution will satisfy feasibility and optimality tolerances absolutely or relatively according to whether the solver yields a basic solution.

The HiGHS simplex solvers and the interior point solver after crossover yield an optimal basic solution of the LP, consisting of $m$ basic variables and $n-m$ nonbasic variables. At any basis, the nonbasic variables are zero, and values

*[Content truncated]*

---
