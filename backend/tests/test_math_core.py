"""Tests for the psychometric core: IRT, Elo, SM-2 spaced repetition, readiness."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.math import (
    DynamicEloTracker,
    ItemResponseTheory,
    ReadinessPredictor,
    SmartErrorLogEngine,
)

IRT = ItemResponseTheory
ELO = DynamicEloTracker
SM2 = SmartErrorLogEngine
RD = ReadinessPredictor


class TestIRTProbability:
    def test_three_pl_at_theta_equals_b(self):
        p = IRT.probability(0.0, b=0.0, a=1.0)
        assert p == pytest.approx(0.625, abs=1e-8)
        assert p == pytest.approx(0.25 + 0.75 / (1 + np.exp(0)), abs=1e-12)

    def test_probability_without_guessing_at_b(self):
        assert IRT.probability(0.0, b=0.0, a=1.0, c=0.0) == pytest.approx(0.5, abs=1e-8)

    def test_probability_increases_with_theta(self):
        assert IRT.probability(1.0, b=0.0) > IRT.probability(0.0, b=0.0)
        assert IRT.probability(0.0, b=0.0) > IRT.probability(-1.0, b=0.0)

    def test_probability_monotonic_across_range(self):
        thetas = np.linspace(-3.0, 3.0, 61)
        ps = [IRT.probability(t, 0.0) for t in thetas]
        assert all(ps[i] <= ps[i + 1] for i in range(len(ps) - 1))

    def test_probability_bounds(self):
        for t in (-3.0, 0.0, 3.0):
            p = IRT.probability(t, b=0.5, a=1.7)
            assert 1e-8 < p < 1 - 1e-8

    def test_asymptotic_limits(self):
        assert IRT.probability(-6.0, b=0.0, c=0.25) == pytest.approx(0.25, abs=1e-3)
        assert IRT.probability(6.0, b=0.0, c=0.25) == pytest.approx(1.0, abs=1e-3)

    def test_invalid_discrimination(self):
        with pytest.raises(ValueError):
            IRT.probability(0.0, b=0.0, a=0.0)
        with pytest.raises(ValueError):
            IRT.probability(0.0, b=0.0, a=-2.0)

    def test_clipping_at_limits(self):
        p = IRT.probability(-100.0, b=0.0)
        assert p >= 1e-8
        p2 = IRT.probability(100.0, b=0.0)
        assert p2 <= 1 - 1e-8


class TestIRTFisher:
    def test_fisher_reduces_to_2pl_for_c_zero(self):
        for t in (-2.0, 0.0, 1.5):
            p = IRT.probability(t, b=0.3, a=1.4, c=0.0)
            assert IRT.fisher_information(t, 0.3, a=1.4, c=0.0) == pytest.approx(
                (1.4 ** 2) * p * (1 - p), rel=1e-9
            )

    def test_fisher_nonnegative(self):
        for t in np.linspace(-3, 3, 25):
            assert IRT.fisher_information(t, 0.0, a=1.0) >= 0.0

    def test_fisher_peak_near_b(self):
        info_center = IRT.fisher_information(0.0, b=0.0, a=1.0, c=0.0)
        info_off = IRT.fisher_information(1.5, b=0.0, a=1.0, c=0.0)
        assert info_center > info_off

    def test_fisher_scales_with_a_squared_at_item_center(self):
        for t in (0.0,):
            f1 = IRT.fisher_information(t, 0.0, a=1.0, c=0.0)
            f2 = IRT.fisher_information(t, 0.0, a=2.0, c=0.0)
            assert f2 == pytest.approx(4.0 * f1, rel=1e-6)
        p_center = IRT.probability(0.0, b=0.0, a=1.0, c=0.0)
        assert IRT.fisher_information(0.0, b=0.0, a=1.0, c=0.0) == pytest.approx(
            p_center * (1 - p_center)
        )


class TestIRTEstimateTheta:
    def test_all_correct_estimates_high_theta(self):
        theta = IRT.estimate_theta([1, 1, 1, 1], b=[-2.0, -1.0, 0.0, 1.0])
        assert 0.5 < theta < 2.5

    def test_all_incorrect_estimates_low_theta(self):
        theta = IRT.estimate_theta([0, 0, 0, 0], b=[-2.0, -1.0, 0.0, 1.0])
        assert theta < -0.5

    def test_mixed_pattern_mle_in_range(self):
        theta = IRT.estimate_theta([0, 1, 1, 0], b=[-2.0, -1.0, 0.0, 1.0])
        assert -2.0 < theta < 2.0

    def test_mle_method_all_correct_falls_back_to_eap(self):
        theta = IRT.estimate_theta([1, 1, 1, 1], b=[-2.0, -1.0, 0.0, 1.0], method="mle")
        assert 0.5 < theta < 2.5

    def test_eap_method_returns_finite(self):
        theta = IRT.estimate_theta([0, 1, 1, 0], b=[-2.0, -1.0, 0.0, 1.0], method="eap")
        assert -3.0 <= theta <= 3.0

    def test_empty_pattern_raises(self):
        with pytest.raises(ValueError):
            IRT.estimate_theta([], b=[])

    def test_returns_float_rounded_to_4(self):
        theta = IRT.estimate_theta([0, 1, 1, 0], b=[-2.0, -1.0, 0.0, 1.0])
        assert isinstance(theta, float)
        assert round(theta, 4) == theta

    def test_pattern_with_discrimination(self):
        theta = IRT.estimate_theta([1, 0, 1, 0], b=[-1.0, 0.0, 1.0, 2.0], a=[1.5, 1.5, 1.5, 1.5])
        assert -3.0 <= theta <= 3.0

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            IRT.estimate_theta([1, 0], b=[0.0, 0.0], method="nope")


class TestIRTSelectNextQuestion:
    def test_question_near_theta_wins(self):
        items = [
            {"id": "easy", "b": -2.5, "a": 1.0},
            {"id": "mid", "b": 0.0, "a": 1.0},
            {"id": "hard", "b": 2.5, "a": 1.0},
        ]
        chosen = IRT.select_next_question(0.0, items)
        assert chosen["id"] == "mid"

    def test_tie_break_by_lower_b(self):
        items = [
            {"id": "low-b", "b": 0.1, "a": 1.0},
            {"id": "high-b", "b": 0.3, "a": 1.0},
        ]
        chosen = IRT.select_next_question(0.0, items)
        assert chosen["id"] == "low-b"

    def test_empty_items_returns_none(self):
        assert IRT.select_next_question(0.0, []) is None

    def test_high_discrimination_preferred_off_center(self):
        items = [
            {"id": "sharp", "b": 1.0, "a": 3.0},
            {"id": "flat", "b": 0.5, "a": 0.5},
        ]
        chosen = IRT.select_next_question(1.0, items)
        assert chosen["id"] == "sharp"

    def test_max_info_selected_always(self):
        items = [{"id": f"i{i}", "b": b, "a": 1.0} for i, b in enumerate([-1.0, 0.25, 1.5])]
        theta = 0.25
        chosen = IRT.select_next_question(theta, items)
        infos = [IRT.fisher_information(theta, it["b"], it["a"]) for it in items]
        assert IRT.fisher_information(theta, chosen["b"], chosen["a"]) == max(infos)


class TestElo:
    def test_expected_score_equal(self):
        assert ELO.expected_score(1500, 1500) == pytest.approx(0.5)

    def test_expected_score_1600_vs_1400(self):
        assert ELO.expected_score(1600, 1400) == pytest.approx(0.7597, abs=1e-3)
        assert ELO.expected_score(1600, 1400) == pytest.approx(1 / (1 + 10 ** ((1400 - 1600) / 400)), abs=1e-9)

    def test_expected_scores_sum_to_one(self):
        assert ELO.expected_score(1500, 1600) + ELO.expected_score(1600, 1500) == pytest.approx(1.0)

    def test_decay_within_norm_is_one(self):
        assert ELO._decay_gamma(0.0) == 1.0
        assert ELO._decay_gamma(45.0) == 1.0
        assert ELO._decay_gamma(90.0) == 1.0

    def test_decay_at_norm_plus_tau(self):
        assert ELO._decay_gamma(105.0, t_norm=90.0, tau=15.0) == pytest.approx(np.exp(-1.0), abs=1e-6)
        assert ELO._decay_gamma(105.0) == pytest.approx(0.3679, abs=1e-3)

    def test_decay_negative_delta_is_one(self):
        assert ELO._decay_gamma(-10.0) == 1.0

    def test_decay_monotonically_decreasing(self):
        g1 = ELO._decay_gamma(100.0)
        g2 = ELO._decay_gamma(200.0)
        assert g2 < g1

    def test_k_factor_boundary(self):
        assert ELO.k_factor(0) == 40.0
        assert ELO.k_factor(99) == 40.0
        assert ELO.k_factor(100) == 16.0
        assert ELO.k_factor(5000) == 16.0

    def test_winner_raises_rating(self):
        r_win = ELO.update_rating(1500.0, 100.0, 1.0, delta_seconds=30.0, total_solved=10)
        r_loss = ELO.update_rating(1500.0, 100.0, 0.0, delta_seconds=30.0, total_solved=10)
        assert r_win > 1500.0
        assert r_loss < 1500.0

    def test_k16_smaller_change_than_k40(self):
        big = ELO.update_rating(1500.0, 100.0, 1.0, delta_seconds=30.0, total_solved=50)
        small = ELO.update_rating(1500.0, 100.0, 1.0, delta_seconds=30.0, total_solved=100)
        assert abs(big - 1500.0) > abs(small - 1500.0)
        assert ELO.k_factor(50) == 40.0
        assert ELO.k_factor(100) == 16.0

    def test_draw_against_equal_opponent_keeps_rating(self):
        assert ELO.update_rating(1500.0, 1500.0, 0.5, delta_seconds=30.0, total_solved=10) == pytest.approx(1500.0)

    def test_draw_against_weaker_opponent_lowers_rating(self):
        delta = 40.0 * (0.5 - ELO.expected_score(1500.0, 100.0))
        r_draw = ELO.update_rating(1500.0, 100.0, 0.5, delta_seconds=30.0, total_solved=10)
        assert r_draw == pytest.approx(1500.0 + delta)
        assert r_draw < 1500.0

    def test_rating_returns_4_decimals(self):
        r = ELO.update_rating(1500.0, 100.0, 1.0, delta_seconds=30.0, total_solved=10)
        assert isinstance(r, float)
        assert round(r, 4) == r

    def test_item_difficulty_opponent_mapping(self):
        assert ELO.update_vs_item_difficulty(1500.0, 0.0, 1.0, 30.0, 10) == pytest.approx(
            ELO.update_rating(1500.0, 100.0, 1.0, 30.0, 10)
        )
        assert ELO.update_vs_item_difficulty(1500.0, -3.0, 1.0, 30.0, 10) == pytest.approx(
            ELO.update_rating(1500.0, -1100.0, 1.0, 30.0, 10)
        )
        assert ELO.update_vs_item_difficulty(1500.0, 3.0, 1.0, 30.0, 10) == pytest.approx(
            ELO.update_rating(1500.0, 1300.0, 1.0, 30.0, 10)
        )

    def test_invalid_score_raises(self):
        with pytest.raises(ValueError):
            ELO.update_rating(1500.0, 100.0, 0.7, 30.0, 10)

    def test_streak_multiplier(self):
        assert ELO.streak_multiplier(0) == 1.0
        assert ELO.streak_multiplier(5) == pytest.approx(1.1)
        assert ELO.streak_multiplier(10) == pytest.approx(1.2)
        assert ELO.streak_multiplier(100) == pytest.approx(1.2)

    def test_rating_bounded_due_to_decay(self):
        assert ELO.update_rating(1500.0, 100.0, 1.0, delta_seconds=3600.0, total_solved=10) == pytest.approx(1500.0, abs=0.01)


class TestSM2:
    def test_interval_sequence(self):
        assert SM2.calculate_next_interval(1, 2.5) == 1
        assert SM2.calculate_next_interval(2, 2.5) == 3
        assert SM2.calculate_next_interval(3, 2.5) == round(SM2.calculate_next_interval(2, 2.5) * 2.5)

    def test_interval_three_matches_round(self):
        i3 = SM2.calculate_next_interval(3, 2.5)
        expected = round(SM2.calculate_next_interval(2, 2.5) * 2.5)
        assert i3 == expected
        assert i3 in (7, 8)

    def test_interval_minimum_one(self):
        assert SM2.calculate_next_interval(3, 1.3) == max(1, round(3 * 1.3))
        assert SM2.calculate_next_interval(3, 1.3) >= 1

    def test_quality_five_increases_ef(self):
        assert SM2.update_ef(2.5, 5.0) == pytest.approx(2.6)

    def test_quality_two_decreases_ef(self):
        assert SM2.update_ef(2.5, 2.0) < 2.5

    def test_quality_zero_floored(self):
        assert SM2.update_ef(2.5, 0.0) == pytest.approx(max(1.3, 2.5 - 0.8))
        assert SM2.update_ef(1.3, 0.0) == pytest.approx(1.3)

    def test_quality_three_formula(self):
        assert SM2.update_ef(2.5, 3.0) == pytest.approx(2.5 + (0.1 - 2 * (0.08 + 2 * 0.02)))

    def test_quality_out_of_range_raises(self):
        with pytest.raises(ValueError):
            SM2.update_ef(2.5, 6.0)
        with pytest.raises(ValueError):
            SM2.update_ef(2.5, -1.0)

    def test_init_invalid_ef(self):
        with pytest.raises(ValueError):
            SM2(ef=1.0)
        assert SM2(ef=2.5).ef == 2.5

    def test_schedule_review_first_time(self):
        s = SM2().schedule_review(error_count=1, last_quality=5.0)
        assert s["interval_days"] == 1
        assert s["review_number"] == 1
        assert s["ef"] == pytest.approx(2.6)

    def test_schedule_review_resets_on_poor_quality(self):
        s = SM2().schedule_review(error_count=3, last_quality=2.0)
        assert s["interval_days"] == 1
        assert s["review_number"] == 1
        assert s["ef"] < 2.5

    def test_schedule_review_good_quality_progresses(self):
        s = SM2().schedule_review(error_count=3, last_quality=4.0)
        assert s["interval_days"] > 1
        assert s["review_number"] == 3

    def test_schedule_review_due_at_is_iso_date(self):
        s = SM2().schedule_review(error_count=1, last_quality=4.0)
        assert s["due_at"] == (__import__("datetime").date.today() + __import__("datetime").timedelta(days=s["interval_days"])).isoformat()

    def test_schedule_review_custom_ef(self):
        s = SM2().schedule_review(error_count=1, last_quality=5.0, current_ef=3.0)
        assert s["ef"] == pytest.approx(3.1)

    def test_clone_parameters_range(self):
        original = {"min_interval": {"min": 1, "max": 5, "step": 1}}
        clone = SM2.clone_parameters(original, seed=42)
        assert 1.0 <= clone["min_interval"] <= 5.0

    def test_clone_parameters_values(self):
        original = {"factor": {"values": [1.0, 2.0, 3.0]}}
        clone = SM2.clone_parameters(original, seed=7)
        assert clone["factor"] in (1.0, 2.0, 3.0)

    def test_clone_parameters_seed_deterministic(self):
        original = {"x": {"min": 10, "max": 20, "step": 1}}
        c1 = SM2.clone_parameters(original, seed=123)
        c2 = SM2.clone_parameters(original, seed=123)
        assert c1 == c2

    def test_clone_parameters_different_seeds(self):
        original = {"x": {"min": 1, "max": 100, "step": 1}}
        seeds = [SM2.clone_parameters(original, seed=s)["x"] for s in range(10)]
        assert len(set(seeds)) > 1

    def test_clone_returns_new_dict(self):
        original = {"x": {"min": 1, "max": 10, "step": 1}}
        clone = SM2.clone_parameters(original, seed=1)
        assert clone is not original
        assert set(clone) == set(original)

    def test_clone_throws_on_bad_template(self):
        with pytest.raises(ValueError):
            SM2.clone_parameters({"x": {"foo": 1}})
        with pytest.raises(ValueError):
            SM2.clone_parameters({"x": {"values": []}})


class TestReadiness:
    def test_baseline_case(self):
        psi = RD.readiness_score(1.0, 1.0, 1.0, 1.0, t_avg=45.0)
        assert psi == pytest.approx(1.05)

    def test_baseline_breakdown(self):
        psi = RD.readiness_score(1.0, 1.0, 1.0, 1.0, t_avg=45.0)
        assert psi == pytest.approx((0.27 + 0.20 + 0.13 + 0.40) * 1.0 + 0.10 * ((90 - 45) / 90))

    def test_variance_penalty(self):
        psi_var = RD.readiness_score(2.0, 1.0, 0.0, -1.0, t_avg=90.0)
        psi_flat = RD.readiness_score(0.5, 0.5, 0.5, 0.5, t_avg=90.0)
        thetas = np.array([2.0, 1.0, 0.0, -1.0])
        assert psi_var == pytest.approx(
            np.dot([0.27, 0.20, 0.13, 0.40], thetas) - 0.15 * np.var(thetas) + 0.0
        )
        assert psi_flat == pytest.approx(0.5, abs=1e-9)

    def test_speed_capped_at_one(self):
        fast = RD.readiness_score(0.0, 0.0, 0.0, 0.0, t_avg=0.0)
        assert fast == pytest.approx(0.10)

    def test_slow_speed_gives_zero_component(self):
        slow = RD.readiness_score(0.0, 0.0, 0.0, 0.0, t_avg=120.0)
        assert slow == pytest.approx(0.0)

    def test_all_negative_thetas_gives_negative_psi(self):
        psi = RD.readiness_score(-3.0, -3.0, -3.0, -3.0, t_avg=90.0)
        assert psi < 0.0

    def test_grant_probability_at_cutoff(self):
        assert RD.grant_probability(0.0) == pytest.approx(0.5)

    def test_grant_probability_positive_psi(self):
        assert RD.grant_probability(2.0) == pytest.approx(0.8808, abs=1e-3)
        assert RD.grant_probability(2.0) == pytest.approx(1 / (1 + np.exp(-2.0)), abs=1e-9)

    def test_grant_probability_custom_cutoff(self):
        assert RD.grant_probability(1.0, psi_cutoff=1.0) == pytest.approx(0.5)
        assert RD.grant_probability(0.0, psi_cutoff=-2.0) == pytest.approx(1 / (1 + np.exp(-2.0)), abs=1e-9)

    def test_interpret_band_high(self):
        assert RD.interpret_band(1.5) == "high"
        assert RD.interpret_band(1.0 + 1e-6) == "high"

    def test_interpret_band_medium(self):
        assert RD.interpret_band(0.0) == "medium"
        assert RD.interpret_band(0.5) == "medium"
        assert RD.interpret_band(1.0) == "medium"

    def test_interpret_band_low(self):
        assert RD.interpret_band(-0.5) == "low"
        assert RD.interpret_band(-3.0) == "low"

    def test_weights_sum(self):
        assert sum(RD.W.values()) == pytest.approx(1.0)
