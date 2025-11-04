"""Solver Configuration - Optimized settings from incremental testing."""

class SolverConfig:
    """HiGHS MIP settings that reduced solve from 120s to 16s."""

    HIGHS_MIP_FAST = {
        'presolve': 'on',
        'parallel': 'on',
        'mip_rel_gap': 0.02,
        'time_limit': 30.0,
    }

    @staticmethod
    def configure(solver, mode='fast'):
        solver.highs_options = SolverConfig.HIGHS_MIP_FAST
        return solver
