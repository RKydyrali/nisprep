"""Grant-readiness predictor: weighted theta blend minus variance penalty plus speed bonus."""

from __future__ import annotations

import math

import numpy as np

__all__ = ["ReadinessPredictor"]


class ReadinessPredictor:
    """Predicts grant-readiness from subject thetas, cross-block variance and speed."""

    W = {"math": 0.27, "quant": 0.20, "nat_sci": 0.13, "lang": 0.40}
    PENALIZATION = 0.15
    SPEED_WEIGHT = 0.10

    @staticmethod
    def _speed_component(t_avg: float, t_norm: float = 90.0) -> float:
        """T_speed = min(1.0, (t_norm - t_avg) / t_norm), 0 when slower than t_norm."""
        if t_avg > t_norm:
            return 0.0
        return min(1.0, (t_norm - t_avg) / t_norm)

    @classmethod
    def readiness_score(
        cls,
        theta_math: float,
        theta_quant: float,
        theta_nat_sci: float,
        theta_lang: float,
        t_avg: float,
        t_norm: float = 90.0,
    ) -> float:
        """Psi = sum(w_k * theta_k) - 0.15 * var(theta) + 0.10 * T_speed."""
        thetas = np.array([theta_math, theta_quant, theta_nat_sci, theta_lang], dtype=float)
        sigma2 = float(np.var(thetas))
        weighted = (
            cls.W["math"] * theta_math
            + cls.W["quant"] * theta_quant
            + cls.W["nat_sci"] * theta_nat_sci
            + cls.W["lang"] * theta_lang
        )
        t_speed = cls._speed_component(t_avg, t_norm)
        return float(weighted - cls.PENALIZATION * sigma2 + cls.SPEED_WEIGHT * t_speed)

    @staticmethod
    def grant_probability(psi: float, psi_cutoff: float = 0.0) -> float:
        """P_grant = 1 / (1 + exp(-(psi - psi_cutoff)))."""
        return 1.0 / (1.0 + math.exp(-(psi - psi_cutoff)))

    @staticmethod
    def interpret_band(psi: float) -> str:
        """Band mapping: high (>1), medium [0, 1], low (<0)."""
        if psi > 1.0:
            return "high"
        if psi >= 0.0:
            return "medium"
        return "low"
