import os
import re

core_modules = [
    "position_engine", "proxy_v2", "regime_classifier", "trend_table",
    "fibonacci", "andrews_pitchfork", "wall_street_pattern", "manual_trend_channel",
    "diversification", "cluster_technique", "capital_tiers", "risk_aggregation_triple_system",
    "unified_protocol", "andrews_gate_alternative", "funding_rate_exact", "oos_xrp_faithful",
    "oos_xrp_recommended", "golden_master", "cluster_technique_threshold_robustness",
    "min_borders_sensitivity", "structural_confirmation_measure", "structure_causal_vs_batch_comparison",
    "walkforward_faithful", "walkforward_recommended", "walkforward_unified", "ablation_test_cycle",
    "replay_structure_causal_v5_v6_v7", "cross_stress_test_faithful_gates", "cross_stress_test_unified_capital_tiers"
]

backtest_modules = [
    "backtest_phase2", "backtest_phase2_faithful", "backtest_phase2_recommended", "backtest_phase2_v4",
    "backtest_phase2_v5", "backtest_phase2_v6", "backtest_phase2_v7", "backtest_phase2_v7_reverse",
    "backtest_phase2_v7_squeeze", "backtest_phase2_ut2", "backtest_phase2_patterns", "backtest_phase2_faithful_manual_channel",
    "backtest_phase2_diversification", "backtest_phase2_capital_tiers", "backtest_phase2_fib", "backtest_phase2_trend",
    "backtest_cascade3", "funding_rate_analysis"
]

def fix_imports_final(content):
    # 1. Clean sys.path hacks more aggressively
    content = re.sub(r'import sys.*?sys\.path\.insert\(0,.*?\)', '', content, flags=re.DOTALL)
    content = re.sub(r'sys\.path\.insert\(0,.*?\)', '', content)
    
    # 2. Fix specific broken lines from previous runs
    content = content.replace("import emile.backtests.backtest_phase2_faithful as backtest_phase2_faithful as mod", 
                              "from emile.backtests import backtest_phase2_faithful as mod")
    content = content.replace("import emile.run_all as run_all", "from emile import run_all")
    
    # 3. Update env_config
    content = re.sub(r'from\s+env_config\s+import', 'from emile.config.env_config import', content)
    
    # 4. Global replacements for core/backtests
    for mod in core_modules:
        content = re.sub(r'from\s+' + mod + r'\s+import', f'from emile.core.{mod} import', content)
        # Avoid double 'as' or double 'emile.core'
        content = content.replace(f"import emile.core.{mod} as {mod}", f"from emile.core import {mod}")
        content = re.sub(r'import\s+' + mod + r'\b', f'from emile.core import {mod}', content)

    for mod in backtest_modules:
        content = re.sub(r'from\s+' + mod + r'\s+import', f'from emile.backtests.{mod} import', content)
        content = content.replace(f"import emile.backtests.{mod} as {mod}", f"from emile.backtests import {mod}")
        content = re.sub(r'import\s+' + mod + r'\b', f'from emile.backtests import {mod}', content)

    # 5. Fix run_all.py ENGINES mapping
    if 'Engine("base",' in content:
        for mod in backtest_modules:
             content = content.replace(f'"{mod}"', f'"emile.backtests.{mod}"')
        content = content.replace('"unified_protocol"', '"emile.core.unified_protocol"')
        content = content.replace('"backtest_phase2_faithful"', '"emile.backtests.backtest_phase2_faithful"')

    return content

for folder in ["emile", "tests"]:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()
                updated = fix_imports_final(content)
                with open(path, "w") as f:
                    f.write(updated)

print("Final import fix complete.")
