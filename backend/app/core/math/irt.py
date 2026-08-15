"""Item Response Theory (3PL) engine for CAT: probability, information, ML/EAP estimation.

Implements the three-parameter logistic model used to drive question selection
and latent-ability (theta) estimation on the NIS prep platform.
"""

from __future__ import annotations

import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize_scalar
from scipy.stats import norm

__all__ = ["ItemResponseTheory"]


class ItemResponseTheory:
    """3PL IRT: item characteristic curves, Fisher information, theta estimation."""

    D = 1.702
    GUESSING = 0.25
    THETA_MIN = -3.0
    THETA_MAX = 3.0
    _PROB_EPS = 1e-8

    @classmethod
    def probability(cls, theta: float, b: float, a: float = 1.0, c: float = GUESSING) -> float:
        """3PL probability P_i(theta) = c + (1 - c) / (1 + exp(-D * a * (theta - b)))."""
        if a <= 0:
            raise ValueError(f"discrimination must be positive, got {a}")
        if not 0.0 <= c < 1.0:
            raise ValueError(f"guessing parameter must be in [0, 1), got {c}")
        z = cls.D * a * (theta - b)
        p = c + (1.0 - c) / (1.0 + np.exp(-z))
        return float(np.clip(p, cls._PROB_EPS, 1.0 - cls._PROB_EPS))

    @classmethod
    def fisher_information(
        cls, theta: float, b: float, a: float = 1.0, c: float = GUESSING
    ) -> float:
        """Fisher information for 3PL: a^2 * (1-P)/P * ((P-c)/(1-c))^2."""
        p = cls.probability(theta, b, a, c)
        if c == 0.0:
            return float(a * a * p * (1.0 - p))
        pseudo_guess = (p - c) / (1.0 - c)
        pseudo_guess = float(np.clip(pseudo_guess, cls._PROB_EPS, 1.0 - cls._PROB_EPS))
        return float(a * a * (1.0 - p) / p * pseudo_guess ** 2)

    @classmethod
    def log_likelihood(
        cls,
        theta: float,
        b: np.ndarray,
        u: np.ndarray,
        a: np.ndarray | None = None,
        c: float = GUESSING,
    ) -> float:
        """Log-likelihood ln L(theta) = sum [u_i ln P_i + (1-u_i) ln(1-P_i)]."""
        if b.size != u.size:
            raise ValueError("b and u must have the same length")
        if a is None:
            a = np.ones_like(b, dtype=float)
        if a.size != u.size:
            raise ValueError("a and u must have the same length")
        probs = np.array(
            [cls.probability(theta, float(bb), float(aa), c) for bb, aa in zip(b, a)]
        )
        probs = np.clip(probs, cls._PROB_EPS, 1.0 - cls._PROB_EPS)
        ua = np.asarray(u, dtype=float)
        return float(np.sum(ua * np.log(probs) + (1.0 - ua) * np.log(1.0 - probs)))

    @classmethod
    def _eap(cls, b: np.ndarray, u: np.ndarray, a: np.ndarray, c: float) -> float:
        """Expected a posteriori: integrate theta * L * phi / integrate L * phi over [-6, 6]."""
        if b.size == 0:
            raise ValueError("cannot compute EAP with an empty response pattern")

        def integrand_num(theta: float) -> float:
            return theta * np.exp(cls.log_likelihood(theta, b, u, a, c)) * norm.pdf(theta)

        def integrand_den(theta: float) -> float:
            return np.exp(cls.log_likelihood(theta, b, u, a, c)) * norm.pdf(theta)

        num, _ = quad(integrand_num, -6.0, 6.0, limit=200)
        den, _ = quad(integrand_den, -6.0, 6.0, limit=200)
        if den <= 0.0:
            return 0.0
        return float(np.clip(num / den, cls.THETA_MIN, cls.THETA_MAX))

    @classmethod
    def estimate_theta(
        cls,
        response_pattern: list[int] | np.ndarray,
        b: list[float],
        a: list[float] | None = None,
        c: float = GUESSING,
        method: str = "auto",
    ) -> float:
        """Estimate latent ability via MLE (with EAP fallback) or direct EAP.

        Degenerate patterns (all 0, all 1) or an MLE solution pinned to the
        boundary theta = +-3.0 automatically fall back to EAP.
        """
        u = np.asarray(response_pattern, dtype=float)
        b_arr = np.asarray(b, dtype=float)
        if u.size == 0:
            raise ValueError("response_pattern must not be empty")
        if b_arr.size != u.size:
            raise ValueError("b and response_pattern must have the same length")
        if a is None:
            a_arr = np.ones_like(b_arr, dtype=float)
        else:
            a_arr = np.asarray(a, dtype=float)
        if a_arr.size != u.size:
            raise ValueError("a and response_pattern must have the same length")

        if method not in ("auto", "mle", "eap"):
            raise ValueError(f"unknown method {method!r}, expected 'auto', 'mle' or 'eap'")

        if method == "eap":
            return round(cls._eap(b_arr, u, a_arr, c), 4)

        all_zero = bool(np.all(u == 0.0))
        all_one = bool(np.all(u == 1.0))
        degenerate = all_zero or all_one

        if degenerate:
            return round(cls._eap(b_arr, u, a_arr, c), 4)

        result = minimize_scalar(
            lambda th: -cls.log_likelihood(th, b_arr, u, a_arr, c),
            bounds=(cls.THETA_MIN, cls.THETA_MAX),
            method="bounded",
            options={"xatol": 1e-8},
        )
        theta_hat = float(result.x)

        at_boundary = (
            theta_hat <= cls.THETA_MIN + 1e-6 or theta_hat >= cls.THETA_MAX - 1e-6
        )
        if at_boundary:
            theta_hat = cls._eap(b_arr, u, a_arr, c)

        return round(theta_hat, 4)

    @classmethod
    def select_next_question(cls, theta: float, items: list[dict]) -> dict | None:
        """Pick the unused item maximizing Fisher information at theta (tie-break: lower b)."""
        if not items:
            return None
        best = None
        best_info = -1.0
        for item in items:
            info = cls.fisher_information(theta, float(item["b"]), float(item.get("a", 1.0)))
            if info > best_info or (
                abs(info - best_info) < 1e-12
                and best is not None
                and float(item["b"]) < float(best["b"])
            ):
                best = item
                best_info = info
        return best
