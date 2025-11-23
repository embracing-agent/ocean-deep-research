# Testing Guide for Ocean Deep Research

This guide will help you verify that the multi-model research application is working correctly.

## Step 1: Backend Testing

### 1.1 Test Backend API Health Check

First, start the backend server:

```bash
cd /home/user/ocean-deep-research
python backend/app.py
```

In another terminal, test the health endpoint:

```bash
curl http://localhost:5000/api/health
```

**Expected output:**
```json
{
  "status": "healthy",
  "agents": ["chatgpt", "claude", "gemini", "grok"]
}
```

### 1.2 Test Individual Model Agents

Create a test script to verify each model independently:

```bash
cd /home/user/ocean-deep-research
python test_models.py
```

This will test each model with a simple question and show you which ones are working.

### 1.3 Test Full Research Endpoint

Test the complete 4-round research process via API:

```bash
curl -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
```

**What to check:**
- All 4 rounds should complete
- Each round should have responses from all 4 agents
- Round 2 should show voting results
- Round 4 should show final rankings and best answer

## Step 2: Frontend Testing

### 2.1 Start the Frontend

In a new terminal:

```bash
cd /home/user/ocean-deep-research/frontend
npm install  # First time only
npm start
```

The app should open at http://localhost:3000

### 2.2 UI Functionality Tests

1. **Input Validation**
   - Try submitting without a question (should show error)
   - Enter a question and submit

2. **Round 1 Display**
   - Verify all 4 agent cards appear (ChatGPT, Claude, Gemini, Grok)
   - Check each agent has a colored icon and name
   - Verify responses are displayed in scrollable boxes

3. **Round 2 Display**
   - Check evaluations from each agent are shown
   - Verify voting results appear
   - Confirm "Best from Round 1" badge is displayed

4. **Round 3 Display**
   - Verify improved responses from all agents
   - Check that responses differ from Round 1

5. **Round 4 Display**
   - Check final evaluations with rankings
   - Verify score cards show points for each agent
   - Confirm winner badge appears on highest-scoring agent

6. **Final Answer**
   - Verify the final answer section appears
   - Check it shows the response from the winning agent

## Step 3: Model-Specific Testing

### 3.1 Test Each Model Individually

Run the individual model test script to identify which models are working:

```bash
python test_individual_models.py
```

### 3.2 Common Issues by Model

**ChatGPT Errors:**
- "Model not found" → API key may not have access to GPT-5 Pro
- "Invalid API key" → Check OPENAI_API_KEY in .env

**Claude Errors:**
- "Invalid API key" → Verify ANTHROPIC_API_KEY
- "Model not found" → Confirm API has access to claude-sonnet-4-5-20250929

**Gemini Errors:**
- "API key not valid" → Check GOOGLE_API_KEY
- "Model not found" → gemini-3-pro-preview may not be available yet

**Grok Errors:**
- "Unauthorized" → Verify XAI_API_KEY
- "Model not found" → Confirm access to grok-4-0709

## Step 4: Performance Testing

### 4.1 Measure Response Time

Test with a simple question to measure baseline performance:

```bash
time curl -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What is 2+2?"}'
```

**Expected:**
- Round 1 should complete in parallel (~10-30 seconds)
- Total time: 1-3 minutes for all 4 rounds

### 4.2 Test Complex Questions

Try increasingly complex questions:

1. Simple: "What is the capital of France?"
2. Medium: "Explain quantum computing in simple terms"
3. Complex: "Compare and contrast the economic policies of keynesian and austrian economics"

## Step 5: Error Handling Testing

### 5.1 Test API Key Issues

Temporarily corrupt one API key in .env and verify:
- The application still works for other models
- Error messages are shown for the failing model
- The UI displays the error gracefully

### 5.2 Test Network Issues

Kill the backend while frontend is running:
- Verify error message appears
- Check that UI doesn't crash

## Quick Test Commands

Here's a quick test script you can run:

```bash
# Test 1: Health check
echo "Testing health endpoint..."
curl -s http://localhost:5000/api/health | jq

# Test 2: Simple research question
echo -e "\n\nTesting simple research question..."
curl -s -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}' | jq '.round1.responses | keys'

# Test 3: Check all rounds complete
echo -e "\n\nChecking all rounds..."
curl -s -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}' | jq 'keys'
```

## Success Criteria

✅ **Backend is working if:**
- Health endpoint returns 200 status
- All 4 model agents are listed
- Research endpoint completes all 4 rounds
- Each round has responses from all agents

✅ **Frontend is working if:**
- UI loads at http://localhost:3000
- Can submit questions successfully
- All 4 rounds display properly
- Final answer appears with winner badge

✅ **Full system is working if:**
- Can complete end-to-end research from UI
- All 4 models provide unique responses
- Voting and scoring work correctly
- Best answer is selected appropriately

## Troubleshooting

### Models returning errors?
1. Check API keys are correct in .env
2. Verify API keys have access to specified models
3. Check backend console for detailed error messages
4. Review model availability in your API tier

### Frontend not connecting to backend?
1. Ensure backend is running on port 5000
2. Check CORS is enabled in backend/app.py
3. Verify proxy setting in frontend/package.json

### Slow performance?
1. Parallel execution should work for Round 1
2. Check network connection to API endpoints
3. Some models (like thinking models) take longer

### UI not updating?
1. Check browser console for errors
2. Verify axios requests are succeeding
3. Ensure backend is returning proper JSON format
