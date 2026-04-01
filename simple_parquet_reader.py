"""
Simple parquet reader using only pyarrow (no pandas)
"""
import pyarrow.parquet as pq
import json
from pathlib import Path

def show_parquet_info(parquet_file):
    """Show basic info and samples from parquet file"""
    print(f"\n{'='*80}")
    print(f"📄 {parquet_file.name}")
    print('='*80)

    try:
        # Read parquet metadata
        parquet_file_obj = pq.ParquetFile(parquet_file)

        print(f"\n📊 Schema:")
        for field in parquet_file_obj.schema:
            print(f"  - {field.name}: {field.type}")

        print(f"\n📈 Rows: {parquet_file_obj.metadata.num_rows}")
        print(f"💾 Size: {parquet_file.stat().st_size / (1024*1024):.2f} MB")

        # Read first few rows
        table = parquet_file_obj.read_row_group(0, columns=None)

        print(f"\n📝 Sample data (first 2 rows):\n")

        # Convert to Python objects
        data = table.to_pydict()

        num_samples = min(2, len(data[list(data.keys())[0]]))

        for i in range(num_samples):
            print(f"\n{'─'*80}")
            print(f"Row {i+1}:")
            print('─'*80)

            for col_name, col_data in data.items():
                value = col_data[i]

                # Format value for display
                if isinstance(value, bytes):
                    display = f"[BYTES: {len(value)} bytes]"
                elif isinstance(value, str) and len(value) > 200:
                    display = value[:200] + "..."
                elif isinstance(value, list):
                    if len(value) > 0 and isinstance(value[0], dict):
                        display = f"[List of {len(value)} dicts]"
                        # Show first dict structure
                        if len(value) > 0:
                            print(f"\n{col_name}: {display}")
                            print(f"  First item keys: {list(value[0].keys())}")
                            for k, v in list(value[0].items())[:3]:
                                if isinstance(v, bytes):
                                    print(f"    {k}: [BYTES: {len(v)} bytes]")
                                elif isinstance(v, str) and len(v) > 100:
                                    print(f"    {k}: {v[:100]}...")
                                else:
                                    print(f"    {k}: {v}")
                            continue
                    else:
                        display = str(value)[:300]
                else:
                    display = str(value)

                print(f"\n{col_name}: {display}")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    dataset_root = Path(r"F:\datasets\TIGER-Lab_Mantis-Instruct")

    print("🔍 Mantis-Instruct Dataset - Parquet File Analysis")
    print("="*80)

    # Test different datasets
    test_files = [
        "birds-to-words/train-00000-of-00001.parquet",
        "chartqa/train-00000-of-00001.parquet",
        "docvqa/train-00000-of-00001.parquet",
    ]

    for file_path in test_files:
        full_path = dataset_root / file_path
        if full_path.exists():
            show_parquet_info(full_path)
        else:
            print(f"\n⚠️  Not found: {file_path}")

    print("\n\n✅ Analysis complete!")
