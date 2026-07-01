import io
import re
import requests
from pypdf import PdfReader

def get_lines_with_y(page):
    text_runs = []
    def visitor(text, cm, tm, fontDict, fontSize):
        if text.strip():
            text_runs.append((text, tm[4], tm[5]))
    page.extract_text(visitor_text=visitor)
    
    if not text_runs:
        return []
    
    # Sort text runs primarily by Y-coordinate descending (top to bottom)
    text_runs.sort(key=lambda x: x[2], reverse=True)
    
    lines = []
    current_y = None
    current_line_runs = []
    
    for text, x, y in text_runs:
        if current_y is None:
            current_y = y
            current_line_runs.append((text, x))
        elif abs(current_y - y) < 5:  # Tolerance of 5 points for the same line
            current_line_runs.append((text, x))
        else:
            current_line_runs.sort(key=lambda item: item[1])
            line_text = "".join(item[0] for item in current_line_runs)
            lines.append((line_text, current_y))
            
            current_y = y
            current_line_runs = [(text, x)]
            
    if current_line_runs:
        current_line_runs.sort(key=lambda item: item[1])
        line_text = "".join(item[0] for item in current_line_runs)
        lines.append((line_text, current_y))
        
    return lines

def test_extract_coordinates():
    url = "https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/0606_m22_qp_12.pdf"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://pastpapers.papacambridge.com/"
    }
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("Failed to download QP")
        return
        
    reader = PdfReader(io.BytesIO(res.content))
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        print(f"Page {page_num+1} size: {page.mediabox.width:.2f}x{page.mediabox.height:.2f}, mediabox: {page.mediabox}")

if __name__ == "__main__":
    test_extract_coordinates()

