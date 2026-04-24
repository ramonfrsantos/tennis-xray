from __future__ import annotations

import numpy as np

from backend.app.modelos import EstimativaBayesiana, QuadroAnalise


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(valor, maximo))


class MotorBayesianoBiomecanico:
    """Camada 2: atualiza a confianca biomecanica com posterior Beta."""

    def __init__(
        self,
        alpha_inicial: float = 18.0,
        beta_inicial: float = 7.0,
        simulacoes: int = 6000,
        semente: int = 42,
    ):
        self.alpha_inicial = alpha_inicial
        self.beta_inicial = beta_inicial
        self.simulacoes = simulacoes
        self._rng = np.random.default_rng(semente)

    def atualizar(self, quadros: list[QuadroAnalise]) -> EstimativaBayesiana:
        atletas_p1 = [self._buscar_atleta(quadro, "P1") for quadro in quadros]
        atletas_p2 = [self._buscar_atleta(quadro, "P2") for quadro in quadros]

        consistentes_p1 = sum(1 for atleta in atletas_p1 if self._quadro_consistente(atleta))
        consistentes_p2 = sum(1 for atleta in atletas_p2 if self._quadro_consistente(atleta))
        total = max(len(quadros), 1)

        alpha_p1 = self.alpha_inicial + consistentes_p1
        beta_p1 = self.beta_inicial + (total - consistentes_p1)
        alpha_p2 = self.alpha_inicial + consistentes_p2
        beta_p2 = self.beta_inicial + (total - consistentes_p2)

        amostras_p1 = self._rng.beta(alpha_p1, beta_p1, size=self.simulacoes)
        amostras_p2 = self._rng.beta(alpha_p2, beta_p2, size=self.simulacoes)

        qualidade_p1 = float(amostras_p1.mean())
        qualidade_p2 = float(amostras_p2.mean())
        intervalo_p1 = np.percentile(amostras_p1, [2.5, 97.5])
        intervalo_p2 = np.percentile(amostras_p2, [2.5, 97.5])

        assimetria_p1 = float(np.mean([1.0 - atleta.indice_simetria for atleta in atletas_p1]))
        assimetria_p2 = float(np.mean([1.0 - atleta.indice_simetria for atleta in atletas_p2]))
        momento = self._calcular_momento(atletas_p1, atletas_p2)

        return EstimativaBayesiana(
            qualidade_movimento_p1=round(_limitar(qualidade_p1 + momento, 0.01, 0.99), 3),
            qualidade_movimento_p2=round(_limitar(qualidade_p2 - momento, 0.01, 0.99), 3),
            intervalo_p1_inferior=round(float(intervalo_p1[0]), 3),
            intervalo_p1_superior=round(float(intervalo_p1[1]), 3),
            intervalo_p2_inferior=round(float(intervalo_p2[0]), 3),
            intervalo_p2_superior=round(float(intervalo_p2[1]), 3),
            risco_assimetria_p1=round(_limitar(assimetria_p1 * 1.45, 0.01, 0.99), 3),
            risco_assimetria_p2=round(_limitar(assimetria_p2 * 1.45, 0.01, 0.99), 3),
            ajuste_momento=round(momento, 3),
            observacoes_processadas=total,
            incerteza_media=round(
                float((intervalo_p1[1] - intervalo_p1[0] + intervalo_p2[1] - intervalo_p2[0]) / 2),
                3,
            ),
        )

    def _quadro_consistente(self, atleta) -> bool:
        return (
            atleta.indice_estabilidade >= 0.74
            and atleta.indice_simetria >= 0.78
            and 118 <= atleta.flexao_joelho_graus <= 160
        )

    def _calcular_momento(self, atletas_p1: list, atletas_p2: list) -> float:
        janela = min(12, len(atletas_p1), len(atletas_p2))
        if janela < 4:
            return 0.0

        media_p1 = np.mean([atleta.indice_estabilidade for atleta in atletas_p1[-janela:]])
        media_p2 = np.mean([atleta.indice_estabilidade for atleta in atletas_p2[-janela:]])
        simetria_p1 = np.mean([atleta.indice_simetria for atleta in atletas_p1[-janela:]])
        simetria_p2 = np.mean([atleta.indice_simetria for atleta in atletas_p2[-janela:]])
        momento = ((media_p1 + simetria_p1) - (media_p2 + simetria_p2)) * 0.035
        return _limitar(float(momento), -0.04, 0.04)

    def _buscar_atleta(self, quadro: QuadroAnalise, id_atleta: str):
        for atleta in quadro.atletas:
            if atleta.id_atleta == id_atleta:
                return atleta
        raise ValueError(f"Atleta {id_atleta} nao encontrado no quadro {quadro.indice}")

