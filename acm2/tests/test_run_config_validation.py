"""
Unit tests for RunConfig validation (__post_init__).

Tests that all fallbacks have been eliminated and validation works correctly.
"""
import pytest
from app.services.run_executor import RunConfig, GeneratorType


class TestRunConfigValidation:
    """Test RunConfig.__post_init__() validation."""
    
    def get_valid_config(self):
        """Helper to get a valid minimal RunConfig."""
        return RunConfig(
            document_ids=["doc1"],
            document_contents={"doc1": "test content"},
            generators=[GeneratorType.FPF],
            models=["openai:gpt-4"],
            instructions="test instructions",
            iterations=1,
            enable_single_eval=False,
            enable_pairwise=False,
            eval_iterations=1,
            eval_judge_models=[],
            max_retries=3,
            retry_delay=2.0,
            request_timeout=600,
            eval_timeout=600,
            generation_concurrency=5,
            eval_concurrency=5,
            log_level="INFO",
            fpf_log_output="file",
            fpf_log_file_path="/tmp/fpf.log",
        )
    
    # =========================================================================
    # Test Required Numeric Fields
    # =========================================================================
    
    def test_iterations_required(self):
        """Test that iterations is required."""
        config_dict = self.get_valid_config().__dict__
        del config_dict['iterations']
        
        with pytest.raises(TypeError, match="iterations"):
            RunConfig(**config_dict)
    
    def test_eval_iterations_required(self):
        """Test that eval_iterations is required."""
        config_dict = self.get_valid_config().__dict__
        del config_dict['eval_iterations']
        
        with pytest.raises(TypeError, match="eval_iterations"):
            RunConfig(**config_dict)
    
    def test_max_retries_required(self):
        """Test that max_retries is required."""
        config_dict = self.get_valid_config().__dict__
        del config_dict['max_retries']
        
        with pytest.raises(TypeError, match="max_retries"):
            RunConfig(**config_dict)
    
    def test_max_retries_range(self):
        """Test max_retries must be 1-10."""
        config = self.get_valid_config()
        config.max_retries = 0
        
        with pytest.raises(ValueError, match="max_retries must be 1-10"):
            config.__post_init__()
        
        config.max_retries = 11
        with pytest.raises(ValueError, match="max_retries must be 1-10"):
            config.__post_init__()
    
    def test_retry_delay_range(self):
        """Test retry_delay must be 0.5-30.0."""
        config = self.get_valid_config()
        config.retry_delay = 0.4
        
        with pytest.raises(ValueError, match="retry_delay must be 0.5-30.0"):
            config.__post_init__()
        
        config.retry_delay = 31.0
        with pytest.raises(ValueError, match="retry_delay must be 0.5-30.0"):
            config.__post_init__()
    
    def test_request_timeout_range(self):
        """Test request_timeout must be 60-3600."""
        config = self.get_valid_config()
        config.request_timeout = 59
        
        with pytest.raises(ValueError, match="request_timeout must be 60-3600"):
            config.__post_init__()
        
        config.request_timeout = 3601
        with pytest.raises(ValueError, match="request_timeout must be 60-3600"):
            config.__post_init__()
    
    def test_concurrency_ranges(self):
        """Test concurrency limits must be 1-50."""
        config = self.get_valid_config()
        config.generation_concurrency = 0
        
        with pytest.raises(ValueError, match="generation_concurrency must be 1-50"):
            config.__post_init__()
        
        config.generation_concurrency = 51
        with pytest.raises(ValueError, match="generation_concurrency must be 1-50"):
            config.__post_init__()
    
    # =========================================================================
    # Test Logging Configuration
    # =========================================================================
    
    def test_log_level_required(self):
        """Test log_level is required and must be valid."""
        config = self.get_valid_config()
        config.log_level = "INVALID"
        
        with pytest.raises(ValueError, match="log_level must be"):
            config.__post_init__()
    
    def test_fpf_log_output_required(self):
        """Test fpf_log_output is required and must be valid."""
        config = self.get_valid_config()
        config.fpf_log_output = "invalid"
        
        with pytest.raises(ValueError, match="fpf_log_output must be"):
            config.__post_init__()
    
    def test_fpf_log_file_path_required_when_file_output(self):
        """Test fpf_log_file_path required when fpf_log_output='file'."""
        config = self.get_valid_config()
        config.fpf_log_output = "file"
        config.fpf_log_file_path = None
        
        with pytest.raises(ValueError, match="fpf_log_file_path required"):
            config.__post_init__()
    
    # =========================================================================
    # Test Input Validation
    # =========================================================================
    
    def test_document_ids_required(self):
        """Test document_ids cannot be empty."""
        config = self.get_valid_config()
        config.document_ids = []
        
        with pytest.raises(ValueError, match="document_ids is required"):
            config.__post_init__()
    
    def test_document_contents_required(self):
        """Test document_contents must include all doc_ids."""
        config = self.get_valid_config()
        config.document_ids = ["doc1", "doc2"]
        config.document_contents = {"doc1": "content"}
        
        with pytest.raises(ValueError, match="Missing content for document_id"):
            config.__post_init__()
    
    def test_document_contents_cannot_be_empty(self):
        """Test document contents cannot be empty or whitespace."""
        config = self.get_valid_config()
        config.document_contents = {"doc1": ""}
        
        with pytest.raises(ValueError, match="Content for document_id doc1 is empty"):
            config.__post_init__()
        
        config.document_contents = {"doc1": "   "}
        with pytest.raises(ValueError, match="Content for document_id doc1 is empty"):
            config.__post_init__()
    
    def test_generators_required(self):
        """Test generators list cannot be empty."""
        config = self.get_valid_config()
        config.generators = []
        
        with pytest.raises(ValueError, match="generators list is required"):
            config.__post_init__()
    
    def test_models_required(self):
        """Test models list cannot be empty."""
        config = self.get_valid_config()
        config.models = []
        
        with pytest.raises(ValueError, match="models list is required"):
            config.__post_init__()
    
    # =========================================================================
    # Test Conditional Requirements
    # =========================================================================
    
    def test_fpf_requires_instructions(self):
        """Test FPF generator requires instructions."""
        config = self.get_valid_config()
        config.generators = [GeneratorType.FPF]
        config.instructions = None
        
        with pytest.raises(ValueError, match="FPF generator requires instructions"):
            config.__post_init__()
    
    def test_single_eval_requires_instructions(self):
        """Test single eval requires instructions and judge models."""
        config = self.get_valid_config()
        config.enable_single_eval = True
        config.single_eval_instructions = None
        
        with pytest.raises(ValueError, match="Single evaluation enabled but no instructions"):
            config.__post_init__()
        
        config.single_eval_instructions = "test"
        config.eval_judge_models = []
        with pytest.raises(ValueError, match="eval_judge_models required"):
            config.__post_init__()
    
    def test_pairwise_requires_instructions(self):
        """Test pairwise requires instructions."""
        config = self.get_valid_config()
        config.enable_pairwise = True
        config.pairwise_eval_instructions = None
        
        with pytest.raises(ValueError, match="Pairwise evaluation enabled but no instructions"):
            config.__post_init__()
    
    def test_eval_requires_criteria(self):
        """Test any evaluation requires eval_criteria."""
        config = self.get_valid_config()
        config.enable_single_eval = True
        config.single_eval_instructions = "test"
        config.eval_judge_models = ["openai:gpt-4"]
        config.eval_criteria = None
        
        with pytest.raises(ValueError, match="Evaluation enabled but no criteria"):
            config.__post_init__()
    
    def test_combine_requires_models_and_instructions(self):
        """Test combine phase requires models and instructions."""
        config = self.get_valid_config()
        config.enable_combine = True
        config.combine_models = []
        
        with pytest.raises(ValueError, match="Combine enabled but no models"):
            config.__post_init__()
        
        config.combine_models = ["openai:gpt-4"]
        config.combine_instructions = None
        with pytest.raises(ValueError, match="Combine enabled but no instructions"):
            config.__post_init__()
    
    # =========================================================================
    # Test Optional Fields
    # =========================================================================
    
    def test_pairwise_top_n_optional(self):
        """Test pairwise_top_n is optional but must be >= 2 if set."""
        config = self.get_valid_config()
        config.pairwise_top_n = None  # Should be valid
        config.__post_init__()  # Should not raise
        
        config.pairwise_top_n = 1
        with pytest.raises(ValueError, match="pairwise_top_n must be >= 2"):
            config.__post_init__()
    
    def test_post_combine_top_n_optional(self):
        """Test post_combine_top_n is optional but must be >= 2 if set."""
        config = self.get_valid_config()
        config.post_combine_top_n = None  # Should be valid
        config.__post_init__()  # Should not raise
        
        config.post_combine_top_n = 1
        with pytest.raises(ValueError, match="post_combine_top_n must be >= 2"):
            config.__post_init__()
    
    # =========================================================================
    # Test Valid Configuration
    # =========================================================================
    
    def test_valid_minimal_config(self):
        """Test that a valid minimal config passes validation."""
        config = self.get_valid_config()
        config.__post_init__()  # Should not raise
    
    def test_valid_full_config(self):
        """Test that a valid full config with all features passes."""
        config = self.get_valid_config()
        config.enable_single_eval = True
        config.enable_pairwise = True
        config.enable_combine = True
        config.single_eval_instructions = "eval instructions"
        config.pairwise_eval_instructions = "pairwise instructions"
        config.eval_criteria = "criteria"
        config.eval_judge_models = ["openai:gpt-4"]
        config.combine_models = ["openai:gpt-4"]
        config.combine_instructions = "combine instructions"
        config.combine_strategy = "merge"
        config.pairwise_top_n = 5
        config.post_combine_top_n = 3
        
        config.__post_init__()  # Should not raise
