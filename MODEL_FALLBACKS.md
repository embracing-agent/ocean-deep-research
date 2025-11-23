# Model Fallback Options

If the specified model IDs don't work, try these alternatives:

## ChatGPT Fallbacks

Current: `gpt-5-pro-2025-10-06`

Try these in order:
1. `o3-mini` - Latest thinking model
2. `o1-preview` - Reasoning model
3. `gpt-4-turbo-preview` - Latest GPT-4
4. `gpt-4` - Stable GPT-4

**To change:** Edit `backend/model_agents.py` line 16

## Claude Fallbacks

Current: `claude-sonnet-4-5-20250929`

Try these in order:
1. `claude-sonnet-4-20250514` - Claude Sonnet 4
2. `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet (latest stable)
3. `claude-3-opus-20240229` - Claude 3 Opus

**To change:** Edit `backend/model_agents.py` line 231

## Gemini Fallbacks

Current: `gemini-3-pro-preview`

Try these in order:
1. `gemini-2.0-flash-thinking-exp-01-21` - Gemini 2.0 Flash Thinking
2. `gemini-2.0-flash-exp` - Gemini 2.0 Flash Experimental
3. `gemini-1.5-pro-latest` - Gemini 1.5 Pro (stable)
4. `gemini-pro` - Gemini Pro

**To change:** Edit `backend/model_agents.py` line 438

## Grok Fallbacks

Current: `grok-4-0709`

Try these in order:
1. `grok-beta` - Grok Beta
2. `grok-2-latest` - Grok 2
3. `grok-2-1212` - Specific Grok 2 version

**To change:** Edit `backend/model_agents.py` line 606

## How to Update Model IDs

1. Open `backend/model_agents.py`
2. Find the `__init__` method for the agent you want to update
3. Change the `self.model = "..."` line
4. Save the file
5. Restart the backend server
6. Run `python test_models.py` again to verify

## Example: Changing ChatGPT Model

```python
# In backend/model_agents.py, around line 16
class ChatGPTAgent:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
        # Change this line:
        self.model = "gpt-4-turbo-preview"  # Instead of gpt-5-pro-2025-10-06
```

Then restart backend and test again.
