from __future__ import annotations

import math
from collections import deque
from statistics import fmean, median

from backend.app.modelos import (
    AtletaQuadro,
    BolaQuadro,
    CaixaDelimitadora,
    Coordenada,
    MarcadorCorporal,
    MetricasBiomecanicas,
    PontoQuadra,
    QuadroAnalise,
)


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(valor, maximo))


class VisaoQuadra:
    """Camada 1: tracking, marcadores corporais e normalizacao da quadra.

    A versao entregue aqui gera uma simulacao deterministica e visualizavel,
    pronta para ser conectada posteriormente a YOLO/Pose reais.
    """

    LARGURA_QUADRA_M = 10.97
    COMPRIMENTO_QUADRA_M = 23.77

    def __init__(self, fps: float = 15.0, janela: int = 120):
        self.fps = fps
        self._buffer: deque[QuadroAnalise] = deque(maxlen=janela)

    @property
    def quadros(self) -> list[QuadroAnalise]:
        return list(self._buffer)

    def resetar(self) -> None:
        self._buffer.clear()

    def gerar_quadro_demo(
        self,
        indice: int,
        total_quadros: int = 90,
    ) -> QuadroAnalise:
        progresso = indice / max(total_quadros - 1, 1)
        pulso = math.sin(progresso * math.pi * 6)
        contra_pulso = math.sin(progresso * math.pi * 6 + math.pi)
        deslocamento_bola = math.sin(progresso * math.pi * 8 + 0.35)

        p1_x = 0.49 + 0.13 * math.sin(progresso * math.pi * 2.5)
        p1_y = 0.78 + 0.04 * math.cos(progresso * math.pi * 2.2)
        p2_x = 0.53 + 0.12 * math.sin(progresso * math.pi * 2.8 + 0.8)
        p2_y = 0.29 + 0.05 * math.cos(progresso * math.pi * 2.0 + 1.0)

        bola_x = _limitar(0.5 + 0.18 * deslocamento_bola, 0.26, 0.74)
        bola_y = _limitar(0.54 + 0.22 * math.sin(progresso * math.pi * 8), 0.24, 0.84)

        ultimo_quadro = self._buffer[-1] if self._buffer else None
        atleta_p1 = self._criar_atleta(
            id_atleta="P1",
            rotulo="Jogador 1",
            centro_x=p1_x,
            centro_y=p1_y,
            inclinacao=8.0 * pulso,
            abertura=0.74 + 0.12 * abs(math.cos(progresso * math.pi * 6)),
            cobertura=2.8 + 0.7 * abs(math.sin(progresso * math.pi * 3)),
            ultimo_quadro=ultimo_quadro,
        )
        atleta_p2 = self._criar_atleta(
            id_atleta="P2",
            rotulo="Jogador 2",
            centro_x=p2_x,
            centro_y=p2_y,
            inclinacao=-9.0 * contra_pulso,
            abertura=0.67 + 0.10 * abs(math.sin(progresso * math.pi * 7)),
            cobertura=2.5 + 0.8 * abs(math.cos(progresso * math.pi * 3.2)),
            ultimo_quadro=ultimo_quadro,
        )
        bola = self._criar_bola(bola_x, bola_y, ultimo_quadro)

        quadro = QuadroAnalise(
            indice=indice,
            tempo_s=indice / self.fps,
            atletas=[atleta_p1, atleta_p2],
            bola=bola,
            pontos_quadra=self._pontos_quadra_video(),
        )
        self._buffer.append(quadro)
        return quadro

    def computar_metricas(self) -> MetricasBiomecanicas:
        quadros = list(self._buffer)
        if not quadros:
            return MetricasBiomecanicas(
                profundidade_media_p1_m=0.0,
                profundidade_media_p2_m=0.0,
                diferenca_agressividade=0.0,
                cobertura_lateral_p1_m=0.0,
                cobertura_lateral_p2_m=0.0,
                razao_cobertura=1.0,
                velocidade_media_bola_ms=0.0,
                estabilidade_tronco_p1=0.0,
                estabilidade_tronco_p2=0.0,
                simetria_apoio_p1=0.0,
                simetria_apoio_p2=0.0,
                amplitude_tronco_max_graus=0.0,
                qualidade_tracking=0.0,
                quadros_utilizados=0,
            )

        atletas_p1 = [self._buscar_atleta(quadro, "P1") for quadro in quadros]
        atletas_p2 = [self._buscar_atleta(quadro, "P2") for quadro in quadros]
        rede_y = self.COMPRIMENTO_QUADRA_M / 2

        profundidade_p1 = fmean(abs(a.centro_quadra_m.y - rede_y) for a in atletas_p1)
        profundidade_p2 = fmean(abs(a.centro_quadra_m.y - rede_y) for a in atletas_p2)
        cobertura_p1 = max(a.centro_quadra_m.x for a in atletas_p1) - min(
            a.centro_quadra_m.x for a in atletas_p1
        )
        cobertura_p2 = max(a.centro_quadra_m.x for a in atletas_p2) - min(
            a.centro_quadra_m.x for a in atletas_p2
        )
        velocidades_bola = [quadro.bola.velocidade_ms for quadro in quadros if quadro.bola]
        confiancas = [
            atleta.confianca_tracking
            for quadro in quadros
            for atleta in quadro.atletas
        ]

        return MetricasBiomecanicas(
            profundidade_media_p1_m=round(profundidade_p1, 2),
            profundidade_media_p2_m=round(profundidade_p2, 2),
            diferenca_agressividade=round(profundidade_p2 - profundidade_p1, 2),
            cobertura_lateral_p1_m=round(cobertura_p1, 2),
            cobertura_lateral_p2_m=round(cobertura_p2, 2),
            razao_cobertura=round(cobertura_p1 / (cobertura_p2 + 1e-6), 2),
            velocidade_media_bola_ms=round(median(velocidades_bola), 2) if velocidades_bola else 0.0,
            estabilidade_tronco_p1=round(fmean(a.indice_estabilidade for a in atletas_p1), 2),
            estabilidade_tronco_p2=round(fmean(a.indice_estabilidade for a in atletas_p2), 2),
            simetria_apoio_p1=round(fmean(a.indice_simetria for a in atletas_p1), 2),
            simetria_apoio_p2=round(fmean(a.indice_simetria for a in atletas_p2), 2),
            amplitude_tronco_max_graus=round(
                max(abs(a.angulo_tronco_graus) for a in atletas_p1 + atletas_p2),
                2,
            ),
            qualidade_tracking=round(fmean(confiancas), 2),
            quadros_utilizados=len(quadros),
        )

    def _criar_atleta(
        self,
        id_atleta: str,
        rotulo: str,
        centro_x: float,
        centro_y: float,
        inclinacao: float,
        abertura: float,
        cobertura: float,
        ultimo_quadro: QuadroAnalise | None,
    ) -> AtletaQuadro:
        escala = 0.35 + centro_y * 0.55
        largura = 0.034 + escala * 0.03
        altura = 0.11 + escala * 0.13
        angulo_tronco = inclinacao
        flexao_joelho = 144.0 - 18.0 * abs(math.sin(math.radians(inclinacao * 6)))
        largura_base = abertura
        estabilidade = _limitar(0.93 - abs(angulo_tronco) / 42.0 - abs(largura_base - 0.75) / 2.5, 0.52, 0.97)
        simetria = _limitar(0.9 - abs(angulo_tronco) / 80.0 + (largura_base - 0.7) / 4.0, 0.58, 0.98)
        confianca = _limitar(0.96 - abs(centro_x - 0.5) * 0.15, 0.78, 0.98)

        centro_quadra = Coordenada(
            x=round(centro_x * self.LARGURA_QUADRA_M, 2),
            y=round(centro_y * self.COMPRIMENTO_QUADRA_M, 2),
        )
        caixa = CaixaDelimitadora(
            x=round(centro_x - largura / 2, 4),
            y=round(centro_y - altura / 2, 4),
            largura=round(largura, 4),
            altura=round(altura, 4),
        )

        velocidade = self._velocidade_atleta(id_atleta, centro_quadra, ultimo_quadro)
        marcadores = self._gerar_marcadores(centro_x, centro_y, largura, altura, angulo_tronco)

        return AtletaQuadro(
            id_atleta=id_atleta,
            rotulo=rotulo,
            caixa=caixa,
            centro_video=Coordenada(x=round(centro_x, 4), y=round(centro_y, 4)),
            centro_quadra_m=centro_quadra,
            velocidade_ms=round(velocidade, 2),
            angulo_tronco_graus=round(angulo_tronco, 2),
            flexao_joelho_graus=round(flexao_joelho, 2),
            largura_base_apoio_m=round(largura_base, 2),
            indice_estabilidade=round(estabilidade, 2),
            indice_simetria=round(simetria, 2),
            cobertura_lateral_m=round(cobertura, 2),
            marcadores=marcadores,
            confianca_tracking=round(confianca, 2),
        )

    def _criar_bola(
        self,
        centro_x: float,
        centro_y: float,
        ultimo_quadro: QuadroAnalise | None,
    ) -> BolaQuadro:
        posicao_quadra = Coordenada(
            x=round(centro_x * self.LARGURA_QUADRA_M, 2),
            y=round(centro_y * self.COMPRIMENTO_QUADRA_M, 2),
        )
        velocidade = 0.0
        if ultimo_quadro and ultimo_quadro.bola:
            dx = posicao_quadra.x - ultimo_quadro.bola.posicao_quadra_m.x
            dy = posicao_quadra.y - ultimo_quadro.bola.posicao_quadra_m.y
            velocidade = math.sqrt(dx * dx + dy * dy) * self.fps

        return BolaQuadro(
            posicao_video=Coordenada(x=round(centro_x, 4), y=round(centro_y, 4)),
            posicao_quadra_m=posicao_quadra,
            velocidade_ms=round(velocidade, 2),
            confianca_tracking=0.95,
        )

    def _gerar_marcadores(
        self,
        centro_x: float,
        centro_y: float,
        largura: float,
        altura: float,
        angulo_tronco: float,
    ) -> list[MarcadorCorporal]:
        deslocamento = math.sin(math.radians(angulo_tronco)) * largura * 0.25
        cabeca = Coordenada(x=centro_x + deslocamento * 0.3, y=centro_y - altura * 0.45)
        ombro_e = Coordenada(x=centro_x - largura * 0.24 + deslocamento, y=centro_y - altura * 0.25)
        ombro_d = Coordenada(x=centro_x + largura * 0.24 + deslocamento, y=centro_y - altura * 0.24)
        quadril_e = Coordenada(x=centro_x - largura * 0.18, y=centro_y + altura * 0.02)
        quadril_d = Coordenada(x=centro_x + largura * 0.18, y=centro_y + altura * 0.02)
        joelho_e = Coordenada(x=centro_x - largura * 0.16, y=centro_y + altura * 0.28)
        joelho_d = Coordenada(x=centro_x + largura * 0.17, y=centro_y + altura * 0.27)
        tornozelo_e = Coordenada(x=centro_x - largura * 0.23, y=centro_y + altura * 0.49)
        tornozelo_d = Coordenada(x=centro_x + largura * 0.25, y=centro_y + altura * 0.49)

        pares = [
            ("cabeca", cabeca),
            ("ombro_esquerdo", ombro_e),
            ("ombro_direito", ombro_d),
            ("quadril_esquerdo", quadril_e),
            ("quadril_direito", quadril_d),
            ("joelho_esquerdo", joelho_e),
            ("joelho_direito", joelho_d),
            ("tornozelo_esquerdo", tornozelo_e),
            ("tornozelo_direito", tornozelo_d),
        ]
        return [
            MarcadorCorporal(
                nome=nome,
                posicao=Coordenada(x=round(posicao.x, 4), y=round(posicao.y, 4)),
                confianca=0.96,
            )
            for nome, posicao in pares
        ]

    def _velocidade_atleta(
        self,
        id_atleta: str,
        centro_quadra: Coordenada,
        ultimo_quadro: QuadroAnalise | None,
    ) -> float:
        if not ultimo_quadro:
            return 0.0

        atleta_anterior = self._buscar_atleta(ultimo_quadro, id_atleta)
        dx = centro_quadra.x - atleta_anterior.centro_quadra_m.x
        dy = centro_quadra.y - atleta_anterior.centro_quadra_m.y
        return math.sqrt(dx * dx + dy * dy) * self.fps

    def _buscar_atleta(self, quadro: QuadroAnalise, id_atleta: str) -> AtletaQuadro:
        for atleta in quadro.atletas:
            if atleta.id_atleta == id_atleta:
                return atleta
        raise ValueError(f"Atleta {id_atleta} nao encontrado no quadro {quadro.indice}")

    def _pontos_quadra_video(self) -> list[PontoQuadra]:
        pontos = [
            ("sup_esquerda", 0.28, 0.33),
            ("sup_direita", 0.72, 0.33),
            ("inf_esquerda", 0.18, 0.86),
            ("inf_direita", 0.82, 0.86),
            ("servico_sup_esquerda", 0.35, 0.47),
            ("servico_sup_direita", 0.65, 0.47),
            ("servico_inf_esquerda", 0.28, 0.67),
            ("servico_inf_direita", 0.72, 0.67),
            ("centro_sup", 0.50, 0.47),
            ("centro_inf", 0.50, 0.67),
            ("rede_esquerda", 0.22, 0.56),
            ("rede_direita", 0.78, 0.56),
        ]
        return [
            PontoQuadra(
                nome=nome,
                posicao_video=Coordenada(x=x, y=y),
            )
            for nome, x, y in pontos
        ]

