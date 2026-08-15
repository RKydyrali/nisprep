"""Dynamic Elo rating for CAT: decayed updates against ideal item difficulty."""

from __future__ import annotations

import math

__all__ = ["DynamicEloTracker"]


class DynamicEloTracker:
    """Elo ratings with time decay and item-difficulty opponents for adaptive tests."""

    @staticmethod
    def expected_score(ra: float, rb: float) -> float:
        """Expected score E = 1 / (1 + 10^((rb - ra) / 400))."""
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    @staticmethod
    def _decay_gamma(delta_seconds: float, t_norm: float = 90.0, tau: float = 15.0) -> float:
        """Decay gamma(dt) = exp(-max(0, dt - t_norm) / tau); 1.0 while within t_norm."""
        if delta_seconds <= t_norm:
            return 1.0
        return math.exp(-(delta_seconds - t_norm) / tau)

    @staticmethod
    def k_factor(total_solved: int) -> float:
        """K = 40 for novices (<100 solved), K = 16 for experienced solvers."""
        return 40.0 if total_solved < 100 else 16.0

    @classmethod
    def update_rating(
        cls,
        current_rating: float,
        opponent_rating: float,
        score: float,
        delta_seconds: float,
        total_solved: int,
        t_norm: float = 90.0,
        tau: float = 15.0,
    ) -> float:
        """R' = R + K * (S - E) * gamma(dt); S in {0, 0.5, 1}."""
        if score not in (0.0, 0.5, 1.0):
            raise ValueError(f"score must be 0, 0.5 or 1, got {score}")
        expected = cls.expected_score(current_rating, opponent_rating)
        gamma = cls._decay_gamma(delta_seconds, t_norm, tau)
        new_rating = current_rating + cls.k_factor(total_solved) * (score - expected) * gamma
        return round(float(new_rating), 4)

    @classmethod
    def update_vs_item_difficulty(
        cls,
        current_rating: float,
        item_b: float,
        score: float,
        delta_seconds: float,
        total_solved: int,
        t_norm: float = 90.0,
        tau: float = 15.0,
    ) -> float:
        """Update against the 'ideal solver' whose rating mirrors item difficulty: rb = 100 + b*400."""
        opponent_rating = 100.0 + item_b * 400.0
        return cls.update_rating(
            current_rating, opponent_rating, score, delta_seconds, total_solved, t_norm, tau
        )

    @staticmethod
    def streak_multiplier(streak_days: int) -> float:
        """Gamification bonus: 1.0 + min(0.2, 0.02 * streak_days), capped at 1.2."""
        return 1.0 + min(0.2, 0.02 * streak_days)
