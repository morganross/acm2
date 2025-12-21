import asyncio
import json
from app.infra.db.session import async_session_factory
from app.infra.db.repositories import RunRepository

async def main():
    run_id = "220ddff1-aea8-4596-9c18-54ddb44493a5"
    async with async_session_factory() as session:
        repo = RunRepository(session)
        run = await repo.get_with_tasks(run_id)
        if run:
            print(f"Updating run {run.id}...")
            
            # Construct generated_docs
            generated_docs = [
                {
                    "id": "7469e725.662f.fpf.1.google_gemini-3-pro-preview",
                    "model": "google:gemini-3-pro-preview",
                    "source_doc_id": "0dd19fd9-45f8-456a-822f-44517469e725",
                    "generator": "fpf",
                    "iteration": 1
                }
            ]
            
            # Update results_summary
            if run.results_summary:
                new_summary = dict(run.results_summary)
                new_summary["generated_docs"] = generated_docs
                
                # Also ensure other missing keys are present if needed
                # But generated_docs is the critical one for the UI list
                
                run.results_summary = new_summary
                
                # Force update
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(run, "results_summary")
                
                await session.commit()
                print("Run updated successfully.")
                
                # Verify
                await session.refresh(run)
                print("Keys after update:", run.results_summary.keys())
            else:
                print("results_summary is None!")
        else:
            print("Run not found")

if __name__ == "__main__":
    asyncio.run(main())
