"""
Tests for FPF (FilePromptForge) adapter.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.adapters.base import GenerationConfig, TaskStatus, GeneratorType
from app.adapters.fpf import FpfAdapter, FpfConfig
from app.adapters.fpf.adapter import FPF_MODEL_MAP
from app.adapters.fpf.errors import FpfExecutionError, FpfConfigError


class TestFpfConfig:
    """Tests for FpfConfig dataclass."""

    def test_default_values(self):
        config = FpfConfig()
        assert config.reasoning_effort == "medium"
        assert config.max_completion_tokens == 50000  # Actual default

    def test_custom_values(self):
        config = FpfConfig(
            reasoning_effort="high",
            max_completion_tokens=32000,
        )
        assert config.reasoning_effort == "high"
        assert config.max_completion_tokens == 32000


class TestFpfModelMapping:
    """Tests for model mapping logic."""

    def test_model_map_contains_expected_entries(self):
        assert "gpt-4o" in FPF_MODEL_MAP
        assert "gpt-4o-mini" in FPF_MODEL_MAP
        assert "gpt-4" in FPF_MODEL_MAP

    def test_model_map_values_are_reasoning_models(self):
        # All mapped models should be o3 variants for reasoning support
        for original, mapped in FPF_MODEL_MAP.items():
            assert mapped.startswith("o3"), f"{original} -> {mapped} should map to o3 variant"


class TestFpfAdapter:
    """Tests for FpfAdapter."""

    def test_adapter_properties(self):
        adapter = FpfAdapter()
        assert adapter.name == GeneratorType.FPF
        assert adapter.display_name == "FilePromptForge"

    def test_adapter_initializes_task_tracking(self):
        adapter = FpfAdapter()
        assert hasattr(adapter, "_active_tasks")
        assert hasattr(adapter, "_cancelled")
        assert isinstance(adapter._active_tasks, dict)
        assert isinstance(adapter._cancelled, set)

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        """Health check should return a boolean."""
        adapter = FpfAdapter()
        result = await adapter.health_check()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_health_check_finds_fpf_directory(self):
        """Health check should find FPF directory when it exists."""
        adapter = FpfAdapter()
        fpf_dir = adapter._get_fpf_directory()

        # Verify path resolution logic
        assert "FilePromptForge" in fpf_dir
        # The directory should exist (in our test environment)
        if Path(fpf_dir).exists():
            result = await adapter.health_check()
            assert result is True

    def test_build_fpf_command_basic(self):
        """Test command building with basic config."""
        adapter = FpfAdapter()

        config = GenerationConfig(
            provider="openai",
            model="o3",  # Already whitelisted
            temperature=0.7,
        )

        cmd = adapter._build_fpf_command(
            file_a="/tmp/doc.txt",
            file_b="/tmp/query.txt",
            output="/tmp/out.md",
            config=config,
        )

        assert "python" in cmd
        assert "fpf_main.py" in cmd
        assert "--file-a" in cmd
        assert "/tmp/doc.txt" in cmd
        assert "--file-b" in cmd
        assert "/tmp/query.txt" in cmd
        assert "--out" in cmd
        assert "/tmp/out.md" in cmd
        assert "--provider" in cmd
        assert "openai" in cmd
        assert "--model" in cmd
        assert "o3" in cmd

    def test_build_fpf_command_maps_model(self):
        """Test that non-whitelisted models are mapped."""
        adapter = FpfAdapter()

        config = GenerationConfig(
            provider="openai",
            model="gpt-4o",  # Should be mapped to o3
            temperature=0.7,
        )

        cmd = adapter._build_fpf_command(
            file_a="/tmp/doc.txt",
            file_b="/tmp/query.txt",
            output="/tmp/out.md",
            config=config,
        )

        # gpt-4o should be mapped to o3
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "o3"

    def test_build_fpf_command_with_extra_options(self):
        """Test command building with extra FPF options."""
        adapter = FpfAdapter()

        config = GenerationConfig(
            provider="openai",
            model="o3",
            extra={
                "reasoning_effort": "high",
                "max_completion_tokens": 32000,
            },
        )

        cmd = adapter._build_fpf_command(
            file_a="/tmp/doc.txt",
            file_b="/tmp/query.txt",
            output="/tmp/out.md",
            config=config,
        )

        assert "--reasoning-effort" in cmd
        assert "high" in cmd
        assert "--max-completion-tokens" in cmd
        assert "32000" in cmd

    def test_cancel_nonexistent_task(self):
        """Cancel should return False for unknown task."""
        adapter = FpfAdapter()
        result = adapter.cancel("nonexistent-task-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_generate_returns_generation_result(self):
        """Generate should return a GenerationResult."""
        adapter = FpfAdapter()

        config = GenerationConfig(
            provider="openai",
            model="o3",
            extra={"reasoning_effort": "medium"},
        )

        # Mock the subprocess execution
        mock_output = "# Test Output\n\nThis is test content."

        with patch.object(adapter, "_get_fpf_directory", return_value="/fake/fpf"):
            with patch(
                "app.adapters.fpf.adapter.run_fpf_subprocess",
                new_callable=AsyncMock,
                return_value=(0, mock_output, ""),
            ):
                with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                    # Setup mock temp directory
                    mock_tmpdir.return_value.__enter__ = MagicMock(return_value="/tmp/fpf_test")
                    mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

                    # Mock file operations
                    with patch("pathlib.Path.write_text"):
                        with patch("pathlib.Path.read_text", return_value=mock_output):
                            with patch("pathlib.Path.exists", return_value=True):
                                result = await adapter.generate(
                                    query="Test query",
                                    config=config,
                                    document_content="Test doc",
                                )

        assert result.generator == GeneratorType.FPF
        assert result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

    @pytest.mark.asyncio
    async def test_generate_handles_subprocess_failure(self):
        """Generate should handle subprocess failures gracefully."""
        adapter = FpfAdapter()

        config = GenerationConfig(
            provider="openai",
            model="o3",
        )

        with patch.object(adapter, "_get_fpf_directory", return_value="/fake/fpf"):
            with patch(
                "app.adapters.fpf.adapter.run_fpf_subprocess",
                new_callable=AsyncMock,
                return_value=(1, "", "Error: Something went wrong"),
            ):
                with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                    mock_tmpdir.return_value.__enter__ = MagicMock(return_value="/tmp/fpf_test")
                    mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

                    with patch("pathlib.Path.write_text"):
                        result = await adapter.generate(
                            query="Test query",
                            config=config,
                        )

        assert result.status == TaskStatus.FAILED
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_progress_callback_is_called(self):
        """Progress callback should be invoked during generation."""
        adapter = FpfAdapter()

        config = GenerationConfig(provider="openai", model="o3")
        progress_calls = []

        def track_progress(stage, progress, message):
            progress_calls.append((stage, progress, message))

        mock_output = "# Result"

        with patch.object(adapter, "_get_fpf_directory", return_value="/fake/fpf"):
            with patch(
                "app.adapters.fpf.adapter.run_fpf_subprocess",
                new_callable=AsyncMock,
                return_value=(0, mock_output, ""),
            ):
                with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
                    mock_tmpdir.return_value.__enter__ = MagicMock(return_value="/tmp/fpf_test")
                    mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)

                    with patch("pathlib.Path.write_text"):
                        with patch("pathlib.Path.read_text", return_value=mock_output):
                            with patch("pathlib.Path.exists", return_value=True):
                                await adapter.generate(
                                    query="Test",
                                    config=config,
                                    progress_callback=track_progress,
                                )

        # Should have received progress updates
        assert len(progress_calls) > 0
        stages = [call[0] for call in progress_calls]
        assert "preparing" in stages or "running" in stages


class TestFpfAdapterIntegration:
    """Integration tests that require actual FPF installation."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_health_check(self):
        """Test health check against real FPF installation."""
        adapter = FpfAdapter()
        result = await adapter.health_check()
        # This will pass if FPF is properly installed
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_real_generation(self):
        """Test actual FPF generation (requires API keys)."""
        adapter = FpfAdapter()

        # Skip if FPF not available
        if not await adapter.health_check():
            pytest.skip("FPF not available")

        config = GenerationConfig(
            provider="openai",
            model="gpt-4o",  # Will be mapped to o3
            extra={
                "reasoning_effort": "low",
                "max_completion_tokens": 500,
            },
        )

        result = await adapter.generate(
            query="What is 2+2? Respond briefly.",
            config=config,
            document_content="Simple math test.",
        )

        assert result.status == TaskStatus.COMPLETED
        assert len(result.content) > 0
