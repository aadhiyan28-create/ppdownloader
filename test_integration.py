"""
Integration test: run the same MCQ extraction logic used by the app on a 0620 paper
and print the parsed questions with their boundaries.
"""
import io
import re
import requests
from pypdf import PdfReader
from pypdf.generic import RectangleObject
from reportlab.lib.pagesizes import A4

BASE_URL = "https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pastpapers.papacambridge.com/"
}

def fetch_paper(subject_code, year, series, component_variant):
    year_short = str(year)[-2:]
    filename = f"{subject_code}_{series}{year_short}_qp_{component_variant}.pdf"
    url = f"{BASE_URL}{filename}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            if response.headers.get('Content-Type') == 'application/pdf' or response.content.startswith(b'%PDF'):
                return response.content, filename
    except Exception:
        pass
    return None, filename

def _is_formula_page(reader, page_num, subject_code=None, comp_var=None):
    if page_num == 1:
        return True
    if subject_code == "0620" and comp_var and comp_var.startswith("4"):
        page = reader.pages[page_num]
        text = page.extract_text().lower()
        if ("the periodic table of elements" in text
                and "the volume of one mole of any gas is 24 dm3" in text):
            return True
    return False

def parse_question_boundaries(reader, subject_code="0620", comp_var="11"):
    skip_pages = set()
    for page_num in range(len(reader.pages)):
        if _is_formula_page(reader, page_num, subject_code, comp_var):
            skip_pages.add(page_num)

    # MCQ collection
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
                if not re.match(r'^\d+\s*$', first_word):
                    continue
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

    X_MIN, X_MAX = 47, 50
    column_candidates = [c for c in candidates if X_MIN - 1 <= c["x"] <= X_MAX + 1]
    if not column_candidates:
        return {}

    column_candidates.sort(key=lambda c: (c["page"], -c["y"]))
    seen = set()
    deduped = []
    for c in column_candidates:
        if c["num"] not in seen:
            deduped.append(c)
            seen.add(c["num"])

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
            if i + 1 < len(deduped) and deduped[i + 1]["num"] == expected:
                i += 1
            else:
                break
        else:
            i += 1

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

    validated_questions = {}
    for c in chain:
        validated_questions[c["num"]] = {
            "start_page": c["page"],
            "start_y": c["y"],
        }

    nums = sorted(validated_questions.keys())
    questions = {}
    for idx, num in enumerate(nums):
        data = validated_questions[num]
        end_p = len(reader.pages) - 1
        while end_p in skip_pages and end_p > data["start_page"]:
            end_p -= 1

        if idx == len(nums) - 1 and idx > 0:
            prev_end = questions[nums[idx - 1]]["end_page"]
            if prev_end >= data["start_page"]:
                end_p = prev_end

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

            if next_page == data["start_page"]:
                questions[num]["end_page"] = next_page
                questions[num]["end_y"] = next_data["start_y"]
            else:
                end_p = next_page - 1
                while end_p in skip_pages and end_p > data["start_page"]:
                    end_p -= 1
                questions[num]["end_page"] = end_p
                questions[num]["end_y"] = None

        # Simulate crop boundaries
        crop_bottom = 0
        crop_top = 842
        if data.get("start_y") is not None and data["start_y"] <= 742:
            crop_top = data["start_y"] + 40
        if data.get("end_y") is not None:
            crop_bottom = data["end_y"] + 20

        questions[num]["crop_bottom"] = crop_bottom
        questions[num]["crop_top"] = crop_top

        # A4 size check
        a4_w, a4_h = A4
        questions[num]["a4_size"] = (a4_w, a4_h)

    return questions


pdf_content, filename = fetch_paper("0620", 2016, "s", "13")
if pdf_content:
    reader = PdfReader(io.BytesIO(pdf_content))
    qs = parse_question_boundaries(reader, "0620", "13")
    print(f"\n=== {filename} — {len(qs)} questions ===\n")
    for num in sorted(qs.keys()):
        q = qs[num]
        print(f"Q{num}: pages {q['start_page']}-{q['end_page']}, "
              f"start_y={q['start_y']:.1f}, end_y={q['end_y']}, "
              f"crop=[{q['crop_bottom']:.1f}, {q['crop_top']:.1f}], "
              f"A4={q['a4_size']}")
else:
    print("Failed to fetch paper.")
