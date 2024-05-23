# This file is part of the DiscoPoP software (http://www.discopop.tu-darmstadt.de)
#
# Copyright (c) 2020, Technische Universitaet Darmstadt, Germany
#
# This software may be modified and distributed under the terms of
# the 3-Clause BSD License.  See the LICENSE file in the package base
# directory for details.


from multiprocessing import Pool
from typing import List, cast, Set

from alive_progress import alive_bar  # type: ignore

from .PatternInfo import PatternInfo
from ..PEGraphX import (
    CUNode,
    LoopNode,
    PEGraphX,
    NodeType,
    Node,
    LineID,
    DepType,
    EdgeType,
    NodeID,
)
from ..utils import filter_for_hotspots, is_reduction_var, classify_loop_variables
from ..variable import Variable


class ReductionInfo(PatternInfo):
    """Class, that contains reduction detection result"""

    def __init__(self, pet: PEGraphX, node: Node):
        """
        :param pet: PET graph
        :param node: node, where reduction was detected
        """
        PatternInfo.__init__(self, node)
        self.pragma = "#pragma omp parallel for"

        fp, p, lp, s, r = classify_loop_variables(pet, node)
        self.first_private = fp
        self.private = p
        self.last_private = lp
        self.shared = s
        self.reduction = r

    def __str__(self):
        return (
            f"Reduction at: {self.node_id}\n"
            f"Start line: {self.start_line}\n"
            f"End line: {self.end_line}\n"
            f"pragma: {self.pragma}\n"
            f"private: {[v.name for v in self.private]}\n"
            f"shared: {[v.name for v in self.shared]}\n"
            f"first private: {[v.name for v in self.first_private]}\n"
            f'reduction: {[v.operation + ":" + v.name for v in self.reduction]}\n'
            f"last private: {[v.name for v in self.last_private]}"
        )


global_pet = None


def run_detection(pet: PEGraphX, hotspots) -> List[ReductionInfo]:
    """Search for reduction pattern

    :param pet: PET graph
    :return: List of detected pattern info
    """
    import tqdm  # type: ignore

    global global_pet
    global_pet = pet
    result: List[ReductionInfo] = []
    nodes = pet.all_nodes(LoopNode)

    nodes = cast(List[LoopNode], filter_for_hotspots(pet, cast(List[Node], nodes), hotspots))

    param_list = [(node) for node in nodes]
    with Pool(initializer=__initialize_worker, initargs=(pet,)) as pool:
        tmp_result = list(tqdm.tqdm(pool.imap_unordered(__check_node, param_list), total=len(param_list)))
    for local_result in tmp_result:
        result += local_result
    print("GLOBAL RES: ", [r.start_line for r in result])

    for pattern in result:
        pattern.get_workload(pet)
        pattern.get_per_iteration_workload(pet)

    return result


def __initialize_worker(pet):
    global global_pet
    global_pet = pet


def __check_node(param_tuple):
    global global_pet
    local_result = []
    node = param_tuple
    if __detect_reduction(global_pet, node):
        node.reduction = True
        if node.loop_iterations >= 0 and not node.contains_array_reduction:
            local_result.append(ReductionInfo(global_pet, node))

    return local_result


def __detect_reduction(pet: PEGraphX, root: LoopNode) -> bool:
    """Detects reduction pattern in loop

    :param pet: PET graph
    :param root: the loop node
    :return: true if is reduction loop
    """
    all_vars = []
    for node in pet.subtree_of_type(root, CUNode):
        all_vars.extend(node.local_vars)
        all_vars.extend(node.global_vars)

    # get required metadata
    loop_start_lines: List[LineID] = []
    root_children = pet.subtree_of_type(root, (CUNode, LoopNode))
    root_children_cus: List[CUNode] = [cast(CUNode, cu) for cu in root_children if cu.type == NodeType.CU]
    root_children_loops: List[LoopNode] = [cast(LoopNode, cu) for cu in root_children if cu.type == NodeType.LOOP]
    for v in root_children_loops:
        loop_start_lines.append(v.start_position())
    reduction_vars = [
        v
        for v in all_vars
        if is_reduction_var(root.start_position(), v.name, pet.reduction_vars)
        # and "**" not in v.type --> replaced by check for array reduction
    ]
    reduction_var_names = [v.name for v in reduction_vars]
    fp, p, lp, s, r = classify_loop_variables(pet, root)

    # get parents of loop
    parent_function_lineid = pet.get_parent_function(root).start_position()
    called_functions_lineids = __get_called_functions(pet, root)

    if __check_loop_dependencies(
        pet,
        root,
        root_children_cus,
        root_children_loops,
        loop_start_lines,
        reduction_var_names,
        fp,
        p,
        lp,
        parent_function_lineid,
        called_functions_lineids,
    ):
        return False

    # mark loop as containing array reductions, if variable types are accordingly
    if reduction_vars and len([v for v in reduction_vars if "**" in v.type]) > 0:
        root.contains_array_reduction = True

    # if the loop contains any reduction variable, create a reduction suggestion
    return bool(reduction_vars)


def __check_loop_dependencies(
    pet: PEGraphX,
    root_loop: LoopNode,
    root_children_cus: List[CUNode],
    root_children_loops: List[LoopNode],
    loop_start_lines: List[LineID],
    reduction_var_names: List[str],
    first_privates: List[Variable],
    privates: List[Variable],
    last_privates: List[Variable],
    parent_function_lineid: LineID,
    called_functions_lineids: List[LineID],
) -> bool:
    """Returns True, if dependencies between the respective subgraphs chave been found.
    Returns False otherwise, which results in the potential suggestion of a Reduction pattern."""
    # get recursive children of source and target
    loop_children_ids = [node.id for node in root_children_cus]

    # get dependency edges between children nodes
    deps = set()
    for n in loop_children_ids:
        deps.update([(s, t, d) for s, t, d in pet.in_edges(n, EdgeType.DATA) if s in loop_children_ids])
        deps.update([(s, t, d) for s, t, d in pet.out_edges(n, EdgeType.DATA) if t in loop_children_ids])

    for source, target, dep in deps:
        # check if targeted variable is readonly inside loop
        if pet.is_readonly_inside_loop_body(
            dep,
            root_loop,
            root_children_cus,
            root_children_loops,
            loops_start_lines=loop_start_lines,
        ):
            # variable is readonly -> no problem
            continue

        # check if targeted variable is loop index
        if pet.is_loop_index(dep.var_name, loop_start_lines, root_children_cus):
            continue

        # targeted variable is not read-only
        if dep.dtype == DepType.INIT:
            continue
        elif dep.dtype == DepType.RAW:
            # check RAW dependencies
            # Reductions are only valid, if the value of the reduction variable is not stored in a shared variable.
            # This property is violated if a RAW dependency for the reduction variable between different CUs exist
            # since CUs follow the Read-Compute-Write pattern.
            if dep.var_name in reduction_var_names:
                if source != target:
                    # if raw_deps for reduction variables between different CU's exist,
                    # the above described property is violated
                    # --> not a valid reduction
                    return True
            else:
                # RAW does not target a reduction variable.
                # RAW problematic, if it is not an intra-iteration RAW.
                if (
                    not dep.intra_iteration
                    and (dep.metadata_intra_iteration_dep is None or len(dep.metadata_intra_iteration_dep) == 0)
                    and parent_function_lineid
                    in (dep.metadata_intra_call_dep if dep.metadata_intra_call_dep is not None else [])
                ) or (
                    False
                    if dep.metadata_inter_call_dep is None
                    else (len([cf for cf in called_functions_lineids if cf in dep.metadata_inter_call_dep]) > 0)
                ):
                    return True
        elif dep.dtype == DepType.WAR:
            # check WAR dependencies
            # WAR problematic, if it is not an intra-iteration WAR and the variable is not private or firstprivate
            if (
                not dep.intra_iteration
                and (dep.metadata_intra_iteration_dep is None or len(dep.metadata_intra_iteration_dep) == 0)
                and parent_function_lineid
                in (dep.metadata_intra_call_dep if dep.metadata_intra_call_dep is not None else [])
            ) or (
                False
                if dep.metadata_inter_call_dep is None
                else (len([cf for cf in called_functions_lineids if cf in dep.metadata_inter_call_dep]) > 0)
            ):
                if dep.var_name not in [v.name for v in first_privates + privates + last_privates]:
                    return True
        elif dep.dtype == DepType.WAW:
            # check WAW dependencies
            # handled by variable classification
            pass
        else:
            raise ValueError("Unsupported dependency type: ", dep.dtype)

    # no problem found. Potentially suggest reduction
    return False


def __get_called_functions(pet: PEGraphX, root_loop: LoopNode) -> List[LineID]:
    """duplicates exists: do_all_detector <-> reduction_detector !"""
    # identify children CUs without following function calls
    called_functions: Set[NodeID] = set()
    queue = [root_loop.id]
    visited: Set[NodeID] = set()
    while queue:
        current = queue.pop()
        visited.add(current)
        # get called functions
        for s, t, e in pet.out_edges(current, EdgeType.CALLSNODE):
            called_functions.add(t)
        # add children to queue
        for s, t, e in pet.out_edges(current, EdgeType.CHILD):
            if t not in queue and t not in visited:
                queue.append(t)

    # convert node ids of called functions to line ids
    return [pet.node_at(n).start_position() for n in called_functions]
