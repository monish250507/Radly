import re
from typing import List, Dict, Any, Optional
from .logger import paperblast_logger as logger


async def extract_text_from_document(input_data: Any, file_type: str = 'txt') -> str:
    """
    Extracts raw text from document buffer/string.
    """
    if isinstance(input_data, str):
        return input_data
    if isinstance(input_data, bytes):
        return input_data.decode('utf-8', errors='ignore')
    return str(input_data)

def parse_paper_structure(raw_text: str) -> Dict[str, Any]:
    if not raw_text or not isinstance(raw_text, str):
        return {'rawText': '', 'sections': [], 'equations': [], 'tables': [], 'numbers': [], 'claims': [], 'figures': [], 'datasets': [], 'metrics': []}

    # Enforce size limits (e.g. 5MB)
    if len(raw_text) > 5 * 1024 * 1024:
        logger.warning("Paper exceeds 5MB size limit, parsing truncated.")
        raw_text = raw_text[:5 * 1024 * 1024]

    # Strip LaTeX comments
    clean_text = re.sub(r'^[ \t]*%[^\n]*', '', raw_text, flags=re.MULTILINE)

    sections = extract_sections(clean_text)
    equations = extract_equations(clean_text)
    tables = extract_tables(clean_text)
    figures = extract_figures(clean_text)
    numbers = extract_numerical_claims(clean_text)
    claims = extract_claims(clean_text)
    datasets = extract_datasets(clean_text)
    metrics = extract_metrics(clean_text)

    return {
        'rawText': clean_text,
        'sections': sections,
        'equations': equations,
        'tables': tables,
        'figures': figures,
        'numbers': numbers,
        'claims': claims,
        'datasets': datasets,
        'metrics': metrics
    }

def extract_sections(text: str) -> List[Dict[str, Any]]:
    sections = []
    lines = text.split('\n')

    current_section = {
        'id': 'sec-1-abstract',
        'title': 'Abstract',
        'content': [],
        'startLine': 1,
        'endLine': 1
    }

    canonical_heading_regex = re.compile(r'^(?:(?:\d+\.|\d+\.\d+|\d+)\s+)?(Abstract|Introduction|Related Work|Background|Problem Formulation|Methodology|Method|Methods|Model Architecture|Experimental Setup|Experiments|Evaluation|Results|Discussion|Ablation Study|Conclusion|References|Appendix)\s*$', re.IGNORECASE)
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
        if tex_match:
            is_heading = True
        elif len(clean_line) < 60 and (canonical_heading_regex.match(clean_line) or numbered_heading_regex.match(clean_line)):
            is_heading = True

        if is_heading:
            if len(current_section['content']) > 0:
                current_section['endLine'] = line_num - 1
                body_text = '\n'.join(current_section['content']).strip()
                if body_text:
                    sec_dict = dict(current_section)
                    sec_dict['text'] = body_text
                    del sec_dict['content']
                    sections.append(sec_dict)

            title = 'Section'
            if tex_match:
                title = tex_match.group(2)
            else:
                title = clean_line

            title = re.sub(r'^[\d.]+\s*', '', title).strip()
            safe_title = re.sub(r'[^a-z0-9]+', '-', title.lower())
            sec_id = f"sec-{len(sections) + 1}-{safe_title}"

            current_section = {
                'id': sec_id,
                'title': title,
                'content': [],
                'startLine': line_num,
                'endLine': line_num
            }
        else:
            current_section['content'].append(line)

    if len(current_section['content']) > 0:
        current_section['endLine'] = len(lines)
        body_text = '\n'.join(current_section['content']).strip()
        if body_text:
            sec_dict = dict(current_section)
            sec_dict['text'] = body_text
            del sec_dict['content']
            sections.append(sec_dict)

    if not sections:
        sections.append({
            'id': 'sec-1-manuscript-body',
            'title': 'Full Manuscript Body',
            'text': text,
            'startLine': 1,
            'endLine': len(lines)
        })

    return sections

def extract_equations(text: str) -> List[Dict[str, Any]]:
    equations = []
    env_regex = re.compile(r'\\begin\{(equation|align|eqnarray)\*?\}([\s\S]*?)\\end\{\1\*?\}')
    eq_count = 1

    for match in env_regex.finditer(text):
        content = match.group(2).strip()
        # Attempt to find variables (heuristic: single letters often used as math variables)
        variables = list(set(re.findall(r'\b[a-zA-Z]\b', content)))
        
        equations.append({
            'id': f'eq-{eq_count}',
            'label': f'Equation ({eq_count})',
            'content': content,
            'raw': match.group(0),
            'type': match.group(1),
            'variables': variables,
            'index': match.start()
        })
        eq_count += 1

    display_regex = re.compile(r'\$\$([\s\S]*?)\$\$')
    for match in display_regex.finditer(text):
        content = match.group(1).strip()
        variables = list(set(re.findall(r'\b[a-zA-Z]\b', content)))
        
        equations.append({
            'id': f'eq-{eq_count}',
            'label': f'Equation ({eq_count})',
            'content': content,
            'raw': match.group(0),
            'type': 'display',
            'variables': variables,
            'index': match.start()
        })
        eq_count += 1

    return equations

def extract_tables(text: str) -> List[Dict[str, Any]]:
    tables = []
    tex_table_regex = re.compile(r'\\begin\{table\*?\}([\s\S]*?)\\end\{table\*?\}')
    tab_count = 1

    for match in tex_table_regex.finditer(text):
        raw = match.group(0)
        caption_match = re.search(r'\\caption\{([^}]+)\}', raw)
        caption = caption_match.group(1) if caption_match else f"Table {tab_count}"

        tables.append({
            'id': f'table-{tab_count}',
            'label': f'Table {tab_count}',
            'caption': caption,
            'content': raw,
            'type': 'latex',
            'index': match.start()
        })
        tab_count += 1

    md_table_regex = re.compile(r'(?:\|[^\n]+\|\n)+')
    for match in md_table_regex.finditer(text):
        raw = match.group(0)
        if '|---' in raw or '| ---' in raw:
            tables.append({
                'id': f'table-{tab_count}',
                'label': f'Table {tab_count}',
                'caption': f'Markdown Table {tab_count}',
                'content': raw,
                'type': 'markdown',
                'index': match.start()
            })
            tab_count += 1

    return tables

def extract_figures(text: str) -> List[Dict[str, Any]]:
    figures = []
    tex_fig_regex = re.compile(r'\\begin\{figure\*?\}([\s\S]*?)\\end\{figure\*?\}')
    fig_count = 1

    for match in tex_fig_regex.finditer(text):
        raw = match.group(0)
        caption_match = re.search(r'\\caption\{([^}]+)\}', raw)
        caption = caption_match.group(1) if caption_match else f"Figure {fig_count}"

        figures.append({
            'id': f'fig-{fig_count}',
            'label': f'Figure {fig_count}',
            'caption': caption,
            'content': raw,
            'type': 'latex',
            'index': match.start()
        })
        fig_count += 1

    md_fig_regex = re.compile(r'!\[([^\]]*)\]\([^)]+\)')
    for match in md_fig_regex.finditer(text):
        caption = match.group(1) or f"Figure {fig_count}"
        figures.append({
            'id': f'fig-{fig_count}',
            'label': f'Figure {fig_count}',
            'caption': caption,
            'content': match.group(0),
            'type': 'markdown',
            'index': match.start()
        })
        fig_count += 1

    return figures

def extract_numerical_claims(text: str) -> List[Dict[str, Any]]:
    claims = []
    num_regex = re.compile(r'\b(\d+(?:\.\d+)?(?:%|e-?\d+|\s*(?:ms|GB|MB|params|dim|layers|heads|epochs)\b))', re.IGNORECASE)
    
    for match in num_regex.finditer(text):
        claims.append({
            'value': match.group(1),
            'index': match.start(),
            'type': 'numerical_result'
        })
        
    return claims

def extract_claims(text: str) -> List[Dict[str, Any]]:
    """
    Distinguish between parameter statements, experimental observations, and scientific conclusions.
    Uses basic heuristic matching.
    """
    claims = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    param_regex = re.compile(r'\b(?:set|using|with|learning rate|batch size|epochs|optimizer|adam|sgd|weight decay|momentum|dropout|rank|alpha)\b', re.IGNORECASE)
    obs_regex = re.compile(r'\b(?:achieves|outperforms|decreases|increases|improves|reduces|accuracy|f1|loss)\b', re.IGNORECASE)
    concl_regex = re.compile(r'\b(?:we conclude|demonstrates|shows that|indicates that|suggests|prove)\b', re.IGNORECASE)

    for s in sentences:
        s_clean = s.strip()
        if not s_clean or len(s_clean) < 10:
            continue
            
        claim_type = None
        if concl_regex.search(s_clean):
            claim_type = 'scientific_conclusion'
        elif obs_regex.search(s_clean):
            claim_type = 'experimental_observation'
        elif param_regex.search(s_clean) and any(char.isdigit() for char in s_clean):
            claim_type = 'parameter_statement'
            
        if claim_type:
            claims.append({
                'text': s_clean,
                'type': claim_type
            })

    return claims

def extract_datasets(text: str) -> List[Dict[str, Any]]:
    datasets = []
    # Heuristic dataset names or explicitly marked datasets
    dataset_regex = re.compile(r'\b(?:CIFAR-10|CIFAR-100|ImageNet|MNIST|COCO|WMT|SQuAD|GLUE|SuperGLUE|Kitti|Cityscapes|IMDB)\b', re.IGNORECASE)
    for match in dataset_regex.finditer(text):
        datasets.append({
            'name': match.group(0),
            'index': match.start()
        })
    return datasets

def extract_metrics(text: str) -> List[Dict[str, Any]]:
    metrics = []
    metric_regex = re.compile(r'\b(?:Accuracy|F1|Precision|Recall|BLEU|ROUGE|FID|IS|MSE|MAE|RMSE|IoU)\b', re.IGNORECASE)
    for match in metric_regex.finditer(text):
        metrics.append({
            'name': match.group(0),
            'index': match.start()
        })
    return metrics
