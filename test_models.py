#!/usr/bin/env python3
"""
Test script to verify each AI model is working correctly.
This tests each model individually with a simple question.
"""

import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from model_agents import ChatGPTAgent, ClaudeAgent, GeminiAgent, GrokAgent

load_dotenv()

def test_model(name, agent, question):
    """Test a single model agent"""
    print(f"\n{'='*60}")
    print(f"Testing {name}...")
    print(f"{'='*60}")

    try:
        response = agent.generate_response(question)
        print(f"✓ {name} is working!")
        print(f"\nResponse preview (first 200 chars):")
        print(f"{response[:200]}..." if len(response) > 200 else response)
        return True
    except Exception as e:
        print(f"✗ {name} failed with error:")
        print(f"  {str(e)}")
        return False

def main():
    """Run tests for all models"""
    print("="*60)
    print("Ocean Deep Research - Model Testing")
    print("="*60)

    # Simple test question
    question = "What is the capital of France? Please answer in one sentence."

    print(f"\nTest question: {question}\n")

    # Initialize agents
    results = {}

    # Test ChatGPT
    try:
        chatgpt = ChatGPTAgent(os.getenv('OPENAI_API_KEY'))
        results['ChatGPT'] = test_model('ChatGPT', chatgpt, question)
    except Exception as e:
        print(f"✗ Failed to initialize ChatGPT: {e}")
        results['ChatGPT'] = False

    # Test Claude
    try:
        claude = ClaudeAgent(os.getenv('ANTHROPIC_API_KEY'))
        results['Claude'] = test_model('Claude', claude, question)
    except Exception as e:
        print(f"✗ Failed to initialize Claude: {e}")
        results['Claude'] = False

    # Test Gemini
    try:
        gemini = GeminiAgent(os.getenv('GOOGLE_API_KEY'))
        results['Gemini'] = test_model('Gemini', gemini, question)
    except Exception as e:
        print(f"✗ Failed to initialize Gemini: {e}")
        results['Gemini'] = False

    # Test Grok
    try:
        grok = GrokAgent(os.getenv('XAI_API_KEY'))
        results['Grok'] = test_model('Grok', grok, question)
    except Exception as e:
        print(f"✗ Failed to initialize Grok: {e}")
        results['Grok'] = False

    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")

    working = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "✓ Working" if success else "✗ Failed"
        print(f"{name:15} {status}")

    print(f"\n{working}/{total} models working correctly")

    if working == total:
        print("\n🎉 All models are working! Ready to run the full application.")
    elif working > 0:
        print(f"\n⚠️  {total - working} model(s) have issues. Check API keys and model availability.")
    else:
        print("\n❌ No models are working. Please check your API keys in .env file.")

    return working == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
