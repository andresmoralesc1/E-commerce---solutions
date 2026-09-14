"""Tests unitarios para classifier."""
from app.services.classifier import SKUState, classify, state_color


class TestClassify:
    def test_ganador(self):
        assert classify(50.0) == SKUState.GANADOR
        assert classify(31.0) == SKUState.GANADOR

    def test_a_optimizar(self):
        assert classify(30.0) == SKUState.A_OPTIMIZAR
        assert classify(20.0) == SKUState.A_OPTIMIZAR
        assert classify(15.1) == SKUState.A_OPTIMIZAR

    def test_en_riesgo(self):
        assert classify(15.0) == SKUState.EN_RIESGO
        assert classify(10.0) == SKUState.EN_RIESGO
        assert classify(0.1) == SKUState.EN_RIESGO

    def test_a_perdida(self):
        assert classify(0.0) == SKUState.A_PERDIDA
        assert classify(-10.5) == SKUState.A_PERDIDA
        assert classify(-100.0) == SKUState.A_PERDIDA

    def test_none(self):
        # None -> default A_OPTIMIZAR (sin dato)
        assert classify(None) == SKUState.A_OPTIMIZAR

    def test_boundary(self):
        # 30 inclusive
        assert classify(30.0) == SKUState.A_OPTIMIZAR
        assert classify(30.001) == SKUState.GANADOR
        assert classify(15.0) == SKUState.EN_RIESGO
        assert classify(15.001) == SKUState.A_OPTIMIZAR


class TestStateColor:
    def test_colors(self):
        assert state_color(SKUState.GANADOR) == "green"
        assert state_color(SKUState.A_OPTIMIZAR) == "yellow"
        assert state_color(SKUState.EN_RIESGO) == "orange"
        assert state_color(SKUState.A_PERDIDA) == "red"

    def test_string_input(self):
        assert state_color("GANADOR") == "green"
        assert state_color("UNKNOWN") == "gray"