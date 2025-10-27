# Highs - Options

**Pages:** 2

---

## List of options · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/options/definitions/

**Contents:**
- List of options
- presolve
- solver
- parallel
- run_crossover
- time_limit
- ranging
- infinite_cost
- infinite_bound
- small_matrix_value

---

## Introduction · HiGHS Documentation

**URL:** https://ergo-code.github.io/HiGHS/dev/options/intro/

**Contents:**
- Introduction
- Options file
- Option methods

The options that control HiGHS are of four types: boolean, integer, double and string. Their values can be specified:

When running the Executable via the command line, some options values can be set explicitly in the command, and all options can be set by means of an options file.

A sample options file, giving documentation of all the options is written to the console by the command:

The following code illustrates how to access the HiGHS options in Python. To set the value of option name, call:

where the value passed can be an identifier of the appropriate type, or an explicit value.

To get the value of option name, call:

To get the type of option name, call:

Examples of calls to options methods are given in the examples section.

**Examples:**

Example 1 (unknown):
```unknown
$ bin/highs --options_file=""
```

Example 2 (unknown):
```unknown
status = h.setOptionValue(name, value)
```

Example 3 (unknown):
```unknown
[status, value] = h.getOptionValue(name)
```

Example 4 (unknown):
```unknown
[status, type] = h.getOptionType(name)
```

---
