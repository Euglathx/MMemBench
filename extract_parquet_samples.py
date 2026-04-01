"""
Extract sample data from parquet files using pyarrow
"""
import pyarrow.parquet as pq
import json
import re

def clean_value(value, max_length=300):
    """Clean and truncate values for display"""
    if value is None:
        return "None"

    value_str = str(value)

    # Replace base64 image data
    value_str = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{50,}', '[IMAGE_BASE64]', value_str)

    # Replace long binary-like strings
    if len(value_str) > 100 and value_str.startswith("b'"):
        return '[BINARY_DATA]'

    # Truncate long strings
    if len(value_str) > max_length:
        return value_str[:max_length] + '...'

    return value_str

def extract_samples(parquet_file, num_samples=3):
    """Extract sample rows from parquet file"""
    print(f"\n{'='*80}")
    print(f"📄 File: {parquet_file}")
    print('='*80)

    try:
        # Read parquet file
        table = pq.read_table(parquet_file)
        df = table.to_pandas()

        print(f"\n📊 Schema: {list(df.columns)}")
        print(f"📈 Total rows: {len(df)}")
        print(f"💾 File size: {parquet_file.stat().st_size / (1024*1024):.2f} MB")

        # Extract samples
        num_samples = min(num_samples, len(df))
        print(f"\n📝 Extracting {num_samples} samples:\n")

        for i in range(num_samples):
            print(f"\n{'─'*80}")
            print(f"Sample {i+1}:")
            print('─'*80)

            for col in df.columns:
                value = df.iloc[i][col]

                # Handle different types
                if isinstance(value, (list, dict)):
                    # For lists/dicts, show structure
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            # List of dicts (like images)
                            print(f"\n{col}: [List of {len(value)} items]")
                            for idx, item in enumerate(value[:2]):  # Show first 2
                                print(f"  [{idx}]:")
                                for k, v in item.items():
                                    print(f"    {k}: {clean_value(v, 150)}")
                            if len(value) > 2:
                                print(f"  ... and {len(value)-2} more items")
                        else:
                            # Simple list
                            print(f"\n{col}: {clean_value(value, 400)}")
                    elif isinstance(value, dict):
                        print(f"\n{col}:")
                        for k, v in value.items():
                            print(f"  {k}: {clean_value(v, 200)}")
                    else:
                        print(f"\n{col}: {clean_value(value, 400)}")
                else:
                    cleaned = clean_value(value, 400)
                    print(f"\n{col}: {cleaned}")

        return True

    except Exception as e:
        print(f"\n❌ Error reading file: {e}")
        return False

if __name__ == "__main__":
    from pathlib import Path

    dataset_root = Path(r"F:\datasets\TIGER-Lab_Mantis-Instruct")

    print("🔍 Extracting samples from Mantis-Instruct parquet files")
    print("="*80)

    # Test a few different datasets
    test_files = [
        "birds-to-words/train-00000-of-00001.parquet",
        "chartqa/train-00000-of-00001.parquet",
        "llava_665k_multi/train-00000-of-00002.parquet",
    ]

    for file_path in test_files:
        full_path = dataset_root / file_path
        if full_path.exists():
            extract_samples(full_path, num_samples=2)
        else:
            print(f"\n⚠️  File not found: {file_path}")

    print("\n\n✅ Sample extraction complete!")
