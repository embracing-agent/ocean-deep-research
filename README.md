# 🌊 Ocean Deep Research

A multi-model AI research platform that uses the world's best frontier AI models to conduct deep research and provide comprehensive answers through a collaborative, multi-round evaluation process.

## Features

- **Multi-Model Research**: Leverages 4 frontier AI models:
  - ChatGPT 5 Pro Thinking (OpenAI)
  - Claude Sonnet 4.5 with Extended Thinking (Anthropic)
  - Gemini 3.0 Pro Deep Search (Google)
  - Grok 4 (xAI)

- **4-Round Research Process**:
  1. **Round 1**: All agents answer your question independently in parallel
  2. **Round 2**: Each agent evaluates all responses and votes for the best one
  3. **Round 3**: Agents regenerate improved answers based on peer feedback
  4. **Round 4**: Final evaluation and ranking to select the best answer

- **Interactive UI**: Beautiful web interface showing full responses from each agent in every iteration

## Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ocean-deep-research
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install frontend dependencies:
```bash
cd frontend
npm install
cd ..
```

4. Configure API keys:
   - Copy `.env.example` to `.env` (already created)
   - Add your API keys for:
     - OPENAI_API_KEY
     - ANTHROPIC_API_KEY
     - GOOGLE_API_KEY
     - XAI_API_KEY

## Running the Application

### Option 1: Using the run script

```bash
python run.py
```

This will start both the backend (Flask) and frontend (React) servers.

### Option 2: Manual start

**Terminal 1 - Backend:**
```bash
cd backend
python app.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

## Usage

1. Open http://localhost:3000 in your browser
2. Enter your research question in the text area
3. Click "Start Deep Research"
4. Watch as all 4 AI models research your question through 4 rounds
5. View the final best answer selected by consensus

## Architecture

```
ocean-deep-research/
├── backend/
│   ├── app.py              # Flask API server
│   └── model_agents.py     # AI model integrations
├── frontend/
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── index.js        # React entry point
│   │   └── index.css       # Styles
│   ├── public/
│   └── package.json
├── .env                     # API keys (not in git)
├── requirements.txt         # Python dependencies
└── README.md
```

## API Endpoints

### POST /api/research
Conducts multi-model deep research on a question.

**Request:**
```json
{
  "question": "Your research question here"
}
```

**Response:**
```json
{
  "question": "...",
  "round1": {
    "responses": { "chatgpt": "...", "claude": "...", ... }
  },
  "round2": {
    "evaluations": { ... },
    "best_from_round1": "...",
    "votes": { ... }
  },
  "round3": {
    "responses": { ... }
  },
  "round4": {
    "evaluations": { ... },
    "best_final": "...",
    "scores": { ... },
    "final_answer": "..."
  }
}
```

### GET /api/health
Health check endpoint.

## Model Information

- **ChatGPT**: `gpt-5-pro-2025-10-06` with high reasoning effort
- **Claude**: `claude-sonnet-4-5-20250929` with extended thinking (10K budget tokens)
- **Gemini**: `gemini-3-pro-preview` with deep search capabilities
- **Grok**: `grok-4-0709` with advanced reasoning

## Troubleshooting

### Grok API Errors
The application includes special handling for Grok's response format. If you encounter issues:
- Verify your XAI_API_KEY is correct
- Check that the Grok API endpoint is accessible
- Review error messages in the backend console

### Model Availability
If a specific model is not available or returns errors:
- Check your API key has access to the model
- Verify the model ID is correct for your API tier
- Review the backend logs for detailed error messages

## License

MIT License - see LICENSE file for details
