from __future__ import annotations

import unicodedata

from backend.app.modelos import EstimativaBayesiana, MetricasBiomecanicas, RelatorioInteligente


def _normalizar(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto.lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(valor, maximo))


class InteligenciaContextual:
    """Camada 4: interpreta anotacoes humanas e gera sinal estruturado."""

    pesos_alerta = {
        "dor": 0.28,
        "desconforto": 0.18,
        "joelho": 0.16,
        "quadril": 0.15,
        "lombar": 0.15,
        "fadiga": 0.22,
        "cansaco": 0.18,
        "rigidez": 0.12,
        "assimetria": 0.18,
    }
    pesos_positivos = {
        "solto": -0.08,
        "leve": -0.05,
        "estavel": -0.08,
        "confortavel": -0.06,
        "explosivo": -0.04,
    }

    def gerar(
        self,
        metricas: MetricasBiomecanicas,
        estimativa: EstimativaBayesiana,
        anotacao: str | None = None,
    ) -> RelatorioInteligente:
        anotacao = anotacao or ""
        texto = _normalizar(anotacao)
        prioridade = 0.12
        ajuste_confianca = 0.0
        achados: list[str] = []

        for termo, peso in self.pesos_alerta.items():
            if termo in texto:
                prioridade += peso
                ajuste_confianca += peso * 0.08
                achados.append(f"Anotacao destacou {termo}.")

        for termo, peso in self.pesos_positivos.items():
            if termo in texto:
                prioridade += peso
                ajuste_confianca += peso * 0.05
                achados.append(f"Anotacao descreveu estado {termo}.")

        if estimativa.risco_assimetria_p1 > 0.26:
            prioridade += 0.09
            achados.append("Jogador 1 apresenta risco leve a moderado de assimetria.")
        if estimativa.risco_assimetria_p2 > 0.26:
            prioridade += 0.09
            achados.append("Jogador 2 apresenta risco leve a moderado de assimetria.")
        if metricas.estabilidade_tronco_p1 < 0.76 or metricas.estabilidade_tronco_p2 < 0.76:
            prioridade += 0.07
            achados.append("A estabilidade do tronco caiu abaixo da zona ideal em parte da captura.")

        prioridade = _limitar(prioridade, 0.05, 0.98)
        ajuste_confianca = _limitar(ajuste_confianca, -0.08, 0.08)

        if not achados:
            achados.append("Sem alerta textual adicional; manter leitura pelo tracking e pelos intervalos bayesianos.")

        resumo = (
            "Leitura contextual priorizou "
            f"{'revisao clinica' if prioridade >= 0.55 else 'monitoramento orientado'} "
            "com base nas anotacoes e nos sinais estruturados da sessao."
        )

        return RelatorioInteligente(
            ajuste_confianca=round(ajuste_confianca, 3),
            prioridade_clinica=round(prioridade, 3),
            resumo=resumo,
            achados_principais=achados[:5],
            anotacao_processada=anotacao or "Sem anotacao adicional.",
        )

