"""
Evaluation criteria management for ACM2.

Provides default criteria and utilities for loading/validating criteria.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from .models import EvaluationCriterion


# Default criteria for document evaluation
DEFAULT_CRITERIA: List[EvaluationCriterion] = [
    EvaluationCriterion(
        name="factuality",
        description=(
            "Accuracy of facts and data presented. "
            "1=Contains fabrications or severe errors. "
            "3=Mostly accurate with minor slips. "
            "5=Perfect accuracy, zero hallucinations."
        ),
        weight=1.5,
    ),
    EvaluationCriterion(
        name="relevance",
        description=(
            "Alignment with the user's query and intent. "
            "1=Ignores instructions. "
            "3=Follows general topic but misses constraints. "
            "5=Follows every instruction perfectly."
        ),
        weight=1.2,
    ),
    EvaluationCriterion(
        name="completeness",
        description=(
            "Coverage of all necessary aspects. "
            "1=Fragmentary or missing major sections. "
            "3=Covers basics but lacks depth. "
            "5=Comprehensive, leaving no question unanswered."
        ),
        weight=1.0,
    ),
    EvaluationCriterion(
        name="clarity",
        description=(
            "Readability, flow, and professional tone. "
            "1=Incoherent or riddled with errors. "
            "3=Readable but dry or awkward. "
            "5=Masterful, compelling, and error-free."
        ),
        weight=0.8,
    ),
    EvaluationCriterion(
        name="structure",
        description=(
            "Organization and logical flow. "
            "1=Disorganized or missing structure. "
            "3=Basic structure but inconsistent. "
            "5=Perfect organization with clear sections."
        ),
        weight=0.8,
    ),
    EvaluationCriterion(
        name="depth",
        description=(
            "Level of insight and critical analysis. "
            "1=Surface level summary only. "
            "3=Some analysis but mostly descriptive. "
            "5=Deep, insightful analysis with nuance."
        ),
        weight=1.0,
    ),
]


def get_default_criteria() -> List[EvaluationCriterion]:
    """
    Get the default evaluation criteria.
    
    Returns:
        List of default EvaluationCriterion objects
    """
    return DEFAULT_CRITERIA.copy()


def load_criteria_from_yaml(path: str) -> List[EvaluationCriterion]:
    """
    Load evaluation criteria from a YAML file.
    
    Expected format:
    ```yaml
    criteria:
      - name: factuality
        description: "..."
        weight: 1.5
      - name: relevance
        description: "..."
    ```
    
    Args:
        path: Path to YAML file
        
    Returns:
        List of EvaluationCriterion objects
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Criteria file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data or "criteria" not in data:
        raise ValueError(f"Invalid criteria file format: missing 'criteria' key")
    
    criteria = []
    for item in data["criteria"]:
        if isinstance(item, str):
            # Simple string format: just the name
            criteria.append(EvaluationCriterion(
                name=item,
                description=f"Evaluate the {item} of the document.",
            ))
        elif isinstance(item, dict):
            # Full object format
            if "name" not in item:
                raise ValueError(f"Criterion missing 'name': {item}")
            criteria.append(EvaluationCriterion(
                name=item["name"],
                description=item.get("description", f"Evaluate the {item['name']}."),
                weight=float(item.get("weight", 1.0)),
            ))
        else:
            raise ValueError(f"Invalid criterion format: {item}")
    
    return criteria


def save_criteria_to_yaml(criteria: List[EvaluationCriterion], path: str) -> None:
    """
    Save evaluation criteria to a YAML file.
    
    Args:
        criteria: List of criteria to save
        path: Output path
    """
    data = {
        "criteria": [
            {
                "name": c.name,
                "description": c.description,
                "weight": c.weight,
            }
            for c in criteria
        ]
    }
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def format_criteria_for_prompt(criteria: List[EvaluationCriterion]) -> str:
    """
    Format criteria list for inclusion in LLM prompt.
    
    Args:
        criteria: List of criteria
        
    Returns:
        Formatted string with bullet points
    """
    lines = [c.to_prompt_line() for c in criteria]
    return "\n".join(lines)


def get_criteria_weights(criteria: List[EvaluationCriterion]) -> Dict[str, float]:
    """
    Extract weights mapping from criteria list.
    
    Args:
        criteria: List of criteria
        
    Returns:
        Dict mapping criterion name to weight
    """
    return {c.name: c.weight for c in criteria}


def validate_criteria(criteria: List[EvaluationCriterion]) -> List[str]:
    """
    Validate a list of criteria and return any errors.
    
    Args:
        criteria: List of criteria to validate
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    if not criteria:
        errors.append("Criteria list is empty")
        return errors
    
    names_seen = set()
    for c in criteria:
        if not c.name:
            errors.append("Criterion has empty name")
        elif c.name in names_seen:
            errors.append(f"Duplicate criterion name: {c.name}")
        else:
            names_seen.add(c.name)
        
        if not c.description:
            errors.append(f"Criterion '{c.name}' has empty description")
        
        if c.weight <= 0:
            errors.append(f"Criterion '{c.name}' has invalid weight: {c.weight}")
    
    return errors


class CriteriaManager:
    """
    Manages evaluation criteria with caching and validation.
    """
    
    def __init__(self, custom_path: Optional[str] = None):
        """
        Initialize criteria manager.
        
        Args:
            custom_path: Optional path to custom criteria YAML file
        """
        self._custom_path = custom_path
        self._criteria: Optional[List[EvaluationCriterion]] = None
    
    @property
    def criteria(self) -> List[EvaluationCriterion]:
        """
        Get the active criteria list.
        
        Loads from custom path if set, otherwise uses defaults.
        Results are cached.
        """
        if self._criteria is None:
            if self._custom_path and os.path.exists(self._custom_path):
                self._criteria = load_criteria_from_yaml(self._custom_path)
            else:
                self._criteria = get_default_criteria()
        return self._criteria
    
    @property
    def weights(self) -> Dict[str, float]:
        """Get criteria weights mapping."""
        return get_criteria_weights(self.criteria)
    
    @property
    def names(self) -> List[str]:
        """Get list of criterion names."""
        return [c.name for c in self.criteria]
    
    def format_for_prompt(self) -> str:
        """Format criteria for LLM prompt."""
        return format_criteria_for_prompt(self.criteria)
    
    def reload(self) -> None:
        """Force reload of criteria from source."""
        self._criteria = None
        _ = self.criteria  # Trigger reload
    
    def set_criteria(self, criteria: List[EvaluationCriterion]) -> None:
        """
        Set custom criteria programmatically.
        
        Args:
            criteria: List of criteria to use
            
        Raises:
            ValueError: If criteria are invalid
        """
        errors = validate_criteria(criteria)
        if errors:
            raise ValueError(f"Invalid criteria: {'; '.join(errors)}")
        self._criteria = criteria
