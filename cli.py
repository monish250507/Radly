import argparse
import os
import sys
import time
import httpx

API_URL = os.getenv("PAPERBLAST_API_URL", "http://localhost:5000/api")

def ingest_cmd(args):
    url = f"{API_URL}/ingest-github"
    print(f"Ingesting repository: {args.repo}...")
    try:
        r = httpx.post(url, json={"repoUrl": args.repo}, timeout=30.0)
        r.raise_for_status()
        data = r.json()
        print(f"Success! Found {data.get('fileCount')} files.")
    except Exception as e:
        print(f"Error ingesting repository: {e}")
        sys.exit(1)

def analyze_cmd(args):
    url = f"{API_URL}/jobs/analyze"
    print(f"Starting analysis for PR Diff... (Mocked files payload)")
    payload = {
        "files": [],
        "paper": {"content": "mock content"},
        "changeQuery": "mock diff"
    }
    try:
        r = httpx.post(url, json=payload, timeout=10.0)
        r.raise_for_status()
        job_id = r.json().get("jobId")
        print(f"Job Queued. Job ID: {job_id}")
        
        # Poll
        status_url = f"{API_URL}/jobs/{job_id}"
        while True:
            resp = httpx.get(status_url, timeout=5.0)
            resp.raise_for_status()
            job = resp.json()
            status = job.get("status")
            print(f"Status: {status}")
            if status in ["READY", "FAILED"]:
                print(f"Final Result: {job.get('result') or job.get('error')}")
                break
            time.sleep(2)
            
    except Exception as e:
        print(f"Error during analysis: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="PaperBlast CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # Ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest a GitHub repository")
    ingest_p.add_argument("repo", help="GitHub repo URL")
    
    # Analyze
    analyze_p = subparsers.add_parser("analyze", help="Analyze a diff or PR")
    analyze_p.add_argument("diff", help="Diff payload or PR link")
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        ingest_cmd(args)
    elif args.command == "analyze":
        analyze_cmd(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
