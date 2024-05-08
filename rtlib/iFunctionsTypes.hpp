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

#include "loop/LoopManager.hpp"
#include "memory/MemoryManager.hpp"

#include <cstdint>
#include <unordered_map>
#include <set>
#include <string>
#include <vector>

namespace __dp {
    /******* Data structures *******/

typedef enum {
  RAW,
  WAR,
  WAW,
  INIT,
  RAW_II_0,
  RAW_II_1,
  RAW_II_2,
  WAR_II_0,
  WAR_II_1,
  WAR_II_2,
  WAW_II_0,
  WAW_II_1,
  WAW_II_2,
  // .._II_x to represent inter-iteration dependencies by loop level in case of
  // nested loops
} depType;

typedef enum {
  NOM,
  II_0,
  II_1,
  II_2 // NOM -> Normal
} depTypeModifier;

struct AccessInfo {
  AccessInfo(bool isRead, LID lid, char *var, std::string AAvar, ADDR addr,
             bool skip = false)
      : isRead(isRead), lid(lid), var(var), AAvar(AAvar), addr(addr),
        skip(skip) {}

  AccessInfo() : lid(0) {}

  bool isRead;
  // hybrid analysis
  bool skip;
  // End HA
  LID lid;
  char *var;
  std::string AAvar; // name of allocated variable -> "Anti Aliased Variable"
  ADDR addr;
  bool isStackAccess = false;
  bool addrIsFirstWrittenInScope = false;
  bool positiveScopeChangeOccuredSinceLastAccess = false;
};

// For runtime dependency merging
struct Dep {
  Dep(depType T, LID dep, char *var, std::string AAvar)
      : type(T), depOn(dep), var(var), AAvar(AAvar) {}

  depType type;
  LID depOn;
  char *var;
  std::string AAvar;
};

struct compDep {
  bool operator()(const Dep &a, const Dep &b) const {
    if (a.type < b.type) {
      return true;
    } else if (a.type == b.type && a.depOn < b.depOn) {
      return true;
    }
    // comparison between string is very time-consuming. So just compare
    // variable names according to address (we only need to distinguish them)
    else if (a.type == b.type && a.depOn == b.depOn &&
             ((size_t)a.var < (size_t)b.var)) {
      return true;
    }

    return false;
  }
};

typedef std::set<Dep, compDep> depSet;
typedef std::unordered_map<LID, depSet *> depMap;
// Hybrid anaysis
typedef std::unordered_map<std::string, std::set<std::string>> stringDepMap;
// End HA

// For function merging
// 1) when two BGN func are identical

typedef std::unordered_map<LID, std::set<LID> *> BGNFuncList;

// Hybrid analysis
typedef std::set<std::uint32_t> ReportedBBSet;
typedef std::set<std::string> ReportedBBPairSet;
// End HA
// 2) when two END func are identical

typedef std::set<LID> ENDFuncList;
} // namespace __dp

// issue a warning if DP_PTHREAD_COMPATIBILITY_MODE is enabled
#ifdef DP_PTHREAD_COMPATIBILITY_MODE
#warning                                                                       \
    "DP_PTHREAD_COMPATIBILITY_MODE enabled! This may have negative implications on the profiling time."
#endif
