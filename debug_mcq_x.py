"""
Debug script: MCQ detection on a random 0620 paper.
Shows only candidates that survive strict x=[47,50] and sequence filtering.
"""
import sys
import io
import re
import random
import requests
from pypdf import PdfReader

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

def get_mcq_candidates(reader, subject_code, comp_var):
    skip_pages = set()
    for page_num in range(len(reader.pages)):
        if _is_formula_page(reader, page_num, subject_code, comp_var):
            skip_pages.add(page_num)

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
                # STRICT: only pure standalone digits, no letters like (a) or suffixes
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
    return candidates, skip_pages

def analyze_paper(subject_code, year, series, comp_var):
    pdf_content, filename = fetch_paper(subject_code, year, series, comp_var)
    if not pdf_content:
        print(f"FAILED to fetch: {filename}")
        return False

    print(f"\n=== ANALYZING: {filename} ===")
    reader = PdfReader(io.BytesIO(pdf_content))
    candidates, skip_pages = get_mcq_candidates(reader, subject_code, comp_var)

    if not candidates:
        print("No candidates found.")
        return True

    # Step 2: FIRMLY stick to x ∈ [47, 50] with ±1 sub-pixel tolerance
    X_MIN, X_MAX = 47, 50
    column_candidates = [
        c for c in candidates
        if X_MIN - 1 <= c["x"] <= X_MAX + 1
    ]

    print(f"\nAll candidates: {len(candidates)}")
    print(f"After strict x=[47,50] filter: {len(column_candidates)}")
    if column_candidates:
        xs = [c["x"] for c in column_candidates]
        print(f"  x range: {min(xs):.1f} – {max(xs):.1f}")

    if not column_candidates:
        print("No candidates in strict x-range.")
        return True

    # Step 3: Build strict consecutive ascending chain, removing outliers
    column_candidates.sort(key=lambda c: (c["page"], -c["y"]))

    # Deduplicate: keep only the first occurrence of each number in doc order
    seen = set()
    deduped = []
    for c in column_candidates:
        if c["num"] not in seen:
            deduped.append(c)
            seen.add(c["num"])

    print(f"\nDeduped sequence (doc order): {[c['num'] for c in deduped]}")

    # Walk the sequence and skip isolated outliers that break consecutiveness.
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
            # Isolated outlier? Peek ahead: if next is expected, skip outlier
            if i + 1 < len(deduped) and deduped[i + 1]["num"] == expected:
                i += 1
            else:
                break
        else:
            i += 1

    print(f"\nChain after outlier removal: {[c['num'] for c in chain]}")

    # Fallback: if chain is too short, find longest consecutive run
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
        print(f"Chain after fallback: {[c['num'] for c in chain]}")

    if not chain:
        print("No valid chain found.")
        return True

    print(f"\n=== FINAL QUESTIONS (x=[47,50], strict chain) ===")
    print(f"{'Num':<6} {'Page':<6} {'X':<8} {'Y':<10} Text")
    print("-" * 60)
    for c in chain:
        print(f"{c['num']:<6} {c['page']:<6} {c['x']:<8.1f} {c['y']:<10.1f} {c['text']}")

    return True

# Try the same working paper
subject_code = "0620"
year = 2016
series = "s"
variant = 3
comp_var = f"1{variant}"
print(f"Selected paper: 0620 {series}{str(year)[-2:]} qp_{comp_var}")
analyze_paper(subject_code, year, series, comp_var)
