import argparse
import os
import sys
import time
import httpx

API_URL = os.getenv("RADLY_API_URL", "http://localhost:5000/api")


def ingest_cmd(args):
    url = f"{API_URL}/ingest-github"
    print(f"Ingesting repository: {args.repo}...")
    try:
        r = httpx.post(url, json={"repoUrl": args.repo}, timeout=30.0)
        r.raise_for_status()
        data = r.json()
        print(f"Success! Found {data.get('fileCount')} files, {len(data.get('symbols', []))} symbols.")
    except Exception as e:
        print(f"Error ingesting repository: {e}")
        sys.exit(1)


def analyze_cmd(args):
    """
    P0 FIX: No more mock payload. This command requires:
      --repo   A GitHub repo URL or local path (submitted via /api/ingest-github)
      --paper  Path to the paper file (txt/pdf/docx)
      --query  The change description / diff / PR query

    Without real inputs the command refuses with a clear error.
    """
    # Validate required arguments
    if not args.repo:
        print("ERROR: --repo is required. Provide a GitHub URL or local repo path.")
        print("  Example: radly analyze --repo https://github.com/org/repo --paper paper.txt --query 'changed learning_rate from 0.01 to 0.001'")
        sys.exit(1)
    if not args.paper:
        print("ERROR: --paper is required. Provide the path to the research paper file.")
        sys.exit(1)
    if not args.query:
        print("ERROR: --query is required. Describe the code change or diff.")
        sys.exit(1)

    # Step 1: Ingest the repository to get code symbols
    print(f"Step 1/3: Ingesting repository {args.repo}...")
    try:
        ingest_url = f"{API_URL}/ingest-github"
        ingest_resp = httpx.post(ingest_url, json={"repoUrl": args.repo}, timeout=60.0)
        ingest_resp.raise_for_status()
        ingest_data = ingest_resp.json()
        code_symbols = ingest_data.get("symbols", [])
        print(f"  → Found {len(code_symbols)} code symbols from {ingest_data.get('fileCount', 0)} files.")
    except Exception as e:
        print(f"Error ingesting repository: {e}")
        sys.exit(1)

    # Step 2: Read and parse the paper
    print(f"Step 2/3: Reading paper from {args.paper}...")
    if not os.path.exists(args.paper):
        print(f"ERROR: Paper file not found: {args.paper}")
        sys.exit(1)
    try:
        with open(args.paper, "r", encoding="utf-8", errors="replace") as f:
            paper_content = f.read()
        file_ext = os.path.splitext(args.paper)[1].lstrip(".") or "txt"
        parse_url = f"{API_URL}/parse-paper"
        parse_resp = httpx.post(parse_url, json={"documentBuffer": paper_content, "fileType": file_ext}, timeout=30.0)
        parse_resp.raise_for_status()
        paper_ast = parse_resp.json().get("paperAST", {})
        sections = len(paper_ast.get("sections", []))
        equations = len(paper_ast.get("equations", []))
        print(f"  → Parsed {sections} sections, {equations} equations.")
    except Exception as e:
        print(f"Error parsing paper: {e}")
        sys.exit(1)

    # Step 3: Submit real analysis job
    print(f"Step 3/3: Submitting impact analysis for query: '{args.query}'...")
    analyze_url = f"{API_URL}/jobs/analyze"
    payload = {
        "files": [],         # symbols already ingested; passed via code_symbols in direct mode
        "paper": {"content": paper_content, "fileType": file_ext},
        "changeQuery": args.query,
        "options": {"repoUrl": args.repo}
    }
    try:
        r = httpx.post(analyze_url, json=payload, timeout=30.0)
        r.raise_for_status()
        job_id = r.json().get("jobId")
        print(f"Job queued. Job ID: {job_id}")

        # Poll for result
        status_url = f"{API_URL}/jobs/{job_id}"
        while True:
            resp = httpx.get(status_url, timeout=10.0)
            resp.raise_for_status()
            job = resp.json()
            status = job.get("status")
            progress = (job.get("result") or {}).get("_progress", "")
            print(f"  Status: {status}{f' ({progress})' if progress else ''}")
            if status == "READY":
                result = job.get("result", {})
                print(f"\n=== Analysis Complete ===")
                print(f"  Overall status   : {result.get('status')}")
                print(f"  Risk level       : {result.get('risk_level')}")
                print(f"  Sections affected: {result.get('impact_summary', {}).get('sections_affected', 0)}")
                print(f"  Equations        : {result.get('impact_summary', {}).get('equations_affected', 0)}")
                for sec in result.get("affected_sections", [])[:5]:
                    print(f"    [{sec.get('risk')}] {sec.get('title')} — {sec.get('reason', '')[:80]}")
                break
            elif status == "FAILED":
                print(f"\nAnalysis FAILED: {job.get('error')}")
                sys.exit(1)
            time.sleep(2)

    except Exception as e:
        print(f"Error during analysis: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Radly CLI — trace code changes to research paper impact",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  radly ingest --repo https://github.com/org/repo
  radly analyze --repo https://github.com/org/repo --paper paper.txt --query "changed learning_rate from 0.01 to 0.001"
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # Ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest a GitHub repository")
    ingest_p.add_argument("--repo", required=True, help="GitHub repo URL")

    # Analyze — P0 FIX: requires real --repo, --paper, --query
    analyze_p = subparsers.add_parser("analyze", help="Analyze the impact of a code change on a research paper")
    analyze_p.add_argument("--repo", required=True, help="GitHub repo URL or local path")
    analyze_p.add_argument("--paper", required=True, help="Path to research paper file (.txt, .pdf, .docx)")
    analyze_p.add_argument("--query", required=True, help="Code change description, diff, or PR query")

    args = parser.parse_args()

    if args.command == "ingest":
        ingest_cmd(args)
    elif args.command == "analyze":
        analyze_cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
