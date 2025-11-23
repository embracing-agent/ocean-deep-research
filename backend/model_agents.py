import openai
from anthropic import Anthropic
import google.generativeai as genai
import requests
import json
import time


class ChatGPTAgent:
    """ChatGPT 5 Pro Thinking Agent"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
        # Using GPT-5 Pro as specified
        self.model = "gpt-5-pro-2025-10-06"

    def generate_response(self, question):
        """Generate initial response using ChatGPT thinking mode"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a deep research assistant. Provide thorough, well-researched answers with detailed reasoning."
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                reasoning_effort="high"  # Enable deep thinking
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to GPT-4 if o3-mini is not available
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a deep research assistant. Provide thorough, well-researched answers with detailed reasoning."
                        },
                        {
                            "role": "user",
                            "content": question
                        }
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                return response.choices[0].message.content
            except Exception as fallback_error:
                return f"ChatGPT Error: {str(fallback_error)}"

    def evaluate_responses(self, question, all_responses, criteria):
        """Evaluate all responses and vote for the best one"""
        evaluation_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Here are the responses from all agents:

ChatGPT: {all_responses.get('chatgpt', 'N/A')}

Claude: {all_responses.get('claude', 'N/A')}

Gemini: {all_responses.get('gemini', 'N/A')}

Grok: {all_responses.get('grok', 'N/A')}

Please evaluate each response based on the criteria above. Then vote for the BEST response by specifying which agent (chatgpt, claude, gemini, or grok) provided the most accurate and comprehensive answer.

Provide your evaluation and end with: VOTE: [agent_name]"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an impartial evaluator of AI responses."
                    },
                    {
                        "role": "user",
                        "content": evaluation_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=3000
            )

            eval_text = response.choices[0].message.content
            vote = self._extract_vote(eval_text)

            return {
                'evaluation': eval_text,
                'vote': vote
            }
        except Exception as e:
            return {
                'evaluation': f"Error: {str(e)}",
                'vote': None
            }

    def regenerate_response(self, question, original_responses, evaluations):
        """Regenerate response after reviewing other responses and evaluations"""
        context = f"""Original Question: {question}

Previous responses from all agents:
ChatGPT: {original_responses.get('chatgpt', 'N/A')}
Claude: {original_responses.get('claude', 'N/A')}
Gemini: {original_responses.get('gemini', 'N/A')}
Grok: {original_responses.get('grok', 'N/A')}

Evaluations from other agents:
{json.dumps(evaluations, indent=2)}

Based on the feedback and other agents' perspectives, provide an improved, comprehensive answer to the original question."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a deep research assistant who learns from peer feedback."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                temperature=0.7,
                max_tokens=4000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error regenerating: {str(e)}"

    def final_evaluation(self, question, final_responses, criteria):
        """Final evaluation and ranking of all regenerated responses"""
        eval_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Final responses from all agents:
ChatGPT: {final_responses.get('chatgpt', 'N/A')}
Claude: {final_responses.get('claude', 'N/A')}
Gemini: {final_responses.get('gemini', 'N/A')}
Grok: {final_responses.get('grok', 'N/A')}

Please rank all responses from 1 (best) to 4 (worst) based on accuracy, comprehensiveness, and quality.

Provide your evaluation and end with:
RANKINGS:
chatgpt: [1-4]
claude: [1-4]
gemini: [1-4]
grok: [1-4]"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an impartial evaluator of AI responses."
                    },
                    {
                        "role": "user",
                        "content": eval_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=3000
            )

            eval_text = response.choices[0].message.content
            rankings = self._extract_rankings(eval_text)

            return {
                'evaluation': eval_text,
                'rankings': rankings
            }
        except Exception as e:
            return {
                'evaluation': f"Error: {str(e)}",
                'rankings': {}
            }

    def _extract_vote(self, text):
        """Extract vote from evaluation text"""
        text_lower = text.lower()
        if 'vote: chatgpt' in text_lower:
            return 'chatgpt'
        elif 'vote: claude' in text_lower:
            return 'claude'
        elif 'vote: gemini' in text_lower:
            return 'gemini'
        elif 'vote: grok' in text_lower:
            return 'grok'
        return None

    def _extract_rankings(self, text):
        """Extract rankings from evaluation text"""
        rankings = {}
        lines = text.lower().split('\n')
        for line in lines:
            for agent in ['chatgpt', 'claude', 'gemini', 'grok']:
                if agent in line and ':' in line:
                    try:
                        rank = int(line.split(':')[-1].strip())
                        if 1 <= rank <= 4:
                            rankings[agent] = rank
                    except:
                        pass
        return rankings


class ClaudeAgent:
    """Claude Sonnet 4.5 with Extended Thinking Agent"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def generate_response(self, question):
        """Generate response using Claude with extended thinking"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={
                    "type": "enabled",
                    "budget_tokens": 10000
                },
                messages=[
                    {
                        "role": "user",
                        "content": f"Conduct deep research on this question and provide a comprehensive answer: {question}"
                    }
                ]
            )

            # Extract the text content from response
            full_response = ""
            for block in response.content:
                if block.type == "text":
                    full_response += block.text + "\n"

            return full_response.strip()
        except Exception as e:
            return f"Claude Error: {str(e)}"

    def evaluate_responses(self, question, all_responses, criteria):
        """Evaluate all responses and vote for the best one"""
        evaluation_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Here are the responses from all agents:

ChatGPT: {all_responses.get('chatgpt', 'N/A')}

Claude: {all_responses.get('claude', 'N/A')}

Gemini: {all_responses.get('gemini', 'N/A')}

Grok: {all_responses.get('grok', 'N/A')}

Please evaluate each response based on the criteria above. Then vote for the BEST response by specifying which agent (chatgpt, claude, gemini, or grok) provided the most accurate and comprehensive answer.

Provide your evaluation and end with: VOTE: [agent_name]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                messages=[
                    {
                        "role": "user",
                        "content": evaluation_prompt
                    }
                ]
            )

            eval_text = ""
            for block in response.content:
                if block.type == "text":
                    eval_text += block.text

            vote = self._extract_vote(eval_text)

            return {
                'evaluation': eval_text,
                'vote': vote
            }
        except Exception as e:
            return {
                'evaluation': f"Error: {str(e)}",
                'vote': None
            }

    def regenerate_response(self, question, original_responses, evaluations):
        """Regenerate response after reviewing feedback"""
        context = f"""Original Question: {question}

Previous responses from all agents:
ChatGPT: {original_responses.get('chatgpt', 'N/A')}
Claude: {original_responses.get('claude', 'N/A')}
Gemini: {original_responses.get('gemini', 'N/A')}
Grok: {original_responses.get('grok', 'N/A')}

Evaluations from other agents:
{json.dumps(evaluations, indent=2)}

Based on the feedback and other agents' perspectives, provide an improved, comprehensive answer to the original question."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={
                    "type": "enabled",
                    "budget_tokens": 8000
                },
                messages=[
                    {
                        "role": "user",
                        "content": context
                    }
                ]
            )

            full_response = ""
            for block in response.content:
                if block.type == "text":
                    full_response += block.text + "\n"

            return full_response.strip()
        except Exception as e:
            return f"Error regenerating: {str(e)}"

    def final_evaluation(self, question, final_responses, criteria):
        """Final evaluation and ranking"""
        eval_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Final responses from all agents:
ChatGPT: {final_responses.get('chatgpt', 'N/A')}
Claude: {final_responses.get('claude', 'N/A')}
Gemini: {final_responses.get('gemini', 'N/A')}
Grok: {final_responses.get('grok', 'N/A')}

Please rank all responses from 1 (best) to 4 (worst) based on accuracy, comprehensiveness, and quality.

Provide your evaluation and end with:
RANKINGS:
chatgpt: [1-4]
claude: [1-4]
gemini: [1-4]
grok: [1-4]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                messages=[
                    {
                        "role": "user",
                        "content": eval_prompt
                    }
                ]
            )

            eval_text = ""
            for block in response.content:
                if block.type == "text":
                    eval_text += block.text

            rankings = self._extract_rankings(eval_text)

            return {
                'evaluation': eval_text,
                'rankings': rankings
            }
        except Exception as e:
            return {
                'evaluation': f"Error: {str(e)}",
                'rankings': {}
            }

    def _extract_vote(self, text):
        """Extract vote from evaluation text"""
        text_lower = text.lower()
        if 'vote: chatgpt' in text_lower:
            return 'chatgpt'
        elif 'vote: claude' in text_lower:
            return 'claude'
        elif 'vote: gemini' in text_lower:
            return 'gemini'
        elif 'vote: grok' in text_lower:
            return 'grok'
        return None

    def _extract_rankings(self, text):
        """Extract rankings from evaluation text"""
        rankings = {}
        lines = text.lower().split('\n')
        for line in lines:
            for agent in ['chatgpt', 'claude', 'gemini', 'grok']:
                if agent in line and ':' in line:
                    try:
                        rank = int(line.split(':')[-1].strip())
                        if 1 <= rank <= 4:
                            rankings[agent] = rank
                    except:
                        pass
        return rankings


class GeminiAgent:
    """Gemini 3.0 Pro Deep Search Agent"""

    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        # Using Gemini 3.0 Pro Preview as specified
        self.model = genai.GenerativeModel('gemini-3-pro-preview')

    def generate_response(self, question):
        """Generate response using Gemini with deep search"""
        try:
            prompt = f"Conduct deep research and provide a comprehensive answer to: {question}"

            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=8000,
                )
            )

            return response.text
        except Exception as e:
            return f"Gemini Error: {str(e)}"

    def evaluate_responses(self, question, all_responses, criteria):
        """Evaluate all responses and vote"""
        evaluation_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Here are the responses from all agents:

ChatGPT: {all_responses.get('chatgpt', 'N/A')}

Claude: {all_responses.get('claude', 'N/A')}

Gemini: {all_responses.get('gemini', 'N/A')}

Grok: {all_responses.get('grok', 'N/A')}

Please evaluate each response based on the criteria above. Then vote for the BEST response by specifying which agent (chatgpt, claude, gemini, or grok) provided the most accurate and comprehensive answer.

Provide your evaluation and end with: VOTE: [agent_name]"""

        try:
            response = self.model.generate_content(
                evaluation_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4000,
                )
            )

            eval_text = response.text
            vote = self._extract_vote(eval_text)

            return {
                'evaluation': eval_text,
                'vote': vote
            }
        except Exception as e:
            return {
                'evaluation': f"Error: {str(e)}",
                'vote': None
            }

    def regenerate_response(self, question, original_responses, evaluations):
        """Regenerate response with feedback"""
        context = f"""Original Question: {question}

Previous responses from all agents:
ChatGPT: {original_responses.get('chatgpt', 'N/A')}
Claude: {original_responses.get('claude', 'N/A')}
Gemini: {original_responses.get('gemini', 'N/A')}
Grok: {original_responses.get('grok', 'N/A')}

Evaluations from other agents:
{json.dumps(evaluations, indent=2)}

Based on the feedback and other agents' perspectives, provide an improved, comprehensive answer to the original question."""

        try:
            response = self.model.generate_content(
                context,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=8000,
                )
            )
            return response.text
        except Exception as e:
            return f"Error regenerating: {str(e)}"

    def final_evaluation(self, question, final_responses, criteria):
        """Final evaluation and ranking"""
        eval_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Final responses from all agents:
ChatGPT: {final_responses.get('chatgpt', 'N/A')}
Claude: {final_responses.get('claude', 'N/A')}
Gemini: {final_responses.get('gemini', 'N/A')}
Grok: {final_responses.get('grok', 'N/A')}

Please rank all responses from 1 (best) to 4 (worst) based on accuracy, comprehensiveness, and quality.

Provide your evaluation and end with:
RANKINGS:
chatgpt: [1-4]
claude: [1-4]
gemini: [1-4]
grok: [1-4]"""

        try:
            response = self.model.generate_content(
                eval_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4000,
                )
            )

            eval_text = response.text
            rankings = self._extract_rankings(eval_text)

            return {
                'evaluation': eval_text,
                'rankings': rankings
            }
        except Exception as e:
            return {
                'evaluation': f"Error: {str(e)}",
                'rankings': {}
            }

    def _extract_vote(self, text):
        """Extract vote from evaluation text"""
        text_lower = text.lower()
        if 'vote: chatgpt' in text_lower:
            return 'chatgpt'
        elif 'vote: claude' in text_lower:
            return 'claude'
        elif 'vote: gemini' in text_lower:
            return 'gemini'
        elif 'vote: grok' in text_lower:
            return 'grok'
        return None

    def _extract_rankings(self, text):
        """Extract rankings from evaluation text"""
        rankings = {}
        lines = text.lower().split('\n')
        for line in lines:
            for agent in ['chatgpt', 'claude', 'gemini', 'grok']:
                if agent in line and ':' in line:
                    try:
                        rank = int(line.split(':')[-1].strip())
                        if 1 <= rank <= 4:
                            rankings[agent] = rank
                    except:
                        pass
        return rankings


class GrokAgent:
    """Grok 4 Agent with fixed API response handling"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.model = "grok-4-0709"  # Using Grok 4 as specified

    def _make_request(self, messages, temperature=0.7, max_tokens=4000):
        """Make API request to Grok with proper error handling"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            # FIX: Handle Grok's response format properly
            # Check if 'choices' exists in response
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            # Alternative: check for 'response' or 'output' field
            elif 'response' in result:
                return result['response']
            elif 'output' in result:
                return result['output']
            # If message is nested differently
            elif 'message' in result:
                return result['message'].get('content', str(result))
            else:
                # Return the full result as string if format is unexpected
                return f"Grok response (unexpected format): {json.dumps(result, indent=2)}"

        except requests.exceptions.RequestException as e:
            return f"Grok API Error: {str(e)}"
        except Exception as e:
            return f"Grok Error: {str(e)}"

    def generate_response(self, question):
        """Generate response using Grok"""
        messages = [
            {
                "role": "system",
                "content": "You are Grok, a deep research assistant. Provide thorough, well-researched answers with detailed reasoning."
            },
            {
                "role": "user",
                "content": question
            }
        ]

        return self._make_request(messages, temperature=0.7, max_tokens=4000)

    def evaluate_responses(self, question, all_responses, criteria):
        """Evaluate all responses and vote"""
        evaluation_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Here are the responses from all agents:

ChatGPT: {all_responses.get('chatgpt', 'N/A')}

Claude: {all_responses.get('claude', 'N/A')}

Gemini: {all_responses.get('gemini', 'N/A')}

Grok: {all_responses.get('grok', 'N/A')}

Please evaluate each response based on the criteria above. Then vote for the BEST response by specifying which agent (chatgpt, claude, gemini, or grok) provided the most accurate and comprehensive answer.

Provide your evaluation and end with: VOTE: [agent_name]"""

        messages = [
            {
                "role": "system",
                "content": "You are an impartial evaluator of AI responses."
            },
            {
                "role": "user",
                "content": evaluation_prompt
            }
        ]

        eval_text = self._make_request(messages, temperature=0.3, max_tokens=3000)
        vote = self._extract_vote(eval_text)

        return {
            'evaluation': eval_text,
            'vote': vote
        }

    def regenerate_response(self, question, original_responses, evaluations):
        """Regenerate response with feedback"""
        context = f"""Original Question: {question}

Previous responses from all agents:
ChatGPT: {original_responses.get('chatgpt', 'N/A')}
Claude: {original_responses.get('claude', 'N/A')}
Gemini: {original_responses.get('gemini', 'N/A')}
Grok: {original_responses.get('grok', 'N/A')}

Evaluations from other agents:
{json.dumps(evaluations, indent=2)}

Based on the feedback and other agents' perspectives, provide an improved, comprehensive answer to the original question."""

        messages = [
            {
                "role": "system",
                "content": "You are Grok, a deep research assistant who learns from peer feedback."
            },
            {
                "role": "user",
                "content": context
            }
        ]

        return self._make_request(messages, temperature=0.7, max_tokens=4000)

    def final_evaluation(self, question, final_responses, criteria):
        """Final evaluation and ranking"""
        eval_prompt = f"""Original Question: {question}

Evaluation Criteria:
{criteria}

Final responses from all agents:
ChatGPT: {final_responses.get('chatgpt', 'N/A')}
Claude: {final_responses.get('claude', 'N/A')}
Gemini: {final_responses.get('gemini', 'N/A')}
Grok: {final_responses.get('grok', 'N/A')}

Please rank all responses from 1 (best) to 4 (worst) based on accuracy, comprehensiveness, and quality.

Provide your evaluation and end with:
RANKINGS:
chatgpt: [1-4]
claude: [1-4]
gemini: [1-4]
grok: [1-4]"""

        messages = [
            {
                "role": "system",
                "content": "You are an impartial evaluator of AI responses."
            },
            {
                "role": "user",
                "content": eval_prompt
            }
        ]

        eval_text = self._make_request(messages, temperature=0.3, max_tokens=3000)
        rankings = self._extract_rankings(eval_text)

        return {
            'evaluation': eval_text,
            'rankings': rankings
        }

    def _extract_vote(self, text):
        """Extract vote from evaluation text"""
        if not isinstance(text, str):
            return None
        text_lower = text.lower()
        if 'vote: chatgpt' in text_lower:
            return 'chatgpt'
        elif 'vote: claude' in text_lower:
            return 'claude'
        elif 'vote: gemini' in text_lower:
            return 'gemini'
        elif 'vote: grok' in text_lower:
            return 'grok'
        return None

    def _extract_rankings(self, text):
        """Extract rankings from evaluation text"""
        if not isinstance(text, str):
            return {}
        rankings = {}
        lines = text.lower().split('\n')
        for line in lines:
            for agent in ['chatgpt', 'claude', 'gemini', 'grok']:
                if agent in line and ':' in line:
                    try:
                        rank = int(line.split(':')[-1].strip())
                        if 1 <= rank <= 4:
                            rankings[agent] = rank
                    except:
                        pass
        return rankings


class EvaluationFramework:
    """Dynamic evaluation framework based on the user's question"""

    def __init__(self, question):
        self.question = question

    def get_criteria(self):
        """Generate evaluation criteria based on the question type"""
        criteria = """
General Evaluation Criteria:

1. Accuracy: Is the information correct and factual?
2. Completeness: Does it fully answer the question?
3. Clarity: Is the explanation clear and easy to understand?
4. Depth: Does it provide sufficient detail and reasoning?
5. Relevance: Does it stay focused on the question?
6. Sources/Evidence: Are claims supported with reasoning or evidence?
7. Practical Value: Is the answer actionable and useful?

Consider the specific context of the question when evaluating.
"""
        return criteria
