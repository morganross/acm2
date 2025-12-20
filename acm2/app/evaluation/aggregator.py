"""
Result aggregation utilities for evaluation.

Provides functions for aggregating and summarizing evaluation results
across multiple runs, iterations, and judge models.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import (
    CriterionScore,
    DocumentRanking,
    EloRating,
    PairwiseResult,
    SingleEvalResult,
)


@dataclass
class AggregatedScore:
    """Aggregated score across multiple evaluations."""
    
    criterion: str
    mean: float
    min_score: int
    max_score: int
    std_dev: float
    count: int
    
    @classmethod
    def from_scores(cls, criterion: str, scores: List[int]) -> "AggregatedScore":
        """Create from list of scores."""
        if not scores:
            return cls(criterion=criterion, mean=0, min_score=0, max_score=0, std_dev=0, count=0)
        
        n = len(scores)
        mean = sum(scores) / n
        variance = sum((s - mean) ** 2 for s in scores) / n if n > 1 else 0
        
        return cls(
            criterion=criterion,
            mean=mean,
            min_score=min(scores),
            max_score=max(scores),
            std_dev=variance ** 0.5,
            count=n,
        )


@dataclass
class DocumentAggregate:
    """Aggregated results for a single document."""
    
    doc_id: str
    overall_mean: float
    scores_by_criterion: Dict[str, AggregatedScore]
    num_evaluations: int
    model_breakdown: Dict[str, float]  # model -> avg score


def aggregate_single_results(
    results: List[SingleEvalResult],
) -> Dict[str, DocumentAggregate]:
    """
    Aggregate single-doc evaluation results by document.
    
    Args:
        results: List of all single-doc results
        
    Returns:
        Dict mapping doc_id to DocumentAggregate
    """
    # Group results by document
    by_doc: Dict[str, List[SingleEvalResult]] = defaultdict(list)
    for r in results:
        by_doc[r.doc_id].append(r)
    
    aggregates = {}
    for doc_id, doc_results in by_doc.items():
        # Collect scores by criterion
        scores_by_crit: Dict[str, List[int]] = defaultdict(list)
        model_scores: Dict[str, List[float]] = defaultdict(list)
        
        for result in doc_results:
            model_scores[result.model].append(result.average_score)
            for cs in result.scores:
                scores_by_crit[cs.criterion].append(cs.score)
        
        # Calculate aggregated scores
        crit_aggregates = {
            crit: AggregatedScore.from_scores(crit, scores)
            for crit, scores in scores_by_crit.items()
        }
        
        # Overall mean
        all_scores = [s for scores in scores_by_crit.values() for s in scores]
        overall_mean = sum(all_scores) / len(all_scores) if all_scores else 0
        
        # Model breakdown
        model_breakdown = {
            model: sum(scores) / len(scores)
            for model, scores in model_scores.items()
        }
        
        aggregates[doc_id] = DocumentAggregate(
            doc_id=doc_id,
            overall_mean=overall_mean,
            scores_by_criterion=crit_aggregates,
            num_evaluations=len(doc_results),
            model_breakdown=model_breakdown,
        )
    
    return aggregates


@dataclass
class PairwiseAggregate:
    """Aggregated pairwise results for a document pair."""
    
    doc_id_1: str
    doc_id_2: str
    wins_doc_1: int
    wins_doc_2: int
    total_comparisons: int
    
    @property
    def win_rate_1(self) -> float:
        """Win rate for doc 1."""
        if self.total_comparisons == 0:
            return 0.5
        return self.wins_doc_1 / self.total_comparisons
    
    @property
    def win_rate_2(self) -> float:
        """Win rate for doc 2."""
        if self.total_comparisons == 0:
            return 0.5
        return self.wins_doc_2 / self.total_comparisons
    
    @property
    def dominant_winner(self) -> Optional[str]:
        """Document that won majority of comparisons, or None if tied."""
        if self.wins_doc_1 > self.wins_doc_2:
            return self.doc_id_1
        elif self.wins_doc_2 > self.wins_doc_1:
            return self.doc_id_2
        return None


def aggregate_pairwise_results(
    results: List[PairwiseResult],
) -> Dict[Tuple[str, str], PairwiseAggregate]:
    """
    Aggregate pairwise results by document pair.
    
    Args:
        results: List of all pairwise results
        
    Returns:
        Dict mapping (doc_id_1, doc_id_2) to PairwiseAggregate
    """
    # Group by normalized pair (sorted)
    by_pair: Dict[Tuple[str, str], List[PairwiseResult]] = defaultdict(list)
    for r in results:
        key = tuple(sorted([r.doc_id_1, r.doc_id_2]))
        by_pair[key].append(r)
    
    aggregates = {}
    for (d1, d2), pair_results in by_pair.items():
        wins_1 = sum(1 for r in pair_results if r.winner_doc_id == d1)
        wins_2 = sum(1 for r in pair_results if r.winner_doc_id == d2)
        
        aggregates[(d1, d2)] = PairwiseAggregate(
            doc_id_1=d1,
            doc_id_2=d2,
            wins_doc_1=wins_1,
            wins_doc_2=wins_2,
            total_comparisons=len(pair_results),
        )
    
    return aggregates


def compute_win_matrix(
    results: List[PairwiseResult],
    doc_ids: List[str],
) -> Dict[str, Dict[str, int]]:
    """
    Compute win matrix from pairwise results.
    
    Args:
        results: List of pairwise results
        doc_ids: All document IDs
        
    Returns:
        Nested dict where matrix[winner][loser] = win count
    """
    matrix: Dict[str, Dict[str, int]] = {
        d: {other: 0 for other in doc_ids if other != d}
        for d in doc_ids
    }
    
    for r in results:
        loser = r.doc_id_2 if r.winner_doc_id == r.doc_id_1 else r.doc_id_1
        if r.winner_doc_id in matrix and loser in matrix[r.winner_doc_id]:
            matrix[r.winner_doc_id][loser] += 1
    
    return matrix


def rank_by_total_wins(
    results: List[PairwiseResult],
    doc_ids: List[str],
) -> List[Tuple[str, int]]:
    """
    Rank documents by total pairwise wins.
    
    Args:
        results: List of pairwise results
        doc_ids: All document IDs
        
    Returns:
        List of (doc_id, win_count) sorted by wins descending
    """
    wins: Dict[str, int] = {d: 0 for d in doc_ids}
    
    for r in results:
        wins[r.winner_doc_id] = wins.get(r.winner_doc_id, 0) + 1
    
    ranked = sorted(wins.items(), key=lambda x: x[1], reverse=True)
    return ranked


def combine_rankings(
    single_rankings: List[Tuple[str, float]],  # (doc_id, score)
    elo_ratings: List[EloRating],
    single_weight: float = 0.3,
    elo_weight: float = 0.7,
) -> List[DocumentRanking]:
    """
    Combine single-doc scores and Elo ratings into final rankings.
    
    Args:
        single_rankings: List of (doc_id, avg_score) from single eval
        elo_ratings: List of Elo ratings from pairwise eval
        single_weight: Weight for single-doc scores
        elo_weight: Weight for Elo ratings
        
    Returns:
        List of DocumentRanking sorted by combined score
    """
    # Normalize scores to 0-1 range
    single_dict = dict(single_rankings)
    elo_dict = {r.doc_id: r for r in elo_ratings}
    
    # Get all doc IDs
    all_docs = set(single_dict.keys()) | set(elo_dict.keys())
    
    # Normalize single scores (1-5 -> 0-1)
    single_norm = {d: (single_dict.get(d, 3) - 1) / 4 for d in all_docs}
    
    # Normalize Elo (find min/max)
    if elo_dict:
        elo_values = [r.rating for r in elo_ratings]
        elo_min, elo_max = min(elo_values), max(elo_values)
        elo_range = elo_max - elo_min if elo_max > elo_min else 1
        elo_norm = {d: (elo_dict[d].rating - elo_min) / elo_range if d in elo_dict else 0.5 for d in all_docs}
    else:
        elo_norm = {d: 0.5 for d in all_docs}
    
    # Compute combined scores
    combined = []
    for doc_id in all_docs:
        score = single_weight * single_norm[doc_id] + elo_weight * elo_norm[doc_id]
        elo_r = elo_dict.get(doc_id)
        
        combined.append(DocumentRanking(
            doc_id=doc_id,
            rank=0,
            elo_rating=elo_r.rating if elo_r else None,
            avg_score=single_dict.get(doc_id),
            wins=elo_r.wins if elo_r else 0,
            losses=elo_r.losses if elo_r else 0,
        ))
    
    # Sort by combined score
    combined.sort(key=lambda r: (
        single_weight * single_norm[r.doc_id] + elo_weight * elo_norm[r.doc_id]
    ), reverse=True)
    
    # Assign ranks
    for i, r in enumerate(combined, 1):
        r.rank = i
    
    return combined
