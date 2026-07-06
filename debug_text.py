"""
Debug script: show what text is extracted per question.
Usage: python3 debug_text.py <path_to_pdf>
"""
import sys, re
from pypdf import PdfReader

def _is_formula_page(page_num):
    return page_num == 1

def get_leftmost_candidates(page, page_num):
    text_runs = []
    def visitor(text, cm, tm, fontDict, fontSize):
        if text.strip():
            text_runs.append((text, tm[4], tm[5]))
    page.extract_text(visitor_text=visitor)
    if not text_runs:
        return []
    text_runs.sort(key=lambda x: x[2], reverse=True)
    grouped_lines = []
    current_y = None
    current_line = []
    for text, x, y in text_runs:
        if current_y is None:
            current_y = y
            current_line.append((text, x))
        elif abs(current_y - y) < 5:
            current_line.append((text, x))
        else:
            current_line.sort(key=lambda item: item[1])
            grouped_lines.append((current_line, current_y))
            current_y = y
            current_line = [(text, x)]
    if current_line:
        current_line.sort(key=lambda item: item[1])
        grouped_lines.append((current_line, current_y))
    candidates = []
    for line_runs, y in grouped_lines:
        if not line_runs:
            continue
        leftmost_text, leftmost_x = line_runs[0]
        match = re.match(r'^\s*(\d+)\s*(?:\([a-z]\)|[A-Z]|\b)', leftmost_text)
        if match and leftmost_x < 100:
            num = int(match.group(1))
            line_text = "".join(item[0] for item in line_runs)
            candidates.append({"num": num, "page": page_num, "y": y, "x": leftmost_x, "text": line_text})
    return candidates

path = sys.argv[1] if len(sys.argv) > 1 else None
if not path:
    print("Usage: python3 debug_text.py <path_to_pdf>")
    sys.exit(1)

reader = PdfReader(path)
skip_pages = {pn for pn in range(len(reader.pages)) if _is_formula_page(pn)}

all_candidates = []
for page_num in range(1, len(reader.pages)):
    if page_num in skip_pages:
        continue
    all_candidates.extend(get_leftmost_candidates(reader.pages[page_num], page_num))
all_candidates.sort(key=lambda c: (c["page"], -c["y"]))

validated = {}
last_val = 0
for i, candidate in enumerate(all_candidates):
    num = candidate["num"]
    if num > last_val and num <= last_val + 2:
        has_next = any(nc["num"] in (num+1, num+2) for nc in all_candidates[i+1:])
        if has_next or not any(c["num"] > num for c in all_candidates[i+1:]):
            validated[num] = candidate
            last_val = num

nums = sorted(validated.keys())
print(f"\n=== Found {len(nums)} questions ===")
for idx, num in enumerate(nums):
    d = validated[num]
    end_page = len(reader.pages) - 1
    if idx < len(nums) - 1:
        nd = validated[nums[idx+1]]
        if nd["y"] > 650:
            end_page = nd["page"] - 1
        else:
            end_page = nd["page"]
    
    combined = ""
    for p in range(d["page"], end_page + 1):
        if p in skip_pages:
            continue
        t = reader.pages[p].extract_text()
        if t:
            combined += t + "\n"
    
    print(f"\n--- Q{num} (pages {d['page']}-{end_page}, start_y={d['y']:.1f}) ---")
    print(repr(combined[:400]))
