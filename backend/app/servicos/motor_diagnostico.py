from __future__ import annotations

from backend.app.modelos import (
    AlertaDiagnostico,
    DiagnosticoSessao,
    EstimativaBayesiana,
    MetricasBiomecanicas,
    RelatorioInteligente,
)


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(valor, maximo))


class MotorDiagnostico:
    """Camada 5: transforma sinais numericos em alertas acionaveis."""

    def avaliar(
        self,
        metricas: MetricasBiomecanicas,
        estimativa: EstimativaBayesiana,
        relatorio: RelatorioInteligente,
    ) -> DiagnosticoSessao:
        alertas: list[AlertaDiagnostico] = []

        if estimativa.risco_assimetria_p1 >= 0.28 or metricas.simetria_apoio_p1 < 0.78:
            alertas.append(
                AlertaDiagnostico(
                    tipo="ASSIMETRIA",
                    atleta="Jogador 1",
                    severidade="moderada" if estimativa.risco_assimetria_p1 < 0.42 else "alta",
                    mensagem="Oscilacao entre apoio esquerdo e direito acima da faixa de conforto.",
                    confianca=round(max(estimativa.risco_assimetria_p1, 0.32), 2),
                )
            )

        if estimativa.risco_assimetria_p2 >= 0.28 or metricas.simetria_apoio_p2 < 0.78:
            alertas.append(
                AlertaDiagnostico(
                    tipo="ASSIMETRIA",
                    atleta="Jogador 2",
                    severidade="moderada" if estimativa.risco_assimetria_p2 < 0.42 else "alta",
                    mensagem="Recuperacao lateral irregular e transferencia de carga inconsistente.",
                    confianca=round(max(estimativa.risco_assimetria_p2, 0.31), 2),
                )
            )

        if metricas.estabilidade_tronco_p1 < 0.76 or metricas.estabilidade_tronco_p2 < 0.76:
            alertas.append(
                AlertaDiagnostico(
                    tipo="ESTABILIDADE",
                    atleta="Sessao",
                    severidade="moderada",
                    mensagem="Tronco perdeu rigidez em parte da janela capturada, sugerindo fadiga tecnica.",
                    confianca=round(max(0.35, relatorio.prioridade_clinica * 0.8), 2),
                )
            )

        if not alertas:
            alertas.append(
                AlertaDiagnostico(
                    tipo="CONTROLE",
                    atleta="Sessao",
                    severidade="baixa",
                    mensagem="Execucao manteve padrao estavel durante a janela observada.",
                    confianca=0.78,
                )
            )

        maior_alerta = max(alertas, key=lambda alerta: alerta.confianca)
        nivel_risco = "alto" if maior_alerta.confianca >= 0.58 else "moderado" if maior_alerta.confianca >= 0.35 else "baixo"

        if maior_alerta.tipo == "ASSIMETRIA":
            sinal_principal = "ASSIMETRIA_EM_APOIO"
            recomendacoes = [
                "Comparar sequencia lateral esquerda e direita em camera lenta.",
                "Repetir captura com foco em quadril, joelhos e tornozelos.",
                "Cruzar o alerta com avaliacao presencial antes de aumentar carga de treino.",
            ]
        elif maior_alerta.tipo == "ESTABILIDADE":
            sinal_principal = "RISCO_DE_SOBRECARGA"
            recomendacoes = [
                "Reduzir volume da repeticao atual e monitorar estabilidade do tronco.",
                "Checar fadiga acumulada e padrao respiratorio do atleta.",
                "Reprocessar nova janela apos intervalo curto para comparar recuperacao.",
            ]
        else:
            sinal_principal = "MOVIMENTO_ESTAVEL"
            recomendacoes = [
                "Manter o protocolo atual de coleta.",
                "Registrar nova janela com outra camera para validar o padrao.",
            ]

        confianca = _limitar(
            (1.0 - estimativa.incerteza_media) * 0.45
            + metricas.qualidade_tracking * 0.35
            + (0.45 + relatorio.ajuste_confianca) * 0.20,
            0.18,
            0.96,
        )

        resumo_execucao = (
            f"Diagnostico consolidado em {sinal_principal.lower()}: "
            f"tracking {metricas.qualidade_tracking:.0%}, "
            f"incerteza media {estimativa.incerteza_media:.0%} e "
            f"prioridade clinica {relatorio.prioridade_clinica:.0%}."
        )

        return DiagnosticoSessao(
            sinal_principal=sinal_principal,
            nivel_risco=nivel_risco,
            confianca=round(confianca, 3),
            resumo_execucao=resumo_execucao,
            recomendacoes=recomendacoes,
            alertas=alertas,
        )

