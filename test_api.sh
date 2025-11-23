#!/bin/bash
# Quick API testing script for Ocean Deep Research

echo "========================================"
echo "Ocean Deep Research - API Testing"
echo "========================================"

# Check if backend is running
if ! curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
    echo ""
    echo "❌ Backend is not running!"
    echo "Please start the backend with: python backend/app.py"
    exit 1
fi

echo ""
echo "✓ Backend is running"
echo ""

# Test 1: Health check
echo "Test 1: Health Check"
echo "--------------------"
curl -s http://localhost:5000/api/health | python3 -m json.tool
echo ""

# Test 2: Simple research question
echo ""
echo "Test 2: Simple Research Question"
echo "---------------------------------"
echo "Question: What is 2+2?"
echo ""
echo "Starting research (this will take 1-3 minutes)..."
echo ""

curl -s -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What is 2+2? Answer in one sentence."}' > /tmp/research_result.json

# Check if request was successful
if [ $? -eq 0 ]; then
    echo "✓ Research completed successfully!"
    echo ""

    # Show round 1 responses
    echo "Round 1 - Agent Responses:"
    echo "--------------------------"
    python3 -c "
import json
import sys
with open('/tmp/research_result.json') as f:
    data = json.load(f)
    for agent, response in data['round1']['responses'].items():
        print(f'\n{agent.upper()}:')
        print(response[:150] + '...' if len(response) > 150 else response)
"

    echo ""
    echo ""
    echo "Round 2 - Voting Results:"
    echo "-------------------------"
    python3 -c "
import json
with open('/tmp/research_result.json') as f:
    data = json.load(f)
    votes = data['round2']['votes']
    best = data['round2']['best_from_round1']
    print(f'Votes: {votes}')
    print(f'Best from Round 1: {best}')
"

    echo ""
    echo ""
    echo "Round 4 - Final Results:"
    echo "------------------------"
    python3 -c "
import json
with open('/tmp/research_result.json') as f:
    data = json.load(f)
    scores = data['round4']['scores']
    best = data['round4']['best_final']
    print(f'Final Scores: {scores}')
    print(f'Winner: {best.upper()}')
    print('')
    print('Final Answer:')
    print(data['round4']['final_answer'][:200] + '...' if len(data['round4']['final_answer']) > 200 else data['round4']['final_answer'])
"

    echo ""
    echo ""
    echo "========================================"
    echo "✅ All tests passed!"
    echo "========================================"

else
    echo "❌ Research request failed!"
    exit 1
fi
