/*
 * This file is part of the DiscoPoP software
 * (http://www.discopop.tu-darmstadt.de)
 *
 * Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
 *
 * This software may be modified and distributed under the terms of
 * the 3-Clause BSD License. See the LICENSE file in the package base
 * directory for details.
 *
 */

#pragma once

#include "DPTypes.hpp"
#include "iFunctionsTypes.hpp"
#include "abstract_shadow.hpp"

#include <string>

namespace __dp {

/******* Helper functions *******/
void addDep(depType type, LID curr, LID depOn, char *var, char *AAvar);

void outputDeps();

void outputLoops();

void outputFuncs();

void outputAllocations();

void generateStringDepMap();

void readRuntimeInfo();

void initParallelization();

void initSingleThreadedExecution();

void mergeDeps();

void *analyzeDeps(void *arg);

void analyzeSingleAccess(__dp::Shadow* SMem, __dp::AccessInfo& access);

std::string getMemoryRegionIdFromAddr(std::string fallback, ADDR addr);

void finalizeParallelization();

void finalizeSingleThreadedExecution();

void clearStackAccesses(ADDR stack_lower_bound, ADDR stack_upper_bound);
} // namespace __dp
