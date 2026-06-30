import streamlit as st
import requests
import io
import time
import re
from pypdf import PdfWriter, PdfReader
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

def parse_question_boundaries(reader):
    """Parses PDF pages to find structural question boundaries."""
    questions = {}
    current_q = 0
    
    for page_num in range(1, len(reader.pages)):
        text = reader.pages[page_num].extract_text()
        if not text:
            continue
            
        lines = text.split('\n')
        for line in lines:
            line_stripped = line.strip()
            # Match number at start of line: e.g. "1 " or "1." or "1(a)"
            match = re.match(r'^(\d+)([\s\.\(]|$)', line_stripped)
            if match:
                num = int(match.group(1))
                if num == current_q + 1:
                    if current_q > 0:
                        questions[current_q]["end_page"] = page_num
                    current_q = num
                    questions[current_q] = {
                        "start_page": page_num,
                        "end_page": len(reader.pages) - 1
                    }
    
    # Extract text for each question bounded range
    for q_num, data in questions.items():
        combined_text = ""
        for p in range(data["start_page"], data["end_page"] + 1):
            combined_text += reader.pages[p].extract_text() + "\n"
        data["text"] = combined_text
        
    return questions

def create_banner_overlay(subject_code, year, series, comp_var, q_num):
    """Generates a text banner overlay for extracted pages."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    year_short = str(year)[-2:]
    text = f"Source: {subject_code} / {series}{year_short} / qp_{comp_var} — Question {q_num}"
    
    can.setFillColorRGB(1, 1, 1)
    can.rect(40, 785, 530, 25, fill=1, stroke=1)
    
    can.setFillColorRGB(0, 0, 0)
    can.setFont("Helvetica-Bold", 12)
    can.drawString(50, 793, text)
    
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
st.title("📚 IGCSE Past Paper Booklet Generator")
st.markdown("Generate custom compiled IGCSE past paper booklets for practice. Downloads files securely and merges them into a single PDF.")

app_mode = st.radio("Select Generation Mode", ["Full Booklet Mode", "Topical Question Bank Mode"], horizontal=True)
is_topical = (app_mode == "Topical Question Bank Mode")

if is_topical:
    st.info("Topical Mode: We will scan papers for your keywords and extract only matching questions.")
    keyword = st.text_input("Topic Keywords (comma-separated, e.g., Stoichiometry, Acid, Velocity)", value="").strip()
else:
    keyword = ""

with st.form("paper_form"):
    st.subheader("Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        student_name = st.text_input("Student Name (for Cover Page)")
        subject_name = st.selectbox("Subject", list(SUBJECT_MAPPING.keys()))
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
    elif is_topical and not keyword:
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
                cover_pdf = generate_cover_page(student_name, subject_name, years, paper_component, selected_series, mode_str, keyword)
                merger.append(cover_pdf)
                
                successful_topical_papers = []
                
                if is_topical:
                    # Collect pages for topical mode using stateful parsing
                    for pdf_bytes, year, series, comp_var in downloaded_pdfs:
                        reader = PdfReader(io.BytesIO(pdf_bytes))
                        questions = parse_question_boundaries(reader)
                        
                        matched_q_nums = []
                        keywords_list = [kw.strip().lower() for kw in keyword.split(',') if kw.strip()]
                        for q_num, data in questions.items():
                            text_lower = data["text"].lower()
                            if any(re.search(rf"\b{re.escape(kw)}\b", text_lower) for kw in keywords_list):
                                matched_q_nums.append(q_num)
                        
                        if matched_q_nums:
                            successful_topical_papers.append((year, series, comp_var))
                            
                            for q_num in matched_q_nums:
                                data = questions[q_num]
                                for p_num in range(data["start_page"], data["end_page"] + 1):
                                    p_obj = reader.pages[p_num]
                                    
                                    # Stamp the overlay only on the FIRST page of this specific question
                                    if p_num == data["start_page"]:
                                        overlay_pdf = create_banner_overlay(subject_code, year, series, comp_var, q_num)
                                        overlay_reader = PdfReader(overlay_pdf)
                                        overlay_page = overlay_reader.pages[0]
                                        p_obj.merge_page(overlay_page)
                                        
                                    merger.add_page(p_obj)
                                    
                    if successful_topical_papers:
                        # Generate Index Page and insert it right after the cover (index 1)
                        # We use dict.fromkeys to deduplicate in case a paper had multiple matches
                        unique_papers = list(dict.fromkeys(successful_topical_papers))
                        index_pdf = generate_index_page(unique_papers, subject_code)
                        index_reader = PdfReader(index_pdf)
                        merger.insert_page(index_reader.pages[0], 1)
                    else:
                        st.warning("No questions found matching your keyword in the downloaded papers.")
                else:
                    # Full Booklet Mode
                    for pdf_bytes, year, series, comp_var in downloaded_pdfs:
                        reader = PdfReader(io.BytesIO(pdf_bytes))
                        for page_num in range(1, len(reader.pages)): # Skip cover page
                            merger.add_page(reader.pages[page_num])
                    
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
