from typing import List, Dict, Any, Union
from app.infra.db.models.run import Run
from app.api.schemas.runs import GeneratorType
from .models import TimelineRow, TimelinePhase, TimelineStatus

def build_expected_plan(run: Union[Run, Dict[str, Any]]) -> List[TimelineRow]:
    """
    Build the expected execution plan based on run configuration.
    """
    rows: List[TimelineRow] = []
    
    if isinstance(run, dict):
        # Handle dict (from in-memory store)
        # Config might be at top level or in 'config' key depending on storage format
        # RunStore.create stores flat fields.
        # Let's assume run is the flat dict matching RunCreate/RunDetail
        config = run # It's the run dict itself
        # But wait, RunStore stores flat fields, but Run model has 'config' JSON column.
        # Let's check RunStore.create again.
    else:
        config = run.config
    
    # Extract configuration
    # If run is dict, we need to be careful about where fields are.
    # RunStore.create:
    # "document_ids": data.document_ids,
    # "generators": data.generators,
    # "models": ...
    # So they are at top level.
    
    if isinstance(run, dict):
        doc_ids = run.get("document_ids") or []
        generators = run.get("generators") or []
        models = run.get("models") or []
        iterations = run.get("iterations", 1)
        eval_settings = run.get("evaluation") or {}
        pairwise_settings = run.get("pairwise") or {}
    else:
        doc_ids = config.get("document_ids") or []
        generators = config.get("generators") or []
        models = config.get("models") or []
        iterations = config.get("iterations", 1)
        eval_settings = config.get("evaluation") or {}
        pairwise_settings = config.get("pairwise") or {}
    
    run_index = 1
    
    # 1. Generation Phase
    # For each document x generator x model x iteration
    for doc_id in doc_ids:
        for gen in generators:
            for model_cfg in models:
                # Handle both dict and object access for model config
                if isinstance(model_cfg, dict):
                    model_name = model_cfg.get("model")
                    provider = model_cfg.get("provider")
                else:
                    model_name = model_cfg.model
                    provider = model_cfg.provider
                    
                full_model_name = f"{provider}:{model_name}"
                
                for i in range(1, iterations + 1):
                    rows.append(TimelineRow(
                        expected_run_index=run_index,
                        phase=TimelinePhase.GENERATION,
                        eval_type="generation",
                        judge_model=full_model_name, # For generation, judge is the generator
                        target=f"{doc_id} (Iter {i})",
                        status=TimelineStatus.PENDING
                    ))
                    run_index += 1

    # 2. Single Eval Phase
    if eval_settings.get("enabled", True):
        eval_model = eval_settings.get("eval_model", "")
        if not eval_model:
            raise ValueError("eval_model is required from preset when evaluation is enabled")
        
        # One eval per generated artifact
        # We iterate the same loops as generation
        for doc_id in doc_ids:
            for gen in generators:
                for model_cfg in models:
                    if isinstance(model_cfg, dict):
                        model_name = model_cfg.get("model")
                    else:
                        model_name = model_cfg.model
                        
                    for i in range(1, iterations + 1):
                        rows.append(TimelineRow(
                            expected_run_index=run_index,
                            phase=TimelinePhase.PRECOMBINE_SINGLE,
                            eval_type="single",
                            judge_model=eval_model,
                            target=f"Eval: {doc_id} / {model_name} / {i}",
                            status=TimelineStatus.PENDING
                        ))
                        run_index += 1

    # 3. Pairwise Eval Phase
    if pairwise_settings.get("enabled", False):
        judge_model = pairwise_settings.get("judge_model", "")
        if not judge_model:
            raise ValueError("judge_model is required from preset when pairwise is enabled")
        # We can't predict exact pairs if top_n is used, but we can add a placeholder
        # or if we assume full round robin for small sets.
        # For now, let's add a generic "Pairwise Tournament" row or estimate count.
        # The spec suggests "Top #i vs Top #j".
        
        # Let's assume a simple estimation: N artifacts -> N*(N-1)/2 pairs if full.
        # If top_n is set, it's top_n*(top_n-1)/2.
        
        # For the timeline chart, maybe we just show "Pairwise Phase" as a block?
        # Or we generate rows for "Match 1", "Match 2", etc.
        
        # Let's generate a placeholder row for now, as exact pairs are dynamic.
        rows.append(TimelineRow(
            expected_run_index=run_index,
            phase=TimelinePhase.PRECOMBINE_PAIRWISE,
            eval_type="pairwise",
            judge_model=judge_model,
            target="Dynamic Pairwise Tournament",
            status=TimelineStatus.PENDING
        ))
        run_index += 1

    return rows
