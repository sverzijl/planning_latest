# Highs - Getting Started

**Pages:** 3

---

## About · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/

**Contents:**
- HiGHS - High Performance Optimization Software
- Specification
- Using HiGHS
- Overview
- Solvers
- Citing HiGHS
- Performance benchmarks
- Feedback

This HiGHS documentation is a work in progress.

HiGHS is software for the definition, modification and solution of large scale sparse linear optimization models.

HiGHS is freely available from GitHub under the MIT licence and has no third-party dependencies.

HiGHS can solve linear programming (LP) models of the form:

\[\begin{aligned} \min \quad & c^T\! x \\ \textrm{subject to} \quad & L \le Ax \le U \\ & l \le x \le u, \end{aligned}\]

as well as mixed integer linear programming (MILP) models of the same form, for which some of the variables must take integer values.

HiGHS also solves quadratic programming (QP) models, which contain an additional objective term $\frac{1}{2}x^T\! Q x$, where the Hessian matrix $Q$ is positive semi-definite. HiGHS cannot solve QP models where some of the variables must take integer values.

Read the Terminology section for more details.

HiGHS can be used as a stand-alone executable on Windows, Linux and MacOS. There is also a C++11 library that can be used within a C++ project or, via its C, C#, FORTRAN, Julia, Python and Rust interfaces.

Get started by following Install HiGHS.

The stand-alone executable allows models to be solved from MPS or (CPLEX) LP files, with full control of the HiGHS run-time options, and the solution can be written to files in human and computer-readable formats.

The HiGHS shared library allows models to be loaded, built and modified. It can also be used to extract solution data and perform other operations relating to the incumbent model. The basic functionality is introduced via a Guide, with links to examples of its use in the Python interface highspy. This makes use of the C++ structures and enums, and is as close as possible to the native C++ library calls. These can be studied via the C++ header file.

The C interface cannot make use of the C++ structures and enums, and its methods are documented explicitly.

For LPs, HiGHS has implementations of the revised simplex method, interior point method, and PDLP first order method. MIPs are solved by branch-and-cut, and QPs by active set. More information on the HiGHS solvers is available.

If you use HiGHS in an academic context, please cite the following article:

Parallelizing the dual revised simplex method, Q. Huangfu and J. A. J. Hall, Mathematical Programming Computation, 10 (1), 119-142, 2018. DOI: 10.1007/s12532-017-0130-5

The performance of HiGHS relative to some commercial and open-source simplex solvers may be assessed via the M

*[Content truncated]*

---

## Install HiGHS · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/installation/

**Contents:**
- Install HiGHS
- Compile from source
- HiGHS with HiPO
    - BLAS
    - Metis
  - HiPO
- Bazel build
- Install via a package manager
- Precompiled Binaries
  - Platform strings

HiGHS uses CMake as build system, and requires at least version 3.15. Details about building from source using CMake can be found in HiGHS/cmake/README.md.

HiGHS does not have any external dependencies, however, the new interior point solver HiPO uses BLAS and Metis. At the moment HiPO is optional and can be enabled via CMake. To build HiPO, you need to have Metis and BLAS installed on your machine. Please follow the instructions below.

On Linux, libblas and libopenblas are supported. We recomment libopenblas for its better performance, and it is found by default if available on the system. Install with

On MacOS no BLAS installation is required because HiPO uses Apple Accelerate by default.

On Windows, OpenBLAS is required. It could be installed via vcpkg with

Note, that [threads] is required for HiPO.

To specify explicitly which BLAS vendor to look for, BLA_VENDOR coud be set in CMake, e.g. -DBLA_VENDOR=Apple or -DBLA_VENDOR=OpenBLAS. Alternatively, to specify which BLAS library to use, set BLAS_LIBRARIES to the full path of the library e.g. -DBLAS_LIBRARIES=/path_to/libopenblas.so.

There are some known issues with Metis so the recommented version is in this fork, branch 510-ts. This is version 5.10 with several patches for more reliable build and execution. Clone the repository with

On Windows, do not forget to specify configuration type

To install HiPO, on Linux and MacOS, run

On Windows, you also need to specify the path to OpenBLAS. If it was installed with vcpkg as suggested above, add the path to vcpkg.cmake to the CMake flags, e.g.

Alternatively, building with Bazel is supported for Bazel-based projects. To build HiGHS, from the root directory, run

HiGHS can be installed using a package manager in the cases of Julia, Python, CSharp and Rust.

These binaries are provided by the Julia community and are not officially supported by the HiGHS development team. If you have trouble using these libraries, please open a GitHub issue and tag @odow in your question.

Precompiled static executables are available for a variety of platforms at

Multiple versions are available. Each version has the form vX.Y.Z. In general, you should choose the most recent version.

To install a precompiled binary, download the appropriate HiGHSstatic.vX.Y.Z.[platform-string].tar.gz file and extract the executable located at /bin/highs.

Do not download the file starting with HiGHSstatic-logs. These files contain information from the automated compilation system. Clic

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
sudo apt update
sudo apt install libopenblas-dev
```

Example 2 (unknown):
```unknown
vcpkg install openblas[threads]
```

Example 3 (unknown):
```unknown
git clone https://github.com/galabovaa/METIS.git
cd METIS
git checkout 510-ts
```

Example 4 (unknown):
```unknown
cmake -S. -B build
-DGKLIB_PATH=/path_to_METIS_repo/GKlib
-DCMAKE_INSTALL_PREFIX=path_to_installs_dir
cmake --build build
cmake --install build
```

---

## Executable · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/executable/

**Contents:**
- Executable
  - Running the executable
  - Command line options
  - Return code values

HiGHS can run as a stand-alone program with a command-line interface. It solves an optimization problem provided by either an MPS file, or LP file. Note that HiGHS cannot read the lpsolve LP file format.

For convenience, the executable is assumed to be bin/highs. The model given by the MPS file model.mps is solved by the command:

If the model file is not in the folder from which the command was issued, then a path name can be given.

HiGHS is controlled by option values. When it is run from the command line, some fundamental option values may be specified directly. Many more may be specified via a file containing HiGHS options settings. Formally, the usage is:

The list of options section gives a full list of options, and their default values. In a file containing HiGHS options they are specified as name = value, with one per line, and any line beginning with # treated as a comment. For example, the primal-dual hybrid gradient method for LP (PDLP) is used with all feasibility and optimality tolerances set to 1e-4 if HiGHS reads the following in its options file.

Consistent with the callable methods in HiGHS, there are three possible return codes

**Examples:**

Example 1 (unknown):
```unknown
$ bin/highs model.mps
```

Example 2 (unknown):
```unknown
$ bin/highs --help
usage:
      ./bin/highs [options] [file]

options:
      --model_file file          File of model to solve.
      --options_file file        File containing HiGHS options.
      --read_solution_file file  File of solution to read.
      --read_basis_file text     File of initial basis to read. 
      --write_model_file text    File for writing out model.
      --solution_file text       File for writing out solution.
      --write_basis_file text    File for writing out final basis.
      --presolve text            Set presolve option to:
                                   
...
```

Example 3 (unknown):
```unknown
solver = pdlp
kkt_tolerance = 1e-4
```

---
