"""
Model Feature Registry

Tracks which features are in which incremental test level.
This provides clear documentation and enables automated validation.
"""

from typing import List, Dict, Set


# Feature definitions
MODEL_FEATURES = {
    'Level01': ['production_variables', 'demand_satisfaction'],

    'Level02': ['production_variables', 'demand_satisfaction', 'material_balance'],

    'Level03': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory'],

    'Level04': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic'],

    'Level05': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables'],

    'Level06': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables', 'mix_based_production'],

    'Level07': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables', 'mix_based_production', 'truck_capacity'],

    'Level08': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables', 'mix_based_production', 'truck_capacity',
                'pallet_tracking'],

    'Level09': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables', 'mix_based_production', 'truck_capacity',
                'pallet_tracking', 'multiple_products'],

    'Level10': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables', 'mix_based_production', 'truck_capacity',
                'pallet_tracking', 'multiple_products', 'distributed_initial_inventory'],

    'Level11': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'sliding_window_basic', 'multi_node_network',
                'transport_variables', 'mix_based_production', 'truck_capacity',
                'pallet_tracking', 'multiple_products', 'distributed_initial_inventory',
                'all_features_combined'],

    'Level12': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'transport_variables',
                'mix_based_production', 'truck_capacity', 'pallet_tracking',
                'multiple_products', 'distributed_initial_inventory',
                'sliding_window_all_nodes'],

    'Level13': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'mix_based_production',
                'truck_capacity', 'pallet_tracking', 'multiple_products',
                'distributed_initial_inventory', 'sliding_window_all_nodes',
                'in_transit_variables'],

    'Level14': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'mix_based_production',
                'truck_capacity', 'pallet_tracking', 'multiple_products',
                'distributed_initial_inventory', 'sliding_window_all_nodes',
                'in_transit_variables', 'demand_consumed_in_sliding_window'],

    'Level15': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'mix_based_production',
                'truck_capacity', 'pallet_tracking', 'multiple_products',
                'distributed_initial_inventory', 'sliding_window_all_nodes',
                'in_transit_variables', 'demand_consumed_in_sliding_window',
                'dynamic_arrivals'],

    'Level16': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'mix_based_production',
                'truck_capacity', 'pallet_tracking', 'multiple_products',
                'distributed_initial_inventory', 'sliding_window_all_nodes',
                'in_transit_variables', 'demand_consumed_in_sliding_window',
                'dynamic_arrivals', 'arrivals_in_sliding_window_q'],

    'Level17': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'mix_based_production',
                'truck_capacity', 'pallet_tracking', 'multiple_products',
                'distributed_initial_inventory', 'sliding_window_all_nodes',
                'in_transit_variables', 'demand_consumed_in_sliding_window',
                'dynamic_arrivals', 'arrivals_in_sliding_window_q',
                'frozen_state', 'freeze_thaw_transitions'],

    'Level18': ['production_variables', 'demand_satisfaction', 'material_balance',
                'initial_inventory', 'multi_node_network', 'truck_capacity',
                'pallet_tracking', 'multiple_products', 'distributed_initial_inventory',
                'sliding_window_all_nodes', 'in_transit_variables',
                'demand_consumed_in_sliding_window', 'dynamic_arrivals',
                'arrivals_in_sliding_window_q', 'frozen_state', 'freeze_thaw_transitions',
                'mix_integer_variables', 'optimized_mip_settings'],
}


# Feature dependencies (prerequisites)
FEATURE_DEPENDENCIES = {
    'material_balance': ['production_variables'],
    'sliding_window_basic': ['material_balance'],
    'sliding_window_all_nodes': ['material_balance', 'multi_node_network'],
    'in_transit_variables': ['multi_node_network', 'transport_variables'],
    'dynamic_arrivals': ['in_transit_variables'],
    'arrivals_in_sliding_window_q': ['sliding_window_all_nodes', 'dynamic_arrivals'],
    'freeze_thaw_transitions': ['frozen_state'],
    'mix_integer_variables': ['production_variables'],
    'demand_consumed_in_sliding_window': ['sliding_window_all_nodes'],
}


# Performance expectations (solve time in seconds)
PERFORMANCE_TARGETS = {
    'Level01': {'simple': 0.01, 'real_1week': 0.05, 'real_4weeks': 0.1},
    'Level04': {'simple': 0.01, 'real_1week': 0.05, 'real_4weeks': 0.1},
    'Level08': {'simple': 0.05, 'real_1week': 0.2, 'real_4weeks': 1.0},
    'Level16': {'simple': 0.1, 'real_1week': 0.5, 'real_4weeks': 2.0},
    'Level18': {'simple': 0.5, 'real_1week': 5.0, 'real_4weeks': 30.0},  # MIP with integers
}


# Quality expectations (minimum production, maximum shortage rate)
QUALITY_TARGETS = {
    'simple_data': {'min_production': 100, 'max_shortage_rate': 0.05},  # 5% shortage OK
    'real_1week': {'min_production': 10000, 'max_shortage_rate': 0.15},  # 15% shortage OK
    'real_4weeks': {'min_production': 100000, 'max_shortage_rate': 0.15},
}


def get_features_at_level(level: int) -> List[str]:
    """Get list of features at a specific level."""
    key = f'Level{level:02d}'
    return MODEL_FEATURES.get(key, [])


def get_new_features_at_level(level: int) -> List[str]:
    """Get features ADDED at this level (not in previous level)."""
    current = set(get_features_at_level(level))
    previous = set(get_features_at_level(level - 1)) if level > 1 else set()

    return list(current - previous)


def validate_feature_dependencies(features: List[str]) -> bool:
    """Validate all feature dependencies are satisfied."""
    feature_set = set(features)

    for feature in features:
        deps = FEATURE_DEPENDENCIES.get(feature, [])
        for dep in deps:
            if dep not in feature_set:
                raise ValueError(
                    f"Feature '{feature}' requires '{dep}' but it's not enabled. "
                    f"Add '{dep}' first or check FEATURE_DEPENDENCIES."
                )

    return True


def get_current_level() -> str:
    """Get the highest implemented level."""
    levels = sorted([int(k.replace('Level', '')) for k in MODEL_FEATURES.keys()])
    return f"Level{levels[-1]:02d}" if levels else "Level00"


def get_performance_target(level: int, data_scale: str) -> float:
    """Get expected solve time for level and data scale."""
    key = f'Level{level:02d}'
    targets = PERFORMANCE_TARGETS.get(key, {})
    return targets.get(data_scale, 60.0)  # Default: 60s


def get_quality_target(data_scale: str) -> Dict:
    """Get quality targets for data scale."""
    return QUALITY_TARGETS.get(data_scale, {
        'min_production': 0,
        'max_shortage_rate': 0.5
    })


# Critical bugs fixed (for documentation)
BUGS_FIXED = {
    'disposal_pathway': {
        'level_found': 'During development',
        'fix': 'Only allow disposal when inventory expires (t >= expiration_date)',
        'file': 'sliding_window_model.py:575-626',
    },
    'init_inv_multi_counting': {
        'level_found': 'Level 4',
        'fix': 'Only add init_inv when window includes Day 1',
        'file': 'sliding_window_model.py:774-781',
        'impact': 'Created 793k virtual units (16× overcounting)',
    },
    'sliding_window_formulation': {
        'level_found': 'Level 4',
        'fix': 'Changed inventory[t] <= Q-O to O <= Q',
        'file': 'sliding_window_model.py:857, 940, 1003',
        'impact': 'CAUSED INFEASIBILITY - most critical bug',
    },
    'product_id_mismatch': {
        'level_found': 'Validation layer',
        'fix': 'Automatic alias resolution',
        'file': 'validation/data_coordinator.py',
    },
    'thawed_inventory_overcreation': {
        'level_found': 'Level 17',
        'fix': 'Only create thawed inventory where needed',
        'file': 'verified_sliding_window_model.py:408-415',
    },
    'arrivals_in_sliding_window': {
        'level_found': 'Level 17',
        'fix': 'Check departure_date in model.dates (not window_dates)',
        'file': 'verified_sliding_window_model.py:522-527',
    },
    'mip_solver_settings': {
        'level_found': 'Level 18',
        'fix': 'Use optimized HiGHS settings (presolve=on, parallel=on, gap=2%)',
        'file': 'solver_config.py',
        'impact': 'Reduced solve time from 120s+ to 16s',
    },
}


if __name__ == "__main__":
    # Demo usage
    print("Feature Registry Demo")
    print("=" * 80)

    print(f"\nCurrent level: {get_current_level()}")

    print(f"\nFeatures at Level 18:")
    for feature in get_features_at_level(18):
        print(f"  - {feature}")

    print(f"\nNEW in Level 18:")
    for feature in get_new_features_at_level(18):
        print(f"  + {feature}")

    print(f"\nPerformance targets:")
    for level in [1, 4, 8, 16, 18]:
        for scale in ['simple', 'real_1week', 'real_4weeks']:
            target = get_performance_target(level, scale)
            print(f"  Level {level:2d} ({scale:12s}): <{target:6.1f}s")

    print(f"\nBugs fixed via incremental approach:")
    for bug_name, info in BUGS_FIXED.items():
        print(f"  - {bug_name}: {info['fix']}")
