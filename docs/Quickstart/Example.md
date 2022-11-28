---
layout: default
title: Example
parent: Quickstart
nav_order: 3
---

# Quickstart Example

## Prerequisites
We assume that you have finished the [setup](../Setup.md) already.
In order to follow the example, please make sure you know the paths to the following executables, files and folders. 
Occurrences of names in capital letters (e.g. `DP_SOURCE`) should be replaced by the respective (absolute) paths.

- From installation of prerequisites:
    - `clang` / `clang++`
- From DiscoPoP Profiler installation:
    - `DP_SOURCE`: Path to the DiscoPoP source folder
    - `DP_BUILD`: Path to the DiscoPoP build folder

## Important Note
For the sake of simplicity, this example only shows the process to profile a single file manually.
In case you want to analyse a more complex project, please refer to the respective tutorial pages for detailed instructions regarding the [manual profiling](../Tutorials/Manual.md), the assisted profiling using the [Execution Wizard script](../Tutorials/Execution_Wizard.md) or the assisted profiling via the [graphical Configuration Wizard](../Tutorials/Configuration_Wizard.md).


<!--
    - Setup (install packages + Python dependencies + CMake build)
    - Apply DiscoPoP to the provided example code
    - Display and interpret suggestions (Not in detail. Link to a Wiki page which describes the suggestions instead)
    - Implement suggestion (in a provided, parallelized copy of the source code)
    - Compile sequential and parallel version of the code
    - Execute sequential and parallel version of the code and compare execution times (example should result in a significant difference)
-->

## Step 0: Enter the Example Directory
As a first step, please change your working directory to the `DP_SOURCE/example` directory:

    cd DP_SOURCE/example

## Step 1: Profiling

### Step 1.1: Create File Mapping
DiscoPoP requires an overview of the files in the target project (`FileMapping.txt`). This file can be created by simply executing the `dp-fmap` script located in the `DP_SOURCE/scripts` folder:

    ../scripts/dp-fmap

### Step 1.2: Compile the Target
To prepare the following instrumentation and profiling steps, we first have to compile the target source code to LLVM-IR.

    clang++ -g -c -O0 -S -emit-llvm -fno-discard-value-names example.cpp -o example.ll

The additional specified flags ensure the addition of debug information into `example.ll`, which is required for the later analyses steps.

### Step 1.3: Instrumentation and Static Analysis
After creating the LLVM-IR representation of our target source code, the `DiscoPoP` optimizer pass is loaded and executed.

    opt-11 -S -load=DP_BUILD/libi/LLVMDiscoPoP.so --DiscoPoP example.ll -o example_dp.ll --fm-path FileMapping.txt

In this process, the static analyses are executed and the instrumented version of `example.ll`, named `example_dp.ll` is created in order to prepare the dynamic profiling step.

### Step 1.4: Linking
In order to execute the profiled version of the target source code, we have to link it into an executable, in this case named `out_prof`.
Specifically, we have to link the DiscoPoP Runtime libraries in order to allow the profiling.

    clang++ example_dp.ll -o out_prof -LDP_BUILD/rtlib -lDiscoPoP_RT -lpthread

### Step 1.5: 
To execute the profiling and finish the collection of the required data, the created executable `out_prof` needs to be executed.

    ./out_prof

As a major result of the profiling, a file named `out_prof_dep.txt` will be created which contains information on the identified data dependencies.
Further details regarding the gathered data can be found [here](../Profiling/Data_Details.md).


## Step 2: Creating Parallelization Suggestions
In order to generate parallelization suggestions from the [gathered data](../Profiling/Data_Details.md), the [DiscoPoP Explorer](../Pattern_Detection/DiscoPoP_Explorer.md) has to be executed. Since all gathered data is stored in the current working directory and no files have been renamed, it is sufficient to specify the `--path` and the `--dep-file` arguments in order to generate the parallelization suggestions.
`--dep-file` has to be specified since it's name depends on the name of the original executable.

    discopop_explorer --path=. --dep-file=out_prof_dep.txt

By default, the DiscoPoP Explorer outputs parallelization suggestions to the console.
It should show three different suggestions in total.
The first should be a `Do-all` with the `Start line 1:8`.
The second should be a `Do-all` with the `Start line 1:12` and the third should be a `Geometric Decomposition`.
For detailed information on how to interpret and implement the created suggestions, please refer to their respective [pages](../Pattern_Detection/Patterns/Patterns.md).
One important thing to note is, however, that the second `Do-all` suggestion mentions a `reduction` variable (`sum`), which shows that the underlying identified parallel patterns for both `Do-all` suggestions are different.
Nevertheless, both are reported as `Do-all` patterns due to their similarities with regard to the OpenMP code used in order to implement the suggestions.

<br>
<i>Note: This potentially unclear reporting of `Do-all` and `Reduction` patterns will be fixed in the near future to further increase the readability of the created suggestions without tool support.</i>