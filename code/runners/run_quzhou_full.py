"""
Quzhou Full-Scale Run — 505 farmers × 4 tiers × 3 models

Reuses the exact same tier prompt structure as the 10-farmer pilot
(tier1.py, tier2.py, tier3.py, tier4.py).

Usage:
    python3 code/runners/run_quzhou_full.py run <tier> <provider>
    python3 code/runners/run_quzhou_full.py run 1 claude
    python3 code/runners/run_quzhou_full.py run all claude
    python3 code/runners/run_quzhou_full.py run 1,2,3,4 all
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Path setup ───────────────────────────────────────────────

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "raw_agent_output" / "quzhou"
PROMPT_DIR = PROJECT_ROOT / "prompts" / "quzhou"
SKILL_DOC_PATH = PROMPT_DIR / "T4_farmer_skill" / "SKILL.md"

sys.path.insert(0, str(PROJECT_ROOT / "code" / "analysis"))
from profiles import load_profiles_quzhou, FarmerProfile

# Kimi env workaround
KIMI_CLI_CMD_ENV = {"DYLD_LIBRARY_PATH": "/opt/homebrew/opt/expat/lib"}

# ── Constants ────────────────────────────────────────────────

LLM_TIMEOUT_SEC = 300
MAX_RETRIES = 3
RETRY_BACKOFF = [30, 60, 120]  # seconds
PROGRESS_EVERY = 10

MU_TO_HA = 1.0 / 15.0

# ── JSON extraction ─────────────────────────────────────────

def extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response text."""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    brace_depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    return None


# ── CLI Callers (with exponential backoff) ──────────────────

def _clean_env_for_claude() -> dict:
    """Strip Claude Code session env vars so subprocess uses the user's
    real OAuth subscription at ~/.claude/credentials/ (stable, auto-refreshing
    via interactive CLI) instead of the outer harness's short-lived tokens."""
    strip_keys = {
        "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_ENTRYPOINT", "CLAUDECODE",
        "CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST",
        "CLAUDE_CODE_EXECPATH", "CLAUDE_CODE_SDK_HAS_OAUTH_REFRESH",
        "CLAUDE_AGENT_SDK_VERSION",
    }
    return {k: v for k, v in os.environ.items() if k not in strip_keys}


def call_claude(prompt: str) -> dict:
    """Call Claude Code via CLI with retry."""
    last_err = None
    clean_env = _clean_env_for_claude()
    for attempt in range(MAX_RETRIES + 1):
        try:
            t0 = time.time()
            result = subprocess.run(
                ["claude", "-p", "--allowedTools", ""],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=LLM_TIMEOUT_SEC,
                env=clean_env,
            )
            elapsed = round(time.time() - t0, 1)
            raw = result.stdout.strip()
            if result.returncode != 0 and not raw:
                raise RuntimeError(f"claude CLI failed: {result.stderr[:300]}")
            # Check for auth errors
            if '"authentication_error"' in raw or '"error"' in raw[:50]:
                raise RuntimeError(f"Auth error: {raw[:200]}")
            decision = extract_json(raw)
            return {
                "raw_response": raw,
                "decision": decision,
                "elapsed_seconds": elapsed,
                "model": "claude-cli",
                "attempts": attempt + 1,
            }
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                print(f"      Retry {attempt+1}/{MAX_RETRIES} after {wait}s — {e}")
                time.sleep(wait)
    return {"raw_response": "", "decision": None,
            "error": str(last_err), "model": "claude-cli",
            "attempts": MAX_RETRIES + 1}


def call_codex(prompt: str) -> dict:
    """Call Codex via CLI with retry."""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            t0 = time.time()
            result = subprocess.run(
                ["npx", "@openai/codex", "exec",
                 "--skip-git-repo-check", "--full-auto",
                 prompt],
                capture_output=True, text=True,
                timeout=LLM_TIMEOUT_SEC,
            )
            elapsed = round(time.time() - t0, 1)
            raw = result.stdout.strip()
            if result.returncode != 0 and not raw:
                raise RuntimeError(f"codex CLI failed: {result.stderr[:300]}")
            decision = extract_json(raw)
            return {
                "raw_response": raw,
                "decision": decision,
                "elapsed_seconds": elapsed,
                "model": "codex-cli/gpt-5.4",
                "attempts": attempt + 1,
            }
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                print(f"      Retry {attempt+1}/{MAX_RETRIES} after {wait}s — {e}")
                time.sleep(wait)
    return {"raw_response": "", "decision": None,
            "error": str(last_err), "model": "codex-cli/gpt-5.4",
            "attempts": MAX_RETRIES + 1}


def call_kimi(prompt: str) -> dict:
    """Call Kimi CLI with retry."""
    env = {**os.environ, **KIMI_CLI_CMD_ENV}
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            t0 = time.time()
            result = subprocess.run(
                ["kimi", "--print", "--final-message-only",
                 "--input-format", "text"],
                input=prompt,
                capture_output=True, text=True,
                timeout=LLM_TIMEOUT_SEC,
                env=env,
            )
            elapsed = round(time.time() - t0, 1)
            raw = result.stdout.strip()
            if result.returncode != 0 and not raw:
                raise RuntimeError(f"kimi CLI failed: {result.stderr[:300]}")
            decision = extract_json(raw)
            return {
                "raw_response": raw,
                "decision": decision,
                "elapsed_seconds": elapsed,
                "model": "kimi-cli/kimi-for-coding",
                "attempts": attempt + 1,
            }
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                print(f"      Retry {attempt+1}/{MAX_RETRIES} after {wait}s — {e}")
                time.sleep(wait)
    return {"raw_response": "", "decision": None,
            "error": str(last_err), "model": "kimi-cli/kimi-for-coding",
            "attempts": MAX_RETRIES + 1}


CALLERS = {"claude": call_claude, "codex": call_codex, "kimi": call_kimi}


# ── Prompt text (prompts/quzhou/) ────────────────────────────
# T1 and T2 share the short role, T2 and T3 share the profile/task template,
# T3 swaps in the decision guide and T4 swaps in the farmer skill.

def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


TIER1_SYSTEM_PROMPT = _prompt("T1_T2_role.txt")
TIER1_USER_TEMPLATE = _prompt("T1_user.txt")
TIER2_USER_TEMPLATE = _prompt("T2_T3_user.txt")
TIER3_SYSTEM_PROMPT = _prompt("T3_guide.txt")
TIER4_SYSTEM_PROMPT = SKILL_DOC_PATH.read_text(encoding="utf-8")
TIER4_USER_TEMPLATE = _prompt("T4_user.txt")


# ── Prompt Builders ──────────────────────────────────────────

def _profile_to_tier2_fields(prof: FarmerProfile) -> dict:
    """Extract Tier 2+ template fields from a FarmerProfile."""
    farm_size_mu = round(prof.farm_size_ha / MU_TO_HA, 1)
    crops_list = ", ".join(prof.crops_grown[:-1]) + (
        f", and {prof.crops_grown[-1]}" if len(prof.crops_grown) > 1
        else prof.crops_grown[0] if prof.crops_grown else "wheat and maize"
    )
    off_farm_line = "Some family members work off-farm. " if prof.off_farm_work else ""
    irrigation_line = "I have access to well irrigation."
    return {
        "age": prof.age,
        "gender": prof.gender,
        "education": prof.education,
        "experience": prof.farming_experience_years or 20,
        "farm_size_mu": farm_size_mu,
        "crops_list": crops_list,
        "cropping_system": prof.cropping_system or "wheat-maize double cropping",
        "household_size": prof.household_size or 4,
        "off_farm_line": off_farm_line,
        "irrigation_line": irrigation_line,
    }


def build_tier1_prompt(prof: FarmerProfile) -> str:
    """Tier 1: Demographics only (age, gender, education, location)."""
    user = TIER1_USER_TEMPLATE.format(
        age=prof.age,
        gender=prof.gender,
        education=prof.education,
    )
    return TIER1_SYSTEM_PROMPT + "\n\n" + user


def build_tier2_prompt(prof: FarmerProfile) -> str:
    """Tier 2: Demographics + farm context."""
    fields = _profile_to_tier2_fields(prof)
    user = TIER2_USER_TEMPLATE.format(**fields)
    return TIER1_SYSTEM_PROMPT + "\n\n" + user


def build_tier3_prompt(prof: FarmerProfile) -> str:
    """Tier 3: Cognitive grounding system prompt + Tier 2 user prompt."""
    fields = _profile_to_tier2_fields(prof)
    user = TIER2_USER_TEMPLATE.format(**fields)
    return TIER3_SYSTEM_PROMPT + "\n\n" + user


def build_tier4_prompt(prof: FarmerProfile) -> str:
    """Tier 4: FARMER_AGENT_SKILL.md + Tier 4 user prompt (no JSON schema)."""
    fields = _profile_to_tier2_fields(prof)
    user = TIER4_USER_TEMPLATE.format(**fields)
    return TIER4_SYSTEM_PROMPT + "\n\n" + user


PROMPT_BUILDERS = {
    1: build_tier1_prompt,
    2: build_tier2_prompt,
    3: build_tier3_prompt,
    4: build_tier4_prompt,
}


# ── Field name normalization (Tier 4) ───────────────────────

def normalize_plan_entry(p: dict) -> dict:
    """Map Tier 4 skill-doc field names to Tier 1-3 names for comparison."""
    out = dict(p)
    if "nitrogen_total_kg_per_mu" in out and "nitrogen_kg_per_mu" not in out:
        out["nitrogen_kg_per_mu"] = out["nitrogen_total_kg_per_mu"]
    if "field_area_mu" in out and "area_mu" not in out:
        out["area_mu"] = out["field_area_mu"]
    if "yield_expectation_kg_per_mu" in out and "expected_yield_kg_per_mu" not in out:
        out["expected_yield_kg_per_mu"] = out["yield_expectation_kg_per_mu"]
    if "phosphorus_total_kg_per_mu" in out and "phosphorus_kg_per_mu" not in out:
        out["phosphorus_kg_per_mu"] = out["phosphorus_total_kg_per_mu"]
    if "potassium_total_kg_per_mu" in out and "potassium_kg_per_mu" not in out:
        out["potassium_kg_per_mu"] = out["potassium_total_kg_per_mu"]
    return out


# ── Run ──────────────────────────────────────────────────────

def run_quzhou(tiers=None, providers=None):
    """
    Run the full Quzhou experiment.

    Results saved per-farmer to:
        raw_agent_output/quzhou/{provider}/tier{N}/{farmer_id}.json
    """
    tiers = tiers or [1, 2, 3, 4]
    providers = providers or ["claude", "codex", "kimi"]

    # Load ALL profiles
    print("Loading Quzhou profiles...")
    profiles, ground_truth = load_profiles_quzhou(str(DATA_DIR / "quzhou"))
    print(f"  {len(profiles)} profiles, {len(ground_truth)} with ground truth")

    # Save ground truth once
    gt_path = RESULTS_DIR / "_ground_truth.json"
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2, default=str)

    # Save metadata
    meta = {
        "experiment": "quzhou_full",
        "n_profiles": len(profiles),
        "tiers": tiers,
        "providers": providers,
        "timestamp": datetime.now().isoformat(),
        "tier_descriptions": {
            1: "Demographics only (age, gender, education, location)",
            2: "Demographics + farm context (size, crops, system, experience, HH, off-farm, irrigation)",
            3: "Cognitive grounding system prompt (478 words) + Tier 2 user",
            4: "FARMER_AGENT_SKILL.md (1682 words) + Tier 4 user (no JSON schema in user prompt)",
        },
    }
    with open(RESULTS_DIR / "_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    # Run: provider → tier → farmers
    for provider in providers:
        caller = CALLERS[provider]
        for tier in tiers:
            builder = PROMPT_BUILDERS[tier]
            tier_dir = RESULTS_DIR / provider / f"tier{tier}"
            tier_dir.mkdir(parents=True, exist_ok=True)
            errors_log = RESULTS_DIR / provider / "errors.log"

            n_total = len(profiles)
            n_done = 0
            n_skipped = 0
            n_errors = 0
            elapsed_list = []
            t_start = time.time()

            print(f"\n{'='*70}")
            print(f"[{provider.upper()} T{tier}] Starting — {n_total} farmers")
            print(f"{'='*70}")

            for i, prof in enumerate(profiles):
                farmer_id = prof.source_id
                out_path = tier_dir / f"{farmer_id}.json"

                # Skip if already done
                if out_path.exists():
                    try:
                        existing = json.load(open(out_path))
                        if existing.get("decision") is not None:
                            n_skipped += 1
                            n_done += 1
                            continue
                    except (json.JSONDecodeError, KeyError):
                        pass  # Re-run corrupted files

                # Build prompt
                prompt = builder(prof)

                # Call LLM
                result = caller(prompt)

                # Normalize Tier 4 field names
                if tier == 4 and result.get("decision"):
                    dec = result["decision"]
                    if "annual_plan" in dec:
                        dec["annual_plan"] = [
                            normalize_plan_entry(p) for p in dec["annual_plan"]
                        ]

                # Add metadata
                result["farmer_id"] = farmer_id
                result["tier"] = tier
                result["provider"] = provider

                # Save immediately
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, default=str)

                n_done += 1
                if result.get("decision"):
                    elapsed_list.append(result.get("elapsed_seconds", 0))
                else:
                    n_errors += 1
                    err_msg = f"[{provider} T{tier}] {farmer_id}: {result.get('error', 'no JSON parsed')}\n"
                    with open(errors_log, "a") as ef:
                        ef.write(err_msg)

                # Progress report
                if (n_done - n_skipped) % PROGRESS_EVERY == 0 or i == n_total - 1:
                    avg_s = sum(elapsed_list) / len(elapsed_list) if elapsed_list else 0
                    remaining = n_total - n_done
                    eta_h = (remaining * avg_s) / 3600 if avg_s > 0 else 0
                    pct = 100 * n_done / n_total
                    print(f"[{provider.upper()} T{tier}] {n_done}/{n_total} ({pct:.1f}%) — "
                          f"avg {avg_s:.0f}s/call — ETA {eta_h:.1f}h — "
                          f"errors={n_errors}, skipped={n_skipped}")

            elapsed_total = time.time() - t_start
            print(f"[{provider.upper()} T{tier}] DONE in {elapsed_total/60:.1f}min — "
                  f"{n_done} done, {n_errors} errors, {n_skipped} skipped")


# ── Entry Point ──────────────────────────────────────────────

def print_usage():
    print("Usage: python3 code/runners/run_quzhou_full.py run <tiers> <provider>")
    print()
    print("  tiers:    1 | 2 | 3 | 4 | 1,2,3,4 | all")
    print("  provider: claude | codex | kimi | all")
    print()
    print("Examples:")
    print("  python3 code/runners/run_quzhou_full.py run 1 claude")
    print("  python3 code/runners/run_quzhou_full.py run all claude    # T1-T4 for Claude")
    print("  python3 code/runners/run_quzhou_full.py run 1,2,3,4 all  # all tiers, all providers")
    print("  python3 code/runners/run_quzhou_full.py verify            # check completion")


def verify_results():
    """Check how many results exist per tier/provider."""
    print(f"\n{'Provider':<10} {'Tier':>4} {'Done':>6} {'Valid':>6} {'Errors':>7}")
    print("-" * 40)
    for provider in ["claude", "codex", "kimi"]:
        for tier in [1, 2, 3, 4]:
            tier_dir = RESULTS_DIR / provider / f"tier{tier}"
            if not tier_dir.exists():
                print(f"{provider:<10} T{tier:>3}      -      -       -")
                continue
            files = list(tier_dir.glob("*.json"))
            valid = 0
            errors = 0
            for fp in files:
                try:
                    d = json.load(open(fp))
                    if d.get("decision"):
                        valid += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1
            print(f"{provider:<10} T{tier:>3} {len(files):>6} {valid:>6} {errors:>7}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "verify":
        verify_results()
        sys.exit(0)

    if cmd != "run" or len(sys.argv) < 4:
        print_usage()
        sys.exit(1)

    # Parse tiers
    tier_arg = sys.argv[2]
    if tier_arg == "all":
        tiers = [1, 2, 3, 4]
    else:
        tiers = [int(t) for t in tier_arg.split(",")]

    # Parse provider
    prov_arg = sys.argv[3]
    if prov_arg == "all":
        providers = ["claude", "codex", "kimi"]
    else:
        providers = [prov_arg]

    run_quzhou(tiers=tiers, providers=providers)
