"""
Quick analysis of Mantis-Instruct dataset - basic file inventory
"""

import os
import zipfile
from pathlib import Path
import json

def analyze_dataset_quick(root_path):
    """Quick scan of dataset structure"""
    root = Path(root_path)

    print(f"🔍 Quick Dataset Analysis: {root_path}")
    print("=" * 80)

    if not root.exists():
        print(f"❌ Path does not exist: {root_path}")
        return

    # Find all files
    print("\n📁 Scanning for files...")
    parquet_files = list(root.rglob('*.parquet'))
    zip_files = list(root.rglob('*.zip'))

    print(f"Found {len(parquet_files)} parquet files")
    print(f"Found {len(zip_files)} zip files")

    # Analyze by subdirectory
    subdirs = {}
    for item in root.iterdir():
        if item.is_dir():
            subdirs[item.name] = {
                'parquet': list(item.rglob('*.parquet')),
                'zip': list(item.rglob('*.zip')),
                'images': []
            }
            # Count images
            for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                subdirs[item.name]['images'].extend(list(item.rglob(f'*{ext}')))

    # Print summary by subdirectory
    print("\n" + "=" * 80)
    print("📊 DATASET STRUCTURE BY SUBDIRECTORY")
    print("=" * 80)

    total_parquet_size = 0
    total_zip_size = 0
    total_image_count = 0

    for subdir_name in sorted(subdirs.keys()):
        info = subdirs[subdir_name]
        print(f"\n📂 {subdir_name}/")

        # Parquet files
        if info['parquet']:
            parquet_size = sum(f.stat().st_size for f in info['parquet']) / (1024 * 1024)
            total_parquet_size += parquet_size
            print(f"  📊 Parquet: {len(info['parquet'])} files, {parquet_size:.2f} MB")
            for pf in info['parquet']:
                size_mb = pf.stat().st_size / (1024 * 1024)
                print(f"     - {pf.name}: {size_mb:.2f} MB")

        # Zip files
        if info['zip']:
            for zf in info['zip']:
                size_mb = zf.stat().st_size / (1024 * 1024)
                total_zip_size += size_mb

                # Try to check if zip is valid
                try:
                    with zipfile.ZipFile(zf, 'r') as zip_ref:
                        bad_file = zip_ref.testzip()
                        file_count = len(zip_ref.namelist())
                        if bad_file is None:
                            status = "✓ Valid"
                        else:
                            status = "✗ Corrupted"
                except zipfile.BadZipFile:
                    status = "✗ Incomplete/Bad"
                    file_count = "?"
                except Exception as e:
                    status = f"✗ Error: {str(e)[:30]}"
                    file_count = "?"

                print(f"  📦 Zip: {zf.name}: {size_mb:.2f} MB, {file_count} files, {status}")

        # Images
        if info['images']:
            image_count = len(info['images'])
            total_image_count += image_count
            image_size = sum(f.stat().st_size for f in info['images']) / (1024 * 1024)
            print(f"  🖼️  Images: {image_count} files, {image_size:.2f} MB")

    # Overall summary
    print("\n" + "=" * 80)
    print("📋 OVERALL SUMMARY")
    print("=" * 80)
    print(f"\n📂 Subdirectories: {len(subdirs)}")
    print(f"📊 Total parquet files: {len(parquet_files)}, {total_parquet_size:.2f} MB")
    print(f"📦 Total zip files: {len(zip_files)}, {total_zip_size:.2f} MB")
    print(f"🖼️  Total images found: {total_image_count}")
    print(f"💾 Total data size: {(total_parquet_size + total_zip_size):.2f} MB")

    # Check for issues
    print("\n" + "=" * 80)
    print("⚠️  POTENTIAL ISSUES")
    print("=" * 80)

    issues_found = False

    # Check for duplicate files (like "file (1).zip")
    for subdir_name, info in subdirs.items():
        duplicates = [f for f in info['zip'] if '(1)' in f.name or '(2)' in f.name]
        if duplicates:
            issues_found = True
            print(f"\n📂 {subdir_name}/")
            print(f"  ⚠️  Found {len(duplicates)} duplicate download(s):")
            for dup in duplicates:
                print(f"     - {dup.name}")

    # Check for missing pairs (parquet without zip or vice versa)
    for subdir_name, info in subdirs.items():
        has_parquet = len(info['parquet']) > 0
        has_zip = len(info['zip']) > 0
        has_images = len(info['images']) > 0

        if has_parquet and not has_zip and not has_images:
            issues_found = True
            print(f"\n📂 {subdir_name}/")
            print(f"  ⚠️  Has parquet but no zip/images")
        elif has_zip and not has_parquet:
            issues_found = True
            print(f"\n📂 {subdir_name}/")
            print(f"  ⚠️  Has zip but no parquet metadata")

    if not issues_found:
        print("\n✓ No obvious issues detected")

    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    print("\n1. Remove duplicate files (those with '(1)' or '(2)' in filename)")
    print("2. For corrupted/incomplete zips, re-download them")
    print("3. Subdirectories with both parquet and valid zips are ready to use")

    return subdirs

if __name__ == "__main__":
    dataset_path = r"F:\datasets\TIGER-Lab_Mantis-Instruct"
    analyze_dataset_quick(dataset_path)
    print("\n✅ Quick analysis complete!")
