import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

INVALID_NAME_TOKENS = {
    "svg", "author", "premium", "follow", "like", "reply",
    "3rd+", "1st", "2nd", "3rd", "more", "comment", "options", "open options"
}

OPTION_ANCHOR_REGEX = re.compile(
    r"^\s*(?:\*\*)?(?:Open options for|Optionen for|Options for)\s+(?P<name>.+?)(?:['’]s|\s+s)?\s+comment(?:\*\*)?\s*$",
    re.IGNORECASE
)

MARKDOWN_LINK_REGEX = re.compile(r"\[\*\*(.*?)\*\*\]\(.*?\)|\[(.*?)\]\(.*?\)")
TIMESTAMP_REGEX = re.compile(
    r"^\s*(?:\*\*)?(?:\(edited\)\s*)?\d+\s*(?:mo|[smhdwy])(?:\*\*)?\s*$|^\s*(?:\*\*)?\d+\s+(?:minute|hour|day|week|month|year)s?\s+(?:ago)?(?:\*\*)?\s*$",
    re.IGNORECASE
)
FOLLOWER_REGEX = re.compile(r"^\s*\d+[\d,]*\s+followers?\s*$", re.IGNORECASE)

UI_BOUNDARY_REGEXES = [
    re.compile(r"^\s*(?:\*\*)?Like(?:\*\*)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:\*\*)?Reply(?:\*\*)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s+repl(?:y|ies)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s+Comment[s]?\s+on\s+.*$", re.IGNORECASE),
    re.compile(r"^\s*View\s+.*?['’]s\s+(?:profile|graphic|image)\s*$", re.IGNORECASE),
]

# Obvious student / job-seeker signals for local pre-filtering
LOW_VALUE_HEADLINE_PATTERNS = [
    re.compile(r"\bstudent\b", re.IGNORECASE),
    re.compile(r"\bundergraduate\b", re.IGNORECASE),
    re.compile(r"\bintern\b", re.IGNORECASE),
    re.compile(r"\bopen\s+to\s+work\b", re.IGNORECASE),
    re.compile(r"\bjob\s+seeker\b", re.IGNORECASE),
    re.compile(r"\blearning\s+/|studying\b", re.IGNORECASE),
]

# Professional role signals that override low value signals
PROFESSIONAL_ROLE_PATTERNS = [
    re.compile(r"\b(?:co-)?founder\b", re.IGNORECASE),
    re.compile(r"\bceo\b", re.IGNORECASE),
    re.compile(r"\bcto\b", re.IGNORECASE),
    re.compile(r"\bcfo\b", re.IGNORECASE),
    re.compile(r"\bcoo\b", re.IGNORECASE),
    re.compile(r"\bcmo\b", re.IGNORECASE),
    re.compile(r"\bvp\b", re.IGNORECASE),
    re.compile(r"\bdirector\b", re.IGNORECASE),
    re.compile(r"\bmanager\b", re.IGNORECASE),
    re.compile(r"\bhead\s+of\b", re.IGNORECASE),
    re.compile(r"\bowner\b", re.IGNORECASE),
    re.compile(r"\blead\b", re.IGNORECASE),
    re.compile(r"\bengineer\b", re.IGNORECASE),
    re.compile(r"\bconsultant\b", re.IGNORECASE),
    re.compile(r"\barchitect\b", re.IGNORECASE),
    re.compile(r"\bsales\b", re.IGNORECASE),
    re.compile(r"\bbusiness\s+development\b", re.IGNORECASE),
    re.compile(r"\bmarketing\b", re.IGNORECASE),
    re.compile(r"\bentrepreneur\b", re.IGNORECASE),
]


@dataclass
class StructuredCommentRecord:
    name: str
    headline: Optional[str]
    comment: str
    entity_type: str  # "person" or "company"
    is_author_reply: bool
    is_reply: bool = False
    profile_url: Optional[str] = None
    is_candidate: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "headline": self.headline,
            "comment": self.comment,
            "entity_type": self.entity_type,
            "is_author_reply": self.is_author_reply,
            "is_reply": self.is_reply,
            "profile_url": None,  # Explicitly None per specification
            "is_candidate": self.is_candidate,
        }


def strip_markdown(text: str) -> str:
    cleaned = MARKDOWN_LINK_REGEX.sub(lambda m: m.group(1) or m.group(2) or "", text)
    cleaned = re.sub(r"###\s*", "", cleaned)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    return cleaned.strip()


def clean_fallback_name(raw: str) -> str:
    text = strip_markdown(raw)

    # Strip "View [Name]'s hiring graphic/profile"
    match = re.search(r"^View\s+(.*?)(?:['’]s?)\s+(?:hiring graphic|profile|image|open to work graphic)$", text, re.IGNORECASE)
    if match:
        text = match.group(1)

    text = re.sub(r"Author$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^Author\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"•?\s*(?:1st|2nd|3rd\+?|Verified|Premium|svg)\s*•?", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_badge_or_noise_line(line: str) -> bool:
    s = line.strip()
    if not s or s == "(edited)":
        return True
    cleaned = re.sub(r"•?\s*(?:1st|2nd|3rd\+?|Verified|Premium|svg|Author)\s*•?", "", s, flags=re.IGNORECASE).strip()
    return len(cleaned) == 0


def is_ui_boundary(line: str) -> bool:
    if not line:
        return False
    s = line.strip()
    if re.match(r"^\d+$", s):
        return True
    for rx in UI_BOUNDARY_REGEXES:
        if rx.match(s):
            return True
    return False


def clean_comment_body(comment_text: str) -> str:
    lines = comment_text.split("\n")
    clean_lines: List[str] = []
    for l in lines:
        stripped = l.strip()
        if re.match(r"^\s*(?:…|\.\.\.)\s*more\s*$", stripped, re.IGNORECASE):
            continue
        clean_lines.append(l)
    return "\n".join(clean_lines).strip()


def prefilter_candidate_comment(headline: Optional[str], comment: str) -> bool:
    headline_str = (headline or "").strip()
    comment_str = comment.strip()

    has_low_value = any(pat.search(headline_str) for pat in LOW_VALUE_HEADLINE_PATTERNS)
    has_pro_signal = any(pat.search(headline_str) for pat in PROFESSIONAL_ROLE_PATTERNS)

    buying_keywords = [
        "need", "looking", "interested", "pricing", "demo", "tool",
        "solution", "build", "implement", "automate", "test", "cost"
    ]
    has_buying_intent = any(kw in comment_str.lower() for kw in buying_keywords)

    if has_low_value and not has_pro_signal and not has_buying_intent:
        return False

    return True


def is_valid_record(name: str, comment: str) -> bool:
    name_clean = name.strip()
    comment_clean = comment.strip()

    if not name_clean or not comment_clean:
        return False

    if name_clean.lower() in INVALID_NAME_TOKENS:
        return False

    if any(token in name_clean for token in ["• 3rd+", "3rd+Premium", "svg"]):
        return False

    return True


def parse_pasted_comments(raw_text: str) -> List[Dict[str, Any]]:
    if not raw_text or not raw_text.strip():
        return []

    normalized_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [l.rstrip() for l in normalized_text.split("\n")]
    n = len(lines)

    anchor_indices: List[int] = [
        idx for idx, line in enumerate(lines) if TIMESTAMP_REGEX.match(line.strip())
    ]

    if not anchor_indices:
        anchor_indices = [
            idx for idx, line in enumerate(lines)
            if (line.strip().startswith("### [") or OPTION_ANCHOR_REGEX.match(line.strip()))
        ]

    if not anchor_indices:
        return []

    records: List[Dict[str, Any]] = []
    seen_keys = set()

    for anchor_pos, i in enumerate(anchor_indices):
        line = lines[i].strip()
        header_lines: List[str] = []
        start_comment_idx = i + 1

        if TIMESTAMP_REGEX.match(line):
            j = i - 1
            while j >= 0:
                prev_line = lines[j].strip()
                if prev_line:
                    if prev_line.startswith("### ["):
                        header_lines.insert(0, prev_line)
                        break
                    if (prev_line.lower() in ("like", "reply") or
                        re.match(r"^\d+\s+repl(?:y|ies)$", prev_line, re.IGNORECASE) or
                        re.match(r"^\d+\s+Comment[s]?\s+on\s+.*$", prev_line, re.IGNORECASE) or
                        re.match(r"^View\s+.*?['’]s\s+(?:profile|graphic|image)$", prev_line, re.IGNORECASE) or
                        OPTION_ANCHOR_REGEX.match(prev_line)):
                        break
                    header_lines.insert(0, prev_line)
                j -= 1

            if start_comment_idx < n and OPTION_ANCHOR_REGEX.match(lines[start_comment_idx].strip()):
                start_comment_idx += 1

            if not header_lines:
                continue

            raw_name_line = ""
            for hl in header_lines:
                if not is_badge_or_noise_line(hl) and not FOLLOWER_REGEX.match(hl.strip()):
                    raw_name_line = hl
                    break

            if not raw_name_line and header_lines:
                raw_name_line = header_lines[0]

            name = clean_fallback_name(raw_name_line)

        elif OPTION_ANCHOR_REGEX.match(line):
            match = OPTION_ANCHOR_REGEX.match(line)
            anchor_name = match.group("name").strip() if match else None
            j = i - 1
            while j >= 0:
                prev_line = lines[j].strip()
                if prev_line:
                    if prev_line.startswith("### ["):
                        header_lines.insert(0, prev_line)
                        break
                    if is_ui_boundary(prev_line):
                        break
                    header_lines.insert(0, prev_line)
                j -= 1
            name = clean_fallback_name(anchor_name) if anchor_name else (clean_fallback_name(header_lines[0]) if header_lines else "")
            start_comment_idx = i + 1

        else:
            j = i
            while j < n:
                curr_line = lines[j].strip()
                if OPTION_ANCHOR_REGEX.match(curr_line) or TIMESTAMP_REGEX.match(curr_line):
                    header_lines.append(curr_line)
                    start_comment_idx = j + 1
                    break
                if j > i and curr_line.startswith("### ["):
                    break
                if curr_line:
                    header_lines.append(curr_line)
                j += 1
            raw_name_line = header_lines[0] if header_lines else line
            name = clean_fallback_name(raw_name_line)

        is_author_reply = False
        entity_type = "person"
        headline: Optional[str] = None

        all_header_text = " ".join(header_lines) + " " + line
        if "author" in all_header_text.lower():
            is_author_reply = True

        for hl in header_lines:
            hl_strip = hl.strip()
            if FOLLOWER_REGEX.match(hl_strip):
                entity_type = "company"
                headline = strip_markdown(hl_strip)

        if entity_type != "company":
            candidate_headlines = []
            for hl in header_lines:
                hl_clean = strip_markdown(hl)
                if not hl_clean or hl_clean == "(edited)":
                    continue
                if is_badge_or_noise_line(hl):
                    continue
                if hl_clean.lower() == name.lower():
                    continue
                if TIMESTAMP_REGEX.match(hl_clean) or OPTION_ANCHOR_REGEX.match(hl_clean):
                    continue
                if hl.startswith("###"):
                    continue
                candidate_headlines.append(hl_clean)

            if candidate_headlines:
                headline = max(candidate_headlines, key=len)

        comment_lines: List[str] = []
        k = start_comment_idx
        next_anchor_idx = anchor_indices[anchor_pos + 1] if anchor_pos + 1 < len(anchor_indices) else n

        while k < n:
            cline = lines[k].rstrip()
            cstrip = cline.strip()

            if k >= next_anchor_idx and k not in (start_comment_idx,):
                if not (OPTION_ANCHOR_REGEX.match(cstrip) and k == start_comment_idx):
                    break

            if (is_ui_boundary(cstrip) or
                (cstrip.startswith("### [") and k > start_comment_idx)):
                break

            comment_lines.append(cline)
            k += 1

        comment_body = "\n".join(comment_lines).strip()
        comment_body = clean_comment_body(comment_body)

        if is_valid_record(name, comment_body):
            dedup_key = (name.lower(), comment_body.strip().lower()[:50])
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                is_candidate = prefilter_candidate_comment(headline, comment_body)
                record = StructuredCommentRecord(
                    name=name,
                    headline=headline,
                    comment=comment_body,
                    entity_type=entity_type,
                    is_author_reply=is_author_reply,
                    is_reply=is_author_reply,
                    profile_url=None,
                    is_candidate=is_candidate
                )
                records.append(record.to_dict())

    return records
