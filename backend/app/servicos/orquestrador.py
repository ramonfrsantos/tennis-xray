from __future__ import annotations

from backend.app.modelos import AmostraLinhaTempo, RespostaPainel
from backend.app.servicos.camada_visao import VisaoQuadra
from backend.app.servicos.inteligencia_contextual import InteligenciaContextual
from backend.app.servicos.motor_bayesiano import MotorBayesianoBiomecanico
from backend.app.servicos.motor_diagnostico import MotorDiagnostico
from backend.app.servicos.ponte_sessao import PonteSessao


class OrquestradorBiomecanico:
    """Orquestra as cinco camadas em uma resposta pronta para o painel web."""

    def __init__(self):
        self.visao = VisaoQuadra()
        self.motor_bayesiano = MotorBayesianoBiomecanico()
        self.ponte = PonteSessao()
        self.inteligencia = InteligenciaContextual()
        self.motor_diagnostico = MotorDiagnostico()

    def executar_demo(
        self,
        total_quadros: int = 90,
        anotacao: str | None = None,
    ) -> RespostaPainel:
        self.visao.resetar()

        for indice in range(total_quadros):
            self.visao.gerar_quadro_demo(indice=indice, total_quadros=total_quadros)

        quadros = self.visao.quadros
        metricas = self.visao.computar_metricas()
        estimativa = self.motor_bayesiano.atualizar(quadros)
        relatorio = self.inteligencia.gerar(metricas, estimativa, anotacao)
        diagnostico = self.motor_diagnostico.avaliar(metricas, estimativa, relatorio)
        estado_sessao = self.ponte.construir_estado(quadros, metricas, self.visao.fps)
        linha_tempo = self._montar_linha_tempo(quadros)

        return RespostaPainel(
            estado_sessao=estado_sessao,
            quadros=quadros,
            metricas=metricas,
            estimativa=estimativa,
            relatorio=relatorio,
            diagnostico=diagnostico,
            linha_tempo=linha_tempo,
        )

    def _montar_linha_tempo(self, quadros):
        serie: list[AmostraLinhaTempo] = []
        for quadro in quadros:
            atleta_p1 = next(atleta for atleta in quadro.atletas if atleta.id_atleta == "P1")
            atleta_p2 = next(atleta for atleta in quadro.atletas if atleta.id_atleta == "P2")
            serie.append(
                AmostraLinhaTempo(
                    tempo_s=quadro.tempo_s,
                    qualidade_p1=atleta_p1.indice_estabilidade,
                    qualidade_p2=atleta_p2.indice_estabilidade,
                    simetria_p1=atleta_p1.indice_simetria,
                    simetria_p2=atleta_p2.indice_simetria,
                    velocidade_bola_ms=quadro.bola.velocidade_ms if quadro.bola else 0.0,
                    agressividade_instante=round(
                        atleta_p2.centro_quadra_m.y - atleta_p1.centro_quadra_m.y,
                        2,
                    ),
                )
            )
        return serie

