# Highs - Api

**Pages:** 15

---

## Getting started · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/cpp/

**Contents:**
- Getting started
  - Building HiGHS from source code

HiGHS can be cloned from GitHub with the command

HiGHS uses CMake (minimum version 3.15) as a build system, and can use the following compilers

Instructions for building HiGHS from source code are in HiGHS/cmake/README.md.

The simplest setup is to build HiGHS in a build directory within the root directory. The name of the build folder is arbitrary but, assuming it is build, the sequence of commands is as follows

**Examples:**

Example 1 (unknown):
```unknown
git clone https://github.com/ERGO-Code/HiGHS.git
```

Example 2 (unknown):
```unknown
cd HiGHS
cmake -S. -B build 
cmake --build build --parallel
```

---

## Overview · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/classes/

**Contents:**
- Overview

The data members of fundamental classes in HiGHS are defined in this section.

Class data members for internal use only are not documented.

---

## Julia · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/julia/

**Contents:**
- HiGHS.jl
- Installation
- Use with JuMP
- Issues and feedback
- C API

HiGHS.jl is a Julia package that interfaces with HiGHS.

HiGHS.jl has two components:

The C API can be accessed via HiGHS.Highs_xxx functions, where the names and arguments are identical to the C API.

Install HiGHS as follows:

In addition to installing the HiGHS.jl package, this command will also download and install the HiGHS binaries. (You do not need to install or compile HiGHS separately.)

To use a custom binary, read the Custom solver binaries section of the JuMP documentation.

Pass HiGHS.Optimizer to JuMP.Model to create a JuMP model with HiGHS as the optimizer. Set options using set_optimizer_attribute.

For more details, including a range of tutorials and examples using HiGHS, see the JuMP documentation.

HiGHS.jl is maintained by the JuMP community and is not officially maintained or supported by the HiGHS developers.

To report a problem (e.g., incorrect results, or a crash of the solver), or make a suggestion for how to improve HiGHS.jl, please file a GitHub issue at HiGHS.jl.

If you use HiGHS from JuMP, use JuMP.write_to_file(model, "filename.mps") to write your model an MPS file, then upload the MPS file to https://gist.github.com and provide a link to the gist in the GitHub issue.

HiGHS.jl is a thin wrapper around the complete HiGHS C API.

As a basic example, we solve the model:

\[\begin{aligned} \min \quad & x + y \\ \textrm{subject to} \quad & 5 \le x + 2y \le 15 \\ & 6 \le 3x + 2y \\ & 0 \le x \le 4 \\ & 1 \le y \\ & y \in \mathbb{Z}. \end{aligned}\]

Here is the corresponding Julia code:

**Examples:**

Example 1 (unknown):
```unknown
import Pkg
Pkg.add("HiGHS")
```

Example 2 (unknown):
```unknown
using JuMP
import HiGHS
model = Model(HiGHS.Optimizer)
set_optimizer_attribute(model, "presolve", "on")
set_optimizer_attribute(model, "time_limit", 60.0)
```

Example 3 (unknown):
```unknown
julia> using HiGHS

julia> highs = Highs_create()
Ptr{Nothing} @0x00007fc4557d3200

julia> ret = Highs_setBoolOptionValue(highs, "log_to_console", false)
0

julia> @assert ret == 0  # If ret != 0, something went wrong

julia> Highs_addCol(highs, 1.0, 0.0, 4.0, 0, C_NULL, C_NULL)   # x is column 0
0

julia> Highs_addCol(highs, 1.0, 1.0, Inf, 0, C_NULL, C_NULL)   # y is column 1
0

julia> Highs_changeColIntegrality(highs, 1, kHighsVarTypeInteger)
0

julia> Highs_changeObjectiveSense(highs, kHighsObjSenseMinimize)
0

julia> senseP = Ref{Cint}(0)  # Instead of passing `&sense`, pass a Julia `Ref`

...
```

---

## CSharp · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/csharp/

**Contents:**
    - CSharp
    - Build from source
    - NuGet
    - C# API

There is a C# example code in examples/call_highs_from_csharp.cs. From the HiGHS root directory, run

If a CSharp compiler is available, this builds the example using CMake and generates a binary in the build directory (build/bin/csharpexample).

The nuget package Highs.Native is on https://www.nuget.org, at https://www.nuget.org/packages/Highs.Native/.

It can be added to your C# project with dotnet

The nuget package contains runtime libraries for

Details for building locally can be found in nuget/README.md.

The C# API can be called directly. Here are observations on calling the HiGHS C# API from C#:

This is the normal way to call plain old C from C# with the great simplification that you don't have to write the PInvoke declarations yourself.

**Examples:**

Example 1 (unknown):
```unknown
cmake -S. -Bbuild -DCSHARP=ON
```

Example 2 (unknown):
```unknown
dotnet add package Highs.Native --version 1.12.0
```

---

## HighsInfo · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/structs/HighsInfo/

**Contents:**
- HighsInfo
- valid
- simplex_iteration_count
- ipm_iteration_count
- crossover_iteration_count
- pdlp_iteration_count
- qp_iteration_count
- primal_solution_status
- dual_solution_status
- basis_validity

Scalar information about a solved model is communicated via an instance of the HighsInfo structure

---

## HighsModel · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/classes/HighsModel/

**Contents:**
- HighsModel

A QP model is communicated via an instance of the HighsModel class

lp_: Instance of HighsLp class - LP components of the model

hessian_: Instance of HighsHessian class - Hessian matrix

---

## HighsHessian · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/classes/HighsHessian/

**Contents:**
- HighsHessian

A Hessian matrix is communicated via an instance of the HighsHessian class.

---

## HighsLinearObjective · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/structs/HighsLinearObjective/

**Contents:**
- HighsLinearObjective

A linear objective for a model is communicated via an instance of the HighsLinearObjective structure

---

## Examples · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/python/example-py/

**Contents:**
- Examples
- Initialize HiGHS
- Read a model
- Build a model
- Pass a model
- Solve the model
- Print solution information
- Extract results
- Report results
- Option values

HiGHS must be initialized before making calls to the HiGHS Python library, and the examples below assume that it has been done

To read a model into HiGHS from a MPS files and (CPLEX) LP files pass the file name to readModel.

Using the simplified interface, the model can be built as follows:

Alternatively, the model can be built using the more general interface, which allows the user to specify the model in a more flexible way.

Firstly, one variable at a time, via a sequence of calls to addVar and addRow:s

Alternatively, via calls to addCols and addRows.

Pass a model from a HighsLp instance

The incumbent model in HiGHS is solved by calling

The following are markers for documentation that has yet to be added

**Examples:**

Example 1 (unknown):
```unknown
import highspy
import numpy as np
h = highspy.Highs()
```

Example 2 (unknown):
```unknown
# Read a model from MPS file model.mps
filename = 'model.mps'
status = h.readModel(filename)
print('Reading model file ', filename, ' returns a status of ', status)
filename = 'model.dat'
status = h.readModel(filename)
print('Reading model file ', filename, ' returns a status of ', status)
```

Example 3 (unknown):
```unknown
minimize    f  =  x0 +  x1
subject to              x1 <= 7
            5 <=  x0 + 2x1 <= 15
            6 <= 3x0 + 2x1
            0 <= x0 <= 4; 1 <= x1
```

Example 4 (unknown):
```unknown
x0 = h.addVariable(lb = 0, ub = 4)
x1 = h.addVariable(lb = 1, ub = 7)

h.addConstr(5 <=   x0 + 2*x1 <= 15)
h.addConstr(6 <= 3*x0 + 2*x1)

h.minimize(x0 + x1)
```

---

## C · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/c_api/

**Contents:**
- C

Struct to handle callback output data

Add a new column (variable) to the model.

A kHighsStatus constant indicating whether the call succeeded.

Add multiple columns (variables) to the model.

A kHighsStatus constant indicating whether the call succeeded.

Adds linear objective data to HiGHS

A kHighsStatus constant indicating whether the call succeeded.

Add a new row (a linear constraint) to the model.

A kHighsStatus constant indicating whether the call succeeded.

Add multiple rows (linear constraints) to the model.

A kHighsStatus constant indicating whether the call succeeded.

Add a new variable to the model.

A kHighsStatus constant indicating whether the call succeeded.

Add multiple variables to the model.

A kHighsStatus constant indicating whether the call succeeded.

Change a coefficient in the constraint matrix.

A kHighsStatus constant indicating whether the call succeeded.

Change the variable bounds of a column.

A kHighsStatus constant indicating whether the call succeeded.

Change the objective coefficient of a column.

A kHighsStatus constant indicating whether the call succeeded.

Change the integrality of a column.

A kHighsStatus constant indicating whether the call succeeded.

Change the variable bounds of multiple columns given by a mask.

A kHighsStatus constant indicating whether the call succeeded.

Change the variable bounds of multiple adjacent columns.

A kHighsStatus constant indicating whether the call succeeded.

Change the bounds of multiple columns given by an array of indices.

A kHighsStatus constant indicating whether the call succeeded.

Change the cost of multiple columns given by a mask.

A kHighsStatus constant indicating whether the call succeeded.

Change the cost coefficients of multiple adjacent columns.

A kHighsStatus constant indicating whether the call succeeded.

Change the cost of multiple columns given by an array of indices.

A kHighsStatus constant indicating whether the call succeeded.

Change the integrality of multiple columns given by a mask.

A kHighsStatus constant indicating whether the call succeeded.

Change the integrality of multiple adjacent columns.

A kHighsStatus constant indicating whether the call succeeded.

Change the integrality of multiple columns given by an array of indices.

A kHighsStatus constant indicating whether the call succeeded.

Change the objective offset of the model.

A kHighsStatus constant indicating whether the call succeeded.

Change the objective sense of the 

*[Content truncated]*

**Examples:**

Example 1 (unknown):
```unknown
HighsCallbackDataOut
```

Example 2 (unknown):
```unknown
Highs_addCol(highs, cost, lower, upper, num_new_nz, index, value)
```

Example 3 (unknown):
```unknown
Highs_addCols(highs, num_new_col, costs, lower, upper, num_new_nz, starts, index, value)
```

Example 4 (unknown):
```unknown
Highs_addLinearObjective(highs, weight, offset, coefficients, abs_tolerance, rel_tolerance, priority)
```

---

## Getting started · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/python/

**Contents:**
- Getting started
- Install
- Import
- Initialize
- Logging
- Methods
- Return status
- First example
- Extracting values efficiently

HiGHS is available as highspy on PyPi.

If highspy is not already installed, run:

To use highspy within a Python program, it must be imported

When using highspy, it is likely that numpy structures will be needed, so must also be imported

HiGHS must be initialized before making calls to the HiGHS Python library:

When called from C++, or via the C API, console logging is duplicated to a file that, by default, is Highs.log. However, to channel logging to a file from highspy, the name of the file needs to be specified explicitly via a call to setOptionValue('log_file', 'foo.bar').

Detailed documentation of the methods and structures is given in the examples section.

Unless a method just returns data from HiGHS, so is guaranteed to run successfully, each method returns a status to indicate whether it has run successfully. This value is an instance of the enum HighsStatus, and in the examples section, it is referred to as status.

The following Python code reads a model from the file model.mps, and then solves it.

When arrays of values are returned by highspy, accessing them entry-by-entry can be very slow. Such arrays should first be converted into lists. The following example illustrates how the method getSolution() is used to obtain the solution of a model.

For an example LP that is solved in 0.025s, accessing the values directly from solution.col_value takes 0.04s. Forming the list col_value and accessing the values directly from it takes 0.0001s.

**Examples:**

Example 1 (unknown):
```unknown
$ pip install highspy
```

Example 2 (unknown):
```unknown
import highspy
```

Example 3 (unknown):
```unknown
import numpy as np
```

Example 4 (unknown):
```unknown
h = highspy.Highs()
```

---

## HighsLp · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/classes/HighsLp/

**Contents:**
- HighsLp

An LP model is communicated via an instance of the HighsLp class

---

## HighsSparseMatrix · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/classes/HighsSparseMatrix/

**Contents:**
- HighsSparseMatrix

The constraint matrix of an LP model is communicated via an instance of the HighsSparseMatrix class

---

## Enums · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/structures/enums/

**Contents:**
- Enums
- HighsStatus
- MatrixFormat
- ObjSense
- HighsVarType
- HessianFormat
- SolutionStatus
- BasisValidity
- HighsModelStatus
- HighsBasisStatus

The members of the fundamental HiGHS enums are defined below. If Enum refers to a particular enum, and Member to a particular member, the members are available as follows.

Members for internal use only are not documented.

This is (part of) the return value of most HiGHS methods:

due to reaching a time or iteration limit

This defines the format of a HighsSparseMatrix:

This defines optimization sense of a HighsLp:

This defines the feasible values of a variable within a model:

This defines the format of a HighsHessian:

This defines the nature of any primal or dual solution information:

This defines the nature of any basis information:

This defines the status of the model after a call to run

This defines the status of a variable (or slack variable for a constraint) in a basis:

This defines the types of option values that control HiGHS:

This defines the types of (scalar) information available after a call to run:

---

## Other · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/interfaces/other/

**Contents:**
- Other Interfaces
- AMPL
- GAMS
- Javascript
- MATLAB
- R
- Rust

Some of the interfaces listed on this page are not officially supported by the HiGHS development team and are contributed by the community.

HiGHS can be used via AMPL, see the AMPL Documentation.

The interface is available at GAMSlinks, including pre-build libraries.

HiGHSMEX is a MATLAB interface that provides all the functionality of HiGHS, except the following: Reading problem data from a model file; Setting names for the rows and columns of the model, or setting name for the objective; Advanced features such as solution of systems using the current basis matrix.

The interface is avalailable for Windows, MacOS and Linux, and has been tested on Windows and MacOS. Pre-built binaries (mex files) for Windows and MacOS are available in the repository, which also includes instructions for building from source in README.md.

The HiGHS MIP and dual simplex LP solvers have been used within MATLAB (so for all architectures) by default since release 2024a.

---
