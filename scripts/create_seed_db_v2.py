"""
Create seed.db for ACM2 new user initialization.
Uses SQLAlchemy models to ensure schema compatibility.

This is the CORRECT way to create seed.db - using the ORM, not raw SQL.

Usage:
    cd c:\devlop\acm2\acm2
    python -m scripts.create_seed_db_v2
    
Or directly:
    cd c:\devlop\acm2
    python scripts\create_seed_db_v2.py
"""
import sys
import os
from pathlib import Path

# Add the acm2 directory to sys.path so we can import app modules
SCRIPT_DIR = Path(__file__).parent.resolve()
ACM2_DIR = SCRIPT_DIR.parent / "acm2"
if str(ACM2_DIR) not in sys.path:
    sys.path.insert(0, str(ACM2_DIR))

from datetime import datetime
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base and all models - this also registers them with Base.metadata
from app.infra.db.models import (
    Base,
    Preset,
    Content, 
    ContentType,
    Run,
    Document,
    Task,
    Artifact,
    GitHubConnection,
    ProviderKey,
    UsageStats,
    UserMeta,
    UserSettings,
)

# Output path
SEED_DB_PATH = Path(__file__).parent.parent / "acm2" / "data" / "seed.db"

def main():
    # Ensure directory exists
    SEED_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing seed.db and WAL files if present
    for suffix in ["", "-shm", "-wal"]:
        path = Path(f"{SEED_DB_PATH}{suffix}")
        if path.exists():
            path.unlink()
            print(f"Removed existing {path}")
    
    # Create engine with synchronous SQLite
    engine = create_engine(f"sqlite:///{SEED_DB_PATH}", echo=False)
    
    # Create all tables using SQLAlchemy metadata
    print("Creating tables from SQLAlchemy models...")
    Base.metadata.create_all(engine)
    print("Tables created successfully")
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # ============================================================================
        # SEED DATA - IDs
        # ============================================================================
        PRESET_ID = "86f721fc-742c-4489-9626-f148cb3d6209"
        CONTENT_GEN_ID = str(uuid.uuid4())
        CONTENT_SINGLE_EVAL_ID = str(uuid.uuid4())
        CONTENT_PAIRWISE_EVAL_ID = str(uuid.uuid4())
        CONTENT_CRITERIA_ID = str(uuid.uuid4())
        CONTENT_COMBINE_ID = str(uuid.uuid4())
        SAMPLE_INPUT_ID = str(uuid.uuid4())
        
        now = datetime.utcnow()
        
        # ============================================================================
        # CONTENT: Generation Instructions
        # ============================================================================
        gen_instructions = Content(
            id=CONTENT_GEN_ID,
            user_id=None,  # Seed data has no user
            created_at=now,
            name="Default Generation Instructions",
            content_type=ContentType.GENERATION_INSTRUCTIONS.value,
            body="""You are tasked with generating comprehensive, accurate, and well-structured content based on a provided input document. Your generation MUST incorporate mandatory web searches to enhance accuracy and add current information.

## MANDATORY WEB SEARCH REQUIREMENT
You MUST perform web searches during generation to:
1. Verify facts and claims from the source document
2. Find current/updated information on the topics discussed
3. Add relevant context that enhances the content
4. Ensure accuracy of any statistics, dates, or factual claims

## Output Requirements
1. Maintain the core message and intent of the original document
2. Enhance with verified, current information from web searches
3. Structure content logically with clear sections
4. Include proper citations for web-sourced information
5. Ensure factual accuracy through verification

## Format Guidelines
- Use clear headings and subheadings
- Include bullet points for lists when appropriate
- Cite sources for any externally verified information
- Maintain professional, clear language

Generate a comprehensive version of the content that incorporates verified information from web searches.""",
            variables={},
            description="Default generation instructions with mandatory web search",
            tags=["default", "generation"],
        )
        session.add(gen_instructions)
        print(f"Created content: {gen_instructions.name}")
        
        # ============================================================================
        # CONTENT: Single Evaluation Instructions
        # ============================================================================
        single_eval = Content(
            id=CONTENT_SINGLE_EVAL_ID,
            user_id=None,
            created_at=now,
            name="Default Single Evaluation Instructions",
            content_type=ContentType.SINGLE_EVAL_INSTRUCTIONS.value,
            body="""You are an expert content evaluator. Your task is to evaluate a single generated content piece against the original source document. You MUST use web searches to verify factual claims.

## MANDATORY WEB SEARCH REQUIREMENT
You MUST perform web searches to:
1. Verify any factual claims, statistics, or data points
2. Check if information is current and accurate
3. Validate any cited sources or references
4. Identify potential misinformation or outdated content

## Evaluation Process
1. Compare the generated content against the source document
2. Use web searches to verify key factual claims
3. Assess accuracy, completeness, and quality
4. Score according to the provided criteria
5. Provide specific, actionable feedback

## Output Format
Provide your evaluation as a structured assessment with:
- Overall score (1-10)
- Scores for each criterion
- Specific feedback on strengths
- Specific feedback on areas for improvement
- Notes on any factual inaccuracies found via web search""",
            variables={},
            description="Default single evaluation instructions with web search verification",
            tags=["default", "evaluation"],
        )
        session.add(single_eval)
        print(f"Created content: {single_eval.name}")
        
        # ============================================================================
        # CONTENT: Pairwise Evaluation Instructions
        # ============================================================================
        pairwise_eval = Content(
            id=CONTENT_PAIRWISE_EVAL_ID,
            user_id=None,
            created_at=now,
            name="Default Pairwise Evaluation Instructions",
            content_type=ContentType.PAIRWISE_EVAL_INSTRUCTIONS.value,
            body="""You are an expert content evaluator. Your task is to compare two generated content pieces and determine which is better. You MUST use web searches to verify factual claims in both pieces.

## MANDATORY WEB SEARCH REQUIREMENT
You MUST perform web searches to:
1. Verify factual claims in both content pieces
2. Check which piece has more accurate information
3. Validate any statistics, dates, or data points
4. Identify factual errors that affect the comparison

## Comparison Process
1. Read both content pieces carefully
2. Use web searches to verify key claims in each
3. Compare against the evaluation criteria
4. Determine which piece is superior and why
5. Note any factual issues found in either piece

## Output Format
Provide your comparison as:
- Winner selection (A or B)
- Confidence level (low/medium/high)
- Detailed reasoning for your choice
- Comparison across each criterion
- Notes on factual accuracy verified via web search""",
            variables={},
            description="Default pairwise evaluation instructions with web search verification",
            tags=["default", "evaluation", "pairwise"],
        )
        session.add(pairwise_eval)
        print(f"Created content: {pairwise_eval.name}")
        
        # ============================================================================
        # CONTENT: Evaluation Criteria
        # ============================================================================
        eval_criteria = Content(
            id=CONTENT_CRITERIA_ID,
            user_id=None,
            created_at=now,
            name="Default Evaluation Criteria",
            content_type=ContentType.EVAL_CRITERIA.value,
            body="""# Content Evaluation Criteria

## 1. Factual Accuracy (Weight: 15%)
- All facts, statistics, and claims are verifiable and correct
- Information is current and not outdated
- No fabricated or misleading information
- Sources are properly represented

## 2. Source Verification (Weight: 10%)
- Claims are supported by credible sources
- Web search verification confirms accuracy
- No misrepresentation of source material
- Proper attribution where needed

## 3. Hallucination Detection (Weight: 15%)
- No fabricated quotes or statistics
- No invented sources or references
- No false attributions
- All claims traceable to source or verified externally

## 4. Completeness (Weight: 10%)
- All major points from source are covered
- No significant omissions
- Appropriate depth of coverage
- Balanced treatment of topics

## 5. Coherence (Weight: 8%)
- Logical flow of ideas
- Clear transitions between sections
- Consistent argumentation
- Well-organized structure

## 6. Clarity (Weight: 7%)
- Clear, understandable language
- Appropriate vocabulary for audience
- No ambiguous statements
- Effective explanations

## 7. Relevance (Weight: 5%)
- Content stays on topic
- No irrelevant tangents
- Appropriate focus on key points
- Aligned with source intent

## 8. Objectivity (Weight: 5%)
- Balanced presentation
- No unwarranted bias
- Fair treatment of multiple perspectives
- Neutral tone where appropriate

## 9. Conciseness (Weight: 5%)
- No unnecessary repetition
- Efficient use of words
- Appropriate length
- No filler content

## 10. Technical Accuracy (Weight: 5%)
- Correct use of technical terms
- Accurate domain-specific information
- Proper context for technical content
- No misuse of terminology

## 11. Grammar and Style (Weight: 3%)
- Correct grammar and spelling
- Consistent style
- Professional tone
- Proper punctuation

## 12. Citation Quality (Weight: 3%)
- Proper citation format
- Accurate source references
- Appropriate use of citations
- Verifiable references

## 13. Originality (Weight: 3%)
- Fresh perspective on content
- Not mere paraphrasing
- Value-added insights
- Creative presentation

## 14. Audience Appropriateness (Weight: 2%)
- Suitable for target audience
- Appropriate complexity level
- Relevant examples
- Accessible language

## 15. Structure (Weight: 4%)
- Logical organization
- Effective use of headings
- Appropriate paragraphing
- Clear hierarchy of information""",
            variables={},
            description="Default 15-criterion evaluation rubric",
            tags=["default", "criteria"],
        )
        session.add(eval_criteria)
        print(f"Created content: {eval_criteria.name}")
        
        # ============================================================================
        # CONTENT: Combine Instructions
        # ============================================================================
        combine_instructions = Content(
            id=CONTENT_COMBINE_ID,
            user_id=None,
            created_at=now,
            name="Default Combine Instructions",
            content_type=ContentType.COMBINE_INSTRUCTIONS.value,
            body="""You are tasked with synthesizing multiple evaluated content generations into a single, optimal output. Your goal is to combine the best elements from each generation while ensuring the final output is coherent, accurate, and well-structured.

## Synthesis Process
1. Review all generated content pieces and their evaluations
2. Identify the strongest elements from each generation
3. Combine these elements into a unified, coherent piece
4. Ensure factual accuracy of the combined content
5. Verify the final output maintains logical flow

## Quality Requirements
- Incorporate the best aspects of each generation
- Maintain consistent tone and style
- Ensure no contradictions in the combined content
- Preserve all accurate, verified information
- Create smooth transitions between combined sections

## Output Format
- Produce a single, polished piece of content
- Include proper structure with headings as appropriate
- Maintain professional quality throughout
- Ensure the result is better than any individual generation""",
            variables={},
            description="Default combine/synthesis instructions",
            tags=["default", "combine"],
        )
        session.add(combine_instructions)
        print(f"Created content: {combine_instructions.name}")
        
        # ============================================================================
        # CONTENT: Sample Input Document
        # ============================================================================
        sample_input = Content(
            id=SAMPLE_INPUT_ID,
            user_id=None,
            created_at=now,
            name="Sample Input Document",
            content_type=ContentType.INPUT_DOCUMENT.value,
            body="""# The Future of Artificial Intelligence

Artificial Intelligence (AI) is rapidly transforming industries and daily life. From healthcare to finance, AI algorithms are optimizing processes and creating new opportunities. However, the rapid advancement also brings challenges such as ethical considerations, job displacement, and the need for robust regulation.

In healthcare, AI is being used to diagnose diseases with higher accuracy than human doctors. In finance, it detects fraudulent transactions in milliseconds. As we move forward, the collaboration between humans and AI will likely define the next era of innovation.""",
            variables={},
            description="Sample input document for testing",
            tags=["sample", "input"],
        )
        session.add(sample_input)
        print(f"Created content: {sample_input.name}")
        
        # Flush to ensure content IDs are available
        session.flush()
        
        # ============================================================================
        # PRESET: Default Preset
        # ============================================================================
        default_preset = Preset(
            id=PRESET_ID,
            user_id=None,  # Seed data has no user
            created_at=now,
            name="Default Preset",
            description="Default preset configuration for content generation and evaluation with web search verification",
            
            # Configuration (JSON fields)
            documents=[],  # Empty - user will select documents
            models=["gpt-4o", "claude-sonnet-4-20250514"],  # Default models
            generators=["fpf"],  # Default generator
            
            # Execution settings
            iterations=3,
            evaluation_enabled=True,
            pairwise_enabled=True,
            
            # Generator-specific config
            gptr_config=None,
            fpf_config={
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            
            # Logging
            log_level="INFO",
            
            # Timing & Retry
            max_retries=3,
            retry_delay=2.0,
            request_timeout=600,
            eval_timeout=600,
            fpf_max_retries=3,
            fpf_retry_delay=1.0,
            eval_retries=3,
            
            # Concurrency
            generation_concurrency=5,
            eval_concurrency=5,
            eval_iterations=1,
            
            # FPF Logging
            fpf_log_output="file",
            fpf_log_file_path=None,
            
            # Post-Combine
            post_combine_top_n=None,
            
            # Extra settings
            config_overrides=None,
            
            # Input Source
            input_source_type="database",
            input_content_ids=[SAMPLE_INPUT_ID],  # Reference sample input
            github_connection_id=None,
            github_input_paths=[],
            github_output_path=None,
            
            # Output
            output_destination="library",
            output_filename_template="{source_doc_name}_{winner_model}_{timestamp}",
            github_commit_message="ACM2: Add winning document",
            
            # Content references
            generation_instructions_id=CONTENT_GEN_ID,
            single_eval_instructions_id=CONTENT_SINGLE_EVAL_ID,
            pairwise_eval_instructions_id=CONTENT_PAIRWISE_EVAL_ID,
            eval_criteria_id=CONTENT_CRITERIA_ID,
            combine_instructions_id=CONTENT_COMBINE_ID,
        )
        session.add(default_preset)
        print(f"Created preset: {default_preset.name}")
        
        # Commit all changes
        session.commit()
        print("\nCommitted all data to database")
        
        # ============================================================================
        # VERIFICATION
        # ============================================================================
        print("\n=== VERIFICATION ===")
        
        preset_count = session.query(Preset).count()
        content_count = session.query(Content).count()
        
        print(f"Presets: {preset_count}")
        print(f"Contents: {content_count}")
        
        # Verify preset has correct content references
        preset = session.query(Preset).filter_by(id=PRESET_ID).first()
        print(f"\nDefault Preset: {preset.name}")
        print(f"  - generation_instructions_id: {preset.generation_instructions_id}")
        print(f"  - single_eval_instructions_id: {preset.single_eval_instructions_id}")
        print(f"  - pairwise_eval_instructions_id: {preset.pairwise_eval_instructions_id}")
        print(f"  - eval_criteria_id: {preset.eval_criteria_id}")
        print(f"  - combine_instructions_id: {preset.combine_instructions_id}")
        print(f"  - input_content_ids: {preset.input_content_ids}")
        
        # List content items
        print(f"\nContent items:")
        for content in session.query(Content).all():
            print(f"  - {content.name} ({content.content_type})")
        
    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()
    
    print(f"\n✅ Seed database created: {SEED_DB_PATH.absolute()}")
    print(f"   File size: {SEED_DB_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    main()
