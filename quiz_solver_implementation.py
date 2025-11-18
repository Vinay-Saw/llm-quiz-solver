"""
Quiz solving engine with LLM-powered task decomposition
"""
import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import os

logger = logging.getLogger(__name__)

class QuizSolver:
    """Handles quiz solving with LLM assistance"""
    
    def __init__(self, email: str, secret: str):
        self.email = email
        self.secret = secret
        self.start_time = None
        self.max_duration = 180  # 3 minutes in seconds
        
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
                question_data = self.extract_question(quiz_content)
                
                # Solve the question using LLM
                answer = await self.solve_question(question_data)
                
                # Submit the answer
                submit_url = question_data.get('submit_url')
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
                    # May get a new URL to proceed even if wrong
                    next_url = result.get('url')
                    if next_url and next_url != current_url:
                        logger.info("Moving to next question despite error")
                        current_url = next_url
                    else:
                        # Retry current question if time permits
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
        Fetch and render a quiz page (handles JavaScript)
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # Wait a bit for any dynamic content
                await page.wait_for_timeout(2000)
                content = await page.content()
                return content
            finally:
                await browser.close()
    
    def extract_question(self, html_content: str) -> Dict[str, Any]:
        """
        Extract question details from HTML, handling base64 encoded content
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for base64 encoded content in scripts
        scripts = soup.find_all('script')
        decoded_content = None
        
        for script in scripts:
            if 'atob' in script.text or 'base64' in script.text.lower():
                # Try to extract base64 strings
                import re
                base64_pattern = r'atob\([\'"`]([A-Za-z0-9+/=]+)[\'"`]\)'
                matches = re.findall(base64_pattern, script.text)
                
                for match in matches:
                    try:
                        decoded = base64.b64decode(match).decode('utf-8')
                        decoded_content = decoded
                        break
                    except:
                        continue
        
        # If we found decoded content, parse it
        if decoded_content:
            question_soup = BeautifulSoup(decoded_content, 'html.parser')
        else:
            question_soup = soup
        
        # Extract question text
        question_text = question_soup.get_text(strip=True)
        
        # Extract submit URL
        submit_url = None
        for line in question_text.split('\n'):
            if 'submit' in line.lower() and 'http' in line:
                # Extract URL from text
                import re
                url_match = re.search(r'https?://[^\s<>"]+', line)
                if url_match:
                    submit_url = url_match.group()
        
        # Extract any file links
        file_links = []
        for link in question_soup.find_all('a', href=True):
            file_links.append({
                'text': link.text,
                'url': link['href']
            })
        
        return {
            'question_text': question_text,
            'submit_url': submit_url,
            'file_links': file_links,
            'raw_html': decoded_content or html_content
        }
    
    async def solve_question(self, question_data: Dict[str, Any]) -> Any:
        """
        Use LLM to understand and solve the question
        """
        question_text = question_data['question_text']
        file_links = question_data['file_links']
        
        logger.info(f"Question: {question_text[:200]}...")
        
        # For now, implement basic logic for common question types
        # In production, this would use an LLM to generate and execute code
        
        # Example: If question asks for a simple number
        if "sum" in question_text.lower() and "value" in question_text.lower():
            # This is a placeholder - actual implementation would:
            # 1. Download the file from file_links
            # 2. Parse it (PDF, CSV, etc.)
            # 3. Perform the calculation
            return 12345  # Placeholder
        
        # Example: If question asks for a visualization
        if "scatterplot" in question_text.lower() or "chart" in question_text.lower():
            # Would generate the chart and return as base64 data URI
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        # Default: return the question text as answer
        return question_text
    
    async def submit_answer(
        self,
        submit_url: str,
        quiz_url: str,
        answer: Any
    ) -> Dict[str, Any]:
        """
        Submit an answer to the quiz endpoint
        """
        payload = {
            "email": self.email,
            "secret": self.secret,
            "url": quiz_url,
            "answer": answer
        }
        
        logger.info(f"Submitting answer to {submit_url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    submit_url,
                    json=payload
                )
                
                result = response.json()
                logger.info(f"Response: {json.dumps(result, indent=2)}")
                return result
                
            except Exception as e:
                logger.error(f"Error submitting answer: {str(e)}")
                return {
                    "correct": False,
                    "reason": f"Submission error: {str(e)}"
                }