"""
Utility functions for data processing, scraping, and analysis
Refactored for Thread Safety and Robust Execution
"""
import base64
import io
import json
import logging
import tempfile
import os
import subprocess
from typing import Dict, Any, List, Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from matplotlib.figure import Figure # OO Interface
from matplotlib.backends.backend_agg import FigureCanvasAgg

logger = logging.getLogger(__name__)

async def download_file(url: str) -> bytes:
    """Download a file from URL"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.content

async def scrape_table(url: str, table_selector: Optional[str] = None) -> pd.DataFrame:
    """Scrape table data from a URL"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        html = response.text
    
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one(table_selector) if table_selector else soup.find('table')
    
    if not table:
        raise ValueError("No table found on page")
    
    rows = []
    headers = []
    header_row = table.find('tr')
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
    
    for row in table.find_all('tr')[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
        if cells:
            rows.append(cells)
    
    df = pd.DataFrame(rows, columns=headers if headers else None)
    return df

def parse_pdf(pdf_bytes: bytes, page_num: Optional[int] = None) -> str:
    """Extract text from PDF"""
    try:
        from PyPDF2 import PdfReader
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        if page_num is not None:
            if page_num < 1 or page_num > len(reader.pages):
                return ""
            return reader.pages[page_num - 1].extract_text()
        else:
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except ImportError:
        logger.error("PyPDF2 not installed.")
        raise

def create_scatterplot(
    x_data: List[float],
    y_data: List[float],
    x_label: str = "X",
    y_label: str = "Y",
    title: str = "Scatterplot",
    regression_line: bool = False
) -> str:
    """
    Create a scatterplot using the Thread-Safe Object-Oriented Matplotlib API
    """
    # Create a new Figure object explicitly (Thread safe)
    fig = Figure(figsize=(10, 6))
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    
    ax.scatter(x_data, y_data, alpha=0.6)
    
    if regression_line:
        import numpy as np
        z = np.polyfit(x_data, y_data, 1)
        p = np.poly1d(z)
        ax.plot(x_data, p(x_data), "r--", linewidth=2, label=f'y={z[0]:.2f}x+{z[1]:.2f}')
        ax.legend()
    
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    
    # Save to buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    
    # Clean up explicitly
    # (Variables go out of scope, but good practice)
    del fig
    
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"

async def execute_llm_generated_code(code: str) -> Any:
    """
    Execute LLM-generated Python code.
    Includes strict timeouts and error capturing.
    """
    # 1. Safety check: Filter out obvious malicious imports
    # (Note: This is a basic filter. Production needs container sandboxing)
    forbidden = ['os.system', 'subprocess', 'shutil', 'sys.modules']
    for term in forbidden:
        if term in code:
            raise ValueError(f"Security Error: Generated code contains forbidden term '{term}'")

    # 2. Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # 3. Execute with timeout (20 seconds max)
        result = subprocess.run(
            ['python', temp_file],
            capture_output=True,
            text=True,
            timeout=20
        )
        
        if result.returncode == 0:
            # Success: Return stdout (trimmed)
            return result.stdout.strip()
        else:
            # Error: Return stderr
            err_msg = result.stderr.strip()
            logger.error(f"Code execution failed: {err_msg}")
            raise Exception(f"Execution Error: {err_msg}")
            
    except subprocess.TimeoutExpired:
        logger.error("Code execution timed out")
        raise Exception("Execution Timed Out (20s limit)")
    finally:
        # 4. Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)
