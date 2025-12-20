import sys
import json
import asyncio
import os
import traceback

# Ensure stdout is UTF-8
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    try:
        # 1. Parse arguments (passed via env vars or simple args for simplicity)
        # We'll use env vars for config to avoid complex CLI parsing in this internal script
        prompt = os.environ.get("GPTR_PROMPT")
        report_type = os.environ.get("GPTR_REPORT_TYPE", "research_report")
        tone = os.environ.get("GPTR_TONE")
        retriever = os.environ.get("GPTR_RETRIEVER")
        source_urls_json = os.environ.get("GPTR_SOURCE_URLS")
        
        if not prompt:
            raise ValueError("GPTR_PROMPT environment variable is required")

        # 2. Import GPT Researcher (lazy import to speed up failure if env is wrong)
        try:
            from gpt_researcher import GPTResearcher
        except ImportError:
            print(json.dumps({
                "status": "failed",
                "error": "gpt_researcher package not found. Install it with `pip install gpt-researcher`"
            }))
            sys.exit(1)

        # 3. Configure Researcher
        source_urls = json.loads(source_urls_json) if source_urls_json else None
        
        researcher = GPTResearcher(
            query=prompt,
            report_type=report_type,
            report_source="web", # Default to web
            source_urls=source_urls,
            tone=tone if tone else None, # GPT-R might expect None for default
            retriever=retriever
        )

        # 4. Run Research
        # Print an initial progress event (simple indicator for streaming)
        print(json.dumps({"event": "progress", "status": "starting", "progress": 0.0, "message": "Starting GPT-Researcher"}), flush=True)
        # We can hook into websocket/stream here if we want real-time updates later
        # For now, just run and get the report
        report = await researcher.run()
        
        # 5. Get Context/Costs (if available)
        context = researcher.get_research_context()
        costs = researcher.get_costs() # Returns float or dict? usually float estimate
        
        # 6. Output Result as JSON
        result = {
            "status": "success",
            "content": report,
            "context": context,
            "costs": costs,
            "visited_urls": list(researcher.visited_urls) if hasattr(researcher, "visited_urls") else []
        }
        print(json.dumps(result))

    except Exception as e:
        # Catch-all for crashes
        error_info = {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_info))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
