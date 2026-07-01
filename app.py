import streamlit as st
import requests
import io
import time
import re
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# --- CONFIGURATION ---
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
    can = canvas.Canvas(packet, pagesize=letter)
    
    can.setFont("Helvetica-Bold", 24)
    if mode == "Topical":
        can.drawCentredString(300, 700, f"Topical Question Bank: {keyword.title()}")
    else:
        can.drawCentredString(300, 700, "IGCSE Past Paper Booklet")
    
    can.setFont("Helvetica", 16)
    can.drawCentredString(300, 650, f"Subject: {subject_name} ({SUBJECT_MAPPING[subject_name]})")
    
    can.setFont("Helvetica-Oblique", 14)
    if student_name:
        if mode == "Topical":
            can.drawCentredString(300, 600, f"{student_name}'s Custom Topic Booklet: {keyword}")
        else:
            can.drawCentredString(300, 600, f"Prepared for: {student_name}")
        
    can.setFont("Helvetica", 12)
    can.drawString(100, 500, "Booklet Details:")
    can.drawString(120, 480, f"- Years: {years[0]} to {years[1]}")
    can.drawString(120, 460, f"- Component (Paper): {components}")
    
    series_map = {"m": "Feb/March", "s": "May/June", "w": "Oct/Nov"}
    series_str = ", ".join([series_map.get(s, s) for s in series_list])
    can.drawString(120, 440, f"- Exam Series: {series_str}")
    
    can.save()
    packet.seek(0)
    return packet

def generate_index_page(successful_papers, subject_code):
    """Generates an index page with hyperlinks to Mark Schemes."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    can.setFont("Helvetica-Bold", 18)
    can.drawString(100, 750, "Topical Index - Source Papers & Mark Schemes")
    
    can.setFont("Helvetica", 12)
    y_position = 710
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

def _is_formula_page(reader, page_num):
    """Returns True if the page is a front-matter formula sheet that should be skipped."""
    # Hard skip page 2 of the raw PDF (index 1)
    return page_num == 1

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
            # Must be near the left margin (X < 100)
            if leftmost_x < 100:
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

def parse_question_boundaries(reader):
    """Parses PDF pages to find structural question boundaries."""
    questions = {}
    
    # Build set of skippable formula pages
    skip_pages = set()
    for page_num in range(len(reader.pages)):
        if _is_formula_page(reader, page_num):
            skip_pages.add(page_num)
            
    # Pass 1: Extract all leftmost candidates
    all_candidates = []
    for page_num in range(1, len(reader.pages)):
        if page_num in skip_pages:
            continue
        all_candidates.extend(get_leftmost_candidates(reader.pages[page_num], page_num))
        
    # Sort candidates chronologically (by page, then by Y coordinate descending)
    all_candidates.sort(key=lambda c: (c["page"], -c["y"]))
    
    # Pass 2: Sequence verification (chronological 1, 2, 3, ...) with self-healing lookahead
    validated_questions = {}
    last_val = 0
    
    for i, candidate in enumerate(all_candidates):
        num = candidate["num"]
        # The candidate number must be greater than the last validated question, and not unreasonably large
        if num > last_val and num <= last_val + 2:
            # Lookahead: is there a num + 1 (or num + 2) later?
            has_next = False
            for next_cand in all_candidates[i+1:]:
                if next_cand["num"] in (num + 1, num + 2):
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
                
    # Define questions dictionary with boundaries based on the validated sequence
    nums = sorted(validated_questions.keys())
    for idx, num in enumerate(nums):
        data = validated_questions[num]
        questions[num] = {
            "start_page": data["start_page"],
            "start_y": data["start_y"],
            "end_page": len(reader.pages) - 1,
            "end_y": None
        }
        
        if idx < len(nums) - 1:
            next_num = nums[idx + 1]
            next_data = validated_questions[next_num]
            
            # Heuristic: If the next question starts near the top of its page (Y > 650),
            # the current question ended on the previous page.
            if next_data["start_y"] > 650:
                prev_page = next_data["start_page"] - 1
                while prev_page in skip_pages and prev_page > 0:
                    prev_page -= 1
                questions[num]["end_page"] = prev_page
                questions[num]["end_y"] = None
            else:
                questions[num]["end_page"] = next_data["start_page"]
                questions[num]["end_y"] = next_data["start_y"]
                
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

def create_page_overlay(subject_code, year, series, comp_var, q_num, orig_width, orig_height, diagnostic_info=None, draw_banner=False, banner_y=None, draw_red_line_at=None, draw_green_line=False):
    """Generates a text banner overlay and separation lines for extracted pages."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(orig_width, orig_height))
    
    # If banner_y is not custom, default to standard top (orig_height - 35)
    if banner_y is None:
        banner_y = orig_height - 35
        
    if draw_banner:
        year_short = str(year)[-2:]
        text = f"Source: {subject_code} / {series}{year_short} / qp_{comp_var} — Question {q_num}"
        
        # Erase original header / page numbers under the banner
        can.setFillColorRGB(1, 1, 1)
        can.rect(0, banner_y - 20, orig_width, orig_height - (banner_y - 20), fill=1, stroke=0)
        
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
st.set_page_config(page_title="IGCSE Paper Generator", layout="centered")

diagnostic_mode = st.toggle("Developer Diagnostic Mode", value=False)
st.session_state.diagnostic_mode = diagnostic_mode

render_boundary_lines = st.toggle("Show Visual Boundary Lines on PDF", value=False)
st.session_state.render_boundary_lines = render_boundary_lines

st.title("📚 IGCSE Past Paper Booklet Generator")
st.markdown("Generate custom compiled IGCSE past paper booklets for practice. Downloads files securely and merges them into a single PDF.")

subject_name = st.selectbox("Subject", list(SUBJECT_MAPPING.keys()))

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
    st.subheader("Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        student_name = st.text_input("Student Name (for Cover Page)")
        paper_component = st.selectbox("Paper Component", [1, 2, 3, 4, 5, 6], index=3) # Default Paper 4
        
    with col2:
        current_year = 2024
        years = st.slider("Years Selection", min_value=2015, max_value=current_year, value=(2020, 2023))
        
    st.markdown("---")
    st.subheader("Variants & Series")
    
    # Series
    series_options = {"m": "Feb/March (m)", "s": "May/June (s)", "w": "Oct/Nov (w)"}
    selected_series = st.multiselect(
        "Exam Series",
        options=list(series_options.keys()),
        format_func=lambda x: series_options[x],
        default=["s", "w"]
    )
    
    # Variants
    selected_variants = st.multiselect(
        "Variants (For May/June & Oct/Nov)",
        options=[1, 2, 3],
        default=[1, 2, 3]
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
                    questions = parse_question_boundaries(reader)
                    
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
                        # Full Booklet Mode: Match all questions sequentially
                        for q_num in sorted(questions.keys()):
                            matched_q_nums.append((q_num, "Full Booklet Mode"))
                        
                        # Fallback: if no questions found, add all pages directly
                        if not questions:
                            successful_topical_papers.append((year, series, comp_var))
                            for p_num in range(1, len(reader.pages)):
                                merger.add_page(reader.pages[p_num])
                    
                    if matched_q_nums:
                        successful_topical_papers.append((year, series, comp_var))
                        
                        for q_num, matched_pat in matched_q_nums:
                            question_id = f"{subject_code}_{series}{year_short}_{comp_var}_Q{q_num}"
                            if question_id in compiled_question_ids:
                                print(f"Skipping duplicate: {question_id}")
                                continue
                            compiled_question_ids.add(question_id)
                            
                            data = questions[q_num]
                            diagnostic_info = f"[DIAGNOSTIC LOG] — Question {q_num} | Matched Topic: {selected_math_topic if subject_code == '0606' else keyword} | Core Trigger: '{matched_pat}' | Source Page(s): {data['start_page']}-{data['end_page']}"
                            
                            for p_num in range(data["start_page"], data["end_page"] + 1):
                                orig_page = reader.pages[p_num]
                                orig_width = float(orig_page.mediabox.width)
                                orig_height = float(orig_page.mediabox.height)
                                
                                # Deep copy the page object to safely modify mediabox
                                p_obj = copy.copy(orig_page)
                                mb = p_obj.mediabox
                                
                                # Determine crop boundaries for this page
                                crop_bottom = float(mb.bottom)
                                crop_top = float(mb.top)
                                
                                # Start-page: crop above the question's start_y (if mid-page start)
                                if p_num == data["start_page"] and data.get("start_y") is not None:
                                    if data["start_y"] <= orig_height - 100:
                                        crop_top = data["start_y"] + 40
                                        
                                # End-page: crop below the question's end_y (if mid-page end)
                                if p_num == data["end_page"] and data.get("end_y") is not None:
                                    crop_bottom = data["end_y"] - 10
                                    
                                # Apply mediabox crop
                                p_obj.mediabox = RectangleObject([
                                    float(mb.left),
                                    crop_bottom,
                                    float(mb.right),
                                    crop_top
                                ])
                                
                                # Draw banner only on the first page of the question
                                draw_banner = (p_num == data["start_page"])
                                
                                # Banner Y: always at the top of the (cropped) page
                                banner_y = crop_top - 35
                                
                                draw_red = None
                                draw_green = False
                                
                                if p_num == data["end_page"]:
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
                                        draw_green_line=draw_green
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
