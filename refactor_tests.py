import os
import shutil
import re
from pathlib import Path

# 1. Revert to clean state first (will be called before running this script in shell)

# 2. Define paths
ROOT = Path(".")
EMILE_DIR = ROOT / "emile"
CORE_DIR = EMILE_DIR / "core"
BACKTESTS_DIR = EMILE_DIR / "backtests"
CONFIG_DIR = EMILE_DIR / "config"
TESTS_DIR = ROOT / "tests"
UNIT_TESTS_DIR = TESTS_DIR / "unit"
DOCS_DIR = ROOT / "docs"
RESULTS_DIR = ROOT / "results"

# Create directories
for d in [CORE_DIR, BACKTESTS_DIR, CONFIG_DIR, UNIT_TESTS_DIR, DOCS_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").touch()

(EMILE_DIR / "__init__.py").touch()
(TESTS_DIR / "__init__.py").touch()

# 3. Move files
# Move Markdown files to docs/ (except GEMINI.md)
for f in ROOT.glob("*.md"):
    if f.name != "GEMINI.md":
        shutil.move(str(f), str(DOCS_DIR / f.name))

# Move CSV files to results/
for f in ROOT.glob("*.csv"):
    shutil.move(str(f), str(RESULTS_DIR / f.name))

# Move funding_rate_analysis.py to emile/backtests/
if ROOT.joinpath("funding_rate_analysis.py").exists():
    shutil.move("funding_rate_analysis.py", str(BACKTESTS_DIR / "funding_rate_analysis.py"))

# Let's list files in code/
code_dir = ROOT / "code"
core_modules = [
    "position_engine.py", "proxy_v2.py", "regime_classifier.py", "trend_table.py",
    "fibonacci.py", "andrews_pitchfork.py", "wall_street_pattern.py", "manual_trend_channel.py",
    "diversification.py", "cluster_technique.py", "capital_tiers.py", "risk_aggregation_triple_system.py",
    "unified_protocol.py", "andrews_gate_alternative.py", "funding_rate_exact.py", "oos_xrp_faithful.py",
    "oos_xrp_recommended.py", "golden_master.py", "cluster_technique_threshold_robustness.py",
    "min_borders_sensitivity.py", "structural_confirmation_measure.py", "structure_causal_vs_batch_comparison.py",
    "walkforward_faithful.py", "walkforward_recommended.py", "walkforward_unified.py", "ablation_test_cycle.py",
    "replay_structure_causal_v5_v6_v7.py", "cross_stress_test_faithful_gates.py", "cross_stress_test_unified_capital_tiers.py"
]

# Move core files
for m in core_modules:
    src_file = code_dir / m
    if src_file.exists():
        shutil.move(str(src_file), str(CORE_DIR / m))

# Move test files
for f in code_dir.glob("test_*.py"):
    shutil.move(str(f), str(UNIT_TESTS_DIR / f.name))

# Move backtest files
for f in code_dir.glob("backtest_*.py"):
    shutil.move(str(f), str(BACKTESTS_DIR / f.name))

# Move run_all.py to emile/
if (code_dir / "run_all.py").exists():
    shutil.move(str(code_dir / "run_all.py"), str(EMILE_DIR / "run_all.py"))

# Clean up code/ if empty
shutil.rmtree(str(code_dir), ignore_errors=True)

# 4. Write Config File emile/config/env_config.py
config_content = """import os
from pathlib import Path

def get_data_dir() -> Path:
    env_dir = os.getenv("EMILE_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    
    # Fallback default
    default_dir = Path("data/processed")
    if default_dir.exists():
        return default_dir
        
    raise FileNotFoundError(
        "Data directory not found. Please set EMILE_DATA_DIR env var "
        "or ensure 'data/processed' exists at project root."
    )

DATA_DIR = get_data_dir()
"""
with open(CONFIG_DIR / "env_config.py", "w") as f:
    f.write(config_content)

print("Files moved successfully. Starting import and path updates...")
