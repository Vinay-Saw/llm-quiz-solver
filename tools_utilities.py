"""
Utility functions for data processing, scraping, and analysis
"""
import base64
import io
import json
import logging
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

logger = logging.getLogger(__name__)

async def download_file(url: str) -> bytes:
    """Download a file from URL"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

async def scrape_table(url: str, table_selector: Optional[str] = None) -> pd.DataFrame:
    """
    Scrape table data from a URL
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find table
    if table_selector:
        table = soup.select_one(table_selector)
    else:
        table = soup.find('table')
    
    if not table:
        raise ValueError("No table found on page")
    
    # Parse table into DataFrame
    rows = []
    headers = []
    
    # Get headers
    header_row = table.find('tr')
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
    
    # Get data rows
    for row in table.find_all('tr')[1:]:  # Skip header
        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
        if cells:
            rows.append(cells)
    
    df = pd.DataFrame(rows, columns=headers if headers else None)
    return df

def parse_pdf(pdf_bytes: bytes, page_num: Optional[int] = None) -> str:
    """
    Extract text from PDF
    Requires: pip install pypdf2
    """
    try:
        from PyPDF2 import PdfReader
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        if page_num is not None:
            # Extract specific page (1-indexed)
            page = reader.pages[page_num - 1]
            return page.extract_text()
        else:
            # Extract all pages
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except ImportError:
        logger.error("PyPDF2 not installed. Run: pip install pypdf2")
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
    Create a scatterplot and return as base64 data URI
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(x_data, y_data, alpha=0.6)
    
    if regression_line:
        # Add regression line
        import numpy as np
        z = np.polyfit(x_data, y_data, 1)
        p = np.poly1d(z)
        plt.plot(
            x_data,
            p(x_data),
            "r--",
            linewidth=2,
            label=f'y={z[0]:.2f}x+{z[1]:.2f}'
        )
        plt.legend()
    
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    # Convert to base64 data URI
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    data_uri = f"data:image/png;base64,{img_base64}"
    
    # Check size
    if len(data_uri) > 100000:
        logger.warning(f"Image size {len(data_uri)} exceeds 100KB limit")
    
    return data_uri

def analyze_data(df: pd.DataFrame, analysis_type: str, **kwargs) -> Any:
    """
    Perform various data analysis operations
    """
    if analysis_type == "sum":
        column = kwargs.get('column')
        return df[column].sum()
    
    elif analysis_type == "count":
        condition = kwargs.get('condition')
        if condition:
            return len(df[df.eval(condition)])
        return len(df)
    
    elif analysis_type == "correlation":
        col1 = kwargs.get('col1')
        col2 = kwargs.get('col2')
        return df[col1].corr(df[col2])
    
    elif analysis_type == "filter":
        condition = kwargs.get('condition')
        return df[df.eval(condition)]
    
    elif analysis_type == "earliest":
        column = kwargs.get('column')
        date_column = kwargs.get('date_column')
        df_sorted = df.sort_values(date_column)
        return df_sorted[column].iloc[0]
    
    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")

async def execute_llm_generated_code(code: str) -> Any:
    """
    Execute LLM-generated Python code safely
    WARNING: This is potentially unsafe. Use sandboxing in production.
    """
    import subprocess
    import tempfile
    import os
    
    # Write code to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Execute with timeout
        result = subprocess.run(
            ['python', temp_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            logger.error(f"Code execution failed: {result.stderr}")
            raise Exception(f"Execution error: {result.stderr}")
    finally:
        # Clean up
        os.unlink(temp_file)

def format_answer(answer: Any, expected_type: str) -> Any:
    """
    Format answer according to expected type
    """
    if expected_type == "number":
        return float(answer) if '.' in str(answer) else int(answer)
    elif expected_type == "string":
        return str(answer)
    elif expected_type == "boolean":
        return bool(answer)
    elif expected_type == "json":
        if isinstance(answer, str):
            return json.loads(answer)
        return answer
    elif expected_type == "array":
        if isinstance(answer, list):
            return answer
        return [answer]
    else:
        return answer