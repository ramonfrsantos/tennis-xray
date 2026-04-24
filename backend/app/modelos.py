from __future__ import annotations

from pydantic import BaseModel, Field


class Coordenada(BaseModel):
    x: float
    y: float


class CaixaDelimitadora(BaseModel):
    x: float
    y: float
    largura: float
    altura: float


class MarcadorCorporal(BaseModel):
    nome: str
    posicao: Coordenada
    confianca: float = 1.0


class AtletaQuadro(BaseModel):
    id_atleta: str
    rotulo: str
    caixa: CaixaDelimitadora
    centro_video: Coordenada
    centro_quadra_m: Coordenada
    velocidade_ms: float
    angulo_tronco_graus: float
    flexao_joelho_graus: float
    largura_base_apoio_m: float
    indice_estabilidade: float
    indice_simetria: float
    cobertura_lateral_m: float
    marcadores: list[MarcadorCorporal] = Field(default_factory=list)
    confianca_tracking: float = 1.0


class BolaQuadro(BaseModel):
    posicao_video: Coordenada
    posicao_quadra_m: Coordenada
    velocidade_ms: float
    confianca_tracking: float = 1.0


class PontoQuadra(BaseModel):
    nome: str
    posicao_video: Coordenada


class QuadroAnalise(BaseModel):
    indice: int
    tempo_s: float
    atletas: list[AtletaQuadro]
    bola: BolaQuadro | None = None
    pontos_quadra: list[PontoQuadra] = Field(default_factory=list)


class MetricasBiomecanicas(BaseModel):
    profundidade_media_p1_m: float
    profundidade_media_p2_m: float
    diferenca_agressividade: float
    cobertura_lateral_p1_m: float
    cobertura_lateral_p2_m: float
    razao_cobertura: float
    velocidade_media_bola_ms: float
    estabilidade_tronco_p1: float
    estabilidade_tronco_p2: float
    simetria_apoio_p1: float
    simetria_apoio_p2: float
    amplitude_tronco_max_graus: float
    qualidade_tracking: float
    quadros_utilizados: int


class EstimativaBayesiana(BaseModel):
    qualidade_movimento_p1: float
    qualidade_movimento_p2: float
    intervalo_p1_inferior: float
    intervalo_p1_superior: float
    intervalo_p2_inferior: float
    intervalo_p2_superior: float
    risco_assimetria_p1: float
    risco_assimetria_p2: float
    ajuste_momento: float
    observacoes_processadas: int
    incerteza_media: float


class RelatorioInteligente(BaseModel):
    ajuste_confianca: float
    prioridade_clinica: float
    resumo: str
    achados_principais: list[str] = Field(default_factory=list)
    anotacao_processada: str


class AlertaDiagnostico(BaseModel):
    tipo: str
    atleta: str
    severidade: str
    mensagem: str
    confianca: float


class DiagnosticoSessao(BaseModel):
    sinal_principal: str
    nivel_risco: str
    confianca: float
    resumo_execucao: str
    recomendacoes: list[str] = Field(default_factory=list)
    alertas: list[AlertaDiagnostico] = Field(default_factory=list)


class AmostraLinhaTempo(BaseModel):
    tempo_s: float
    qualidade_p1: float
    qualidade_p2: float
    simetria_p1: float
    simetria_p2: float
    velocidade_bola_ms: float
    agressividade_instante: float


class EstadoSessao(BaseModel):
    id_sessao: str
    titulo: str
    superficie: str
    camera: str
    fps: float
    total_quadros: int
    duracao_s: float
    fase_atual: str
    qualidade_calibracao: float
    marcadores_monitorados: list[str] = Field(default_factory=list)
    observacao: str


class RespostaPainel(BaseModel):
    estado_sessao: EstadoSessao
    quadros: list[QuadroAnalise]
    metricas: MetricasBiomecanicas
    estimativa: EstimativaBayesiana
    relatorio: RelatorioInteligente
    diagnostico: DiagnosticoSessao
    linha_tempo: list[AmostraLinhaTempo]


class RequisicaoAnaliseTexto(BaseModel):
    anotacao: str = ""

