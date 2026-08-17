from __future__ import annotations

import argparse
from pathlib import Path

from pilot.municipality_registration import (
    preview_registration,
    promote_registration,
    verify_registered_municipality,
)


ROOT = Path(__file__).resolve().parents[1]
GENERATED_ROOT = ROOT / "generated" / "municipalities"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review and promote a READY municipality into the persistent Paventra registry."
    )
    parser.add_argument(
        "slug",
        help="Municipality slug, for example: blackman",
    )
    args = parser.parse_args()

    slug = args.slug.strip()
    package_path = GENERATED_ROOT / slug

    if not package_path.exists():
        raise SystemExit(
            f"Generated municipality workspace not found: {package_path}"
        )

    preview = preview_registration(
        package_path,
        record_event=False,
    )

    print()
    print("=" * 72)
    print("PAVENTRA REGISTRATION REVIEW")
    print("=" * 72)
    print(f"Municipality:       {preview.formal_name}")
    print(f"Slug:               {preview.slug}")
    print(f"Entity type:        {preview.entity_type}")
    print(f"Data status:        {preview.data_status}")
    print(f"Segment count:      {preview.segment_count}")
    print(f"Source owner:       {preview.source_owner}")
    print(f"Source date:        {preview.source_date}")
    print(f"Source reference:   {preview.source_reference}")
    print(f"Source checksum:    {preview.source_checksum}")
    print(f"Canonical checksum: {preview.canonical_checksum}")
    print(f"Map center:         {preview.map_center}")
    print(f"Map zoom:           {preview.map_zoom}")
    print(f"Scenario catalog:   {preview.scenario_catalog_id}")
    print(f"Inventory adapter:  {preview.inventory_adapter}")
    print(f"Registration path:  {preview.intended_path}")
    print(f"Registration ver.:  {preview.registration_version}")
    print(f"Blocking issues:    {len(preview.issues)}")

    if preview.issues:
        print()
        print("REGISTRATION BLOCKED")
        for issue in preview.issues:
            print(f" - {issue}")
        raise SystemExit(1)

    print()
    print("PREVIEW PASSED")
    print()
    print(
        "This will create a persistent registered municipality in Paventra."
    )
    print(
        "It does NOT mean the municipality has officially approved the provisional data."
    )
    print()

    confirmation = input(
        f"Type the exact slug '{preview.slug}' to promote, or press Enter to cancel: "
    ).strip()

    if confirmation != preview.slug:
        print("Registration cancelled. No persistent changes made.")
        return

    registered = promote_registration(
        package_path,
        confirmation_slug=preview.slug,
        confirmed=True,
    )

    verified = verify_registered_municipality(
        registered.registration_path
    )

    print()
    print("=" * 72)
    print("REGISTRATION PROMOTED")
    print("=" * 72)
    print(f"Municipality:         {verified.config.formal_name}")
    print(f"Slug:                 {verified.config.slug}")
    print(f"Data status:          {verified.config.data_status}")
    print(f"Registration version: {verified.registration_version}")
    print(f"Active data version:  {verified.active_data_version}")
    print(f"Registration state:   {verified.registration_state}")
    print(f"Registration path:    {verified.registration_path}")
    print()
    print("Promotion and verification completed successfully.")
    print()
    print(
        "Final operational acceptance remains separate. "
        f"Use accept_registration('{verified.config.slug}') only after review."
    )


if __name__ == "__main__":
    main()
