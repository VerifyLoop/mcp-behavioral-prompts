"""Tests for the solver's verification tools.

These tools are run for real (sympy/pint) so failures here mean we broke a
genuine math/physics invariant, not a mock.
"""
from __future__ import annotations

from brainer_stem_tutor.solver.mcp_tools.plot_renderer import render_plot_svg
from brainer_stem_tutor.solver.mcp_tools.sympy_cas import (
    sympy_simplify,
    sympy_solve_equation,
    sympy_verify,
)
from brainer_stem_tutor.solver.mcp_tools.unit_checker import (
    check_dimensions,
    normalise_unit,
)


class TestSympyCAS:
    def test_simplify_quadratic(self) -> None:
        # simplify doesn't always factor — test a clearer simplification.
        r = sympy_simplify("(x**2 - 1) / (x - 1)")
        assert r.ok
        assert r.output == "x + 1"

    def test_simplify_invalid(self) -> None:
        # punctuation-only input cannot be parsed by sympify
        r = sympy_simplify("@#$%^&*")
        assert not r.ok

    def test_solve_linear(self) -> None:
        r = sympy_solve_equation("2*x + 4 = 0", "x")
        assert r.ok
        assert r.output == "[-2]"

    def test_solve_quadratic_two_roots(self) -> None:
        r = sympy_solve_equation("x**2 - 4", "x")
        assert r.ok
        assert "2" in r.output and "-2" in r.output

    def test_solve_invalid(self) -> None:
        r = sympy_solve_equation("@#$ not math", "x")
        assert not r.ok

    def test_verify_identical(self) -> None:
        r = sympy_verify("4", "4")
        assert r.ok
        assert r.output == "true"

    def test_verify_algebraic_equivalence(self) -> None:
        r = sympy_verify("(x+1)**2", "x**2 + 2*x + 1")
        assert r.ok, r.notes

    def test_verify_disagrees(self) -> None:
        r = sympy_verify("x + 1", "x + 2")
        assert not r.ok
        assert r.output == "false"

    def test_verify_numeric_tolerance(self) -> None:
        r = sympy_verify("1.0000000001", "1.0")
        assert r.ok


class TestUnitChecker:
    def test_velocity_dimensions(self) -> None:
        # a*t with a in m/s^2 and t in s should give m/s
        r = check_dimensions("m/s", "m/s**2 * s")
        assert r.ok, r.notes

    def test_force_newton(self) -> None:
        r = check_dimensions("N", "kg * m / s**2")
        assert r.ok, r.notes

    def test_mismatch(self) -> None:
        r = check_dimensions("m", "kg")
        assert not r.ok

    def test_normalise_unit_newton(self) -> None:
        r = normalise_unit("N")
        assert r.ok
        # Newton in base units is kg*m/s^2 in some order
        assert "kilogram" in r.output.lower() or "kg" in r.output.lower()

    def test_normalise_unit_invalid(self) -> None:
        r = normalise_unit("not_a_unit_xyz")
        assert not r.ok


class TestPlotRenderer:
    def test_simple_parabola(self) -> None:
        r = render_plot_svg("x**2", -2, 2, samples=20)
        assert r.ok
        assert "<svg" in r.svg
        assert "polyline" in r.svg

    def test_constant_function(self) -> None:
        r = render_plot_svg("3", -1, 1, samples=10)
        assert r.ok  # we expand y range when min==max

    def test_invalid_expression(self) -> None:
        r = render_plot_svg("###", -1, 1)
        assert not r.ok

    def test_invalid_range(self) -> None:
        r = render_plot_svg("x", 1, 1)
        assert not r.ok

    def test_divergent_function_no_finite(self) -> None:
        # log(x) over negative range -> no finite samples
        r = render_plot_svg("log(x)", -2, -1, samples=10)
        # sympy may still produce complex values that aren't isfinite for floats
        # in either case the renderer must not crash
        assert isinstance(r.ok, bool)
