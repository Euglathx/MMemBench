"""
Test Weak Model Integration
============================

Quick test to verify that weak model API calls are working properly.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.simulator import LLMClient, ContextPadder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_llm_client_weak_model():
    """Test LLMClient weak model call"""
    print("\n" + "="*60)
    print("Testing LLMClient Weak Model")
    print("="*60)

    client = LLMClient(
        weak_model="gpt-3.5-turbo"  # Default weak model
    )

    print(f"\nWeak model configured: {client.weak_model}")

    # Test weak model call
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Hello, I am the weak model' in one sentence."}
    ]

    print("\nCalling weak model...")
    response = client.call_weak_model(messages, max_tokens=50)

    if response.get("success"):
        print(f"SUCCESS! Response: {response.get('content', '')}")
        print(f"Usage: {response.get('usage', {})}")
    else:
        print(f"FAILED! Error: {response.get('error', 'Unknown error')}")

    return response.get("success", False)


def test_context_padder_with_weak_model():
    """Test ContextPadder with weak model"""
    print("\n" + "="*60)
    print("Testing Context Padder with Weak Model")
    print("="*60)

    # Test with weak model enabled
    padder = ContextPadder(
        weak_model="gpt-3.5-turbo",
        use_weak_model=True
    )

    print(f"\nContext padder configured:")
    print(f"  Weak model: {padder.weak_model}")
    print(f"  Use weak model: {padder.use_weak_model}")

    # Generate a filler turn using weak model
    print("\nGenerating filler turn with weak model...")
    filler = padder.generate_filler_turn({
        "turn_index": 1,
        "summary": "Discussing people counting in an image with 5 people visible."
    }, topic="background_details")

    print(f"\nFiller generated:")
    print(f"  Topic: {filler.get('topic', 'N/A')}")
    print(f"  User message: {filler['user_message'][:100]}...")
    print(f"  Model response length: {filler['response_length']} chars")
    print(f"  Response preview: {filler['model_response'][:200]}...")

    # Check if response is long enough (indicates weak model was used)
    is_long = filler['response_length'] >= 100
    print(f"\n  Response is {'LONG ENOUGH' if is_long else 'TOO SHORT'} (>= 100 chars expected)")

    return is_long


def test_context_padder_fallback():
    """Test ContextPadder template fallback (no API calls)"""
    print("\n" + "="*60)
    print("Testing Context Padder Template Fallback")
    print("="*60)

    # Test with weak model disabled (should use templates)
    padder = ContextPadder(use_weak_model=False)

    print(f"\nContext padder configured:")
    print(f"  Use weak model: {padder.use_weak_model}")

    # Generate a filler turn using templates
    print("\nGenerating filler turn with templates (no API calls)...")
    filler = padder.generate_filler_turn({
        "turn_index": 0,
        "summary": ""
    })

    print(f"\nFiller generated:")
    print(f"  Topic: {filler.get('topic', 'N/A')}")
    print(f"  User message: {filler['user_message'][:100]}...")
    print(f"  Response length: {filler['response_length']} chars")
    print(f"  Response preview: {filler['model_response'][:200]}...")

    return True


def main():
    """Run all tests"""
    print("="*60)
    print("Weak Model Integration Tests")
    print("="*60)

    results = {}

    # Test 1: LLMClient weak model
    results["llm_client_weak_model"] = test_llm_client_weak_model()

    # Test 2: Context padder with weak model
    results["context_padder_weak_model"] = test_context_padder_with_weak_model()

    # Test 3: Context padder fallback
    results["context_padder_fallback"] = test_context_padder_fallback()

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'All tests passed!' if all_passed else 'Some tests failed!'}")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
