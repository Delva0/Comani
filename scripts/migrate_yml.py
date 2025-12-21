#!/usr/bin/env python
"""
Migrate existing model yml files to standardized format with name+url.
"""
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from comani.utils.civitai import get_version_info
from comani.utils.hf import parse_hf_file_url

MODELS_ROOT = Path(__file__).parent.parent / "comani" / "models"


def extract_name_from_url(url: str) -> str | None:
    """Extract filename from URL based on type."""
    # HuggingFace file URL
    if "huggingface.co" in url:
        # Check if it's a file URL (contains /blob/ or /resolve/)
        if re.search(r"/(blob|resolve)/[^/]+/.+", url):
            try:
                info = parse_hf_file_url(url)
                return info.filename
            except ValueError:
                pass
        # Repo URL - extract repo name
        match = re.match(r"https://huggingface\.co/([^/]+/([^/]+))", url)
        if match:
            return match.group(2)
        return None

    # Civitai URL
    if "civitai.com" in url:
        try:
            _, filename = get_version_info(url)
            return filename
        except Exception as e:
            print(f"  ⚠️  Failed to fetch civitai info: {e}")
            return None

    # Direct URL - extract from path
    parsed = urlparse(url)
    return unquote(parsed.path.split("/")[-1]) or None


def migrate_item(item: str | dict) -> dict:
    """Convert item to standardized {name, url} format."""
    if isinstance(item, str):
        url = item
        name = extract_name_from_url(url)
        if name:
            return {"name": name, "url": url}
        return {"url": url}  # fallback if name extraction fails

    # Already a dict
    url = item.get("url", "")

    # Extract name from existing fields or fetch from API
    name = item.get("name") or item.get("filename") or item.get("dirname")

    if not name and url:
        name = extract_name_from_url(url)

    result = {"url": url}
    if name:
        result = {"name": name, "url": url}

    # Preserve type if explicitly set
    if item.get("type"):
        result["type"] = item["type"]

    return result


def migrate_yml_file(yml_path: Path, dry_run: bool = False) -> bool:
    """Migrate a single yml file. Returns True if changes were made."""
    print(f"\n📄 Processing: {yml_path.relative_to(MODELS_ROOT)}")

    with open(yml_path, encoding="utf-8") as f:
        content = f.read()
        data = yaml.safe_load(content)

    if not data or not isinstance(data, dict):
        print("  ⏭️  Skipped (empty or invalid)")
        return False

    # Check if already migrated (all items have name+url)
    needs_migration = False
    for subdir, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str):
                needs_migration = True
                break
            if isinstance(item, dict):
                # Check for legacy fields or missing name
                if "filename" in item or "dirname" in item:
                    needs_migration = True
                    break
                if "name" not in item:
                    needs_migration = True
                    break
        if needs_migration:
            break

    if not needs_migration:
        print("  ✅ Already migrated")
        return False

    # Migrate items
    new_data = {}
    for subdir, items in data.items():
        if not isinstance(items, list):
            new_data[subdir] = items
            continue

        new_items = []
        for i, item in enumerate(items):
            print(f"  [{i+1}/{len(items)}] ", end="", flush=True)
            new_item = migrate_item(item)
            new_items.append(new_item)

            name = new_item.get("name", "?")
            print(f"{name[:50]}...")

            # Rate limit for API calls
            if isinstance(item, str) and "civitai.com" in item:
                time.sleep(0.3)

        new_data[subdir] = new_items

    if dry_run:
        print("  🔍 Dry run - no changes written")
        return True

    # Write back
    with open(yml_path, "w", encoding="utf-8") as f:
        yaml.dump(new_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"  ✅ Migrated")
    return True


def scan_yml_files(base_dir: Path) -> list[Path]:
    """Recursively find all yml files."""
    results = []
    for item in base_dir.rglob("*.yml"):
        if not item.name.startswith(("_", ".")):
            results.append(item)
    for item in base_dir.rglob("*.yaml"):
        if not item.name.startswith(("_", ".")):
            results.append(item)
    return sorted(results)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Migrate yml files to name+url format")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--file", type=str, help="Process single file")
    args = parser.parse_args()

    print("🔄 Model YML Migration Tool")
    print("=" * 50)

    if args.file:
        yml_path = Path(args.file)
        if not yml_path.is_absolute():
            yml_path = MODELS_ROOT / yml_path
        if yml_path.exists():
            migrate_yml_file(yml_path, dry_run=args.dry_run)
        else:
            print(f"❌ File not found: {yml_path}")
        return

    yml_files = scan_yml_files(MODELS_ROOT)
    print(f"Found {len(yml_files)} yml files")

    migrated = 0
    for yml_path in yml_files:
        if migrate_yml_file(yml_path, dry_run=args.dry_run):
            migrated += 1

    print(f"\n{'=' * 50}")
    print(f"✅ Migration complete: {migrated}/{len(yml_files)} files processed")


if __name__ == "__main__":
    main()
