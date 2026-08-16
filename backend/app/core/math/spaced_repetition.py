"""SM-2 spaced repetition with context-swapping parameter cloning for error logs."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

__all__ = ["SmartErrorLogEngine"]


class SmartErrorLogEngine:
    """Error-log driven spaced repetition: SM-2 intervals + EF updates + clone generation."""

    MIN_EF = 1.3
    INTERVAL_1 = 1
    INTERVAL_2 = 3

    def __init__(self, ef: float = 2.5):
        if ef < self.MIN_EF:
            raise ValueError(f"ef must be >= {self.MIN_EF}, got {ef}")
        self.ef = float(ef)

    @staticmethod
    def calculate_next_interval(interval_number: int, ef: float) -> int:
        """I_1 = 1, I_2 = 3, I_n = round(I_(n-1) * ef) for n >= 3; minimum 1 day.

        Iterative implementation (no recursion — deep review counts must not
        blow the call stack).
        """
        if interval_number < 1:
            raise ValueError(f"interval_number must be >= 1, got {interval_number}")
        if interval_number == 1:
            return SmartErrorLogEngine.INTERVAL_1
        if interval_number == 2:
            return SmartErrorLogEngine.INTERVAL_2
        interval = SmartErrorLogEngine.INTERVAL_2
        for _ in range(3, interval_number + 1):
            interval = max(1, round(interval * ef))
        return interval

    @staticmethod
    def update_ef(ef: float, quality: float) -> float:
        """EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02)), floored at MIN_EF; q in [0, 5]."""
        if not 0.0 <= quality <= 5.0:
            raise ValueError(f"quality must be in [0, 5], got {quality}")
        diff = (5.0 - quality) * (0.08 + (5.0 - quality) * 0.02)
        new_ef = ef + (0.1 - diff)
        return max(SmartErrorLogEngine.MIN_EF, new_ef)

    def schedule_review(
        self,
        error_count: int,
        last_quality: float | None,
        current_ef: float | None = None,
        review_number: int | None = None,
    ) -> dict:
        """Schedule the next review of a persistently failing item.

        Repeat failure (error_count >= 2) resets to a 1-day interval when the last
        quality was poor (< 3); otherwise the SM-2 progression applies. Pass
        ``review_number`` explicitly (e.g. incremented on successful reviews) to
        drive the interval progression I_n = I_(n-1) * EF.
        """
        ef = self.ef if current_ef is None else float(current_ef)
        if error_count >= 2 and last_quality is not None and last_quality < 3:
            interval = SmartErrorLogEngine.INTERVAL_1
            new_ef = SmartErrorLogEngine.update_ef(ef, last_quality)
            n = 1
        else:
            n = max(1, error_count if review_number is None else int(review_number))
            interval = SmartErrorLogEngine.calculate_next_interval(n, ef)
            new_ef = ef if last_quality is None else SmartErrorLogEngine.update_ef(ef, last_quality)
        due_at = (date.today() + timedelta(days=interval)).isoformat()
        return {
            "interval_days": interval,
            "due_at": due_at,
            "ef": round(new_ef, 4),
            "review_number": n,
        }

    @staticmethod
    def clone_parameters(original: dict, seed: int | None = None) -> dict:
        """Resample a parameter template into a new dict for context swapping.

        Templates: {"min": m, "max": M, "step": s} draws from range(m, M+1, s);
        {"values": [...]} draws uniformly from the provided list. Deterministic
        for a fixed seed, otherwise uses numpy's global RNG.
        """
        rng = np.random.default_rng(seed)
        clone: dict[str, float] = {}
        for key, spec in original.items():
            if isinstance(spec, dict) and "min" in spec and "max" in spec:
                low = float(spec["min"])
                high = float(spec["max"])
                step = float(spec.get("step", 1))
                size = int(round((high - low) / step)) + 1
                pool = low + step * np.arange(size)
                chosen = float(rng.choice(pool))
                clone[key] = chosen
            elif isinstance(spec, dict) and "values" in spec:
                values = list(spec["values"])
                if not values:
                    raise ValueError(f"values list for {key!r} must not be empty")
                clone[key] = float(rng.choice(values))
            else:
                raise ValueError(
                    f"template for {key!r} must be {{'min','max','step'}} or {{'values': [...]}}"
                )
        return clone
