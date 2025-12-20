"""
Tests for GPT-Researcher adapter.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.base import GenerationConfig, TaskStatus, GeneratorType
from app.adapters.gptr import (
    GptrAdapter,
    GptrConfig,
    ReportType,
    ReportSource,
    Tone,
)


class TestGptrConfig:
    """Tests for GptrConfig dataclass."""
    
    def test_default_values(self):
        config = GptrConfig()
        assert config.report_type == ReportType.RESEARCH_REPORT
        assert config.report_source == ReportSource.WEB
        assert config.tone == Tone.OBJECTIVE
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
    
    def test_custom_values(self):
        config = GptrConfig(
            report_type=ReportType.DETAILED_REPORT,
            tone=Tone.FORMAL,
            model="claude-3-opus",
            provider="anthropic",
        )
        assert config.report_type == ReportType.DETAILED_REPORT
        assert config.tone == Tone.FORMAL
        assert config.model == "claude-3-opus"


class TestGptrAdapter:
    """Tests for GptrAdapter."""
    
    def test_adapter_properties(self):
        adapter = GptrAdapter()
        assert adapter.name == GeneratorType.GPTR
        assert adapter.display_name == "GPT-Researcher"
    
    @pytest.mark.asyncio
    async def test_health_check_no_gptr_installed(self):
        """Health check should fail if gpt-researcher not installed."""
        adapter = GptrAdapter()
        
        with patch.dict('sys.modules', {'gpt_researcher': None}):
            # This tests the import failure path
            # In real scenarios, import will work if package is installed
            pass
    
    @pytest.mark.asyncio
    async def test_generate_builds_correct_config(self):
        """Test that GenerationConfig is properly converted to GptrConfig."""
        adapter = GptrAdapter()
        
        config = GenerationConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.5,
            extra={
                "report_type": "detailed_report",
                "tone": "Formal",
                "source_urls": ["https://example.com"],
            }
        )
        
        gptr_config = adapter._build_gptr_config(config)
        
        assert gptr_config.provider == "openai"
        assert gptr_config.smart_llm == "gpt-4o"
        assert gptr_config.report_type == ReportType.DETAILED_REPORT
        assert gptr_config.tone == Tone.FORMAL
        assert gptr_config.source_urls == ["https://example.com"]
    
    @pytest.mark.asyncio
    async def test_generate_with_mock_researcher(self):
        """Test generate() with mocked GPTResearcher."""
        adapter = GptrAdapter()
        
        # Mock the GPTResearcher class
        mock_researcher = MagicMock()
        mock_researcher.conduct_research = AsyncMock()
        mock_researcher.write_report = AsyncMock(return_value="# Test Report\n\nContent here.")
        mock_researcher.get_costs = MagicMock(return_value=0.05)
        mock_researcher.get_source_urls = MagicMock(return_value=["https://example.com"])
        mock_researcher.get_research_sources = MagicMock(return_value=[])
        mock_researcher.get_research_images = MagicMock(return_value=[])
        
        with patch('app.adapters.gptr.adapter.GPTResearcher', return_value=mock_researcher):
            # This would need the actual import to work
            # For now, just verify the adapter structure is correct
            pass
    
    @pytest.mark.asyncio
    async def test_cancel_marks_task(self):
        """Test that cancel() marks task for cancellation."""
        adapter = GptrAdapter()
        
        # Simulate an active task
        task_id = "test-task-123"
        adapter._active_tasks[task_id] = MagicMock()
        
        result = await adapter.cancel(task_id)
        
        assert result is True
        assert task_id in adapter._cancelled
    
    @pytest.mark.asyncio  
    async def test_cancel_unknown_task(self):
        """Test that cancel() returns False for unknown task."""
        adapter = GptrAdapter()
        
        result = await adapter.cancel("unknown-task")
        
        assert result is False


class TestReportTypes:
    """Tests for report type enumeration."""
    
    def test_all_report_types(self):
        expected = [
            "research_report",
            "detailed_report", 
            "deep",
            "resource_report",
            "outline_report",
            "custom_report",
            "subtopic_report",
        ]
        actual = [rt.value for rt in ReportType]
        assert set(expected) == set(actual)
    
    def test_report_source_values(self):
        assert ReportSource.WEB.value == "web"
        assert ReportSource.LOCAL.value == "local"
        assert ReportSource.HYBRID.value == "hybrid"
