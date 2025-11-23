import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

from model_agents import (
    ChatGPTAgent,
    ClaudeAgent,
    GeminiAgent,
    GrokAgent,
    EvaluationFramework
)

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize agents
chatgpt_agent = ChatGPTAgent(os.getenv('OPENAI_API_KEY'))
claude_agent = ClaudeAgent(os.getenv('ANTHROPIC_API_KEY'))
gemini_agent = GeminiAgent(os.getenv('GOOGLE_API_KEY'))
grok_agent = GrokAgent(os.getenv('XAI_API_KEY'))

agents = {
    'chatgpt': chatgpt_agent,
    'claude': claude_agent,
    'gemini': gemini_agent,
    'grok': grok_agent
}


def run_round_1(question):
    """Round 1: All agents answer the question in parallel"""
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            name: executor.submit(agent.generate_response, question)
            for name, agent in agents.items()
        }

        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = f"Error: {str(e)}"

    return results


def run_round_2(question, round1_results):
    """Round 2: Each agent evaluates all responses and votes for the best"""
    evaluation_framework = EvaluationFramework(question)
    evaluation_results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            name: executor.submit(
                agent.evaluate_responses,
                question,
                round1_results,
                evaluation_framework.get_criteria()
            )
            for name, agent in agents.items()
        }

        for name, future in futures.items():
            try:
                evaluation_results[name] = future.result()
            except Exception as e:
                evaluation_results[name] = {
                    'evaluation': f"Error: {str(e)}",
                    'vote': None
                }

    # Count votes
    votes = {}
    for name, result in evaluation_results.items():
        if isinstance(result, dict) and 'vote' in result and result['vote']:
            voted_for = result['vote']
            votes[voted_for] = votes.get(voted_for, 0) + 1

    best_from_round1 = max(votes.items(), key=lambda x: x[1])[0] if votes else 'claude'

    return evaluation_results, best_from_round1, votes


def run_round_3(question, round1_results, round2_evaluations):
    """Round 3: Each agent regenerates their answer after reviewing all feedback"""
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            name: executor.submit(
                agent.regenerate_response,
                question,
                round1_results,
                round2_evaluations
            )
            for name, agent in agents.items()
        }

        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = f"Error: {str(e)}"

    return results


def run_round_4(question, round3_results):
    """Round 4: Rate each response and pick the best one"""
    evaluation_framework = EvaluationFramework(question)
    final_evaluations = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            name: executor.submit(
                agent.final_evaluation,
                question,
                round3_results,
                evaluation_framework.get_criteria()
            )
            for name, agent in agents.items()
        }

        for name, future in futures.items():
            try:
                final_evaluations[name] = future.result()
            except Exception as e:
                final_evaluations[name] = {
                    'evaluation': f"Error: {str(e)}",
                    'rankings': {}
                }

    # Aggregate rankings
    scores = {agent_name: 0 for agent_name in agents.keys()}
    for evaluator, result in final_evaluations.items():
        if isinstance(result, dict) and 'rankings' in result:
            for agent_name, rank in result['rankings'].items():
                # Lower rank = better (1st place = 1)
                # Convert to points: 1st = 4pts, 2nd = 3pts, 3rd = 2pts, 4th = 1pt
                scores[agent_name] += (5 - rank)

    best_final = max(scores.items(), key=lambda x: x[1])[0] if scores else 'claude'

    return final_evaluations, best_final, scores


@app.route('/api/research', methods=['POST'])
def research():
    """Main endpoint for multi-model deep research"""
    data = request.json
    question = data.get('question', '')

    if not question:
        return jsonify({'error': 'Question is required'}), 400

    try:
        # Round 1: Initial responses
        print("Starting Round 1: Initial responses...")
        round1_results = run_round_1(question)

        # Round 2: Evaluation and voting
        print("Starting Round 2: Evaluation and voting...")
        round2_evaluations, best_round1, votes = run_round_2(question, round1_results)

        # Round 3: Regenerate with feedback
        print("Starting Round 3: Regenerating with feedback...")
        round3_results = run_round_3(question, round1_results, round2_evaluations)

        # Round 4: Final evaluation
        print("Starting Round 4: Final evaluation...")
        round4_evaluations, best_final, scores = run_round_4(question, round3_results)

        response = {
            'question': question,
            'round1': {
                'responses': round1_results
            },
            'round2': {
                'evaluations': round2_evaluations,
                'best_from_round1': best_round1,
                'votes': votes
            },
            'round3': {
                'responses': round3_results
            },
            'round4': {
                'evaluations': round4_evaluations,
                'best_final': best_final,
                'scores': scores,
                'final_answer': round3_results.get(best_final, 'No final answer available')
            }
        }

        return jsonify(response)

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'agents': list(agents.keys())})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
