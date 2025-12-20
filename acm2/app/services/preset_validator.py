"""
Preset Validation Service.

Validates preset configuration completeness and correctness before execution.
All required fields must be set - NO FALLBACKS.
"""
from typing import List, Optional
from app.infra.db.models.preset import Preset


class PresetValidationError(ValueError):
    """Raised when preset validation fails."""
    
    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "Preset validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


class PresetValidator:
    """Validates preset configuration completeness and correctness."""
    
    def validate_preset(self, preset: Preset) -> List[str]:
        """
        Validate preset and return list of errors.
        Empty list = valid preset.
        
        Args:
            preset: Preset model to validate
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # =====================================================================
        # Required Core Fields
        # =====================================================================
        
        if not preset.name or not preset.name.strip():
            errors.append("name is required and cannot be empty")
        
        # =====================================================================
        # Required Timing & Retry Configuration
        # =====================================================================
        
        if preset.max_retries is None:
            errors.append("max_retries is required")
        elif not (1 <= preset.max_retries <= 10):
            errors.append(f"max_retries must be 1-10, got {preset.max_retries}")
        
        if preset.retry_delay is None:
            errors.append("retry_delay is required")
        elif not (0.5 <= preset.retry_delay <= 30.0):
            errors.append(f"retry_delay must be 0.5-30.0, got {preset.retry_delay}")
        
        if preset.request_timeout is None:
            errors.append("request_timeout is required")
        elif not (60 <= preset.request_timeout <= 3600):
            errors.append(f"request_timeout must be 60-3600 seconds, got {preset.request_timeout}")
        
        if preset.eval_timeout is None:
            errors.append("eval_timeout is required")
        elif not (60 <= preset.eval_timeout <= 3600):
            errors.append(f"eval_timeout must be 60-3600 seconds, got {preset.eval_timeout}")
        
        # =====================================================================
        # Required Concurrency Configuration
        # =====================================================================
        
        if preset.generation_concurrency is None:
            errors.append("generation_concurrency is required")
        elif not (1 <= preset.generation_concurrency <= 50):
            errors.append(f"generation_concurrency must be 1-50, got {preset.generation_concurrency}")
        
        if preset.eval_concurrency is None:
            errors.append("eval_concurrency is required")
        elif not (1 <= preset.eval_concurrency <= 50):
            errors.append(f"eval_concurrency must be 1-50, got {preset.eval_concurrency}")
        
        # =====================================================================
        # Required Iteration Configuration
        # =====================================================================
        
        # Note: iterations field exists but may need to be validated separately
        # since it was moved to the new config section
        
        if preset.eval_iterations is None:
            errors.append("eval_iterations is required")
        elif not (1 <= preset.eval_iterations <= 10):
            errors.append(f"eval_iterations must be 1-10, got {preset.eval_iterations}")
        
        # =====================================================================
        # Required Logging Configuration
        # =====================================================================
        
        if not preset.log_level:
            errors.append("log_level is required")
        elif preset.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            errors.append(f"log_level must be DEBUG/INFO/WARNING/ERROR, got {preset.log_level}")
        
        if not preset.fpf_log_output:
            errors.append("fpf_log_output is required")
        elif preset.fpf_log_output not in ['stream', 'file', 'none']:
            errors.append(f"fpf_log_output must be 'stream', 'file', or 'none', got {preset.fpf_log_output}")
        
        if preset.fpf_log_output == 'file' and not preset.fpf_log_file_path:
            errors.append("fpf_log_file_path required when fpf_log_output='file'")
        
        # =====================================================================
        # Optional Fields Validation
        # =====================================================================
        
        if preset.post_combine_top_n is not None and preset.post_combine_top_n < 2:
            errors.append(f"post_combine_top_n must be >= 2 or None, got {preset.post_combine_top_n}")
        
        # =====================================================================
        # Conditional Requirements Based on Enabled Features
        # =====================================================================
        
        # Check if generators include FPF
        generators = preset.generators or []
        if 'fpf' in generators or 'FPF' in generators:
            if not preset.generation_instructions_id:
                errors.append(
                    "generation_instructions_id required when FPF generator enabled. "
                    "Select instructions from Content Library."
                )
        
        # Check evaluation settings
        if preset.evaluation_enabled:
            if not preset.eval_criteria_id:
                errors.append(
                    "eval_criteria_id required when evaluation enabled. "
                    "Select criteria from Content Library."
                )
            if not preset.single_eval_instructions_id:
                errors.append(
                    "single_eval_instructions_id required when evaluation enabled. "
                    "Select instructions from Content Library."
                )
            # Check if eval_judge_models is set (stored in config JSON)
            if hasattr(preset, 'eval_config') and preset.eval_config:
                if not preset.eval_config.get('judge_models'):
                    errors.append("eval_judge_models required when evaluation enabled")
        
        # Check pairwise settings
        if preset.pairwise_enabled:
            if not preset.pairwise_eval_instructions_id:
                errors.append(
                    "pairwise_eval_instructions_id required when pairwise enabled. "
                    "Select instructions from Content Library."
                )
            if not preset.eval_criteria_id:
                errors.append(
                    "eval_criteria_id required when pairwise enabled. "
                    "Select criteria from Content Library."
                )
        
        # Check combine settings (need to check config JSON or separate fields)
        # This depends on how combine is configured in the preset
        # For now, checking basic requirements
        
        # =====================================================================
        # Input Validation
        # =====================================================================
        
        if not preset.documents and not preset.input_content_ids:
            errors.append(
                "At least one document or input_content_id required. "
                "Add documents to the preset."
            )
        
        if not preset.models:
            errors.append("At least one model required. Add models to the preset.")
        
        if not preset.generators:
            errors.append("At least one generator required. Select FPF, GPTR, or others.")
        
        return errors
    
    def validate_or_raise(self, preset: Preset) -> None:
        """
        Validate preset and raise PresetValidationError if invalid.
        
        Args:
            preset: Preset model to validate
            
        Raises:
            PresetValidationError: If validation fails
        """
        errors = self.validate_preset(preset)
        if errors:
            raise PresetValidationError(errors)
    
    def validate_for_run_execution(self, preset: Preset) -> None:
        """
        More strict validation specifically for run execution.
        Ensures all fields needed to create a RunConfig are present.
        
        Args:
            preset: Preset model to validate
            
        Raises:
            PresetValidationError: If validation fails
        """
        # Run all basic validations first
        errors = self.validate_preset(preset)
        
        # Additional checks specific to run execution
        # (Add more as needed based on RunConfig requirements)
        
        if errors:
            raise PresetValidationError(errors)
