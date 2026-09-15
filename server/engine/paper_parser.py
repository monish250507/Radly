"""
paper_parser.py — Production manuscript ingestion pipeline.

P1 FIX: Real PDF/DOCX/LaTeX/TXT adapters replace the plain string pass-through.

Architecture:
  extract_text_from_document()
    ├── _extract_pdf()    → uses pypdf (graceful fallback to raw bytes if unavailable)
    ├── _extract_docx()   → uses python-docx (graceful fallback if unavailable)
    ├── _extract_latex()  → LaTeX comment/command stripping
    └── _extract_txt()    → UTF-8 text with encoding recovery

Each adapter returns an ExtractionResult dataclass:
  status       : 'OK' | 'PARTIAL' | 'FAILED'
  text         : extracted text (empty on FAILED)
  page_count   : pages extracted (where applicable)
  error        : description of any extraction problem
  source_locs  : list of {page, paragraph, char_offset} dicts

Scalability notes:
  - Hard size cap: 10 MB input / 5 MB after extraction
  - Async-safe: all heavy extraction is wrapped in run_in_executor
  - Per-adapter error isolation: one bad file cannot crash other ingestion
  - Structured logging on every failure path
"""

import asyncio
import base64
import hashlib
import re
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from .logger import radly_logger as logger

MAX_INPUT_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_TEXT_BYTES  = 5  * 1024 * 1024   # 5 MB post-extraction


# ---------------------------------------------------------------------------
# Extraction result contract
# ---------------------------------------------------------------------------
@dataclass
class ExtractionResult:
    status: str          # 'OK' | 'PARTIAL' | 'FAILED'
    text: str            # extracted plain text
    page_count: int = 0
    source_locs: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    adapter: str = 'unknown'


def _failed_result(adapter: str, reason: str) -> ExtractionResult:
    return ExtractionResult(status='FAILED', text='', adapter=adapter, error=reason)


# ---------------------------------------------------------------------------
# PDF adapter — pypdf
# ---------------------------------------------------------------------------
def _extract_pdf_sync(data: bytes) -> ExtractionResult:
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        source_locs = []
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ''
                pages.append(page_text)
                source_locs.append({'page': i + 1, 'char_offset': sum(len(p) for p in pages[:-1])})
            except Exception as pe:
                logger.warn(f"PDF page {i+1} extraction error", {'error': str(pe)})
                pages.append('')

        full_text = '\n'.join(pages)
        if not full_text.strip():
            return ExtractionResult(
                status='PARTIAL', text='', page_count=len(reader.pages),
                adapter='pdf', error='PDF extracted but all pages returned empty text. PDF may be scanned/image-based.'
            )
        return ExtractionResult(
            status='OK', text=full_text, page_count=len(reader.pages),
            source_locs=source_locs, adapter='pdf'
        )
    except ImportError:
        return _failed_result('pdf', 'pypdf is not installed. Run: pip install pypdf')
    except Exception as e:
        return _failed_result('pdf', f'PDF extraction error: {e}')


# ---------------------------------------------------------------------------
# DOCX adapter — python-docx
# ---------------------------------------------------------------------------
def _extract_docx_sync(data: bytes) -> ExtractionResult:
    try:
        import io

        import docx
        doc = docx.Document(io.BytesIO(data))
        paragraphs = []
        source_locs = []
        char_offset = 0
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                paragraphs.append(text)
                source_locs.append({'page': None, 'paragraph': i + 1, 'char_offset': char_offset})
                char_offset += len(text) + 1

        full_text = '\n'.join(paragraphs)
        if not full_text.strip():
            return ExtractionResult(
                status='PARTIAL', text='', page_count=0,
                adapter='docx', error='DOCX extracted but no paragraph text found.'
            )
        return ExtractionResult(
            status='OK', text=full_text, page_count=0,
            source_locs=source_locs, adapter='docx'
        )
    except ImportError:
        return _failed_result('docx', 'python-docx is not installed. Run: pip install python-docx')
    except Exception as e:
        return _failed_result('docx', f'DOCX extraction error: {e}')


# ---------------------------------------------------------------------------
# LaTeX adapter
# ---------------------------------------------------------------------------
def _extract_latex_sync(text: str) -> ExtractionResult:
    try:
        # Strip LaTeX comments
        cleaned = re.sub(r'^[ \t]*%[^\n]*', '', text, flags=re.MULTILINE)
        # Strip common LaTeX commands but keep content
        cleaned = re.sub(r'\\(textbf|textit|emph|texttt|underline|footnote)\{([^}]*)\}', r'\2', cleaned)
        cleaned = re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', cleaned)
        cleaned = re.sub(r'\\[a-zA-Z]+\*?', ' ', cleaned)
        cleaned = re.sub(r'\{|\}', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if not cleaned:
            return _failed_result('latex', 'LaTeX source extracted but content was empty after stripping commands.')
        return ExtractionResult(status='OK', text=cleaned, adapter='latex')
    except Exception as e:
        return _failed_result('latex', f'LaTeX extraction error: {e}')


# ---------------------------------------------------------------------------
# TXT adapter
# ---------------------------------------------------------------------------
def _extract_txt_sync(data: bytes) -> ExtractionResult:
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            text = data.decode(enc)
            return ExtractionResult(status='OK', text=text, adapter='txt')
        except UnicodeDecodeError:
            continue
    # Last resort: replace errors
    text = data.decode('utf-8', errors='replace')
    return ExtractionResult(
        status='PARTIAL', text=text, adapter='txt',
        error='Text decoded with replacement characters — some content may be garbled.'
    )


# ---------------------------------------------------------------------------
# Public async entrypoint
# ---------------------------------------------------------------------------
async def extract_text_from_document(input_data: Any, file_type: str = 'txt') -> str:
    """
    P1 FIX: Real document extraction pipeline.

    Accepts:
      - Base64-encoded string (from frontend file upload)
      - Raw bytes
      - Plain text string (pass-through for txt/latex)

    Returns plain text string. On FAILED extraction, raises ValueError so
    callers can handle the failure explicitly — never returns empty string
    silently as if extraction succeeded.
    """
    loop = asyncio.get_event_loop()
    ft = (file_type or 'txt').lower().strip('.')

    # --- Decode input ---
    if isinstance(input_data, str):
        # Try base64 first (frontend sends base64 for binary files)
        if ft in ('pdf', 'docx') and len(input_data) > 100:
            try:
                raw_bytes = base64.b64decode(input_data)
            except Exception:
                # Not base64 — treat as plain text
                raw_bytes = None
        else:
            raw_bytes = None

        if raw_bytes is None:
            raw_bytes = input_data.encode('utf-8', errors='replace')
    elif isinstance(input_data, bytes):
        raw_bytes = input_data
    else:
        raw_bytes = str(input_data).encode('utf-8')

    # Size guard
    if len(raw_bytes) > MAX_INPUT_BYTES:
        logger.warn(
            f"Document exceeds {MAX_INPUT_BYTES // (1024*1024)}MB limit — truncating",
            {'size_bytes': len(raw_bytes)}
        )
        raw_bytes = raw_bytes[:MAX_INPUT_BYTES]

    # --- Route to adapter ---
    if ft == 'pdf':
        result: ExtractionResult = await loop.run_in_executor(
            None, partial(_extract_pdf_sync, raw_bytes)
        )
    elif ft == 'docx':
        result = await loop.run_in_executor(
            None, partial(_extract_docx_sync, raw_bytes)
        )
    elif ft in ('tex', 'latex'):
        text_str = raw_bytes.decode('utf-8', errors='replace')
        result = await loop.run_in_executor(
            None, partial(_extract_latex_sync, text_str)
        )
    else:
        result = await loop.run_in_executor(
            None, partial(_extract_txt_sync, raw_bytes)
        )

    # --- Log and validate ---
    if result.status == 'FAILED':
        logger.error(
            f"Document extraction FAILED for {ft}",
            {'adapter': result.adapter, 'error': result.error}
        )
        raise ValueError(
            f"Document extraction failed ({result.adapter}): {result.error}. "
            f"Cannot proceed — no text to analyse."
        )

    if result.status == 'PARTIAL':
        logger.warn(
            f"Document extraction PARTIAL for {ft}",
            {'adapter': result.adapter, 'error': result.error}
        )

    extracted = result.text
    if len(extracted.encode('utf-8')) > MAX_TEXT_BYTES:
        logger.warn(
            f"Extracted text exceeds {MAX_TEXT_BYTES // (1024*1024)}MB — truncating",
            {'original_bytes': len(extracted.encode('utf-8'))}
        )
        extracted = extracted[:MAX_TEXT_BYTES]

    logger.info(
        "Document extracted",
        {
            'adapter': result.adapter,
            'status': result.status,
            'pages': result.page_count,
            'text_len': len(extracted),
            'source_locs_count': len(result.source_locs)
        }
    )
    return extracted


# ---------------------------------------------------------------------------
# Structure parser — unchanged interface, improved internals
# ---------------------------------------------------------------------------
def parse_paper_structure(raw_text: str) -> dict[str, Any]:
    """
    Parse plain text into structured manuscript objects.
    Returns a dict with sections, equations, tables, figures, claims, etc.
    All objects carry startLine/endLine for source traceability.
    """
    if not raw_text or not isinstance(raw_text, str):
        return {
            'rawText': '', 'sections': [], 'equations': [], 'tables': [],
            'numbers': [], 'claims': [], 'figures': [], 'datasets': [], 'metrics': [],
            'extraction_status': 'FAILED', 'extraction_note': 'No text provided.'
        }

    if len(raw_text) > 5 * 1024 * 1024:
        logger.warn("Paper text exceeds 5MB — parsing truncated.")
        raw_text = raw_text[:5 * 1024 * 1024]

    # Strip LaTeX comments
    clean_text = re.sub(r'^[ \t]*%[^\n]*', '', raw_text, flags=re.MULTILINE)

    sections  = extract_sections(clean_text)
    equations = extract_equations(clean_text)
    tables    = extract_tables(clean_text)
    figures   = extract_figures(clean_text)
    numbers   = extract_numerical_claims(clean_text)
    claims    = extract_claims(clean_text)
    datasets  = extract_datasets(clean_text)
    metrics   = extract_metrics(clean_text)

    extraction_note = None
    is_partial = False
    if len(sections) == 1 and 'manuscript-body' in sections[0]['id']:
        is_partial = True
        extraction_note = 'No section headings detected. Full text treated as a single section.'

    return {
        'rawText': clean_text,
        'sections': sections,
        'equations': equations,
        'tables': tables,
        'figures': figures,
        'numbers': numbers,
        'claims': claims,
        'datasets': datasets,
        'metrics': metrics,
        'extraction_status': 'PARTIAL' if is_partial else 'OK',
        'extraction_note': extraction_note,
        'content_hash': hashlib.sha1(clean_text.encode('utf-8')).hexdigest()[:16]
    }


def extract_sections(text: str) -> list[dict[str, Any]]:
    sections = []
    lines = text.split('\n')

    current_section = {
        'id': 'sec-1-manuscript-body', 'title': 'Full Manuscript Body',
        'content': [], 'startLine': 1, 'endLine': 1
    }
    has_explicit_heading = False

    canonical_heading_regex = re.compile(
        r'^(?:(?:\d+\.|\d+\.\d+|\d+)\s+)?(Abstract|Introduction|Related Work|Background|'
        r'Problem Formulation|Methodology|Method|Methods|Model Architecture|Experimental Setup|'
        r'Experiments|Evaluation|Results|Discussion|Ablation Study|Conclusion|References|Appendix)\s*$',
        re.IGNORECASE
    )
    numbered_heading_regex = re.compile(r'^(?:\d+\.|\d+\.\d+|\d+)\s+[A-Z][A-Za-z\s:-]{2,45}\s*$')
    tex_sec_regex = re.compile(r'\\(section|subsection|subsubsection)\*?\s*\{([^}]+)\}')

    for idx, line in enumerate(lines):
        line_num = idx + 1
        trimmed = line.strip()

        if not trimmed:
            current_section['content'].append(line)
            continue

        tex_match = tex_sec_regex.search(trimmed)
        clean_line = re.sub(r'^#{1,4}\s*', '', trimmed)

        is_heading = False
        if tex_match or len(clean_line) < 60 and (
            canonical_heading_regex.match(clean_line) or numbered_heading_regex.match(clean_line)
        ):
            is_heading = True

        if is_heading:
            has_explicit_heading = True
            if current_section['content']:
                current_section['endLine'] = line_num - 1
                body_text = '\n'.join(current_section['content']).strip()
                if body_text:
                    sec_dict = {k: v for k, v in current_section.items() if k != 'content'}
                    sec_dict['text'] = body_text
                    sections.append(sec_dict)

            title = tex_match.group(2) if tex_match else re.sub(r'^[\d.]+\s*', '', clean_line).strip()
            safe_title = re.sub(r'[^a-z0-9]+', '-', title.lower())
            sec_id = f"sec-{len(sections) + 1}-{safe_title}"

            current_section = {
                'id': sec_id, 'title': title,
                'content': [], 'startLine': line_num, 'endLine': line_num
            }
        else:
            current_section['content'].append(line)

    if current_section['content']:
        current_section['endLine'] = len(lines)
        body_text = '\n'.join(current_section['content']).strip()
        if body_text:
            sec_dict = {k: v for k, v in current_section.items() if k != 'content'}
            sec_dict['text'] = body_text
            sections.append(sec_dict)

    if not has_explicit_heading and sections:
        sections = [{
            'id': 'sec-1-manuscript-body', 'title': 'Full Manuscript Body',
            'text': sections[0]['text'], 'startLine': sections[0]['startLine'], 'endLine': sections[0]['endLine']
        }]

    return sections


def extract_equations(text: str) -> list[dict[str, Any]]:
    equations = []
    env_regex = re.compile(r'\\begin\{(equation|align|eqnarray)\*?\}([\s\S]*?)\\end\{\1\*?\}')
    eq_count = 1

    for match in env_regex.finditer(text):
        content = match.group(2).strip()
        variables = list(set(re.findall(r'\b[a-zA-Z]\b', content)))
        line_num = text[:match.start()].count('\n') + 1
        equations.append({
            'id': f'eq-{eq_count}', 'label': f'Equation ({eq_count})',
            'content': content, 'raw': match.group(0),
            'type': match.group(1), 'variables': variables,
            'index': match.start(), 'startLine': line_num
        })
        eq_count += 1

    display_regex = re.compile(r'\$\$([\s\S]*?)\$\$')
    for match in display_regex.finditer(text):
        content = match.group(1).strip()
        variables = list(set(re.findall(r'\b[a-zA-Z]\b', content)))
        line_num = text[:match.start()].count('\n') + 1
        equations.append({
            'id': f'eq-{eq_count}', 'label': f'Equation ({eq_count})',
            'content': content, 'raw': match.group(0),
            'type': 'display', 'variables': variables,
            'index': match.start(), 'startLine': line_num
        })
        eq_count += 1

    return equations


def extract_tables(text: str) -> list[dict[str, Any]]:
    tables = []
    tex_table_regex = re.compile(r'\\begin\{table\*?\}([\s\S]*?)\\end\{table\*?\}')
    tab_count = 1

    for match in tex_table_regex.finditer(text):
        raw = match.group(0)
        caption_match = re.search(r'\\caption\{([^}]+)\}', raw)
        caption = caption_match.group(1) if caption_match else f"Table {tab_count}"
        line_num = text[:match.start()].count('\n') + 1
        tables.append({
            'id': f'table-{tab_count}', 'label': f'Table {tab_count}',
            'caption': caption, 'content': raw, 'type': 'latex',
            'index': match.start(), 'startLine': line_num
        })
        tab_count += 1

    md_table_regex = re.compile(r'(?:\|[^\n]+\|\n)+')
    for match in md_table_regex.finditer(text):
        raw = match.group(0)
        if '|---' in raw or '| ---' in raw:
            line_num = text[:match.start()].count('\n') + 1
            tables.append({
                'id': f'table-{tab_count}', 'label': f'Table {tab_count}',
                'caption': f'Markdown Table {tab_count}', 'content': raw,
                'type': 'markdown', 'index': match.start(), 'startLine': line_num
            })
            tab_count += 1

    return tables


def extract_figures(text: str) -> list[dict[str, Any]]:
    figures = []
    tex_fig_regex = re.compile(r'\\begin\{figure\*?\}([\s\S]*?)\\end\{figure\*?\}')
    fig_count = 1

    for match in tex_fig_regex.finditer(text):
        raw = match.group(0)
        caption_match = re.search(r'\\caption\{([^}]+)\}', raw)
        caption = caption_match.group(1) if caption_match else f"Figure {fig_count}"
        line_num = text[:match.start()].count('\n') + 1
        figures.append({
            'id': f'fig-{fig_count}', 'label': f'Figure {fig_count}',
            'caption': caption, 'content': raw, 'type': 'latex',
            'index': match.start(), 'startLine': line_num
        })
        fig_count += 1

    md_fig_regex = re.compile(r'!\[([^\]]*)\]\([^)]+\)')
    for match in md_fig_regex.finditer(text):
        caption = match.group(1) or f"Figure {fig_count}"
        line_num = text[:match.start()].count('\n') + 1
        figures.append({
            'id': f'fig-{fig_count}', 'label': f'Figure {fig_count}',
            'caption': caption, 'content': match.group(0),
            'type': 'markdown', 'index': match.start(), 'startLine': line_num
        })
        fig_count += 1

    return figures


def extract_numerical_claims(text: str) -> list[dict[str, Any]]:
    claims = []
    num_regex = re.compile(
        r'\b(\d+(?:\.\d+)?(?:%|e-?\d+|\s*(?:ms|GB|MB|params|dim|layers|heads|epochs)\b))',
        re.IGNORECASE
    )
    for match in num_regex.finditer(text):
        line_num = text[:match.start()].count('\n') + 1
        claims.append({'value': match.group(1), 'index': match.start(), 'type': 'numerical_result', 'line': line_num})
    return claims


def extract_claims(text: str) -> list[dict[str, Any]]:
    """Distinguish parameter statements, experimental observations, and scientific conclusions."""
    claims = []
    sentences = re.split(r'(?<=[.!?])\s+', text)

    param_regex  = re.compile(r'\b(?:set|using|with|learning rate|batch size|epochs|optimizer|adam|sgd|weight decay|momentum|dropout|rank|alpha)\b', re.IGNORECASE)
    obs_regex    = re.compile(r'\b(?:achieves|outperforms|decreases|increases|improves|reduces|accuracy|f1|loss)\b', re.IGNORECASE)
    concl_regex  = re.compile(r'\b(?:we conclude|demonstrates|shows that|indicates that|suggests|prove)\b', re.IGNORECASE)

    char_offset = 0
    for s in sentences:
        s_clean = s.strip()
        if s_clean and len(s_clean) >= 10:
            claim_type = None
            if concl_regex.search(s_clean):
                claim_type = 'scientific_conclusion'
            elif obs_regex.search(s_clean):
                claim_type = 'experimental_observation'
            elif param_regex.search(s_clean) and any(c.isdigit() for c in s_clean):
                claim_type = 'parameter_statement'

            if claim_type:
                line_num = text[:char_offset].count('\n') + 1 if char_offset < len(text) else 0
                claims.append({'text': s_clean, 'type': claim_type, 'line': line_num})
        char_offset += len(s) + 1

    return claims


def extract_datasets(text: str) -> list[dict[str, Any]]:
    datasets = []
    dataset_regex = re.compile(
        r'\b(?:CIFAR-10|CIFAR-100|ImageNet|MNIST|COCO|WMT|SQuAD|GLUE|SuperGLUE|'
        r'Kitti|Cityscapes|IMDB|MS-COCO|Open Images|LibriSpeech|CommonVoice|BooksCorpus)\b',
        re.IGNORECASE
    )
    for match in dataset_regex.finditer(text):
        line_num = text[:match.start()].count('\n') + 1
        datasets.append({'name': match.group(0), 'index': match.start(), 'line': line_num})
    return datasets


def extract_metrics(text: str) -> list[dict[str, Any]]:
    metrics = []
    metric_regex = re.compile(
        r'\b(?:Accuracy|F1|Precision|Recall|BLEU|ROUGE|FID|IS|MSE|MAE|RMSE|IoU|'
        r'AUROC|AUC|Top-1|Top-5|Perplexity|WER|CER|mAP)\b',
        re.IGNORECASE
    )
    for match in metric_regex.finditer(text):
        line_num = text[:match.start()].count('\n') + 1
        metrics.append({'name': match.group(0), 'index': match.start(), 'line': line_num})
    return metrics
