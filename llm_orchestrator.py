"""
LLM orchestration for intelligent quiz solving
Uses LLMs to understand questions and generate executable code
"""
import json
import logging
import os
import re
from typing import Any, Dict, List
import httpx

logger = logging.getLogger(__name__)

class LLMOrchestrator:
    """Orchestrates LLM calls for quiz solving"""
    
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    async def analyze_question(self, question_text: str, file_links: List[Dict]) -> Dict[str, Any]:
        """
        Analyze question and create execution plan
        """
        prompt = f"""You are a data analysis expert. Analyze this quiz question and create an execution plan.

Question:
{question_text}

Available files: {json.dumps(file_links, indent=2)}

Provide a JSON response with:
1. "task_type": Type of task (scraping, analysis, visualization, etc.)
2. "data_sources": List of data sources needed (URLs, files)
3. "operations": List of operations to perform
4. "output_format": Expected output format (number, string, json_array, data_uri)
5. "answer_key": Which field contains the final answer

Example:
{{
  "task_type": "data_analysis",
  "data_sources": ["https://example.com/data.pdf"],
  "operations": [
    "download_pdf",
    "extract_page_2",
    "parse_table",
    "sum_column_value"
  ],
  "output_format": "number",
  "answer_key": "sum"
}}

Respond ONLY with valid JSON, no other text."""

        try:
            if self.gemini_api_key:
                return await self._call_gemini(prompt)
            elif self.openai_api_key:
                return await self._call_openai(prompt)
            else:
                logger.warning("No API keys configured, using heuristic analysis")
                return self._heuristic_analysis(question_text, file_links)
        except Exception as e:
            logger.error(f"Error analyzing question: {e}")
            return self._heuristic_analysis(question_text, file_links)
    
    async def generate_code(self, plan: Dict[str, Any], question_text: str) -> str:
        """
        Generate executable Python code based on the plan
        """
        prompt = f"""Generate Python code to solve this data analysis task.

Question: {question_text}

Execution Plan:
{json.dumps(plan, indent=2)}

Requirements:
1. Import all necessary libraries (pandas, numpy, matplotlib, etc.)
2. Include error handling
3. Print the final answer as the last line
4. For visualizations, save as base64 data URI
5. Code must be self-contained and executable

Generate ONLY the Python code, no explanations."""

        try:
            if self.gemini_api_key:
                code = await self._call_gemini(prompt, response_type="code")
                return self._extract_code(code)
            elif self.openai_api_key:
                code = await self._call_openai(prompt, response_type="code")
                return self._extract_code(code)
            else:
                return self._generate_template_code(plan)
        except Exception as e:
            logger.error(f"Error generating code: {e}")
            return self._generate_template_code(plan)
    
    async def _call_gemini(self, prompt: str, response_type: str = "json") -> Any:
        """Call Google Gemini API"""
        import google.generativeai as genai
        
        genai.configure(api_key=self.gemini_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        response = model.generate_content(prompt)
        text = response.text
        
        if response_type == "json":
            # Clean and parse JSON
            text = self._clean_json_response(text)
            return json.loads(text)
        else:
            return text
    
    async def _call_openai(self, prompt: str, response_type: str = "json") -> Any:
        """Call OpenAI API"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are a data analysis expert."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1
                }
            )
            
            result = response.json()
            text = result['choices'][0]['message']['content']
            
            if response_type == "json":
                text = self._clean_json_response(text)
                return json.loads(text)
            else:
                return text
    
    def _clean_json_response(self, text: str) -> str:
        """Clean JSON response from LLM (remove markdown, etc.)"""
        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Find JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group()
        return text
    
    def _extract_code(self, text: str) -> str:
        """Extract code from LLM response"""
        # Remove markdown code blocks
        text = re.sub(r'```python\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text.strip()
    
    def _heuristic_analysis(self, question_text: str, file_links: List[Dict]) -> Dict[str, Any]:
        """
        Fallback heuristic analysis when no LLM is available
        """
        question_lower = question_text.lower()
        
        # Detect task type
        if any(word in question_lower for word in ['chart', 'plot', 'graph', 'scatter', 'visualiz']):
            task_type = "visualization"
            output_format = "data_uri"
        elif any(word in question_lower for word in ['sum', 'count', 'average', 'total', 'calculate']):
            task_type = "calculation"
            output_format = "number"
        elif any(word in question_lower for word in ['list', 'which', 'what are']):
            task_type = "extraction"
            output_format = "json_array"
        else:
            task_type = "general"
            output_format = "string"
        
        # Extract data sources
        data_sources = []
        for link in file_links:
            data_sources.append(link['url'])
        
        # Detect operations
        operations = []
        if 'download' in question_lower or file_links:
            operations.append("download_file")
        if 'pdf' in question_lower:
            operations.append("parse_pdf")
        if 'table' in question_lower:
            operations.append("extract_table")
        if 'sum' in question_lower:
            operations.append("sum_values")
        if 'correlation' in question_lower:
            operations.append("calculate_correlation")
        if 'earliest' in question_lower or 'first' in question_lower:
            operations.append("find_earliest")
        
        return {
            "task_type": task_type,
            "data_sources": data_sources,
            "operations": operations,
            "output_format": output_format,
            "answer_key": "result"
        }
    
    def _generate_template_code(self, plan: Dict[str, Any]) -> str:
        """
        Generate template code based on plan
        """
        code_parts = [
            "import pandas as pd",
            "import numpy as np",
            "import matplotlib.pyplot as plt",
            "import base64",
            "import io",
            "import httpx",
            "",
            "# Main execution",
            "try:"
        ]
        
        # Add data loading
        if plan.get('data_sources'):
            code_parts.append("    # Load data")
            for source in plan['data_sources']:
                code_parts.append(f"    # Download from: {source}")
        
        # Add operations
        if plan.get('operations'):
            code_parts.append("    # Process data")
            for op in plan['operations']:
                code_parts.append(f"    # Operation: {op}")
        
        # Add output
        output_format = plan.get('output_format', 'string')
        if output_format == "data_uri":
            code_parts.extend([
                "    # Generate visualization",
                "    plt.figure()",
                "    # ... plotting code ...",
                "    buf = io.BytesIO()",
                "    plt.savefig(buf, format='png')",
                "    buf.seek(0)",
                "    img_b64 = base64.b64encode(buf.read()).decode()",
                "    result = f'data:image/png;base64,{img_b64}'",
                "    print(result)"
            ])
        else:
            code_parts.extend([
                "    result = 0  # Calculate result",
                "    print(result)"
            ])
        
        code_parts.extend([
            "except Exception as e:",
            "    print(f'Error: {e}')"
        ])
        
        return "\n".join(code_parts)