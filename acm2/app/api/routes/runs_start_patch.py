@router.post("/{run_id}/start")
async def start_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Start executing a run.
    """
    try:
        repo = RunRepository(db)
        run = await repo.get_by_id(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        if run.status != RunStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Can only start PENDING runs, current status: {run.status}"
            )
        # Ensure this run was created from a preset; starting ad-hoc runs is disallowed
        if not run.preset_id:
            raise HTTPException(status_code=400, detail="Cannot start run: run was not created from a preset")

        # Verify the preset still exists
        from app.infra.db.repositories import PresetRepository
        preset_repo = PresetRepository(db)
        preset = await preset_repo.get_by_id(run.preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset {run.preset_id} not found for this run")
        
        # Mark as running
        await repo.start(run_id)
        
        # Build RunConfig from run.config
        run_config = run.config or {}
        
        # Fetch documents from Content Library only (legacy 'documents' table deprecated)
        content_repo = ContentRepository(db)
        document_contents = {}
        doc_ids = run_config.get("document_ids") or []
        
        for doc_id in doc_ids:
            # Only use Content Library (input_document type)
            content = await content_repo.get_by_id(doc_id)
            if content and content.content_type == "input_document":
                logger.info(f"Document found in Content Library: {doc_id} -> {content.name}")
                document_contents[doc_id] = content.body
            else:
                # Document not found in Content Library - skip it
                logger.warning(f"Document {doc_id} not found in Content Library (may be orphaned reference from legacy 'documents' table)")

        # Get phase-specific configs from run_config
        # These contain the separate model lists for each phase
        combine_config = run_config.get("combine_config", {}) or run_config.get("config_overrides", {}).get("combine", {})
        eval_config = run_config.get("eval_config", {}) or run_config.get("config_overrides", {}).get("eval", {})
        pairwise_config = run_config.get("pairwise_config", {}) or run_config.get("config_overrides", {}).get("pairwise", {})
        concurrency_config = run_config.get("concurrency_config", {}) or run_config.get("config_overrides", {}).get("concurrency", {})
        
        # Get FPF instructions - prefer generation_instructions_id from Content Library
        # Fall back to fpf_config.prompt_template if no Content Library item specified
        generation_instructions_id = run_config.get("generation_instructions_id")
        instructions = ""
        if generation_instructions_id:
            content = await content_repo.get_by_id(generation_instructions_id)
            if content:
                instructions = content.body
                logger.info(f"Loaded generation instructions from Content Library: {content.name}")
        
        # Fall back to prompt_template if no Content Library instructions
        if not instructions:
            fpf_config = run_config.get("fpf_config") or run_config.get("config_overrides", {}).get("fpf", {})
            instructions = fpf_config.get("prompt_template", "") if fpf_config else ""
            if instructions:
                logger.info("Using prompt_template from fpf_config as generation instructions")
        
        # Fetch custom instruction content from Content Library if IDs are provided
        single_eval_instructions = None
        pairwise_eval_instructions = None
        eval_criteria = None
        combine_instructions = None
        
        single_eval_id = run_config.get("single_eval_instructions_id")
        if single_eval_id:
            content = await content_repo.get_by_id(single_eval_id)
            if content:
                single_eval_instructions = content.body
                logger.info(f"Loaded single eval instructions from Content Library: {content.name}")
        
        pairwise_eval_id = run_config.get("pairwise_eval_instructions_id")
        if pairwise_eval_id:
            content = await content_repo.get_by_id(pairwise_eval_id)
            if content:
                pairwise_eval_instructions = content.body
                logger.info(f"Loaded pairwise eval instructions from Content Library: {content.name}")
        
        eval_criteria_id = run_config.get("eval_criteria_id")
        if eval_criteria_id:
            content = await content_repo.get_by_id(eval_criteria_id)
            if content:
                eval_criteria = content.body
                logger.info(f"Loaded eval criteria from Content Library: {content.name}")
        
        combine_instructions_id = run_config.get("combine_instructions_id")
        if combine_instructions_id:
            content = await content_repo.get_by_id(combine_instructions_id)
            if content:
                combine_instructions = content.body
                logger.info(f"Loaded combine instructions from Content Library: {content.name}")
        
        executor_config = RunConfig(
            document_ids=list(document_contents.keys()),
            document_contents=document_contents,
            instructions=instructions,
            generators=[AdapterGeneratorType(g) for g in (run_config.get("generators") or ["gptr"])],
            # Format models as "provider:model" strings for proper routing
            models=[f"{m['provider']}:{m['model']}" for m in (run_config.get("models") or [])],
            iterations=run_config.get("iterations", 1),
            enable_single_eval=eval_config.get("enabled", run_config.get("evaluation_enabled", True)),
            enable_pairwise=pairwise_config.get("enabled", run_config.get("pairwise_enabled", False)),
            eval_iterations=eval_config.get("iterations", 1),
            # Get judge models from eval_config.judge_models (already formatted as "provider:model" strings)
            # NO FALLBACK - must be configured in preset's eval_config.judge_models
            eval_judge_models=eval_config.get("judge_models") or [],
            # Per-call eval timeout from GUI eval panel
            eval_timeout=eval_config.get("timeout_seconds", 600),
            # pairwise_top_n is in eval_config, not pairwise_config
            pairwise_top_n=eval_config.get("pairwise_top_n"),
            # Custom evaluation instructions from Content Library
            single_eval_instructions=single_eval_instructions,
            pairwise_eval_instructions=pairwise_eval_instructions,
            eval_criteria=eval_criteria,
            enable_combine=combine_config.get("enabled", False),
            combine_strategy=combine_config.get("strategy", "intelligent_merge"),
            # Get combine models from combine_config.selected_models (already formatted as "provider:model" strings)
            # NO FALLBACK - must be configured in preset's combine_config.selected_models
            combine_models=combine_config.get("selected_models") or [],
            combine_instructions=combine_instructions,
            post_combine_top_n=run_config.get("post_combine_top_n"),
            log_level=run_config.get("log_level", "INFO"),
            # Concurrency settings (from GUI Settings page via concurrency_config)
            # REQUIRED from preset - no fallback defaults
            generation_concurrency=concurrency_config.get("max_concurrent", concurrency_config.get("generation_concurrency")) or 5,
            eval_concurrency=concurrency_config.get("eval_concurrency") or 5,
            request_timeout=concurrency_config.get("request_timeout") or 600,
            max_retries=concurrency_config.get("max_retries") or 3,
            retry_delay=concurrency_config.get("retry_delay") or 2.0,
        )
        
        background_tasks.add_task(execute_run_background, run_id, executor_config)
        
        return {"status": "started", "run_id": run_id}
    except Exception as e:
        logger.error(f"Error starting run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
