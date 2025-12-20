"""
Mock evaluators for testing.

Provides deterministic mock implementations for unit testing
without making actual LLM calls.
"""

import random
from typing import Dict, List, Optional

from .criteria import get_default_criteria
from .models import (
    CriterionScore,
    EvaluationCriterion,
    PairwiseResult,
    SingleEvalResult,
)


class MockJudge:
    """
    Mock judge that returns deterministic scores for testing.
    
    Can be configured to return specific scores or use random
    values within a range.
    """
    
    def __init__(
        self,
        default_score: int = 3,
        score_variance: int = 0,
        seed: Optional[int] = None,
    ):
        """
        Initialize mock judge.
        
        Args:
            default_score: Base score to return (1-5)
            score_variance: Random variance (+/-) to add
            seed: Random seed for reproducibility
        """
        self.default_score = default_score
        self.score_variance = score_variance
        self._rng = random.Random(seed)
    
    def _get_score(self) -> int:
        """Get a score with optional variance."""
        if self.score_variance == 0:
            return self.default_score
        
        variance = self._rng.randint(-self.score_variance, self.score_variance)
        score = self.default_score + variance
        return max(1, min(5, score))
    
    async def evaluate_single(
        self,
        doc_id: str,
        content: str,
        trial: int = 1,
        criteria: Optional[List[EvaluationCriterion]] = None,
    ) -> SingleEvalResult:
        """
        Return mock single-doc evaluation.
        
        Args:
            doc_id: Document identifier
            content: Document content (used to vary scores)
            trial: Trial number
            criteria: Criteria to evaluate
            
        Returns:
            SingleEvalResult with mock scores
        """
        crit_list = criteria or get_default_criteria()
        
        # Use content length to add some deterministic variance
        length_factor = len(content) % 3 - 1  # -1, 0, or 1
        
        scores = []
        for crit in crit_list:
            base_score = self._get_score()
            # Vary by criterion name hash for consistency
            crit_factor = hash(crit.name) % 3 - 1
            score = max(1, min(5, base_score + length_factor + crit_factor))
            
            scores.append(CriterionScore(
                criterion=crit.name,
                score=score,
                reason=f"Mock score for {crit.name}",
            ))
        
        return SingleEvalResult(
            doc_id=doc_id,
            model="mock-model",
            trial=trial,
            scores=scores,
        )
    
    async def evaluate_pairwise(
        self,
        doc_id_1: str,
        content_1: str,
        doc_id_2: str,
        content_2: str,
        trial: int = 1,
    ) -> PairwiseResult:
        """
        Return mock pairwise evaluation.
        
        Winner is determined by content length (longer wins)
        or alphabetically if same length.
        
        Args:
            doc_id_1: First document ID
            content_1: First document content
            doc_id_2: Second document ID
            content_2: Second document content
            trial: Trial number
            
        Returns:
            PairwiseResult with mock winner
        """
        # Deterministic winner based on content length
        if len(content_1) > len(content_2):
            winner = doc_id_1
            reason = f"{doc_id_1} is longer"
        elif len(content_2) > len(content_1):
            winner = doc_id_2
            reason = f"{doc_id_2} is longer"
        else:
            # Same length - use alphabetical order
            winner = min(doc_id_1, doc_id_2)
            reason = f"{winner} wins alphabetically"
        
        return PairwiseResult(
            doc_id_1=doc_id_1,
            doc_id_2=doc_id_2,
            winner_doc_id=winner,
            model="mock-model",
            trial=trial,
            reason=reason,
        )


class FixedScoreJudge:
    """
    Judge that returns fixed scores for specific documents.
    
    Useful for testing ranking logic with known inputs.
    """
    
    def __init__(
        self,
        scores: Dict[str, int],
        pairwise_winners: Optional[Dict[tuple, str]] = None,
    ):
        """
        Initialize with fixed scores.
        
        Args:
            scores: Dict mapping doc_id to score (1-5)
            pairwise_winners: Dict mapping (doc1, doc2) to winner doc_id
        """
        self.scores = scores
        self.pairwise_winners = pairwise_winners or {}
    
    async def evaluate_single(
        self,
        doc_id: str,
        content: str,
        trial: int = 1,
        criteria: Optional[List[EvaluationCriterion]] = None,
    ) -> SingleEvalResult:
        """Return fixed score for document."""
        crit_list = criteria or get_default_criteria()
        score = self.scores.get(doc_id, 3)
        
        scores = [
            CriterionScore(
                criterion=crit.name,
                score=score,
                reason=f"Fixed score {score}",
            )
            for crit in crit_list
        ]
        
        return SingleEvalResult(
            doc_id=doc_id,
            model="fixed-model",
            trial=trial,
            scores=scores,
        )
    
    async def evaluate_pairwise(
        self,
        doc_id_1: str,
        content_1: str,
        doc_id_2: str,
        content_2: str,
        trial: int = 1,
    ) -> PairwiseResult:
        """Return fixed winner for pair."""
        # Check explicit winners
        key1 = (doc_id_1, doc_id_2)
        key2 = (doc_id_2, doc_id_1)
        
        if key1 in self.pairwise_winners:
            winner = self.pairwise_winners[key1]
        elif key2 in self.pairwise_winners:
            winner = self.pairwise_winners[key2]
        else:
            # Fall back to higher score
            score1 = self.scores.get(doc_id_1, 3)
            score2 = self.scores.get(doc_id_2, 3)
            winner = doc_id_1 if score1 >= score2 else doc_id_2
        
        return PairwiseResult(
            doc_id_1=doc_id_1,
            doc_id_2=doc_id_2,
            winner_doc_id=winner,
            model="fixed-model",
            trial=trial,
            reason=f"Fixed winner: {winner}",
        )
