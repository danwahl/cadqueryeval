#!/usr/bin/env python3
"""Fetch model metadata from OpenRouter API and save locally.

Usage:
    python tools/fetch_model_metadata.py

This script fetches model information from the OpenRouter API including:
- Pricing (cost per token for prompt and completion)
- Release dates (created timestamp)
- Context length
- Provider information

The metadata is saved to data/model_metadata.json for use in analysis.
"""

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import requests


def fetch_openrouter_models() -> list[dict]:
    """Fetch all models from OpenRouter API."""
    resp = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]


def get_evaluated_models(logs_dir: Path) -> set[str]:
    """Extract model IDs from evaluation logs."""
    models = set()
    for log_file in logs_dir.glob("*.eval"):
        try:
            with zipfile.ZipFile(log_file, "r") as zf:
                with zf.open("header.json") as f:
                    data = json.load(f)
                    model = data.get("eval", {}).get("model", "")
                    # Strip 'openrouter/' prefix if present
                    if model.startswith("openrouter/"):
                        model = model[len("openrouter/") :]
                    if model:
                        models.add(model)
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read {log_file}: {e}", file=sys.stderr)
    return models


def extract_model_metadata(all_models: list[dict], model_ids: set[str]) -> dict:
    """Extract relevant fields for evaluated models."""
    result = {}

    for model in all_models:
        model_id = model.get("id", "")

        # Check if this model matches any of our evaluated models
        if model_id not in model_ids:
            continue

        pricing = model.get("pricing", {})
        created = model.get("created")

        result[model_id] = {
            "name": model.get("name"),
            "created": created,
            "created_date": (
                datetime.fromtimestamp(created).strftime("%Y-%m-%d")
                if created
                else None
            ),
            "context_length": model.get("context_length"),
            "pricing": {
                "prompt": pricing.get("prompt"),  # Cost per token (string)
                "completion": pricing.get("completion"),  # Cost per token (string)
                "prompt_per_million": (
                    float(pricing.get("prompt", 0)) * 1_000_000
                    if pricing.get("prompt")
                    else None
                ),
                "completion_per_million": (
                    float(pricing.get("completion", 0)) * 1_000_000
                    if pricing.get("completion")
                    else None
                ),
            },
            "description": model.get("description"),
            "architecture": model.get("architecture", {}).get("modality"),
            "top_provider": model.get("top_provider", {}).get("max_completion_tokens"),
        }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Fetch model metadata from OpenRouter API"
    )
    parser.add_argument(
        "-d",
        "--logs-dir",
        type=Path,
        default=Path("logs"),
        help="Directory containing .eval log files (default: logs/)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/model_metadata.json"),
        help="Output file path (default: data/model_metadata.json)",
    )
    parser.add_argument(
        "--all-models",
        action="store_true",
        help="Fetch all OpenRouter models, not just evaluated ones",
    )

    args = parser.parse_args()

    # Get models we've evaluated
    if args.all_models:
        print("Fetching metadata for ALL OpenRouter models...")
        model_ids = None
    else:
        if not args.logs_dir.exists():
            print(f"Logs directory not found: {args.logs_dir}", file=sys.stderr)
            sys.exit(1)

        model_ids = get_evaluated_models(args.logs_dir)
        if not model_ids:
            print(f"No evaluation logs found in {args.logs_dir}", file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(model_ids)} evaluated models:")
        for m in sorted(model_ids):
            print(f"  - {m}")

    # Fetch from OpenRouter API
    print("\nFetching models from OpenRouter API...")
    all_models = fetch_openrouter_models()
    print(f"Retrieved {len(all_models)} models from API")

    # Extract metadata
    if model_ids is None:
        # All models mode
        metadata = {
            m["id"]: {
                "name": m.get("name"),
                "created": m.get("created"),
                "context_length": m.get("context_length"),
                "pricing": m.get("pricing"),
            }
            for m in all_models
        }
    else:
        metadata = extract_model_metadata(all_models, model_ids)

    # Report missing models
    if model_ids:
        found = set(metadata.keys())
        missing = model_ids - found
        if missing:
            print(f"\nWarning: {len(missing)} models not found in API:")
            for m in sorted(missing):
                print(f"  - {m}")

    # Save output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, indent=2))
    print(f"\nSaved metadata for {len(metadata)} models to {args.output}")

    # Print summary table
    if metadata:
        print("\n" + "=" * 80)
        print("MODEL METADATA SUMMARY")
        print("=" * 80)
        print(
            f"{'Model':<40} {'Created':<12} {'Prompt $/M':<12} {'Completion $/M':<14}"
        )
        print("-" * 80)
        for model_id in sorted(metadata.keys()):
            m = metadata[model_id]
            created = m.get("created_date", "N/A") or "N/A"
            prompt_cost = m.get("pricing", {}).get("prompt_per_million")
            comp_cost = m.get("pricing", {}).get("completion_per_million")
            prompt_str = f"${prompt_cost:.2f}" if prompt_cost else "N/A"
            comp_str = f"${comp_cost:.2f}" if comp_cost else "N/A"
            print(f"{model_id:<40} {created:<12} {prompt_str:<12} {comp_str:<14}")


if __name__ == "__main__":
    main()
