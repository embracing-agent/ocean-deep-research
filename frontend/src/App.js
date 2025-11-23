import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!question.trim()) {
      setError('Please enter a question');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const response = await axios.post('/api/research', {
        question: question
      });

      setResults(response.data);
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getAgentName = (agentKey) => {
    const names = {
      'chatgpt': 'ChatGPT 5 Pro',
      'claude': 'Claude Sonnet 4.5',
      'gemini': 'Gemini 3.0 Pro',
      'grok': 'Grok 4'
    };
    return names[agentKey] || agentKey;
  };

  return (
    <div className="app">
      <h1>🌊 Ocean Deep Research</h1>
      <p style={{ textAlign: 'center', color: 'white', marginBottom: '30px', fontSize: '18px' }}>
        Multi-Model AI Research Platform - Powered by ChatGPT, Claude, Gemini & Grok
      </p>

      <div className="input-section">
        <h2>Ask Your Question</h2>
        <form onSubmit={handleSubmit}>
          <textarea
            className="question-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Enter your research question here..."
            disabled={loading}
          />
          <button
            type="submit"
            className="submit-button"
            disabled={loading}
          >
            {loading ? 'Researching...' : 'Start Deep Research'}
          </button>
        </form>
      </div>

      {loading && (
        <div className="loading">
          <span>AI agents are researching your question</span>
          <div className="loading-spinner"></div>
        </div>
      )}

      {error && (
        <div className="error">
          <h3>Error</h3>
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="results">
          {/* Round 1: Initial Responses */}
          <div className="round-section">
            <h2>Round 1: Initial Responses</h2>
            <p style={{ marginBottom: '20px', color: '#666' }}>
              All AI agents answer your question independently and in parallel.
            </p>
            <div className="agents-grid">
              {Object.entries(results.round1.responses).map(([agent, response]) => (
                <div key={agent} className={`agent-card ${agent}`}>
                  <h3>
                    <span className={`agent-icon ${agent}`}></span>
                    {getAgentName(agent)}
                  </h3>
                  <div className="response-text">{response}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Round 2: Evaluation & Voting */}
          <div className="round-section">
            <h2>Round 2: Peer Evaluation & Voting</h2>
            <p style={{ marginBottom: '20px', color: '#666' }}>
              Each agent evaluates all responses and votes for the best one.
            </p>
            <div className="agents-grid">
              {Object.entries(results.round2.evaluations).map(([agent, evaluation]) => (
                <div key={agent} className={`agent-card ${agent}`}>
                  <h3>
                    <span className={`agent-icon ${agent}`}></span>
                    {getAgentName(agent)}'s Evaluation
                  </h3>
                  <div className="response-text">
                    {typeof evaluation === 'object' ? evaluation.evaluation : evaluation}
                    {typeof evaluation === 'object' && evaluation.vote && (
                      <div style={{ marginTop: '15px', padding: '10px', background: '#e3f2fd', borderRadius: '5px' }}>
                        <strong>Voted for:</strong> {getAgentName(evaluation.vote)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="voting-section">
              <h3>Voting Results</h3>
              <div className="vote-results">
                {Object.entries(results.round2.votes).map(([agent, votes]) => (
                  <div key={agent} className="vote-badge">
                    {getAgentName(agent)}: {votes} vote{votes !== 1 ? 's' : ''}
                  </div>
                ))}
              </div>
              <p style={{ marginTop: '15px', fontSize: '18px' }}>
                <strong>Best from Round 1:</strong>
                <span className="best-badge">{getAgentName(results.round2.best_from_round1)}</span>
              </p>
            </div>
          </div>

          {/* Round 3: Regenerated Responses */}
          <div className="round-section">
            <h2>Round 3: Improved Responses</h2>
            <p style={{ marginBottom: '20px', color: '#666' }}>
              After reviewing peer feedback, each agent provides an improved answer.
            </p>
            <div className="agents-grid">
              {Object.entries(results.round3.responses).map(([agent, response]) => (
                <div key={agent} className={`agent-card ${agent}`}>
                  <h3>
                    <span className={`agent-icon ${agent}`}></span>
                    {getAgentName(agent)}
                  </h3>
                  <div className="response-text">{response}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Round 4: Final Evaluation */}
          <div className="round-section">
            <h2>Round 4: Final Rankings</h2>
            <p style={{ marginBottom: '20px', color: '#666' }}>
              All agents evaluate and rank the final improved responses.
            </p>
            <div className="agents-grid">
              {Object.entries(results.round4.evaluations).map(([agent, evaluation]) => (
                <div key={agent} className={`agent-card ${agent}`}>
                  <h3>
                    <span className={`agent-icon ${agent}`}></span>
                    {getAgentName(agent)}'s Final Evaluation
                  </h3>
                  <div className="response-text">
                    {typeof evaluation === 'object' ? evaluation.evaluation : evaluation}
                    {typeof evaluation === 'object' && evaluation.rankings && Object.keys(evaluation.rankings).length > 0 && (
                      <div style={{ marginTop: '15px', padding: '10px', background: '#fff3e0', borderRadius: '5px' }}>
                        <strong>Rankings:</strong>
                        <ul style={{ marginTop: '8px', marginLeft: '20px' }}>
                          {Object.entries(evaluation.rankings)
                            .sort((a, b) => a[1] - b[1])
                            .map(([rankedAgent, rank]) => (
                              <li key={rankedAgent}>
                                {getAgentName(rankedAgent)}: Rank {rank}
                              </li>
                            ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="voting-section">
              <h3>Final Scores (Higher is Better)</h3>
              <div className="scores-grid">
                {Object.entries(results.round4.scores)
                  .sort((a, b) => b[1] - a[1])
                  .map(([agent, score]) => (
                    <div key={agent} className="score-card">
                      <h4>{getAgentName(agent)}</h4>
                      <div className="score-value">{score}</div>
                      {agent === results.round4.best_final && (
                        <div className="best-badge" style={{ marginTop: '8px' }}>WINNER</div>
                      )}
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Final Answer */}
          <div className="final-answer-section">
            <h2>🏆 Final Best Answer</h2>
            <p style={{ color: 'white', marginBottom: '20px', fontSize: '16px' }}>
              Selected by consensus from {getAgentName(results.round4.best_final)}
            </p>
            <div className="final-answer-card">
              <h3>Question: {results.question}</h3>
              <div className="response-text" style={{ maxHeight: 'none' }}>
                {results.round4.final_answer}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
