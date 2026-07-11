import streamlit as st
import requests
import io
import time
import re
import json
import os
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURATION ---
CONFIG_FILE = "user_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

SUBJECT_MAPPING = {
    "Biology": "0610",
    "Physics": "0625",
    "Chemistry": "0620",
    "Additional Mathematics": "0606",
    "Extended Mathematics": "0580",
    "Design and Technology": "0445",
    "Economics": "0455",
    "Accounting": "0452"
}

MATH_0606_TOPICS = {
    "Calculus (Differentiation & Integration)": [
        r'd\s*\.\s*x', r'd\s*y\s*/\s*d\s*x', r'd\s*x\s*/\s*d\s*t',
        r'd\s*\^\s*2\s*y\s*/\s*d\s*x\s*\^\s*2',
        r'∫', r'\bintegrat', r'\bdifferentiat', r'\bderived\b',
        r'rate\s+of\s+change', r'stationary\s+point', r'turning\s+point', r'tangent', r'normal'
    ],
    "Logarithmic & Exponential Functions": [
        r'\bln\b', r'\blog\b', r'e\s*\^\s*x',
        r'log\s*_\s*\d+', r'log\s*[a-zA-Z]',
        r'exponential'
    ],
    "Circular Measure": [
        r'radian', r'arc\s+length', r'sector', r'subtends', r'\brad\b',
        r'perimeter\s+of\s+the\s+shaded', r'area\s+of\s+the\s+shaded',
        r'θ', r'\bπ\b'
    ],
    "Trigonometry": [
        r'\bsin\b', r'\bcos\b', r'\btan\b', r'\bsec\b', r'\bcsc\b', r'\bcot\b',
        r'sin\s*\^\s*2', r'cos\s*\^\s*2', r'tan\s*\^\s*2',
        r'trigonometric\s+ratio', r'trigonometric\s+equation', r'identity', r'identities',
        r'amplitude', r'period', r'°'
    ],
    "Permutations, Combinations & Series": [
        r'\bprogression', r'\bseries\b', r'\bbinomial', r'\bpermutation', r'\bcombination',
        r'common\s+difference', r'common\s+ratio', r'sum\s+to\s+infinity',
        r'[nN]\s*[cC]\s*[rR]', r'[nN]\s*[pP]\s*[rR]'
    ],
    "Functions & Quadratics": [
        r'f\s*\(\s*x\s*\)', r'g\s*\(\s*x\s*\)', r'f\s*-\s*1',
        r'domain', r'range', r'modulus', r'discriminant', r'nature\s+of\s+the\s+roots',
        r'factor\s+theorem', r'remainder\s+theorem'
    ],
    "Coordinate Geometry & Vectors": [
        r'perpendicular', r'parallel', r'midpoint', r'intersect',
        r'position\s+vector', r'magnitude', r'velocity', r'collinear',
        r'\b[A-Z]{2}\b'
    ]
}

BASE_URL = "https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pastpapers.papacambridge.com/"
}

# --- HELPER FUNCTIONS ---
def generate_cover_page(student_name, subject_name, years, components, series_list, mode="Full Booklet", keyword=""):
    """Generates a cover page PDF in-memory using reportlab."""
    packet = io.BytesIO()
    # A4 to match the source question pages (letter caused mismatched page size)
    can = canvas.Canvas(packet, pagesize=A4)
    
    can.setFont("Helvetica-Bold", 24)
    if mode == "Topical":
        can.drawCentredString(298, 760, f"Topical Question Bank: {keyword.title()}")
    else:
        can.drawCentredString(298, 760, "IGCSE Past Paper Booklet")
    
    can.setFont("Helvetica", 16)
    can.drawCentredString(298, 710, f"Subject: {subject_name} ({SUBJECT_MAPPING[subject_name]})")
    
    can.setFont("Helvetica-Oblique", 14)
    if student_name:
        if mode == "Topical":
            can.drawCentredString(298, 660, f"{student_name}'s Custom Topic Booklet: {keyword}")
        else:
            can.drawCentredString(298, 660, f"Prepared for: {student_name}")
        
    can.setFont("Helvetica", 12)
    can.drawString(100, 560, "Booklet Details:")
    can.drawString(120, 540, f"- Years: {years[0]} to {years[1]}")
    can.drawString(120, 520, f"- Component (Paper): {components}")
    
    series_map = {"m": "Feb/March", "s": "May/June", "w": "Oct/Nov"}
    series_str = ", ".join([series_map.get(s, s) for s in series_list])
    can.drawString(120, 500, f"- Exam Series: {series_str}")
    
    can.save()
    packet.seek(0)
    return packet

def generate_index_page(successful_papers, subject_code):
    """Generates an index page with hyperlinks to Mark Schemes."""
    packet = io.BytesIO()
    # A4 to match the source question pages
    can = canvas.Canvas(packet, pagesize=A4)
    
    can.setFont("Helvetica-Bold", 18)
    can.drawString(100, 790, "Topical Index - Source Papers & Mark Schemes")
    
    can.setFont("Helvetica", 12)
    y_position = 750
    can.drawString(100, y_position, "Click a paper below to view its official Mark Scheme online:")
    y_position -= 30
    
    for paper in successful_papers:
        year, series, comp_var = paper
        year_short = str(year)[-2:]
        # ms format: {subject_code}_{series}{year_short}_ms_{comp_var}.pdf
        filename = f"{subject_code}_{series}{year_short}_ms_{comp_var}.pdf"
        url = f"{BASE_URL}{filename}"
        
        display_text = f"• {series.upper()} {year} - Paper {comp_var}"
        
        can.setFillColorRGB(0, 0, 1)
        can.drawString(120, y_position, display_text)
        can.linkURL(url, (120, y_position - 2, 400, y_position + 10), relative=1)
        
        y_position -= 20
        if y_position < 50:
            can.showPage()
            y_position = 750
            
    can.save()
    packet.seek(0)
    return packet

def _is_mcq_paper(subject_code, comp_var):
    """Returns True if the paper is a multiple-choice question (MCQ) paper in designated scope."""
    if not subject_code or not comp_var:
        return False
    # Sciences: 0625, 0620, 0610 for Paper 1 & 2
    if subject_code in ("0625", "0620", "0610") and (comp_var.startswith("1") or comp_var.startswith("2")):
        return True
    # Economics (0455), Accounting (0452) for Paper 1
    if subject_code in ("0455", "0452") and comp_var.startswith("1"):
        return True
    return False

def _is_formula_page(reader, page_num, subject_code=None, comp_var=None):
    """Returns True if the page is a front-matter formula sheet or Periodic Table to be skipped."""
    # Hard skip page 2 of the raw PDF (index 1)
    if page_num == 1:
        return True
        
    if subject_code == "0620" and comp_var and comp_var.startswith("4"):
        page = reader.pages[page_num]
        text = page.extract_text().lower()
        # Skip any Chemistry Paper 4 page that contains BOTH the Periodic Table
        # and the mole-volume line.
        if ("the periodic table of elements" in text
                and "the volume of one mole of any gas is 24 dm3" in text):
            return True
            
    return False

def extract_words_with_y(page):
    """Extracts words with their associated Y-coordinates from a PDF page."""
    runs = []
    def visitor(text, cm, tm, fontDict, fontSize):
        if text.strip():
            runs.append((text, tm[4], tm[5]))
    page.extract_text(visitor_text=visitor)
    
    if not runs:
        return []
        
    # Group runs by approximate Y-coordinate descending (top of page to bottom)
    runs.sort(key=lambda x: x[2], reverse=True)
    grouped_lines = []
    current_y = None
    current_line = []
    
    for text, x, y in runs:
        if current_y is None:
            current_y = y
            current_line.append((text, x, y))
        elif abs(current_y - y) < 5:
            current_line.append((text, x, y))
        else:
            current_line.sort(key=lambda item: item[1])
            grouped_lines.extend(current_line)
            current_y = y
            current_line = [(text, x, y)]
    if current_line:
        current_line.sort(key=lambda item: item[1])
        grouped_lines.extend(current_line)
    
    words = []
    for text, x, y in grouped_lines:
        for word in text.split():
            clean = re.sub(r'\W+', '', word.lower())
            if clean:
                words.append((clean, y))
    return words

def detect_text_overlap(page_n, page_n_plus_1):
    """
    Detects if the text at the bottom of page_n is duplicated at the top of page_n_plus_1.
    Looks for an exact match of a 5-word sequence.
    Returns the Y-coordinate on page_n_plus_1 below which the text is NOT duplicated, or None.
    """
    words_n = extract_words_with_y(page_n)
    words_next = extract_words_with_y(page_n_plus_1)
    
    if len(words_n) < 3 or len(words_next) < 3:
        return None
        
    search_space_n = words_n[-100:]
    search_space_next = words_next[:100]
    
    if len(search_space_n) < 3 or len(search_space_next) < 3:
        return None
        
    for i in range(len(search_space_n) - 2):
        seq_n = [w[0] for w in search_space_n[i:i+3]]
        for j in range(len(search_space_next) - 2):
            seq_next = [w[0] for w in search_space_next[j:j+3]]
            if seq_n == seq_next:
                # Match found. Find the lowest Y coordinate among the matched words.
                # Subtracting 10 as a small buffer to ensure the duplicate text is fully removed.
                min_y = min(w[1] for w in search_space_next[j:j+3])
                return min_y - 10
                
    return None

def get_leftmost_candidates(page, page_num):
    """Finds all candidate numbers that appear at the leftmost edge of text runs on a page."""
    text_runs = []
    def visitor(text, cm, tm, fontDict, fontSize):
        if text.strip():
            text_runs.append((text, tm[4], tm[5]))
    page.extract_text(visitor_text=visitor)
    
    if not text_runs:
        return []
        
    # Group runs by approximate Y-coordinate descending (top of page to bottom)
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
        # The leftmost run of the line
        leftmost_text, leftmost_x = line_runs[0]
        
        # Spatial Left-Edge Validation Pattern
        match = re.match(r'^\s*(\d+)\s*(?:\([a-z]\)|[A-Z]|\b)', leftmost_text)
        if match:
            # Reject junk runs: barcodes / leftover text runs with reset transforms
            # sit at x < 25 (e.g. x≈21.8 barcode, x=0.0 fragments), and anything
            # far from the left margin (x > 250) is body content, not a Q number.
            if 25 <= leftmost_x <= 250:
                num = int(match.group(1))
                line_text = "".join(item[0] for item in line_runs)
                candidates.append({
                    "num": num,
                    "page": page_num,
                    "y": y,
                    "x": leftmost_x,
                    "text": line_text
                })
    return candidates

def parse_question_boundaries(reader, subject_code=None, comp_var=None):
    """Parses PDF pages to find structural question boundaries."""
    questions = {}
    
    # Build set of skippable formula pages
    skip_pages = set()
    for page_num in range(len(reader.pages)):
        if _is_formula_page(reader, page_num, subject_code, comp_var):
            skip_pages.add(page_num)
            
    # Pass 1: Extract all leftmost candidates
    all_candidates = []
    for page_num in range(1, len(reader.pages)):
        if page_num in skip_pages:
            continue
        all_candidates.extend(get_leftmost_candidates(reader.pages[page_num], page_num))
        
    # ── MCQ BRANCH (coordinate method) ───────────────────────────────────────
    # Only for: 0625/0620/0610 paper 1&2  AND  0455/0452 paper 1
    if _is_mcq_paper(subject_code, comp_var):
        #
        # METHOD (user-specified):
        # 1. Collect EVERY number in the LEFT HALF of each page, recording its
        #    (x, y) coordinate on that page (many numbers per page allowed).
        # 2. Find which x values cluster together (± tolerance) = the question
        #    column, and keep numbers lying on that line.
        # 3. Walk those numbers in DOCUMENT ORDER and follow the consecutive run
        #    1,2,3,... starting from 1 (stray bubble digits are skipped, not
        #    treated as breaks) — this keeps Q1..Q40 contiguous.
        # 4. For question N: start = y(N) + S, end = y(N+1) + S.
        #
        candidates = []
        for p_num in range(1, len(reader.pages)):
            if p_num in skip_pages:
                continue
            page = reader.pages[p_num]
            width = float(page.mediabox.right) if page.mediabox else 595.0
            limit_x = width / 2.0
            runs = []
            def visitor(text, cm, tm, fontDict, fontSize):
                if text.strip():
                    runs.append((text.strip(), tm[4], tm[5]))
            page.extract_text(visitor_text=visitor)
            for text, x0, y0 in runs:
                first_word = text.split()[0] if text.split() else ""
                if first_word.isdigit() and 0 < int(first_word) <= 60 and x0 < limit_x:
                    # ONLY pure standalone digits — no (a), no 6A, no letters
                    if not re.match(r'^\d+\s*$', first_word):
                        continue
                    # Guard: if the full run text is much longer than the marker
                    # itself, this is likely a sentence continuation,
                    # not a printed question number on the left margin.
                    if len(text.strip()) > len(first_word) + 2:
                        continue
                    candidates.append({
                        "num": int(first_word),
                        "page": p_num,
                        "x": x0,
                        "y": y0,
                        "text": text
                    })

        if not candidates:
            return {}

        # Step 2: FIRMLY stick to x ∈ [47, 50] (±1 tolerance for sub-pixel noise).
        # Anything outside this hard window is NOT the question-number column.
        X_MIN = 47
        X_MAX = 50
        column_candidates = [
            c for c in candidates
            if X_MIN - 1 <= c["x"] <= X_MAX + 1
        ]
        # If the hard range somehow yields nothing, fall back to cluster method.
        if not column_candidates:
            X_TOL = 12
            x_groups = {}
            for c in candidates:
                matched = False
                for gx in x_groups:
                    if abs(gx - c["x"]) <= X_TOL:
                        x_groups[gx].append(c)
                        matched = True
                        break
                if not matched:
                    x_groups[c["x"]] = [c]
            column_candidates = max(x_groups.values(), key=len) if x_groups else []

        # Step 3: Build strict consecutive ascending chain, removing outliers
        # like 8 in 1,2,3,8,4,5,6,7 and filtering out any letter entries.
        column_candidates.sort(key=lambda c: (c["page"], -c["y"]))

        # Deduplicate: keep only the first occurrence of each number in doc order
        seen = set()
        deduped = []
        for c in column_candidates:
            if c["num"] not in seen:
                deduped.append(c)
                seen.add(c["num"])

        # Walk the sequence and skip isolated outliers that break consecutiveness.
        # Example: 1,2,3,8,4,5,6,7 → skip the 8, keep 1,2,3,4,5,6,7
        chain = []
        i = 0
        while i < len(deduped):
            c = deduped[i]
            if not chain:
                chain.append(c)
                i += 1
                continue

            expected = chain[-1]["num"] + 1
            if c["num"] == expected:
                chain.append(c)
                i += 1
            elif c["num"] > expected:
                # Is this an isolated outlier? Peek ahead: if the very next
                # candidate is the expected number, skip this outlier.
                if i + 1 < len(deduped) and deduped[i + 1]["num"] == expected:
                    i += 1  # skip the outlier
                else:
                    break  # genuine sequence break
            else:
                # c["num"] < expected: duplicate / out-of-order — skip
                i += 1

        # Fallback: if chain is too short, find the longest consecutive run
        if len(chain) < 5:
            num_to_cand = {c["num"]: c for c in deduped}
            best = []
            for start_c in deduped:
                cur = []
                val = start_c["num"]
                while val in num_to_cand:
                    cur.append(num_to_cand[val])
                    val += 1
                if len(cur) > len(best):
                    best = cur
            if len(best) > len(chain):
                chain = best

        if not chain:
            return {}

        # Build the validated question list from the chain (ordered by doc flow).
        validated_questions = {}
        for c in chain:
            validated_questions[c["num"]] = {
                "start_page": c["page"],
                "start_y": c["y"],
                "text_line": c["text"]
            }

    # ── THEORY BRANCH (Paper 4, etc.) ─────────────────────────────────────────
    else:
        # Pass 1: Extract all leftmost candidates
        all_candidates = []
        for page_num in range(1, len(reader.pages)):
            if page_num in skip_pages:
                continue
            all_candidates.extend(get_leftmost_candidates(reader.pages[page_num], page_num))

        # Pass 1b: Lock onto the question-number left margin for THIS paper.
        # Every real question number is printed on the same vertical line (same X).
        # False positives (graph axis labels, sub-part indents, stray fragments)
        # sit at other X values. Find the dominant left-margin X (the mode of the
        # left-region candidate X's) and keep only numbers that land on that line.
        from collections import Counter
        if subject_code == "0606":
            left_region = all_candidates
        else:
            left_region = [c for c in all_candidates if c["x"] < 90]

        if left_region:
            # Round to nearest point so tiny sub-pixel differences group together
            margin_x = Counter(round(c["x"]) for c in left_region).most_common(1)[0][0]
            MARGIN_TOL = 6  # points of horizontal wiggle room
            all_candidates = [
                c for c in all_candidates
                if abs(c["x"] - margin_x) <= MARGIN_TOL
            ]

        # Sort candidates chronologically (by page, then by Y coordinate descending)
        all_candidates.sort(key=lambda c: (c["page"], -c["y"]))

        # Pass 2: Sequence verification (chronological 1, 2, 3, ...) with self-healing lookahead
        validated_questions = {}
        last_val = 0

        for i, candidate in enumerate(all_candidates):
            num = candidate["num"]
            # The candidate number must be greater than the last validated question, and not unreasonably large
            if num > last_val and num <= last_val + 3:
                # Lookahead: is there a num + 1, num + 2, or num + 3 later?
                has_next = False
                for next_cand in all_candidates[i+1:]:
                    if next_cand["num"] in (num + 1, num + 2, num + 3):
                        has_next = True
                        break

                # Accept if there's a sequence link ahead, or if this is the last question in the booklet
                if has_next or not any(c["num"] > num for c in all_candidates[i+1:]):
                    validated_questions[num] = {
                        "start_page": candidate["page"],
                        "start_y": candidate["y"],
                        "text_line": candidate["text"]
                    }
                    last_val = num

    # ── SHARED: assign page/Y boundaries ───────────────────────────────────────
    nums = sorted(validated_questions.keys())
    for idx, num in enumerate(nums):
        data = validated_questions[num]

        # Default end page is the end of the booklet, but backtrack past any
        # skip pages (e.g. a periodic table at the very end) so the last
        # question never swallows a skipped page.
        end_p = len(reader.pages) - 1
        while end_p in skip_pages and end_p > data["start_page"]:
            end_p -= 1

        # MCQ papers end with a separate answer grid (pages whose only detected
        # "numbers" are 1, 2, ...). Because MCQ questions are page-bounded, the
        # final question must NOT extend to the booklet's last page — otherwise
        # it would swallow that answer grid.
        if _is_mcq_paper(subject_code, comp_var) and idx == len(nums) - 1 and idx > 0:
            prev_end = questions[nums[idx - 1]]["end_page"]
            if prev_end >= data["start_page"]:
                end_p = prev_end
            # else: last question starts after prev question's end; keep default

        questions[num] = {
            "start_page": data["start_page"],
            "start_y": data["start_y"],
            "end_page": end_p,
            "end_y": None
        }

        if idx < len(nums) - 1:
            next_num = nums[idx + 1]
            next_data = validated_questions[next_num]
            next_page = next_data["start_page"]

            if _is_mcq_paper(subject_code, comp_var):
                # Single-column MCQ papers: each question lives on its own page
                # (or, when two share a page, the current one ENDS at the next
                # question's top). If the next question starts on a different
                # page, snap the boundary to the PAGE EDGE — do NOT crop at the
                # next question's top, or the crop at y≈769 would wipe the whole
                # page. Only crop mid-page when both questions share one page.
                if next_data["start_page"] == data["start_page"]:
                    questions[num]["end_page"] = next_page
                    questions[num]["end_y"] = next_data["start_y"]
                else:
                    prev_page = next_page - 1
                    while prev_page in skip_pages and prev_page > 0:
                        prev_page -= 1
                    questions[num]["end_page"] = prev_page
                    questions[num]["end_y"] = None
            else:
                # Theory papers: If the next question starts on the same page,
                # crop just above it. If on a different page, we can't reliably
                # use its y-value as an end boundary (it belongs to a different
                # page), so end at the bottom of the last non-skip page before
                # the next question.
                if next_page == data["start_page"]:
                    questions[num]["end_page"] = next_page
                    questions[num]["end_y"] = next_data["start_y"]
                else:
                    end_p = next_page - 1
                    while end_p in skip_pages and end_p > data["start_page"]:
                        end_p -= 1
                    questions[num]["end_page"] = end_p
                    questions[num]["end_y"] = None
    # Extract text content for each question bounded range
    for q_num, data in questions.items():
        combined_text = ""
        for p in range(data["start_page"], data["end_page"] + 1):
            if p in skip_pages:
                continue
            page_text = reader.pages[p].extract_text()
            if page_text:
                combined_text += page_text + "\n"
        data["text"] = combined_text
        
    return questions

def create_page_overlay(subject_code, year, series, comp_var, q_num, orig_width, orig_height, diagnostic_info=None, draw_banner=False, banner_y=None, draw_red_line_at=None, draw_green_line=False, draw_green_line_at=None):
    """Generates a text banner overlay and separation lines for extracted pages."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(orig_width, orig_height))
    
    # If banner_y is not custom, default to standard top (orig_height - 35)
    if banner_y is None:
        banner_y = orig_height - 35
        
    if draw_banner:
        year_short = str(year)[-2:]
        text = f"Source: {subject_code} / {series}{year_short} / qp_{comp_var} — Question {q_num}"
        
        # Erase original header / page numbers above the banner only.
        # Do NOT extend below the banner, or it will wipe question content
        # that starts just under the banner strip.
        can.setFillColorRGB(1, 1, 1)
        can.rect(0, banner_y + 25, orig_width, orig_height - (banner_y + 25), fill=1, stroke=0)
        
        can.setFillColorRGB(1, 1, 1)
        if diagnostic_info and st.session_state.get('diagnostic_mode', False):
            can.rect(40, banner_y - 20, orig_width - 80, 45, fill=1, stroke=1)
            can.setFillColorRGB(0, 0, 0)
            can.setFont("Helvetica-Bold", 12)
            can.drawString(50, banner_y + 8, text)
            can.setFillColorRGB(0.8, 0, 0) # Red for diagnostic
            can.setFont("Helvetica", 9)
            can.drawString(50, banner_y - 12, diagnostic_info)
        else:
            can.rect(40, banner_y, orig_width - 80, 25, fill=1, stroke=1)
            can.setFillColorRGB(0, 0, 0)
            can.setFont("Helvetica-Bold", 12)
            can.drawString(50, banner_y + 8, text)
            
    # Draw separation lines if enabled
    if st.session_state.get('render_boundary_lines', False):
        if draw_red_line_at is not None:
            can.setStrokeColorRGB(1, 0, 0) # Bright Red
            can.setLineWidth(4)
            # Offset slightly to be between lines
            can.line(0, draw_red_line_at + 5, orig_width, draw_red_line_at + 5)
        elif draw_green_line:
            can.setStrokeColorRGB(0, 0.8, 0) # Bright Green
            can.setLineWidth(4)
            if draw_green_line_at is not None:
                can.line(0, draw_green_line_at, orig_width, draw_green_line_at)
            else:
                # Draw at Y=45 (above footer margin)
                can.line(0, 45, orig_width, 45)
        
    can.save()
    packet.seek(0)
    return packet

def fetch_paper(subject_code, year, series, component_variant):
    """Fetches a single paper from PapaCambridge."""
    # Target format: {subject_code}_{session}{year_short}_qp_{component_variant}.pdf
    year_short = str(year)[-2:]
    filename = f"{subject_code}_{series}{year_short}_qp_{component_variant}.pdf"
    
    url = f"{BASE_URL}{filename}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            if response.headers.get('Content-Type') == 'application/pdf' or response.content.startswith(b'%PDF'):
                return response.content
        return None
    except Exception as e:
        return None

# --- STREAMLIT UI ---
st.set_page_config(page_title="IGCSE Paper Generator", layout="wide")

# Kilo-AI landing-page aesthetic: matte black canvas, brand nav header, massive
# hero title, terminal-line inputs, neon lime CTA. No cards, no heavy boxes.
KILO_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --bg:        #0E0E10;
    --surface:   #16161A;
    --line:      #27272A;
    --text:      #A1A1AA;
    --text-hi:   #FFFFFF;
    --label:     #52525B;   /* field labels + secondary indicators (muted slate) */
    --dim:       #71717A;   /* terminal note text */
    --accent:    #EAFF53;
}

/* ---- Global typography: JetBrains Mono everywhere ---- */
html, body, [class*="css"], .stApp, input, textarea, select, button,
p, div, span, label, h1, h2, h3, h4, li {
    font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, monospace !important;
}

/* ---- Canvas ---- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }

.block-container {
    max-width: 1040px;
    margin: 0 auto !important;
    padding-top: 1.25rem;
    padding-bottom: 6rem;
    padding-left: 2.5rem;
    padding-right: 2.5rem;
    position: relative !important;
}

/* generous, even gutters between grid columns */
[data-testid="stHorizontalBlock"] { gap: 2.5rem !important; }
[data-testid="stHorizontalBlock"] > [data-testid="column"] { padding: 0 !important; }

/* ============ BRAND NAV HEADER ============ */
.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.25rem 0 2.5rem 0;
}
.nav-left { display: flex; align-items: center; gap: 0.85rem; }
.logo-box {
    display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px;
    background: var(--text-hi);
    color: #0E0E10;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 800; font-size: 14px;
    border-radius: 8px;
    letter-spacing: -0.5px;
}
.nav-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; color: var(--label);
    border: 1px solid var(--line);
    padding: 4px 10px; border-radius: 999px;
}
.nav-doc {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; color: var(--text) !important;
    text-decoration: none !important; letter-spacing: 0.3px;
    transition: color .15s ease;
}
.nav-doc:hover { color: var(--text-hi) !important; }

/* Customise Popover Button */
[data-testid="stPopover"] {
    position: absolute !important;
    top: 1.45rem !important;
    right: 2.5rem !important;
    z-index: 999999;
}
[data-testid="stPopover"] > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important; color: var(--text) !important;
    letter-spacing: 0.3px !important;
    padding: 0 !important;
    height: auto !important;
    min-height: 0 !important;
}
[data-testid="stPopover"] > button:hover {
    color: var(--text-hi) !important;
    background: transparent !important;
}
[data-testid="stPopover"] > button p { color: inherit !important; }
[data-testid="stPopover"] > button svg { display: none !important; }

/* ============ HERO ============ */
/* Force monospace + inline colors on the raw-HTML title (Streamlit tries to
   override h1/span fonts and colors inside markdown containers). */
div[data-testid="stMarkdownContainer"] h1,
div[data-testid="stMarkdownContainer"] span {
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
}
/* Hide Streamlit's auto-injected heading anchor link icons */
[data-testid="stMarkdownContainer"] h1 a,
[data-testid="stMarkdownContainer"] h2 a,
[data-testid="stMarkdownContainer"] h3 a,
[data-testid="stHeaderActionElements"] { display: none !important; }
.hero { text-align: center; margin: 1.5rem 0 3rem 0; }
.hero-title {
    font-family: 'Inter', sans-serif !important;
    font-size: 3.7rem !important;
    line-height: 1.05 !important;
    font-weight: 800 !important;
    color: var(--text-hi) !important;
    letter-spacing: -2px !important;
    margin: 0 auto 1.4rem auto !important;
    max-width: 15ch;
}
.hero-sub {
    font-size: 1.05rem !important;
    color: var(--label) !important;
    max-width: 46ch;
    margin: 0 auto !important;
    line-height: 1.6 !important;
    font-weight: 400 !important;
}

/* ============ LABELS (small, uppercase, tracked, muted) ============ */
[data-testid="stWidgetLabel"] p,
.stRadio > label, .stMultiSelect label, .stCheckbox label, .stToggle label,
[data-testid="stWidgetLabel"] label {
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    color: var(--label) !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* section subheaders -> small uppercase dividers */
h2, h3 {
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    color: var(--label) !important;
    font-family: 'JetBrains Mono', monospace !important;
    margin-top: 1.5rem !important;
}

/* ============ TERMINAL-LINE INPUTS ============ */
/* text inputs */
.stTextInput [data-baseweb="input"],
.stTextInput [data-baseweb="base-input"],
.stTextInput > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}
.stTextInput > div > div {
    border-bottom: 1px solid var(--line) !important;
    transition: border-color .15s ease;
}
.stTextInput > div > div:focus-within { border-bottom-color: var(--text-hi) !important; }
.stTextInput input {
    background: transparent !important;
    color: var(--text-hi) !important;
    border: none !important;
    padding-left: 2px !important;
}
input::placeholder, textarea::placeholder { color: #52525B !important; }

/* selectbox + multiselect */
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid var(--line) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    transition: border-color .15s ease;
    color: var(--text-hi) !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    min-height: 40px !important;
}
/* flush the selected value text to the left margin (kill baseweb inner padding) */
.stSelectbox [data-baseweb="select"] [data-baseweb="select-value"],
.stSelectbox [data-baseweb="select"] > div > div:first-child,
.stMultiSelect [data-baseweb="select"] > div > div:first-child {
    padding-left: 0 !important;
    margin-left: 0 !important;
}
.stSelectbox [data-baseweb="select"] > div:focus-within,
.stMultiSelect [data-baseweb="select"] > div:focus-within {
    border-bottom-color: var(--text-hi) !important;
}
.stSelectbox svg, .stMultiSelect svg { fill: var(--label) !important; }
.stSelectbox input, .stMultiSelect input { color: var(--text-hi) !important; }

/* dropdown popover */
[data-baseweb="popover"] ul, [data-baseweb="menu"] {
    background-color: #16161a !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
}
[data-baseweb="menu"] li { color: var(--text) !important; }
[data-baseweb="menu"] li:hover, [data-baseweb="menu"] li[aria-selected="true"] {
    color: #0E0E10 !important; background-color: var(--accent) !important;
}

/* multiselect tags -> flat dark rectangles in a crisp horizontal row */
.stMultiSelect [data-baseweb="select"] > div > div:first-child {
    display: flex !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 6px !important;
    overflow-x: auto !important;
}
[data-baseweb="tag"] {
    background-color: #121214 !important;
    color: var(--accent) !important;
    border: 1px solid #242427 !important;
    border-radius: 3px !important;
    font-weight: 500 !important;
    font-size: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
    white-space: nowrap !important;
    flex: 0 0 auto !important;
    margin: 2px 0 !important;
}
[data-baseweb="tag"]::before {
    content: "";
    display: inline-block;
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--accent);
    margin: 0 6px 1px 2px;
    flex: 0 0 auto;
}
[data-baseweb="tag"] svg { fill: var(--accent) !important; }
[data-baseweb="tag"] [role="button"]:hover { background: transparent !important; }

/* ============ RADIO (active -> accent) ============ */
[data-testid="stRadio"] > div { display: flex; gap: 1.75rem; flex-wrap: wrap; }
.stRadio div[role="radiogroup"] label span { color: var(--text) !important; }
[data-baseweb="radio"] div[aria-checked="true"] { border-color: var(--accent) !important; }
[data-baseweb="radio"] div[aria-checked="true"] > div { background-color: var(--accent) !important; }

/* ============ TOGGLE (small low-profile pills) ============ */
[data-testid="stToggle"] button[role="switch"],
label[data-baseweb="checkbox"] > div:first-child,
button[role="switch"] {
    transform: scale(0.78);
    transform-origin: left center;
}
button[role="switch"][aria-checked="false"] { background-color: var(--surface) !important; }
button[role="switch"][aria-checked="true"]  { background-color: var(--accent) !important; }
button[role="switch"][aria-checked="false"] > div { background-color: var(--label) !important; }
button[role="switch"][aria-checked="true"]  > div { background-color: #0E0E10 !important; }
button[role="switch"] { border: none !important; box-shadow: none !important; }

/* utility toggle block: tight top-left cluster */
.util-toggles { margin-top: -0.5rem; }
.util-toggles [data-testid="stToggle"] { margin-bottom: -0.4rem; }

/* ============ SLIDER ============ */
/* thumbs */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background-color: var(--accent) !important;
    box-shadow: none !important;
    border: none !important;
}
/* value bubble above the thumb -> transparent bg, muted accent text */
[data-testid="stSlider"] [data-testid="stThumbValue"] {
    background: transparent !important;
    color: var(--accent) !important;
    box-shadow: none !important;
    font-family: 'JetBrains Mono', monospace !important;
}
/* min / max tick labels -> completely transparent bg (kills the yellow box) */
[data-testid="stTickBar"] { background: transparent !important; }
[data-testid="stTickBar"] *,
[data-testid="stTickBarMin"], [data-testid="stTickBarMax"] {
    background: transparent !important;
    color: var(--label) !important;
    box-shadow: none !important;
    font-family: 'JetBrains Mono', monospace !important;
}
/* base track = thin slate line */
[data-testid="stSlider"] [data-baseweb="slider"] > div > div {
    background: var(--line) !important;
    height: 2px !important;
}
/* active selected range = glowing 2px lime line */
[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div {
    background: var(--accent) !important;
    height: 2px !important;
    box-shadow: 0 0 6px rgba(234,255,83,0.5) !important;
}

/* ============ KILO CTA BUTTON ============ */
.stFormSubmitButton > button,
.stDownloadButton > button {
    width: 100% !important;
    background-color: var(--accent) !important;
    color: #0E0E10 !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    padding: 1.1rem 1.5rem !important;
    margin-top: 1.75rem;
    cursor: pointer !important;
    transition: transform .12s ease, filter .15s ease !important;
}
.stFormSubmitButton > button:hover,
.stDownloadButton > button:hover {
    transform: scale(1.005);
    filter: brightness(1.06);
    color: #0E0E10 !important;
    border: none !important;
    cursor: pointer !important;
}
.stFormSubmitButton > button:active,
.stDownloadButton > button:active { transform: scale(0.99); }

/* secondary (non-CTA) buttons stay subtle */
.stButton > button {
    background: transparent !important;
    color: var(--text) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
}
.stButton > button:hover { color: var(--text-hi) !important; border-color: var(--text-hi) !important; }

/* ============ ALERTS -> terminal note blocks ============ */
[data-testid="stAlert"], [data-baseweb="alert"] {
    background-color: transparent !important;
    border: none !important;
    border-left: 2px solid var(--line) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding-left: 1.1rem !important;
}
[data-testid="stAlert"] * { color: var(--dim) !important; font-size: 13px; letter-spacing: 0.04em; }
/* note text: dim, tracked, readable; flush to the column's left margin */
[data-testid="stAlert"], [data-baseweb="alert"] { margin-left: 0 !important; }
/* Cambridge rules / info note -> lime left bar, dim text */
[data-baseweb="alert"][kind="info"] { border-left: 2px solid var(--accent) !important; }
[data-baseweb="alert"][kind="info"] * { color: var(--dim) !important; }
[data-baseweb="alert"][kind="error"] { border-left: 2px solid #ff6b6b !important; }
[data-baseweb="alert"][kind="error"] *, [data-baseweb="alert"][kind="negative"] * { color: #ff6b6b !important; }
[data-baseweb="alert"][kind="success"] { border-left: 2px solid var(--accent) !important; }
[data-baseweb="alert"][kind="success"] *, [data-baseweb="alert"][kind="positive"] * { color: var(--accent) !important; }
/* dim the default alert icons */
[data-baseweb="alert"] svg { fill: var(--dim) !important; }

/* forms & expanders: fully seamless, no card/border/panel */
[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 1rem 0 0 0 !important;
    box-shadow: none !important;
}
.streamlit-expanderHeader, .stExpander header, [data-testid="stExpander"] summary {
    background: transparent !important; color: var(--text) !important;
    border: 1px solid var(--line) !important; border-radius: 8px !important;
}
[data-testid="stExpander"] { border: none !important; }

/* progress + spinner */
[data-testid="stProgress"] > div > div { background-color: var(--accent) !important; }
[data-testid="stProgress"] > div { background-color: var(--line) !important; }
[data-testid="stStatusWidget"], .stStatusWidget, [data-testid="stSpinner"] svg { color: var(--accent) !important; fill: var(--accent) !important; }

hr { border-color: var(--line) !important; }
</style>
"""
st.markdown(KILO_CSS, unsafe_allow_html=True)

user_config = load_config()

# ---- Brand nav header ----
st.markdown(
    """
    <div class="nav-bar">
        <div class="nav-left">
            <span class="logo-box">PP</span>
            <span class="nav-badge">v1.0 / GitHub</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

with st.popover("Customisation", use_container_width=False):
    with st.form("customisation_form", border=False):
        st.write("Set default values.")
        c_name = st.text_input("Default Name", value=user_config.get("default_name", ""))
        
        c_series_options = {"m": "Feb/March (m)", "s": "May/June (s)", "w": "Oct/Nov (w)"}
        c_series = st.multiselect(
            "Default Series", 
            options=list(c_series_options.keys()), 
            format_func=lambda x: c_series_options[x],
            default=user_config.get("default_series", ["s", "w"])
        )
        
        c_variants = st.multiselect(
            "Default Variants",
            options=[1, 2, 3],
            default=user_config.get("default_variants", [1, 2, 3])
        )
        
        if st.form_submit_button("Save Settings"):
            user_config["default_name"] = c_name
            user_config["default_series"] = c_series
            user_config["default_variants"] = c_variants
            save_config(user_config)
            st.rerun()

# ---- Hero ----
st.markdown(
    """
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem; line-height: 1.0;">
        <h1 style="font-family: 'JetBrains Mono', 'Fira Code', monospace !important; font-size: 3.5rem; font-weight: 700; color: #FFFFFF; margin: 0; padding: 0; letter-spacing: -0.03em;">
            The IGCSE Tool
        </h1>
        <h1 style="font-family: 'JetBrains Mono', 'Fira Code', monospace !important; font-size: 3.5rem; font-weight: 700; color: #EAFF53; margin: 0; padding: 0; letter-spacing: -0.03em;">
            the world was missing
        </h1>
    </div>
    """,
    unsafe_allow_html=True
)

# ---- Top selectors: Subject + Paper Component (uniform 50/50 dropdowns) ----
subj_col, comp_col = st.columns(2)
with subj_col:
    subject_name = st.selectbox("Subject", list(SUBJECT_MAPPING.keys()))
with comp_col:
    paper_component = st.selectbox("Paper Component", [1, 2, 3, 4, 5, 6], index=3)  # Default Paper 4

app_mode = st.radio("Select Generation Mode", ["Full Booklet Mode", "Topical Question Bank Mode"], horizontal=True)
is_topical = (app_mode == "Topical Question Bank Mode")

selected_math_topic = ""
keyword = ""
if is_topical:
    st.info("Topical Mode: We will scan papers for your keywords and extract only matching questions.")
    if SUBJECT_MAPPING[subject_name] == "0606":
        selected_math_topic = st.selectbox("Select Additional Mathematics Topic", list(MATH_0606_TOPICS.keys()))
    else:
        keyword = st.text_input("Topic Keywords (comma-separated, e.g., Stoichiometry, Acid, Velocity)", value="").strip()

with st.form("paper_form"):
    # Row 1: Student Name + Years Selection on one perfectly aligned 50/50 axis
    name_col, years_col = st.columns(2)
    with name_col:
        student_name = st.text_input("Student Name (for Cover Page)", value=user_config.get("default_name", ""))
    with years_col:
        current_year = 2024
        years = st.slider("Years Selection", min_value=2015, max_value=current_year, value=(2020, 2023))

    st.subheader("Variants & Series")

    # Row 2: Exam Series + Variants side-by-side (crisp horizontal pill rows)
    series_options = {"m": "Feb/March (m)", "s": "May/June (s)", "w": "Oct/Nov (w)"}
    series_col, variant_col = st.columns(2)
    with series_col:
        selected_series = st.multiselect(
            "Exam Series",
            options=list(series_options.keys()),
            format_func=lambda x: series_options[x],
            default=user_config.get("default_series", ["s", "w"])
        )
    with variant_col:
        selected_variants = st.multiselect(
            "Variants (For May/June & Oct/Nov)",
            options=[1, 2, 3],
            default=user_config.get("default_variants", [1, 2, 3])
        )

    st.info("Note: For Feb/March (m) series, standard variant inputs are ignored and only variant 2 is downloaded as per Cambridge rules.")

    btn_text = "Generate Topical Booklet" if is_topical else "Generate and Download Booklet"
    submit_button = st.form_submit_button(btn_text)

# --- PROCESSING LOGIC ---
if submit_button:
    if not selected_series:
        st.error("Please select at least one exam series.")
    elif is_topical and SUBJECT_MAPPING[subject_name] != "0606" and not keyword:
        st.error("Please enter a keyword for Topical Mode.")
    else:
        subject_code = SUBJECT_MAPPING[subject_name]
        
        # Calculate expected number of papers to fetch for progress bar
        fetch_tasks = []
        for year in range(years[0], years[1] + 1):
            for series in selected_series:
                if series == "m":
                    variant_list = [2]
                else:
                    variant_list = selected_variants
                
                for var in variant_list:
                    comp_var = f"{paper_component}{var}"
                    fetch_tasks.append((year, series, comp_var))
                    
        total_tasks = len(fetch_tasks)
        if total_tasks == 0:
            st.warning("No papers match your selection.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            downloaded_pdfs = []
            failed_downloads = []
            
            for i, task in enumerate(fetch_tasks):
                year, series, comp_var = task
                status_text.text(f"Fetching {subject_code} {series}{str(year)[-2:]} Paper {comp_var}...")
                
                pdf_content = fetch_paper(subject_code, year, series, comp_var)
                if pdf_content:
                    downloaded_pdfs.append((pdf_content, year, series, comp_var))
                else:
                    failed_downloads.append(f"{series}{str(year)[-2:]} Paper {comp_var}")
                    
                # Update progress
                progress_bar.progress((i + 1) / total_tasks)
                time.sleep(0.5) # Slight delay to be polite to the server
                
            status_text.text("Processing & Merging PDFs...")
            
            if downloaded_pdfs:
                merger = PdfWriter()
                
                # 1. Generate Cover Page
                mode_str = "Topical" if is_topical else "Full Booklet"
                cover_keyword = selected_math_topic if subject_code == "0606" else keyword
                cover_pdf = generate_cover_page(student_name, subject_name, years, paper_component, selected_series, mode_str, cover_keyword)
                merger.append(cover_pdf)
                
                successful_topical_papers = []
                compiled_question_ids = set()
                
                import copy
                
                # Collect pages for topical or full booklet mode using stateful parsing
                for pdf_bytes, year, series, comp_var in downloaded_pdfs:
                    reader = PdfReader(io.BytesIO(pdf_bytes))
                    questions = parse_question_boundaries(reader, subject_code, comp_var)
                    
                    year_short = str(year)[-2:]
                    matched_q_nums = []
                    
                    if is_topical:
                        if subject_code == "0606":
                            patterns = MATH_0606_TOPICS[selected_math_topic]
                            for q_num, data in questions.items():
                                text_content = data["text"]
                                text_lower = text_content.lower()
                                
                                match_found = False
                                matched_pat = ""
                                for pat in patterns:
                                    if pat == r'\b[A-Z]{2}\b':
                                        if re.search(pat, text_content) and any(word in text_lower for word in ["vector", "magnitude", "velocity", "collinear", "position"]):
                                            match_found = True
                                            matched_pat = "Vector context pattern"
                                            break
                                    else:
                                        if re.search(pat, text_content, re.IGNORECASE):
                                            match_found = True
                                            matched_pat = pat
                                            break
                                            
                                if match_found:
                                    matched_q_nums.append((q_num, matched_pat))
                        else:
                            keywords_list = [kw.strip().lower() for kw in keyword.split(',') if kw.strip()]
                            for q_num, data in questions.items():
                                text_lower = data["text"].lower()
                                matched_pat = ""
                                for kw in keywords_list:
                                    if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                                        matched_pat = kw
                                        break
                                if matched_pat:
                                    matched_q_nums.append((q_num, matched_pat))
                    else:
                        # Full Booklet Mode: Add ALL pages directly (including front cover at page 0).
                        # Bypass question-based processing entirely — no cropping, no banners, no page skipping.
                        successful_topical_papers.append((year, series, comp_var))
                        for p_num in range(len(reader.pages)):
                            merger.add_page(reader.pages[p_num])
                        # matched_q_nums stays empty, so the per-question loop below is skipped.
                    
                    if matched_q_nums:
                        successful_topical_papers.append((year, series, comp_var))
                        
                        # Re-read from pdf_bytes to avoid modifying shared memory objects across loops!
                        fresh_reader = PdfReader(io.BytesIO(pdf_bytes))
                        for q_num, matched_pat in matched_q_nums:
                            question_id = f"{subject_code}_{series}{year_short}_{comp_var}_Q{q_num}"
                            if question_id in compiled_question_ids:
                                print(f"Skipping duplicate: {question_id}")
                                continue
                            compiled_question_ids.add(question_id)
                            
                            data = questions[q_num]
                            diagnostic_info = f"[DIAGNOSTIC LOG] — Question {q_num} | Matched Topic: {selected_math_topic if subject_code == '0606' else keyword} | Core Trigger: '{matched_pat}' | Source Page(s): {data['start_page']}-{data['end_page']}"
                            
                            for p_num in range(data["start_page"], data["end_page"] + 1):
                                orig_page = fresh_reader.pages[p_num]
                                orig_width = float(orig_page.mediabox.width)
                                orig_height = float(orig_page.mediabox.height)
                                
                                # Deep copy the page object to safely modify mediabox
                                p_obj = copy.copy(orig_page)
                                mb = p_obj.mediabox
                                
                                # Determine crop boundaries for this page
                                crop_bottom = float(mb.bottom)
                                crop_top = float(mb.top)
                                
                                # Only apply mid-page cropping in Topical mode.
                                # In Full Booklet mode, always show the complete page.
                                if is_topical:
                                    # Overlap check with the previous page for multi-page questions
                                    if p_num > data["start_page"]:
                                        overlap_y = detect_text_overlap(fresh_reader.pages[p_num - 1], orig_page)
                                        if overlap_y is not None:
                                            # Crop the top to slice out duplicated text from this page
                                            crop_top = min(crop_top, overlap_y)

                                    # Start-page: crop above the question's start_y (if mid-page start)
                                    if p_num == data["start_page"] and data.get("start_y") is not None:
                                        if data["start_y"] <= orig_height - 100:
                                            crop_top = data["start_y"] + 40
                                            
                                # End-page: crop below the question's end_y (if mid-page end)
                                if p_num == data["end_page"] and data.get("end_y") is not None:
                                    # In PDF coordinates, Y=0 is the bottom. To slice off the next question 
                                    # (which starts at end_y and goes downwards), we set our crop box's bottom 
                                    # boundary slightly ABOVE end_y.
                                    crop_bottom = data["end_y"] + 20
                                
                                # Apply crop to all bounding boxes to guarantee the viewer respects it
                                rect = RectangleObject([
                                    float(mb.left),
                                    crop_bottom,
                                    float(mb.right),
                                    crop_top
                                ])
                                p_obj.mediabox = rect
                                p_obj.cropbox = rect
                                p_obj.trimbox = rect
                                p_obj.artbox = rect
                                
                                # Force standard A4 page size for output consistency
                                a4_width, a4_height = A4
                                a4_rect = RectangleObject([
                                    0,
                                    0,
                                    a4_width,
                                    a4_height
                                ])
                                p_obj.mediabox = a4_rect
                                
                                # Draw banner only on the first page of the question
                                draw_banner = (p_num == data["start_page"])
                                
                                # Banner Y: always at the top of the (cropped) page
                                banner_y = crop_top - 35
                                
                                draw_red = None
                                draw_green = False
                                
                                # Only draw boundary lines in Topical mode
                                if is_topical and p_num == data["end_page"]:
                                    if data.get("end_y") is not None:
                                        draw_red = data["end_y"]
                                    else:
                                        draw_green = True
                                        
                                has_lines = st.session_state.get('render_boundary_lines', False) and (draw_red is not None or draw_green)
                                
                                if draw_banner or has_lines:
                                    overlay_pdf = create_page_overlay(
                                        subject_code, year, series, comp_var, q_num,
                                        orig_width=orig_width,
                                        orig_height=orig_height,
                                        diagnostic_info=diagnostic_info if draw_banner else None,
                                        draw_banner=draw_banner,
                                        banner_y=banner_y,
                                        draw_red_line_at=draw_red,
                                        draw_green_line=draw_green,
                                        draw_green_line_at=crop_bottom + 5 if draw_green else None
                                    )
                                    overlay_reader = PdfReader(overlay_pdf)
                                    overlay_page = overlay_reader.pages[0]
                                    p_obj.merge_page(overlay_page)
                                
                                merger.add_page(p_obj)
                                
                if successful_topical_papers:
                    # Generate Index Page and insert it right after the cover (index 1)
                    unique_papers = list(dict.fromkeys(successful_topical_papers))
                    index_pdf = generate_index_page(unique_papers, subject_code)
                    index_reader = PdfReader(index_pdf)
                    merger.insert_page(index_reader.pages[0], 1)
                elif is_topical:
                    st.warning("No questions found matching your selection.")
                    
                # Save to output stream
                output_pdf = io.BytesIO()
                merger.write(output_pdf)
                merger.close()
                output_pdf.seek(0)
                
                if not is_topical or successful_topical_papers:
                    status_text.success(f"Successfully compiled papers!")
                    if failed_downloads:
                        with st.expander("Failed to download (Files might not exist)"):
                            for f in failed_downloads:
                                st.write(f)
                    
                    # Download Button
                    file_suffix = f"{keyword}_Topic_Bank" if is_topical else "Booklet"
                    st.download_button(
                        label="⬇️ Download Booklet",
                        data=output_pdf,
                        file_name=f"{student_name.replace(' ', '_')}_{subject_code}_{file_suffix}.pdf" if student_name else f"{subject_code}_{file_suffix}.pdf",
                        mime="application/pdf"
                    )
                
            else:
                status_text.error("Failed to download any papers. Please check your selection and try again.")

# ---- Developer settings (anchored at the very bottom) ----
st.markdown("<hr style='margin-top:3rem; margin-bottom:1.25rem;'>", unsafe_allow_html=True)
st.markdown('<div class="util-toggles"></div>', unsafe_allow_html=True)
st.markdown("###### Developer Settings")
dev_col1, dev_col2, _dev_spacer = st.columns([1.1, 1.1, 1.4])
with dev_col1:
    diagnostic_mode = st.toggle("Diagnostic Mode", value=False, key="diagnostic_mode")
with dev_col2:
    render_boundary_lines = st.toggle("Boundary Lines", value=False, key="render_boundary_lines")
