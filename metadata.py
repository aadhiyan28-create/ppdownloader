import os
import re
import yaml

METADATA_FILE = "papers_metadata.yaml"

def load_metadata(filepath=METADATA_FILE):
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def _paper_key(subject_code, year, series, comp_var):
    year_short = str(year)[-2:]
    return f"{subject_code}_{series}{year_short}_qp_{comp_var}"

def _parse_line_entry(line):
    line = str(line).strip()
    if not line:
        return None

    q_match = re.match(r'^Q(\d+)', line, re.IGNORECASE)
    if not q_match:
        return None
    q_num = int(q_match.group(1))

    rest = line[q_match.end():].strip()

    coords = re.match(r'^-?y(-?\d+\.?\d*)-(-?\d+\.?\d*)', rest, re.IGNORECASE)
    start_y = None
    end_y = None
    if coords:
        start_y = float(coords.group(1))
        end_y = float(coords.group(2))
        rest = rest[coords.end():].strip()

    topic = rest.strip() if rest else None

    return {
        "number": q_num,
        "start_y": start_y,
        "end_y": end_y,
        "topic": topic,
        "start_page": None,
        "end_page": None
    }

def _normalize_question_entry(entry):
    if entry is None:
        return None
    if isinstance(entry, dict):
        result = {
            "number": entry.get("number") or entry.get("q") or entry.get("Q"),
            "start_page": entry.get("start_page"),
            "start_y": entry.get("start_y"),
            "end_page": entry.get("end_page"),
            "end_y": entry.get("end_y"),
            "topic": entry.get("topic")
        }
        if result["number"] is None:
            return None
        result["number"] = int(result["number"])
        for k in ("start_y", "end_y"):
            if result[k] is not None:
                result[k] = float(result[k])
        for k in ("start_page", "end_page"):
            if result[k] is not None:
                result[k] = int(result[k])
        return result
    if isinstance(entry, str):
        return _parse_line_entry(entry)
    return None

def get_paper_metadata(metadata, subject_code, year, series, comp_var):
    key = _paper_key(subject_code, year, series, comp_var)
    paper = metadata.get(key)
    if not paper:
        return {}

    questions_raw = paper.get("questions")
    if questions_raw is None:
        lines = paper.get("lines", [])
        questions_raw = lines

    questions = {}
    for entry in questions_raw:
        q = _normalize_question_entry(entry)
        if q is None:
            continue
        q_num = q["number"]
        if q_num in questions:
            existing = questions[q_num]
            for k in ("start_page", "start_y", "end_page", "end_y", "topic"):
                if q.get(k) is not None:
                    existing[k] = q[k]
        else:
            questions[q_num] = q

    return questions

def get_available_metadata_subjects(metadata):
    subjects = set()
    for key in metadata:
        if "_" in key:
            parts = key.split("_")
            if len(parts) >= 4 and parts[0].isdigit() and len(parts[0]) == 4:
                subjects.add(parts[0])
    return sorted(subjects)

def get_metadata_years(metadata, subject_code):
    years = set()
    for key in metadata:
        parts = key.split("_")
        if len(parts) >= 4 and parts[0] == subject_code:
            year_str = parts[1]
            if len(year_str) == 2 and year_str[:-2].isdigit():
                years.add(int("20" + year_str[-2:]))
    return sorted(years)
