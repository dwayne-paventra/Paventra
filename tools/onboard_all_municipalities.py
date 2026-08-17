from __future__ import annotations

import json
from pathlib import Path

from tools.onboard_municipality import prepare_municipality
from pilot.municipality_package_lifecycle import inspect_real_import_package
from pilot.municipality_registration import preview_registration


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs" / "municipalities"
GENERATED_DIR = ROOT / "generated" / "municipalities"


def read_spatial_summary(workspace: Path) -> dict:
    path = workspace / "spatial_review.json"

    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def result_from_workspace(
    formal_name: str,
    workspace: Path,
    status: str,
) -> dict:
    spatial = read_spatial_summary(workspace)

    return {
        "municipality": formal_name,
        "features": spatial.get("feature_count"),
        "matched": spatial.get("matched_count"),
        "match": spatial.get("match_percentage"),
        "invalid": spatial.get("invalid_geometry_count"),
        "status": status,
        "error": "",
    }


def main() -> None:
    configs = sorted(CONFIG_DIR.glob("*.json"))

    if not configs:
        raise SystemExit("No municipality config files found.")

    results = []

    print()
    print("=" * 82)
    print("PAVENTRA MUNICIPALITY BATCH ONBOARDING")
    print("=" * 82)

    for config_path in configs:
        try:
            config = json.loads(
                config_path.read_text(encoding="utf-8-sig")
            )

            formal_name = config.get(
                "formal_name",
                config_path.stem,
            )

            slug = config["slug"]
            workspace = GENERATED_DIR / slug

            print()
            print("-" * 82)
            print(f"Checking: {formal_name}")
            print("-" * 82)

            manifest_path = workspace / "manifest.json"

            if manifest_path.exists():
                inspection = inspect_real_import_package(workspace)

                state = inspection.lifecycle_state.value

                if (
                    state == "Ready for Registration"
                    and not inspection.issues
                ):
                    preview = preview_registration(
                        workspace,
                        record_event=False,
                    )

                    if preview.issues:
                        raise RuntimeError(
                            "Existing workspace registration preview "
                            f"has issues: {preview.issues}"
                        )

                    print(
                        "Existing READY workspace verified; "
                        "skipping rebuild."
                    )

                    results.append(
                        result_from_workspace(
                            formal_name,
                            workspace,
                            "READY",
                        )
                    )
                    continue

                raise RuntimeError(
                    f"Existing workspace is not safely reusable. "
                    f"Lifecycle={state}; issues={inspection.issues}"
                )

            if workspace.exists():
                raise RuntimeError(
                    "Incomplete generated workspace exists without "
                    "manifest.json. Remove it manually before retrying: "
                    f"{workspace}"
                )

            print("No existing workspace. Running onboarding...")

            workspace = prepare_municipality(config)

            results.append(
                result_from_workspace(
                    formal_name,
                    workspace,
                    "READY",
                )
            )

        except Exception as exc:
            results.append(
                {
                    "municipality": (
                        config.get("formal_name", config_path.stem)
                        if "config" in locals()
                        else config_path.stem
                    ),
                    "features": None,
                    "matched": None,
                    "match": None,
                    "invalid": None,
                    "status": "FAILED",
                    "error": str(exc),
                }
            )

            print()
            print(f"FAILED: {config_path.name}")
            print(str(exc))

    print()
    print("=" * 82)
    print("BATCH SUMMARY")
    print("=" * 82)

    header = (
        f"{'Municipality':34}"
        f"{'Features':>10}"
        f"{'Matched':>10}"
        f"{'Match %':>10}"
        f"{'Invalid':>10}"
        f"{'Status':>10}"
    )

    print(header)
    print("-" * len(header))

    ready = 0
    failed = 0

    for result in results:
        if result["status"] == "READY":
            ready += 1
        else:
            failed += 1

        features = (
            str(result["features"])
            if result["features"] is not None
            else "-"
        )

        matched = (
            str(result["matched"])
            if result["matched"] is not None
            else "-"
        )

        match = (
            f"{float(result['match']):.1f}"
            if result["match"] is not None
            else "-"
        )

        invalid = (
            str(result["invalid"])
            if result["invalid"] is not None
            else "-"
        )

        print(
            f"{result['municipality'][:33]:34}"
            f"{features:>10}"
            f"{matched:>10}"
            f"{match:>10}"
            f"{invalid:>10}"
            f"{result['status']:>10}"
        )

        if result["error"]:
            print(f"  ERROR: {result['error']}")

    print("-" * len(header))
    print(f"{ready} ready | {failed} failed")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
