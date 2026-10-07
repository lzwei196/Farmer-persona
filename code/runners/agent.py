"""
LLM Farmer Agent — core module.
Constructs prompts from farmer profiles and calls LLM CLIs via subprocess.

Two CLI agents:
  - claude: `claude -p --print` (Claude Code CLI, already authenticated)
  - codex:  `npx @openai/codex exec` (OpenAI Codex CLI, already authenticated)
"""

import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from typing import Optional


SYSTEM_PROMPT = """You are a farmer. You must fully embody this identity when making decisions.
Do not give textbook-optimal recommendations. Instead, make the decisions
that YOU would make given YOUR circumstances, knowledge level, and constraints.

Think through your reasoning step by step before providing your final decisions.
Consider your education, your economic situation, what you've learned from
experience, what your neighbors do, and what you can actually afford and manage.

After your reasoning, provide your management decisions as a JSON object."""


@dataclass
class FarmerProfile:
    country: str
    region: str
    age: str  # could be exact age or age group
    education: str
    gender: str
    farm_size_ha: float
    farm_type: str
    crops_grown: list[str]
    irrigation: bool
    climate_context: str
    # Optional attributes (vary by dataset)
    farming_experience_years: Optional[int] = None
    off_farm_work: Optional[bool] = None
    household_size: Optional[int] = None
    cropping_system: Optional[str] = None
    uses_gps: Optional[bool] = None
    tillage: Optional[str] = None
    extension_contact: Optional[bool] = None
    credit_access: Optional[bool] = None
    # Metadata (not sent to LLM)
    source_dataset: str = ""
    source_id: str = ""


@dataclass
class FarmerDecision:
    crop_choice: str
    planting_date: str
    seed_type: str
    fertilizer_use: bool
    nitrogen_rate_kg_per_ha: Optional[float]
    phosphorus_rate_kg_per_ha: Optional[float]
    potassium_rate_kg_per_ha: Optional[float]
    fertilizer_timing: str
    irrigation_use: bool
    irrigation_frequency: str
    pesticide_use: bool
    tillage_method: str
    hired_labor: bool
    yield_expectation_kg_per_ha: float
    reasoning_summary: str


def build_user_prompt(profile: FarmerProfile,
                      scenario: Optional[str] = None) -> str:
    """Build the user prompt from a farmer profile."""

    lines = [
        "You are the following farmer:",
        "",
        f"- Country: {profile.country}",
        f"- Region: {profile.region}",
        f"- Age: {profile.age}",
        f"- Education: {profile.education}",
        f"- Gender: {profile.gender}",
        f"- Farm size: {profile.farm_size_ha} hectares",
        f"- Farm type: {profile.farm_type}",
        f"- Crops you typically grow: {', '.join(profile.crops_grown)}",
        f"- Irrigation available: {'Yes' if profile.irrigation else 'No'}",
        f"- Climate: {profile.climate_context}",
    ]

    if profile.farming_experience_years is not None:
        lines.append(f"- Farming experience: {profile.farming_experience_years} years")
    if profile.off_farm_work is not None:
        lines.append(f"- Off-farm work: {'Yes' if profile.off_farm_work else 'No'}")
    if profile.household_size is not None:
        lines.append(f"- Household size: {profile.household_size} members")
    if profile.cropping_system is not None:
        lines.append(f"- Cropping system: {profile.cropping_system}")
    if profile.uses_gps is not None:
        lines.append(f"- Uses GPS/precision ag: {'Yes' if profile.uses_gps else 'No'}")
    if profile.tillage is not None:
        lines.append(f"- Current tillage practice: {profile.tillage}")
    if profile.extension_contact is not None:
        lines.append(f"- Contact with extension services: {'Yes' if profile.extension_contact else 'No'}")
    if profile.credit_access is not None:
        lines.append(f"- Access to agricultural credit: {'Yes' if profile.credit_access else 'No'}")

    primary_crop = profile.crops_grown[0] if profile.crops_grown else "your primary crop"

    lines.extend([
        "",
        f"It is the start of the upcoming growing season. Based on who you are and",
        f"your circumstances, make your management decisions for {primary_crop} this season.",
        "",
        "Provide your reasoning first, then output your decisions as JSON with",
        "exactly these fields:",
        "",
        '''{
  "crop_choice": "the crop you will plant",
  "planting_date": "approximate planting date",
  "seed_type": "traditional/improved/hybrid",
  "fertilizer_use": true or false,
  "nitrogen_rate_kg_per_ha": number or null,
  "phosphorus_rate_kg_per_ha": number or null,
  "potassium_rate_kg_per_ha": number or null,
  "fertilizer_timing": "description of when you apply fertilizer",
  "irrigation_use": true or false,
  "irrigation_frequency": "description if irrigating",
  "pesticide_use": true or false,
  "tillage_method": "conventional/conservation/no-till",
  "hired_labor": true or false,
  "yield_expectation_kg_per_ha": number,
  "reasoning_summary": "one paragraph summarizing your key reasoning"
}'''
    ])

    if scenario:
        lines.extend([
            "",
            "IMPORTANT ADDITIONAL CONDITIONS THIS SEASON:",
            "",
            scenario,
            "",
            "Given these unusual conditions ON TOP OF your normal situation,",
            "how do your management decisions change? Explain your reasoning",
            "about how these conditions interact with each other and with your",
            "specific circumstances."
        ])

    return "\n".join(lines)


def extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response text."""
    # First try fenced code block
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Then try to find the outermost { ... }
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


def call_claude_cli(system: str, user: str, **kwargs) -> dict:
    """
    Call Claude via the `claude` CLI (Claude Code).
    Uses `claude -p` (print mode) with --append-system-prompt for the system prompt.
    The full prompt (system + user) is piped via stdin.
    """
    full_prompt = f"{system}\n\n{user}"

    t0 = time.time()
    result = subprocess.run(
        ["claude", "-p", "--allowedTools", ""],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=180,
    )
    elapsed = round(time.time() - t0, 1)

    raw_text = result.stdout.strip()
    if result.returncode != 0 and not raw_text:
        raise RuntimeError(f"claude CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    decision = extract_json(raw_text)
    return {
        "raw_response": raw_text,
        "decision": decision,
        "model": "claude-cli",
        "elapsed_seconds": elapsed,
        "usage": {"input_tokens": None, "output_tokens": None},
    }


def call_codex_cli(system: str, user: str, **kwargs) -> dict:
    """
    Call OpenAI Codex via the `npx @openai/codex exec` CLI.
    Uses exec (non-interactive) mode with the prompt piped in.
    """
    full_prompt = f"{system}\n\n{user}"

    # Use a temp file to capture the last message
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_file = f.name

    t0 = time.time()
    result = subprocess.run(
        [
            "npx", "@openai/codex", "exec",
            "--skip-git-repo-check",
            "--full-auto",
            "--ephemeral",
            "-o", output_file,
            full_prompt,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    elapsed = round(time.time() - t0, 1)

    # Read output from file (more reliable than stdout for codex)
    import os
    try:
        with open(output_file) as f:
            raw_text = f.read().strip()
    except Exception:
        raw_text = result.stdout.strip()
    finally:
        os.unlink(output_file)

    if result.returncode != 0 and not raw_text:
        raise RuntimeError(f"codex CLI failed (rc={result.returncode}): {result.stderr[:500]}")

    decision = extract_json(raw_text)
    return {
        "raw_response": raw_text,
        "decision": decision,
        "model": "codex-cli",
        "elapsed_seconds": elapsed,
        "usage": {"input_tokens": None, "output_tokens": None},
    }


CALL_FNS = {
    "claude": call_claude_cli,
    "codex": call_codex_cli,
}


def run_agent(profile: FarmerProfile,
              scenario: Optional[str] = None,
              provider: str = "claude",
              n_runs: int = 5,
              **kwargs) -> list[dict]:
    """Run the farmer agent n_runs times and collect results."""
    user_prompt = build_user_prompt(profile, scenario)
    call_fn = CALL_FNS[provider]

    results = []
    for run_id in range(n_runs):
        try:
            result = call_fn(SYSTEM_PROMPT, user_prompt)
            result["run_id"] = run_id
            result["profile"] = asdict(profile)
            result["scenario"] = scenario
            result["provider"] = provider
            results.append(result)
            print(f"  Run {run_id + 1}/{n_runs} complete "
                  f"({result['elapsed_seconds']}s)")
        except Exception as e:
            print(f"  Run {run_id + 1}/{n_runs} FAILED: {e}")
            results.append({
                "run_id": run_id, "error": str(e),
                "profile": asdict(profile), "provider": provider,
            })
    return results
