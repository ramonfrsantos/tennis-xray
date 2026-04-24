from __future__ import annotations

from backend.app.modelos import EstadoSessao, MetricasBiomecanicas, QuadroAnalise


class PonteSessao:
    """Camada 3: contextualiza a captura em um estado de sessao legivel."""

    def construir_estado(
        self,
        quadros: list[QuadroAnalise],
        metricas: MetricasBiomecanicas,
        fps: float,
    ) -> EstadoSessao:
        quadro_atual = quadros[-1]
        fase = self._classificar_fase(quadro_atual, metricas)

        return EstadoSessao(
            id_sessao="sessao-demo-001",
            titulo="Sessao demonstrativa de tracking biomecanico",
            superficie="Quadra dura indoor",
            camera="Camera lateral elevada",
            fps=fps,
            total_quadros=len(quadros),
            duracao_s=round(quadro_atual.tempo_s, 2),
            fase_atual=fase,
            qualidade_calibracao=metricas.qualidade_tracking,
            marcadores_monitorados=[
                "cabeca",
                "ombros",
                "quadris",
                "joelhos",
                "tornozelos",
                "bola",
            ],
            observacao=(
                "Pipeline pronto para evoluir de modo demo para inferencia real "
                "com YOLO, pose estimation e calibracao por homografia."
            ),
        )

    def _classificar_fase(
        self,
        quadro: QuadroAnalise,
        metricas: MetricasBiomecanicas,
    ) -> str:
        bola = quadro.bola
        if not bola:
            return "Aguardando bola"

        if bola.posicao_quadra_m.y < 8:
            return "Preparacao ofensiva"
        if bola.posicao_quadra_m.y > 16:
            return "Recuperacao defensiva"
        if metricas.velocidade_media_bola_ms > 15:
            return "Troca acelerada"
        return "Rali em controle"

