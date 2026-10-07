"""Canonical paths for the AgriAgent project.

Always import from here instead of hardcoding paths. Paths resolve from this
file's location, so they work regardless of the current working directory.
"""
from pathlib import Path

# Resolve from code/analysis/paths.py to the package root.
SRC_DIR = Path(__file__).resolve().parent
AGRIAGENT_DIR = SRC_DIR.parents[1]
REPO_ROOT = AGRIAGENT_DIR

# Data directories
LSMS_DATA_DIR = AGRIAGENT_DIR / "data" / "lsms_raw"
LSMS_PLOT_DTA = LSMS_DATA_DIR / "Plot_dataset.dta"
LSMS_HH_DTA = LSMS_DATA_DIR / "Household_dataset.dta"
LSMS_PLOTCROP_DTA = LSMS_DATA_DIR / "Plotcrop_dataset.dta"
LSMS_IND_DTA = LSMS_DATA_DIR / "Individual_dataset.dta"

# Project data (derived samples, summaries)
DATA_DIR = AGRIAGENT_DIR / "data"
LSMS_OUT_DIR = DATA_DIR
LSMS_4C_PILOT_CSV = LSMS_OUT_DIR / "lsms_4country_pilot.csv"
LSMS_4C_PILOT_STATS = LSMS_OUT_DIR / "lsms_4country_pilot_stats.md"
LSMS_4C_FULL_CSV = LSMS_OUT_DIR / "lsms_4country_full.csv"
LSMS_4C_FULL_STATS = LSMS_OUT_DIR / "lsms_4country_full_stats.md"
LSMS_NIGERIA_PILOT_CSV = LSMS_OUT_DIR / "lsms_pilot_sample.csv"
LSMS_DQ_FINDINGS = LSMS_OUT_DIR / "data_quality_findings.md"

# Prompts
PROMPTS_DIR = AGRIAGENT_DIR / "prompts"
LSMS_4C_TIER1_TEMPLATE = PROMPTS_DIR / "lsms" / "T1_identity_card.txt"
FARMER_AGENT_SKILL = PROMPTS_DIR / "quzhou" / "T4_farmer_skill" / "SKILL.md"

# Results
RESULTS_DIR = AGRIAGENT_DIR / "raw_agent_output"
RESULTS_QUZHOU_DIR = RESULTS_DIR / "quzhou"
RESULTS_LSMS_DIR = RESULTS_DIR / "lsms"
RESULTS_LSMS_COMBINED = RESULTS_LSMS_DIR / "combined"

# Canonical settings
SEED = 42
CLAUDE_CLI_CMD = ["claude", "-p", "--allowedTools", ""]
CODEX_CLI_CMD = ["npx", "@openai/codex", "exec", "--skip-git-repo-check",
                 "--full-auto", "--ephemeral"]
KIMI_CLI_CMD_ENV = {"DYLD_LIBRARY_PATH": "/opt/homebrew/opt/expat/lib"}
LLM_TIMEOUT_SEC = 300
LLM_RETRIES = 1

# Country configuration (active 4-country pilot)
COUNTRY_WAVES = {
    "Nigeria": 4,
    "Ethiopia": 3,
    "Tanzania": 3,
    "Malawi": 4,
}

# Filter constants (from data_quality_findings.md)
PLOT_AREA_MIN_HA = 0.05
PLOT_AREA_MAX_HA = 20.0
N_HA_CAP = 300.0  # kg N / ha — cap above this to NaN
YIELD_HA_CAP = 8000.0  # kg / ha — cap above this to NaN


def ensure_data_exists():
    """Fast check that the LSMS data directory is in place."""
    if not LSMS_DATA_DIR.is_dir():
        raise FileNotFoundError(
            f"LSMS data directory not found at {LSMS_DATA_DIR}. "
            f"Provide the harmonized .dta files under {LSMS_DATA_DIR} "
            "if rerunning sample construction. The packaged derived 280-row sample "
            "does not require these restricted source files."
        )
    if not LSMS_PLOT_DTA.is_file():
        raise FileNotFoundError(f"Missing {LSMS_PLOT_DTA}")
    return True


if __name__ == "__main__":
    # Quick self-check when run directly
    print(f"REPO_ROOT         = {REPO_ROOT}")
    print(f"AGRIAGENT_DIR     = {AGRIAGENT_DIR}")
    print(f"LSMS_DATA_DIR     = {LSMS_DATA_DIR}  (exists: {LSMS_DATA_DIR.is_dir()})")
    print(f"LSMS_PLOT_DTA     = {LSMS_PLOT_DTA}  (exists: {LSMS_PLOT_DTA.is_file()})")
    print(f"LSMS_4C_PILOT_CSV = {LSMS_4C_PILOT_CSV}  (exists: {LSMS_4C_PILOT_CSV.is_file()})")
    print(f"LSMS_4C_TIER1     = {LSMS_4C_TIER1_TEMPLATE}  (exists: {LSMS_4C_TIER1_TEMPLATE.is_file()})")
    ensure_data_exists()
    print("\nAll required paths OK.")
