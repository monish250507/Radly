import time
import json
import re
from typing import List, Dict, Any, Optional

from .groq_client import call_groq_api, UpstreamError
from .logger import paperblast_logger as logger
from .status_model import resolve_overall_status, derive_risk_level
from ..domain.models import VerificationStatus
from ..domain.factories import (
    build_artifact_index, evidence_from_static_matches, evidence_from_ai_sections,
    findings_from_ai_sections, findings_from_static_sections, make_analysis_version,
    make_research_project
)

import uuid
from datetime import datetime
from ..domain.models import ResearchProject, ImpactFinding, VerificationStatus, ArtifactType

VALID_RISKS = {'CRITICAL', 'HIGH', 'MAJOR', 'MINOR'}

def compare_graphs(base_project: ResearchProject, proposed_project: ResearchProject) -> List[ImpactFinding]:
    """
    Diffs two versions of a research project to identify changed artifacts 
    and traces downstream deterministic dependencies.
    """
    findings = []
    
    base_artifacts = {}
    for art in base_project.artifacts.code + base_project.artifacts.sections + base_project.artifacts.equations + base_project.artifacts.tables:
        base_artifacts[art.artifactId] = art
        
    proposed_artifacts = {}
    for art in proposed_project.artifacts.code + proposed_project.artifacts.sections + proposed_project.artifacts.equations + proposed_project.artifacts.tables:
        proposed_artifacts[art.artifactId] = art
        
    changed_artifact_ids = set()
    for art_id, prop_art in proposed_artifacts.items():
        if art_id not in base_artifacts:
            changed_artifact_ids.add(art_id)
        elif base_artifacts[art_id].contentHash != prop_art.contentHash:
            changed_artifact_ids.add(art_id)
            
    adjacency = {}
    for ev in proposed_project.evidenceRecords:
        if ev.sourceArtifactId and ev.targetArtifactId:
            if ev.sourceArtifactId not in adjacency:
                adjacency[ev.sourceArtifactId] = []
            adjacency[ev.sourceArtifactId].append(ev)
            
    visited = set()
    
    def traverse(art_id: str, path: List[str]):
        if art_id in visited:
            return
        visited.add(art_id)
        
        art = proposed_artifacts.get(art_id)
        if art:
            finding = ImpactFinding(
                findingId=f"find_{uuid.uuid4().hex[:8]}",
                changeReference="Code/Data Change",
                affectedArtifactId=art_id,
                affectedArtifactType=art.artifactType.value,
                affectedTitle=art.title or art.symbolName or art.artifactId,
                status=VerificationStatus.AFFECTED if path else VerificationStatus.NO_DEPENDENCY_FOUND,
                risk="HIGH" if art.artifactType in [ArtifactType.CLAIM, ArtifactType.RESULT] else "LOW",
                reason=f"Impacted by upstream change in {path[0]}" if path else "Directly changed",
                evidencePath=path + [art_id],
                createdAt=datetime.utcnow().isoformat() + "Z"
            )
            findings.append(finding)
            
        for edge in adjacency.get(art_id, []):
            traverse(edge.targetArtifactId, path + [art_id])
            
    for changed_id in changed_artifact_ids:
        traverse(changed_id, [])
        
    return findings

def is_valid_risk(r: Any) -> bool:
    return isinstance(r, str) and r.upper() in VALID_RISKS

def truncate_at_sentence(text: str, max_chars: int = 350) -> str:
    if not isinstance(text, str):
        return ''
    trimmed = text.strip()
    if len(trimmed) <= max_chars:
        return trimmed
    sliced = trimmed[:max_chars]
    last_period = sliced.rfind('.')
    if last_period > 60:
        return sliced[:last_period + 1]
    last_space = sliced.rfind(' ')
    if last_space > 60:
        return sliced[:last_space] + '.'
    return sliced + '.'

def match_symbols_to_paper(code_symbols: List[Dict[str, Any]], paper_ast: Dict[str, Any], change_query: str) -> List[Dict[str, Any]]:
    matches = []
    seen_edge_keys = set()
    query_lower = (change_query or '').lower()
    sections = paper_ast.get('sections', [])

    words = [w for w in re.split(r'\W+', query_lower) if len(w) > 3]
    for sec in sections:
        sec_text = (sec.get('text') or '').lower()
        sec_title = (sec.get('title') or '').lower()
        for w in words:
            if w in sec_text or w in sec_title:
                edge_key = f"query:{w}->{sec.get('id')}"
                if edge_key not in seen_edge_keys:
                    seen_edge_keys.add(edge_key)
                    matches.append({
                        'symbol': f"Query Keyword ({w})",
                        'target': sec.get('title'),
                        'targetId': sec.get('id'),
                        'targetType': 'Section',
                        'evidenceBasis': 'keyword_match',
                        'verification': VerificationStatus.NEEDS_REVIEW,
                        'reason': f"Query keyword '{w}' appears in section '{sec.get('title')}' (keyword overlap, not deterministic proof)"
                    })

    for sym in (code_symbols or []):
        symbol_str = sym.get('symbol', '')
        if not symbol_str:
            continue

        symbol_regex = None
        try:
            if len(symbol_str) <= 2:
                symbol_regex = re.compile(rf"\b{re.escape(symbol_str)}\b", re.IGNORECASE)
            else:
                symbol_regex = re.compile(re.escape(symbol_str), re.IGNORECASE)
        except Exception:
            pass

        for sec in sections:
            sec_text = sec.get('text', '')
            has_match = bool(symbol_regex.search(sec_text)) if symbol_regex else symbol_str.lower() in sec_text.lower()
            if has_match:
                edge_key = f"{sym.get('file')}:{sym.get('line')}:{sym.get('symbol')}->{sec.get('id')}"
                if edge_key not in seen_edge_keys:
                    seen_edge_keys.add(edge_key)
                    matches.append({
                        'symbol': f"{sym.get('file')}:{sym.get('line')} ({sym.get('symbol')})",
                        'target': sec.get('title'),
                        'targetId': sec.get('id'),
                        'targetType': 'Section',
                        'evidenceBasis': 'ast_symbol',
                        'verification': VerificationStatus.NEEDS_REVIEW,
                        'reason': f"Symbol '{sym.get('symbol')}' from {sym.get('file')}:{sym.get('line')} appears in section '{sec.get('title')}' (text presence, not call-graph proof)"
                    })

        for eq in paper_ast.get('equations', []):
            if symbol_regex and symbol_regex.search(eq.get('content', '')):
                edge_key = f"{sym.get('file')}:{sym.get('line')}:{sym.get('symbol')}->{eq.get('id')}"
                if edge_key not in seen_edge_keys:
                    seen_edge_keys.add(edge_key)
                    matches.append({
                        'symbol': f"{sym.get('file')}:{sym.get('line')} ({sym.get('symbol')})",
                        'target': eq.get('label'),
                        'targetId': eq.get('id'),
                        'targetType': 'Equation',
                        'evidenceBasis': 'ast_symbol',
                        'verification': VerificationStatus.NEEDS_REVIEW,
                        'reason': f"Symbol '{sym.get('symbol')}' found in equation content '{eq.get('label')}' (text presence only)"
                    })

    return matches

def validate_ai_sections(ai_sections: List[Any], paper_ast: Dict[str, Any]) -> tuple:
    sections = paper_ast.get('sections', [])
    section_index = {s['id']: s for s in sections}
    valid = []
    invalid = []

    if not isinstance(ai_sections, list):
        return valid, invalid

    for item in ai_sections:
        if not isinstance(item, dict):
            invalid.append({'item': item, 'reason': 'not_an_object'})
            continue

        section_id = item.get('section_id')
        resolved_section = section_index.get(section_id)

        if not resolved_section:
            invalid.append({'item': item, 'reason': 'section_id_not_in_paperAST', 'section_id': section_id})
            continue

        risk = item.get('risk').upper() if is_valid_risk(item.get('risk')) else None
        if not risk:
            invalid.append({'item': item, 'reason': 'invalid_risk_value', 'value': item.get('risk')})
            valid.append({
                'section_id': resolved_section['id'],
                'title': resolved_section['title'],
                'risk': 'MINOR',
                'verification': VerificationStatus.UNABLE_TO_VERIFY.value,
                'evidence_basis': 'ai_synthesized',
                'reason': item.get('reason') or '(AI reason not provided)',
                'current_text': truncate_at_sentence(resolved_section.get('text', ''), 350),
                'suggested_text': truncate_at_sentence(str(item.get('suggested_text')), 350) if item.get('suggested_text') else None
            })
            continue

        reason = item.get('reason')
        valid.append({
            'section_id': resolved_section['id'],
            'title': resolved_section['title'],
            'risk': risk,
            'verification': VerificationStatus.NEEDS_REVIEW.value,
            'evidence_basis': 'ai_synthesized',
            'reason': reason.strip() if isinstance(reason, str) and reason.strip() else '(AI did not provide a reason)',
            'current_text': truncate_at_sentence(resolved_section.get('text', ''), 350),
            'suggested_text': truncate_at_sentence(str(item.get('suggested_text')), 350) if item.get('suggested_text') else None
        })

    return valid, invalid

def validate_ai_equations_or_tables(ai_items: List[Any], real_items: List[Dict[str, Any]], id_prefix: str) -> List[Dict[str, Any]]:
    if not isinstance(ai_items, list) or not isinstance(real_items, list):
        return []
    real_ids = {x['id'] for x in real_items}
    valid = []
    for item in ai_items:
        if item and item.get('id') in real_ids:
            risk = item.get('risk').upper() if is_valid_risk(item.get('risk')) else 'MINOR'
            explanation = item.get('explanation')
            valid.append({
                'id': item.get('id'),
                'label': item.get('label') or item.get('id'),
                'risk': risk,
                'verification': VerificationStatus.NEEDS_REVIEW.value,
                'evidence_basis': 'ai_synthesized',
                'explanation': explanation.strip() if isinstance(explanation, str) else '(AI did not provide an explanation)'
            })
    return valid

def build_honest_agent_trace(
    code_symbols_count: int,
    sections_count: int,
    equations_count: int,
    static_match_count: int,
    engine_mode: str,
    ai_valid_sections: int,
    ai_invalid_sections: int
) -> List[Dict[str, str]]:
    trace = [
        {
            'agent': 'Code AST Dependency Agent',
            'role': 'Program Analysis & Symbol Extraction',
            'output_summary': f"Indexed {code_symbols_count} AST symbols across source files."
        },
        {
            'agent': 'Manuscript Impact Analyst Agent',
            'role': 'Paper AST Parsing & Equation Matching',
            'output_summary': f"Parsed {sections_count} manuscript sections and {equations_count} equations. Found {static_match_count} keyword/symbol overlaps (NEEDS_REVIEW)."
        }
    ]

    if engine_mode == 'ai_synthesized':
        trace.append({
            'agent': 'Skeptic Verification Arbiter Agent',
            'role': 'AI Output Validation & Section Reconciliation',
            'output_summary': f"AI synthesis ran. Validated {ai_valid_sections} sections against paperAST; rejected {ai_invalid_sections} sections with unresolvable IDs or invalid fields."
        })
    else:
        trace.append({
            'agent': 'Skeptic Verification Arbiter Agent',
            'role': 'Static AST Reachability (AI Unavailable)',
            'output_summary': "AI synthesis did not run. Returning deterministic keyword/symbol overlap findings only. All results are NEEDS_REVIEW at best."
        })

    return trace

def build_analysis_failed_result(start_time, code_symbols, paper_ast, static_matches, error_summary, analysis_version, artifact_index, section_artifact_map, query_or_code_change):
    from ..domain.models import VerificationStatus
    
    lineage_graph = [{
        'source': m['symbol'],
        'target': m['target'],
        'relationship': m['reason'],
        'verification': m['verification'].value if hasattr(m['verification'], 'value') else m['verification']
    } for m in static_matches[:8]]
    
    # Domain build
    sym_key_map = {m['symbol']: None for m in static_matches}
    evidence_res = evidence_from_static_matches(static_matches, section_artifact_map, sym_key_map, analysis_version.versionId)
    static_evidence = evidence_res["evidenceRecords"]
    
    # Empty static_affected_sections since no finding is actually reported in the legacy response
    findings = findings_from_static_sections([], section_artifact_map, static_evidence, query_or_code_change, analysis_version.versionId)
    
    domain_project = make_research_project(
        analysisVersion=analysis_version,
        artifacts=artifact_index,
        evidenceRecords=static_evidence,
        findings=findings,
        query=query_or_code_change,
        overallStatus=VerificationStatus.ANALYSIS_FAILED
    )

    return {
        'status': VerificationStatus.ANALYSIS_FAILED.value,
        'engine': {
            'mode': 'static_fallback',
            'error_summary': error_summary
        },
        'overall_impact_score': None,
        'risk_level': 'NONE',
        'confidence_score': None,
        'execution_time_ms': int((time.time() - start_time) * 1000),
        'cost_efficiency': {
            'tokens_used_est': None,
            'estimated_cost_usd': 0.00,
            'hardware_accelerator': 'N/A'
        },
        'impact_summary': {
            'sections_affected': 0,
            'equations_affected': 0,
            'tables_affected': 0
        },
        'affected_sections': [],
        'affected_equations': [],
        'affected_tables': [],
        'lineage_graph': lineage_graph,
        'agent_collaboration_trace': build_honest_agent_trace(
            len(code_symbols or []),
            len(paper_ast.get('sections', [])),
            len(paper_ast.get('equations', [])),
            len(static_matches),
            'static_fallback',
            0,
            0
        ),
        'domain': domain_project.model_dump()
    }

async def calculate_blast_radius(code_symbols: List[Dict[str, Any]], paper_ast: Dict[str, Any], query_or_code_change: str, opts: Dict[str, Any] = None) -> Dict[str, Any]:
    start_time = time.time()
    opts = opts or {}
    repo_url = opts.get('repoUrl')
    manuscript_id = opts.get('manuscriptId')

    artifact_index = build_artifact_index(code_symbols, paper_ast, repo_url, manuscript_id)
    section_artifact_map = {a.sectionId: a.artifactId for a in artifact_index.sectionArtifacts if a.sectionId}
    
    server_info = {"version": "1.0.0"} # mock
    analysis_version = make_analysis_version(code_symbols, paper_ast, server_info, repo_url, manuscript_id)

    static_matches = match_symbols_to_paper(code_symbols, paper_ast, query_or_code_change)

    sections = paper_ast.get('sections', [])
    equations = paper_ast.get('equations', [])
    tables = paper_ast.get('tables', [])

    system_prompt = """You are a Skeptic Verification Arbiter that evaluates whether a proposed code or parameter change affects sections of a research paper.

Your job is to return ONLY the sections you can provide a specific, substantiated reason for. If you cannot identify a clear dependency, return an empty affected_sections array.

STRICT RULES:
- Only include sections whose section_id exactly matches one of the provided section IDs.
- Do not invent section IDs.
- Do not force-include sections just to have results.
- If no section is clearly affected, return affected_sections as [].
- overall_impact_score should reflect genuine concern (0 = no impact found, 100 = catastrophic).
- Do not fabricate. If uncertain, omit.

Output must be a valid JSON object:
{
  "overall_impact_score": <number 0-100 or null if genuinely unknown>,
  "risk_level": "<CRITICAL | HIGH | MAJOR | MINOR | NONE>",
  "affected_sections": [
    {
      "section_id": "<exact id from input sections list>",
      "title": "<string>",
      "risk": "<CRITICAL | HIGH | MAJOR | MINOR>",
      "reason": "<specific, substantiated reason — not generic>",
      "suggested_text": "<optional revised text>"
    }
  ],
  "affected_equations": [
    { "id": "<exact id from input>", "label": "<string>", "risk": "<CRITICAL|HIGH|MAJOR|MINOR>", "explanation": "<string>" }
  ],
  "affected_tables": [
    { "id": "<exact id from input>", "label": "<string>", "risk": "<CRITICAL|HIGH|MAJOR|MINOR>", "explanation": "<string>" }
  ],
  "lineage_graph": [
    { "source": "<Code Symbol / File:Line>", "target": "<Paper Section>", "relationship": "<string>" }
  ]
}"""

    compact_symbols = [{
        'symbol': s.get('symbol'),
        'type': s.get('type'),
        'value': str(s.get('value', ''))[:40],
        'file': s.get('file'),
        'line': s.get('line')
    } for s in (code_symbols or [])[:10]]

    compact_sections = [{
        'id': s.get('id'),
        'title': s.get('title'),
        'textSnippet': truncate_at_sentence(s.get('text', ''), 200)
    } for s in sections[:8]]

    compact_equations = [{
        'id': eq.get('id'),
        'label': eq.get('label'),
        'content': str(eq.get('content', ''))[:80]
    } for eq in equations[:4]]

    static_matches_compact = [{
        'symbol': m['symbol'],
        'section': m['target'],
        'basis': m['evidenceBasis']
    } for m in static_matches[:6]]

    user_prompt = f"""[PROPOSED CHANGE]:
"{query_or_code_change}"

[CODE AST SYMBOLS]:
{json.dumps(compact_symbols, indent=2)}

[PAPER SECTIONS] (use these exact section_id values only):
{json.dumps(compact_sections, indent=2)}

[PAPER EQUATIONS]:
{json.dumps(compact_equations, indent=2)}

[STATIC KEYWORD/SYMBOL OVERLAPS DETECTED]:
{json.dumps(static_matches_compact, indent=2)}

Return a JSON object. Only include sections you can provide a substantiated reason for. Return affected_sections: [] if nothing is clearly affected."""

    ai_result = None
    engine_mode = 'static_fallback'
    groq_error = None

    try:
        ai_result = await call_groq_api([{'role': 'user', 'content': user_prompt}], system_prompt, True)
        engine_mode = 'ai_synthesized'
    except Exception as err:
        groq_error = err
        logger.warn('Groq synthesis unavailable', {'reason': str(err)})

    if groq_error is not None:
        lineage_graph = [{
            'source': m['symbol'],
            'target': m['target'],
            'relationship': m['reason'],
            'verification': m['verification'].value if hasattr(m['verification'], 'value') else m['verification']
        } for m in static_matches[:8]]

        static_section_ids = list(set([m['targetId'] for m in static_matches if m['targetType'] == 'Section' and any(s['id'] == m['targetId'] for s in sections)]))

        static_affected_sections = []
        for sid in static_section_ids:
            sec = next(s for s in sections if s['id'] == sid)
            matches_for_sec = [m for m in static_matches if m['targetId'] == sid]
            static_affected_sections.append({
                'section_id': sec['id'],
                'title': sec['title'],
                'risk': 'MINOR',
                'verification': VerificationStatus.NEEDS_REVIEW.value,
                'evidence_basis': 'keyword_match',
                'reason': ' | '.join([m['reason'] for m in matches_for_sec]),
                'current_text': truncate_at_sentence(sec.get('text', ''), 350),
                'suggested_text': None
            })

        overall_status = resolve_overall_status(True, 0, len(static_affected_sections), 0, False)

        sym_key_map = {m['symbol']: None for m in static_matches}
        evidence_res = evidence_from_static_matches(static_matches, section_artifact_map, sym_key_map, analysis_version.versionId)
        static_evidence = evidence_res["evidenceRecords"]
        
        findings = findings_from_static_sections(static_affected_sections, section_artifact_map, static_evidence, query_or_code_change, analysis_version.versionId)

        domain_project = make_research_project(
            analysisVersion=analysis_version,
            artifacts=artifact_index,
            evidenceRecords=static_evidence,
            findings=findings,
            query=query_or_code_change,
            overallStatus=overall_status
        )

        return {
            'status': VerificationStatus.ANALYSIS_FAILED.value,
            'engine': {
                'mode': 'static_fallback',
                'error_summary': str(groq_error),
                'note': 'AI synthesis failed. The following results are from deterministic keyword/symbol overlap only and require human review.'
            },
            'overall_impact_score': None,
            'risk_level': 'NONE',
            'confidence_score': None,
            'execution_time_ms': int((time.time() - start_time) * 1000),
            'cost_efficiency': {
                'tokens_used_est': None,
                'estimated_cost_usd': 0.00,
                'hardware_accelerator': 'N/A — AI synthesis failed'
            },
            'impact_summary': {
                'sections_affected': len(static_affected_sections),
                'equations_affected': 0,
                'tables_affected': 0
            },
            'affected_sections': static_affected_sections,
            'affected_equations': [],
            'affected_tables': [],
            'lineage_graph': lineage_graph,
            'agent_collaboration_trace': build_honest_agent_trace(
                len(code_symbols or []),
                len(sections),
                len(equations),
                len(static_matches),
                'static_fallback',
                0, 0
            ),
            'domain': domain_project.model_dump()
        }

    if not isinstance(ai_result, dict):
        logger.error('AI returned non-object response', {'type': type(ai_result).__name__})
        return build_analysis_failed_result(start_time, code_symbols, paper_ast, static_matches, 'AI returned non-object response', analysis_version, artifact_index, section_artifact_map, query_or_code_change)

    valid_sections, invalid_sections = validate_ai_sections(ai_result.get('affected_sections', []), paper_ast)
    valid_equations = validate_ai_equations_or_tables(ai_result.get('affected_equations', []), equations, 'eq')
    valid_tables = validate_ai_equations_or_tables(ai_result.get('affected_tables', []), tables, 'table')

    if invalid_sections:
        logger.warn('AI returned sections with unresolvable or invalid IDs', {
            'count': len(invalid_sections)
        })

    raw_score = ai_result.get('overall_impact_score')
    impact_score = round(raw_score) if isinstance(raw_score, (int, float)) and 0 <= raw_score <= 100 else None

    risk_level = 'NONE'
    ai_risk = ai_result.get('risk_level')
    if isinstance(ai_risk, str) and ai_risk.upper() in VALID_RISKS:
        risk_level = ai_risk.upper()
    elif valid_sections:
        coverage_ratio = len(valid_sections) / max(len(sections), 1)
        all_likely = all(s['verification'] == VerificationStatus.NEEDS_REVIEW.value for s in valid_sections)
        risk_level = derive_risk_level(coverage_ratio, all_likely)

    if isinstance(ai_result.get('lineage_graph'), list) and len(ai_result['lineage_graph']) > 0:
        lineage_graph = [{
            'source': str(e.get('source', '')),
            'target': str(e.get('target', '')),
            'relationship': str(e.get('relationship', '')),
            'verification': VerificationStatus.NEEDS_REVIEW.value
        } for e in ai_result['lineage_graph']]
    else:
        lineage_graph = [{
            'source': m['symbol'],
            'target': m['target'],
            'relationship': m['reason'],
            'verification': m['verification'].value if hasattr(m['verification'], 'value') else m['verification']
        } for m in static_matches[:8]]

    overall_status = resolve_overall_status(False, 0, len(valid_sections), len(invalid_sections), True)

    # Domain build
    sym_key_map = {m['symbol']: None for m in static_matches}
    evidence_res = evidence_from_static_matches(static_matches, section_artifact_map, sym_key_map, analysis_version.versionId)
    static_evidence = evidence_res["evidenceRecords"]
    
    ai_evidence = evidence_from_ai_sections(valid_sections, section_artifact_map, query_or_code_change, analysis_version.versionId)
    all_evidence = static_evidence + ai_evidence
    
    findings = findings_from_ai_sections(valid_sections, section_artifact_map, ai_evidence, query_or_code_change, analysis_version.versionId)

    domain_project = make_research_project(
        analysisVersion=analysis_version,
        artifacts=artifact_index,
        evidenceRecords=all_evidence,
        findings=findings,
        query=query_or_code_change,
        overallStatus=overall_status
    )

    return {
        'status': overall_status.value if hasattr(overall_status, 'value') else overall_status,
        'engine': {
            'mode': 'ai_synthesized',
            'fallback_reason': None,
            'validation_summary': {
                'sections_accepted': len(valid_sections),
                'sections_rejected': len(invalid_sections),
                'equations_accepted': len(valid_equations),
                'tables_accepted': len(valid_tables)
            }
        },
        'overall_impact_score': impact_score,
        'risk_level': risk_level,
        'confidence_score': None,
        'execution_time_ms': int((time.time() - start_time) * 1000),
        'cost_efficiency': {
            'tokens_used_est': None,
            'estimated_cost_usd': 0.00,
            'hardware_accelerator': 'Groq LPU Inference Engine'
        },
        'impact_summary': {
            'sections_affected': len(valid_sections),
            'equations_affected': len(valid_equations),
            'tables_affected': len(valid_tables)
        },
        'affected_sections': valid_sections,
        'affected_equations': valid_equations,
        'affected_tables': valid_tables,
        'lineage_graph': lineage_graph,
        'agent_collaboration_trace': build_honest_agent_trace(
            len(code_symbols or []),
            len(sections),
            len(equations),
            len(static_matches),
            'ai_synthesized',
            len(valid_sections),
            len(invalid_sections)
        ),
        'domain': domain_project.model_dump()
    }
