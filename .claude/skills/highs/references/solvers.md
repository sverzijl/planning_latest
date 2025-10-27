# Highs - Solvers

**Pages:** 1

---

## Solvers · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/solvers/

**Contents:**
- Solvers
- LP
    - Simplex
    - Interior point
    - Primal-dual hybrid gradient method
- MIP
- QP

HiGHS has implementations of the three main solution techniques for LP. HiGHS will choose the most appropriate technique for a given problem, but this can be over-ridden by setting the option solver.

HiGHS has efficient implementations of both the primal and dual simplex methods, although the dual simplex solver is likely to be faster and is more robust, so is used by default. The novel features of the dual simplex solver are described in

Parallelizing the dual revised simplex method, Q. Huangfu and J. A. J. Hall, Mathematical Programming Computation, 10 (1), 119-142, 2018 DOI: 10.1007/s12532-017-0130-5.

HiGHS has two interior point (IPM) solvers:

IPX is based on the preconditioned conjugate gradient method, as discussed in

Implementation of an interior point method with basis preconditioning, Mathematical Programming Computation, 12, 603-635, 2020. DOI: 10.1007/s12532-020-00181-8.

This solver is serial.

Setting the option solver to "ipm" forces the IPX solver to be used

HiPO is based on a direct factorisation, as discussed in

A factorisation-based regularised interior point method using the augmented system, F. Zanetti and J. Gondzio, 2025, available on arxiv

This solver is parallel.

Setting the option solver to "hipo" forces the HiPO solver to be used.

The hipo_system option can be used to select the approach to use when solving the Newton systems within the interior point solver: select "augmented" to force the solver to use the augmented system, "normaleq" for normal equations, or "choose" to leave the choice to the solver.

HiGHS includes the cuPDLP-C primal-dual hybrid gradient method for LP (PDLP). On Linux and Windows, this can be run on an NVIDIA GPU. On a CPU, it is unlikely to be competitive with the HiGHS interior point or simplex solvers.

Setting the option solver to "pdlp" forces the PDLP solver to be used

The HiGHS MIP solver uses established branch-and-cut techniques. It is largely single-threaded, although implementing a multi-threaded tree search is work in progress.

The HiGHS solver for convex QP problems uses an established primal active set method. The new interior point solver HiPO will soon be able to solve convex QP problems.

---
