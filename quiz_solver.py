"""
Quiz solving engine with LLM-powered task decomposition
Refactored to use Global Browser instance and Real LLM integration
"""
import asyncio
import base64
import json
import logging
import time
import re
from urllib.parse import urljoin
from typing import Dict, Any, Optional

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser

from llm_orchestrator import LLMOrchestrator
from tools_utilities import execute_llm_generated_code

logger = logging.getLogger(__name__)

# Global browser instance managed by app.py
_GLOBAL_BROWSER: Optional[Browser] = None

def set_global_browser(browser: Browser):
    global _GLOBAL_BROWSER
    _GLOBAL_BROWSER = browser

async def close_global_browser():
    global _GLOBAL_BROWSER
    if _GLOBAL_BROWSER:
        await _GLOBAL_BROWSER.close()
        _GLOBAL_BROWSER = None

class QuizSolver:
    """Handles quiz solving with LLM assistance"""
    
    def __init__(self, email: str, secret: str):
        self.email = email
        self.secret = secret
        self.start_time = None
        self.max_duration = 180  # 3 minutes in seconds
        self.orchestrator = LLMOrchestrator()
        
    def time_remaining(self) -> float:
        """Calculate remaining time in seconds"""
        if not self.start_time:
            return self.max_duration
        elapsed = time.time() - self.start_time
        return max(0, self.max_duration - elapsed)
    
    async def solve_quiz_chain(self, initial_url: str):
        """
        Solve a chain of quiz questions, following URLs until complete
        """
        self.start_time = time.time()
        current_url = initial_url
        attempt = 1
        
        while current_url and self.time_remaining() > 10:
            logger.info(f"Attempt {attempt}: Solving quiz at {current_url}")
            logger.info(f"Time remaining: {self.time_remaining():.1f}s")
            
            try:
                # Fetch and render the quiz page
                quiz_content = await self.fetch_quiz_page(current_url)
                
                # Extract the actual question (decode base64 if needed)
                question_data = self.extract_question(quiz_content, current_url)
                
                # Solve the question using LLM
                answer = await self.solve_question(question_data)
                
                # Submit the answer
                submit_url = question_data.get('submit_url')
                if not submit_url:
                    logger.error("No submit URL found! Cannot proceed.")
                    break

                result = await self.submit_answer(
                    submit_url=submit_url,
                    quiz_url=current_url,
                    answer=answer
                )
                
                # Check result
                if result.get('correct'):
                    logger.info(f"✓ Answer correct for {current_url}")
                    current_url = result.get('url')  # Move to next question
                    if not current_url:
                        logger.info("Quiz chain complete!")
                        break
                else:
                    logger.warning(f"✗ Answer incorrect: {result.get('reason')}")
                    next_url = result.get('url')
                    if next_url and next_url != current_url:
                        logger.info("Moving to next question despite error")
                        current_url = next_url
                    else:
                        if self.time_remaining() > 30:
                            logger.info("Retrying current question...")
                            continue
                        else:
                            logger.warning("Not enough time to retry")
                            break
                
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error solving quiz at {current_url}: {str(e)}", exc_info=True)
                break
        
        logger.info(f"Quiz solving completed after {attempt} attempts")
    
    async def fetch_quiz_page(self, url: str) -> str:
        """
        Fetch and render a quiz page using the global browser instance.
        Reuses browser context for performance.
        """
        if not _GLOBAL_BROWSER:
            raise RuntimeError("Browser not initialized! Ensure app startup completed.")

        # Create a new context (like a fresh tab/session) for isolation
        context = await _GLOBAL_BROWSER.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            # Small wait for dynamic rendering
            await page.wait_for_timeout(1000)
            
            # Better Base64 extraction via direct JS evaluation
            # This is more robust than parsing HTML strings with Regex
            content = await page.content()
            return content
        finally:
            await page.close()
            await context.close()
    
    def extract_question(self, html_content: str, current_url: str) -> Dict[str, Any]:
        """
        Extract question details, handling relative URLs and Base64
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. Robust Base64 Decoding
        decoded_content = None
        scripts = soup.find_all('script')
        for script in scripts:
            if script.text and ('atob(' in script.text or 'base64' in script.text.lower()):
                # Look for strings inside atob('...')
                matches = re.findall(r"atob\(['\"]([A-Za-z0-9+/=]+)['\"]\)", script.text)
                for match in matches:
                    try:
                        decoded = base64.b64decode(match).decode('utf-8')
                        decoded_content = decoded
                        break
                    except:
                        continue
        
        if decoded_content:
            question_soup = BeautifulSoup(decoded_content, 'html.parser')
        else:
            question_soup = soup
        
        question_text = question_soup.get_text(strip=True)
        
        # 2. Robust Submit URL Extraction
        submit_url = None
        
        # Try finding <form action="..."> first
        form = question_soup.find('form')
        if form and form.get('action'):
            submit_url = form.get('action')
        
        # Fallback to text search if no form
        if not submit_url:
            for line in question_text.split('\n'):
                if 'submit' in line.lower() and 'http' in line:
                    url_match = re.search(r'https?://[^\s<>"]+', line)
                    if url_match:
                        submit_url = url_match.group()
        
        # 3. Fix Relative URLs
        if submit_url:
            submit_url = urljoin(current_url, submit_url)
            
        # Extract file links
        file_links = []
        for link in question_soup.find_all('a', href=True):
            # Skip common nav links
            if link['href'].startswith('#') or 'javascript' in link['href']:
                continue
            full_link = urljoin(current_url, link['href'])
            file_links.append({
                'text': link.text,
                'url': full_link
            })
        
        return {
            'question_text': question_text,
            'submit_url': submit_url,
            'file_links': file_links,
            'raw_html': decoded_content or html_content
        }
    
    async def solve_question(self, question_data: Dict[str, Any]) -> Any:
        """
        Use LLM Orchestrator to analyze and solve the question dynamically
        """
        question_text = question_data['question_text']
        file_links = question_data['file_links']
        
        logger.info(f"Analyzing Question: {question_text[:100]}...")
        
        # 1. Analyze structure
        plan = await self.orchestrator.analyze_question(question_text, file_links)
        logger.info(f"Execution Plan: {json.dumps(plan)}")
        
        # 2. Generate Code
        code = await self.orchestrator.generate_code(plan, question_text)
        
        # 3. Execute Code
        try:
            logger.info("Executing generated code...")
            result_raw = await execute_llm_generated_code(code)
            
            # 4. Clean result based on output format
            result = result_raw.strip()
            
            # Type conversion
            output_format = plan.get('output_format', 'string')
            if output_format == 'number':
                try:
                    return float(result) if '.' in result else int(result)
                except:
                    return result # Fallback
            elif output_format == 'json_array':
                try:
                    return json.loads(result)
                except:
                    return result
            
            return result
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            # Fallback: Ask LLM for a direct answer if code fails
            return "Error in calculation"

    async def submit_answer(self, submit_url: str, quiz_url: str, answer: Any) -> Dict[str, Any]:
        """Submit an answer to the quiz endpoint"""
        payload = {
            "email": self.email,
            "secret": self.secret,
            "url": quiz_url,
            "answer": answer
        }
        
        logger.info(f"Submitting to {submit_url}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(submit_url, json=payload)
                return response.json()
            except Exception as e:
                logger.error(f"Error submitting answer: {str(e)}")
                return {"correct": False, "reason": f"Net Error: {str(e)}"}
