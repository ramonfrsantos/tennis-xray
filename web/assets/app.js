const elementos = {
  botaoDemo: document.querySelector("#botao-demo"),
  botaoPausar: document.querySelector("#botao-pausar"),
  svgVideo: document.querySelector("#svg-video"),
  svgMini: document.querySelector("#svg-mini"),
  svgLinhaTempo: document.querySelector("#svg-linha-tempo"),
  tituloSessao: document.querySelector("#titulo-sessao"),
  superficie: document.querySelector("#fato-superficie"),
  camera: document.querySelector("#fato-camera"),
  quadros: document.querySelector("#fato-quadros"),
  duracao: document.querySelector("#fato-duracao"),
  observacaoSessao: document.querySelector("#observacao-sessao"),
  listaCamadas: document.querySelector("#lista-camadas"),
  tabelaAtletas: document.querySelector("#tabela-atletas"),
  listaAchados: document.querySelector("#lista-achados"),
  listaAlertas: document.querySelector("#lista-alertas"),
  listaRecomendacoes: document.querySelector("#lista-recomendacoes"),
  textoRelatorio: document.querySelector("#texto-relatorio"),
  gradeMetricas: document.querySelector("#grade-metricas"),
  statusFase: document.querySelector("#status-fase"),
  statusDiagnostico: document.querySelector("#status-diagnostico"),
  hudQuadro: document.querySelector("#hud-quadro"),
  hudBola: document.querySelector("#hud-bola"),
  hudCalibracao: document.querySelector("#hud-calibracao"),
  formUpload: document.querySelector("#form-upload"),
  campoVideo: document.querySelector("#campo-video"),
  statusUpload: document.querySelector("#status-upload"),
  videoUploadCard: document.querySelector("#video-upload-card"),
  videoUpload: document.querySelector("#video-upload"),
  videoWrap: document.querySelector(".video-wrap"),
  botaoCancelarJob: document.querySelector("#botao-cancelar-job"),
  modalCalibracao: document.querySelector("#modal-calibracao"),
  videoCalibracao: document.querySelector("#video-calibracao"),
  canvasCalibracao: document.querySelector("#canvas-calibracao"),
  overlayCalibracao: document.querySelector("#overlay-calibracao"),
  instrucaoCalibracao: document.querySelector("#instrucao-calibracao"),
  alvoCalibracao: document.querySelector("#alvo-calibracao"),
  progressoCalibracao: document.querySelector("#progresso-calibracao"),
  qtdJogadoresCalibracao: document.querySelector("#qtd-jogadores-calibracao"),
  rangeTempoCalibracao: document.querySelector("#range-tempo-calibracao"),
  tempoCalibracao: document.querySelector("#tempo-calibracao"),
  rangeZoomCalibracao: document.querySelector("#range-zoom-calibracao"),
  zoomCalibracao: document.querySelector("#zoom-calibracao"),
  botaoZoomMenosCalibracao: document.querySelector("#botao-zoom-menos-calibracao"),
  botaoZoomMaisCalibracao: document.querySelector("#botao-zoom-mais-calibracao"),
  botaoResetZoomCalibracao: document.querySelector("#botao-reset-zoom-calibracao"),
  botaoContatoRaqueteCalibracao: document.querySelector("#botao-contato-raquete-calibracao"),
  botaoProjecaoContatoCalibracao: document.querySelector("#botao-projecao-contato-calibracao"),
  botaoPrimeiroToqueCalibracao: document.querySelector("#botao-primeiro-toque-calibracao"),
  botaoCalcularVelocidadeSaque: document.querySelector("#botao-calcular-velocidade-saque"),
  botaoAutoRastroBola: document.querySelector("#botao-auto-rastro-bola"),
  botaoModoPontoCalibracao: document.querySelector("#botao-modo-ponto-calibracao"),
  botaoModoTrocaCalibracao: document.querySelector("#botao-modo-troca-calibracao"),
  resultadoVelocidadeSaque: document.querySelector("#resultado-velocidade-saque"),
  textoResultadoVelocidadeSaque: document.querySelector("#texto-resultado-velocidade-saque"),
  botaoDownloadVideoSaque: document.querySelector("#botao-download-video-saque"),
  botaoFecharCalibracao: document.querySelector("#botao-fechar-calibracao"),
  botaoVoltarCalibracao: document.querySelector("#botao-voltar-calibracao"),
  botaoDesfazerCalibracao: document.querySelector("#botao-desfazer-calibracao"),
  botaoPularPontoQuadra: document.querySelector("#botao-pular-ponto-quadra"),
  botaoProximoCalibracao: document.querySelector("#botao-proximo-calibracao"),
  botaoFinalizarCalibracao: document.querySelector("#botao-finalizar-calibracao"),
  formAnotacao: document.querySelector("#form-anotacao"),
  campoAnotacao: document.querySelector("#campo-anotacao"),
  statusAnotacao: document.querySelector("#status-anotacao"),
};

const estado = {
  dados: null,
  arquitetura: [],
  indiceQuadro: 0,
  animando: true,
  temporizador: null,
  modoVideoReal: false,
  metadataAnaliseReal: null,
  jobAtual: null,
  pollingJob: null,
  pollingJobEmAndamento: false,
  falhasConsultaJob: 0,
  carregandoAnaliseCompletaJob: null,
  arquivoUploadSelecionado: null,
  objetoUrlCalibracao: null,
  objetoUrlFrameServidor: null,
  calibracaoServidorId: null,
  frameServidorImagem: null,
  frameServidorSeq: 0,
  frameServidorIndexAtual: null,
  frameServidorTimer: null,
  frameServidorAbortController: null,
  calibracao: null,
  calibracaoPronta: false,
  modoCalibracao: "ponto",
  etapaCalibracao: "quadra",
  indicePontoQuadra: 0,
  indiceCentroBaseCalibracao: 0,
  indiceJogadorCalibracao: 0,
  zoomCalibracao: 1,
  panCalibracao: { x: 0.5, y: 0.5 },
  ultimoPonteiroCalibracao: { x: 0.5, y: 0.5 },
  arrastandoCalibracao: false,
  dragCalibracao: null,
  suprimirCliqueCalibracao: false,
  carregandoFrameCalibracao: false,
  tipoEspecialBola: null,
  previewVelocidadeSaque: null,
  previewVelocidadeSaqueErro: "",
  autoRastroBolaEmAndamento: false,
  autoRastroBolaAguardandoInicio: false,
  autoRastroBolaErro: "",
  autoRastroBolaResumo: null,
  downloadSaqueEmAndamento: false,
  downloadSaqueJobId: null,
  downloadSaqueUrl: null,
  downloadSaqueErro: "",
};

const PONTOS_QUADRA_CALIBRACAO = [
  { id: "sup_esquerda", label: "Base superior externa - canto esquerdo" },
  { id: "sup_direita", label: "Base superior externa - canto direito" },
  { id: "inf_esquerda", label: "Base inferior externa - canto esquerdo" },
  { id: "inf_direita", label: "Base inferior externa - canto direito" },
  { id: "rede_esquerda", label: "Rede - extremidade esquerda na lateral externa" },
  { id: "rede_direita", label: "Rede - extremidade direita na lateral externa" },
  { id: "servico_sup_esquerda", label: "Servico superior - lateral interna esquerda" },
  { id: "servico_sup_direita", label: "Servico superior - lateral interna direita" },
  { id: "servico_inf_esquerda", label: "Servico inferior - lateral interna esquerda" },
  { id: "servico_inf_direita", label: "Servico inferior - lateral interna direita" },
  { id: "centro_sup", label: "T superior - centro da linha de serviço" },
  { id: "centro_inf", label: "T inferior - centro da linha de serviço" },
];

const PONTOS_CENTRO_BASE_CALIBRACAO = [
  { id: "base_sup_centro", label: "Meio da linha de base superior" },
  { id: "base_inf_centro", label: "Meio da linha de base inferior" },
];

const IDS_CANTOS_BASE = ["sup_esquerda", "sup_direita", "inf_esquerda", "inf_direita"];
const IDS_PONTOS_QUADRA_OFICIAIS = PONTOS_QUADRA_CALIBRACAO.map((ponto) => ponto.id);

const MEDIDAS_QUADRA_OFICIAIS = {
  larguraTotalM: 10.97,
  larguraInternaM: 8.23,
  baseAteTM: 5.485,
  tAteRedeM: 6.4,
  tAteLinhaInternaM: 4.115,
};
MEDIDAS_QUADRA_OFICIAIS.comprimentoM = (MEDIDAS_QUADRA_OFICIAIS.baseAteTM + MEDIDAS_QUADRA_OFICIAIS.tAteRedeM) * 2;
MEDIDAS_QUADRA_OFICIAIS.centroXM = MEDIDAS_QUADRA_OFICIAIS.larguraTotalM / 2;
MEDIDAS_QUADRA_OFICIAIS.redeYM = MEDIDAS_QUADRA_OFICIAIS.comprimentoM / 2;
MEDIDAS_QUADRA_OFICIAIS.lateralInternaEsquerdaXM = MEDIDAS_QUADRA_OFICIAIS.centroXM - MEDIDAS_QUADRA_OFICIAIS.tAteLinhaInternaM;
MEDIDAS_QUADRA_OFICIAIS.lateralInternaDireitaXM = MEDIDAS_QUADRA_OFICIAIS.centroXM + MEDIDAS_QUADRA_OFICIAIS.tAteLinhaInternaM;
MEDIDAS_QUADRA_OFICIAIS.servicoSuperiorYM = MEDIDAS_QUADRA_OFICIAIS.baseAteTM;
MEDIDAS_QUADRA_OFICIAIS.servicoInferiorYM = MEDIDAS_QUADRA_OFICIAIS.comprimentoM - MEDIDAS_QUADRA_OFICIAIS.baseAteTM;

const PONTOS_QUADRA_REAIS_M = {
  sup_esquerda: [0, 0],
  sup_direita: [MEDIDAS_QUADRA_OFICIAIS.larguraTotalM, 0],
  inf_esquerda: [0, MEDIDAS_QUADRA_OFICIAIS.comprimentoM],
  inf_direita: [MEDIDAS_QUADRA_OFICIAIS.larguraTotalM, MEDIDAS_QUADRA_OFICIAIS.comprimentoM],
  rede_esquerda: [0, MEDIDAS_QUADRA_OFICIAIS.redeYM],
  rede_direita: [MEDIDAS_QUADRA_OFICIAIS.larguraTotalM, MEDIDAS_QUADRA_OFICIAIS.redeYM],
  servico_sup_esquerda: [MEDIDAS_QUADRA_OFICIAIS.lateralInternaEsquerdaXM, MEDIDAS_QUADRA_OFICIAIS.servicoSuperiorYM],
  servico_sup_direita: [MEDIDAS_QUADRA_OFICIAIS.lateralInternaDireitaXM, MEDIDAS_QUADRA_OFICIAIS.servicoSuperiorYM],
  servico_inf_esquerda: [MEDIDAS_QUADRA_OFICIAIS.lateralInternaEsquerdaXM, MEDIDAS_QUADRA_OFICIAIS.servicoInferiorYM],
  servico_inf_direita: [MEDIDAS_QUADRA_OFICIAIS.lateralInternaDireitaXM, MEDIDAS_QUADRA_OFICIAIS.servicoInferiorYM],
  centro_sup: [MEDIDAS_QUADRA_OFICIAIS.centroXM, MEDIDAS_QUADRA_OFICIAIS.servicoSuperiorYM],
  centro_inf: [MEDIDAS_QUADRA_OFICIAIS.centroXM, MEDIDAS_QUADRA_OFICIAIS.servicoInferiorYM],
};

const PONTOS_AUX_QUADRA_REAIS_M = {
  base_sup_centro: [MEDIDAS_QUADRA_OFICIAIS.centroXM, 0],
  base_inf_centro: [MEDIDAS_QUADRA_OFICIAIS.centroXM, MEDIDAS_QUADRA_OFICIAIS.comprimentoM],
};

const PONTOS_HOMOGRAFIA_QUADRA_REAIS_M = {
  ...PONTOS_QUADRA_REAIS_M,
  ...PONTOS_AUX_QUADRA_REAIS_M,
};

const REFERENCIA_PROJECAO_SAQUE = {
  jogadorReferencia: "p1",
  deltaJogadorQuadraM: { x: -0.183, y: 3.069 },
  deltaJogadorImagemNorm: { x: -0.0026, y: 0.1002 },
  deltaContatoImagemNorm: { x: 0.0002, y: 0.2783 },
  baseInferiorM: 0.741,
  linhaCentralTM: 1.331,
};

const MIN_MARCACOES_BOLA = 0;
const MIN_MARCACOES_BOLA_TROCA = 0;
const AUTO_RASTRO_BOLA_STEP_S = 0.02;
const AUTO_RASTRO_BOLA_MIN_CONFIDENCE = 0.30;
const AUTO_RASTRO_BOLA_MAX_POINTS = 360;
const FRAME_SERVIDOR_DEBOUNCE_MS = 120;
const FRAME_SERVIDOR_PREVIEW_WIDTH = 1280;
const TEMPOS_BOLA_SUGERIDOS = [0.04, 0.12, 0.20, 0.28, 0.36, 0.44, 0.52, 0.60, 0.68, 0.76, 0.86, 0.94];
const MARCAS_BOLA_RECOMENDADAS = [
  { id: "toss_inicio", label: "inicio do lancamento", role: "trajectory" },
  { id: "toss_subindo", label: "bola subindo", role: "trajectory" },
  { id: "toss_meio_subida", label: "meio da subida", role: "trajectory" },
  { id: "toss_apice", label: "ponto mais alto do saque", role: "trajectory" },
  { id: "descida_contato", label: "bola descendo para contato", role: "trajectory" },
  { id: "pre_contato", label: "pre-contato", role: "trajectory" },
  { id: "contato_raquete", label: "contato/bolinha saindo da raquete", role: "serve_contact" },
  { id: "pos_contato", label: "primeiros frames apos contato", role: "trajectory" },
  { id: "cruzando_quadra", label: "cruzando a quadra", role: "trajectory" },
  { id: "perto_rede", label: "perto da rede", role: "trajectory" },
  { id: "apos_rede", label: "apos a rede", role: "trajectory" },
  { id: "primeiro_quique", label: "primeiro toque do saque na quadra", role: "serve_court_bounce" },
  { id: "fundo_quadra", label: "bola proxima ao fundo da quadra", role: "trajectory" },
  { id: "ultimo_visivel", label: "ultimo frame visivel da bola", role: "trajectory" },
];

const TIPOS_ESPECIAIS_BOLA = {
  serve_contact: {
    label: "Ponto de contato com a raquete",
    cor: "#ffb45d",
  },
  serve_contact_ground: {
    label: "Projecao no chao do contato",
    cor: "#d6ff7d",
  },
  serve_court_bounce: {
    label: "Primeiro toque do saque na quadra",
    cor: "#7dd6ff",
  },
};

const formatadorNumero = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 0,
});

const formatadorPercentual = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 0,
});

function formatarNumero(valor, sufixo = "") {
  return `${formatadorNumero.format(valor)}${sufixo}`;
}

function msParaKmh(valor) {
  return (Number(valor) || 0) * 3.6;
}

function formatarVelocidade(valorMs) {
  return formatarNumero(msParaKmh(valorMs), " km/h");
}

function formatarPercentual(valor) {
  return formatadorPercentual.format(valor);
}

function mapaPorNome(pontos) {
  return Object.fromEntries(pontos.map((ponto) => [ponto.nome, ponto.posicao_video]));
}

async function carregarArquitetura() {
  const resposta = await fetch("/api/arquitetura");
  const dados = await resposta.json();
  estado.arquitetura = dados.camadas ?? [];
  elementos.listaCamadas.innerHTML = estado.arquitetura
    .map(
      (camada) => `
        <li>
          <strong>${camada.nome}</strong><br />
          <span>${camada.descricao}</span>
        </li>
      `,
    )
    .join("");
}

async function carregarPainel() {
  desativarVideoReal();
  const anotacao = elementos.campoAnotacao.value.trim();
  const url = new URL("/api/painel/demo", window.location.origin);
  url.searchParams.set("quadros", "90");
  if (anotacao) {
    url.searchParams.set("anotacao", anotacao);
  }

  const resposta = await fetch(url);
  estado.dados = await resposta.json();
  estado.indiceQuadro = 0;
  estado.metadataAnaliseReal = null;
  renderizarPainel();
  iniciarAnimacao();
}

function iniciarAnimacao() {
  if (estado.modoVideoReal) {
    return;
  }

  if (estado.temporizador) {
    window.clearInterval(estado.temporizador);
  }

  estado.animando = true;
  elementos.botaoPausar.textContent = "Pausar animação";
  estado.temporizador = window.setInterval(() => {
    if (!estado.animando || !estado.dados) {
      return;
    }
    estado.indiceQuadro = (estado.indiceQuadro + 1) % estado.dados.quadros.length;
    renderizarDinamica();
  }, 220);
}

function alternarAnimacao() {
  estado.animando = !estado.animando;
  elementos.botaoPausar.textContent = estado.animando ? "Pausar animação" : "Retomar animação";
}

function renderizarPainel() {
  if (!estado.dados) {
    return;
  }
  const { estado_sessao: sessao, metricas, relatorio, diagnostico } = estado.dados;
  elementos.tituloSessao.textContent = sessao.titulo;
  elementos.superficie.textContent = sessao.superficie;
  elementos.camera.textContent = sessao.camera;
  elementos.quadros.textContent = `${sessao.total_quadros} quadros`;
  elementos.duracao.textContent = `${formatarNumero(sessao.duracao_s, " s")}`;
  elementos.observacaoSessao.textContent = sessao.observacao;
  elementos.statusFase.textContent = sessao.fase_atual;
  elementos.statusDiagnostico.textContent = diagnostico.sinal_principal.replaceAll("_", " ");
  elementos.textoRelatorio.textContent = relatorio.resumo;

  renderizarMetricas(metricas, estado.metadataAnaliseReal);
  renderizarListas(relatorio, diagnostico);
  desenharLinhaTempo();
  renderizarDinamica();
}

function renderizarMetricas(metricas, metadata = null) {
  const saqueInfo = metadata?.velocidade_saque;
  const saqueStatus = metadata?.velocidade_saque_status;
  const itens = [
    {
      titulo: "Diferença de agressividade",
      valor: formatarNumero(metricas.diferenca_agressividade, " m"),
      descricao: "Quanto maior, mais o Jogador 1 atacou a rede em relação ao Jogador 2.",
    },
    {
      titulo: "Cobertura lateral P1",
      valor: formatarNumero(metricas.cobertura_lateral_p1_m, " m"),
      descricao: "Amplitude percorrida lateralmente pelo Jogador 1 na quadra.",
    },
    {
      titulo: "Cobertura lateral P2",
      valor: formatarNumero(metricas.cobertura_lateral_p2_m, " m"),
      descricao: "Amplitude percorrida lateralmente pelo Jogador 2 na quadra.",
    },
    {
      titulo: "Velocidade média da bola",
      valor: formatarVelocidade(metricas.velocidade_media_bola_ms),
      descricao: "Proxy visual para intensidade do rali nesta janela.",
    },
    {
      titulo: "Estabilidade média do tronco",
      valor: `${formatarPercentual((metricas.estabilidade_tronco_p1 + metricas.estabilidade_tronco_p2) / 2)}`,
      descricao: "Indicador agregado de rigidez e controle durante as trocas.",
    },
    {
      titulo: "Qualidade do tracking",
      valor: formatarPercentual(metricas.qualidade_tracking),
      descricao: "Confiabilidade média dos boxes e marcadores corporais capturados.",
    },
  ];

  if (metadata) {
    const faltandoSaque = saqueStatus?.faltando?.length
      ? ` Faltando: ${saqueStatus.faltando.join(", ")}.`
      : "";
    const descricaoSaque = saqueInfo
      ? [
          `Método: ${saqueInfo.metodo ?? "3D calibrado"}.`,
          `Voo: ${formatarNumero(saqueInfo.tempo_voo_s ?? 0, " s")}.`,
          `Distância 3D: ${formatarNumero(saqueInfo.distancia_m ?? 0, " m")}.`,
          `Media de voo: ${formatarNumero(saqueInfo.velocidade_media_voo_kmh ?? 0, " km/h")}.`,
          `Fator radar: ${formatarNumero(saqueInfo.fator_radar ?? 1, "x")}.`,
          `Janela overlay: ${formatarNumero(saqueInfo.overlay_duracao_s ?? 1.25, " s")}.`,
        ].join(" ")
      : `Não calculada: marque contato com a raquete, projeção do contato no chão e primeiro toque do saque na quadra.${faltandoSaque}`;

    itens.unshift({
      titulo: "Velocidade de saque",
      valor: saqueInfo?.velocidade_kmh ? formatarNumero(saqueInfo.velocidade_kmh, " km/h") : "não calculada",
      descricao: descricaoSaque,
      detalhe: saqueInfo
        ? `${formatarNumero(saqueInfo.tempo_voo_s ?? 0, " s")} / ${formatarNumero(saqueInfo.distancia_m ?? 0, " m")}`
        : "marque contato e quique",
    });
  }

  const metricasEssenciais = itens.filter((item) => {
    const titulo = item.titulo.toLowerCase();
    return !titulo.includes("agressividade") && !titulo.includes("tronco");
  });

  elementos.gradeMetricas.innerHTML = metricasEssenciais
    .map(
      (item) => `
        <article class="cartao-metrica">
          <span class="rotulo-fato">${item.titulo}</span>
          <div class="valor">${item.valor}</div>
          ${item.detalhe ? `<small>${item.detalhe}</small>` : ""}
        </article>
      `,
    )
    .join("");
}

function renderizarListas(relatorio, diagnostico) {
  elementos.listaAchados.innerHTML = relatorio.achados_principais
    .map((achado) => `<li>${achado}</li>`)
    .join("");

  elementos.listaAlertas.innerHTML = diagnostico.alertas
    .map(
      (alerta) => `
        <li>
          <strong>${alerta.tipo} | ${alerta.atleta}</strong><br />
          ${alerta.mensagem} <br />
          Severidade: ${alerta.severidade} · Confiança: ${formatarPercentual(alerta.confianca)}
        </li>
      `,
    )
    .join("");

  elementos.listaRecomendacoes.innerHTML = diagnostico.recomendacoes
    .map((recomendacao) => `<li>${recomendacao}</li>`)
    .join("");
}

function renderizarDinamica() {
  if (!estado.dados) {
    return;
  }
  const quadro = estado.dados.quadros[estado.indiceQuadro];
  elementos.statusFase.textContent = estado.dados.estado_sessao.fase_atual;
  elementos.hudQuadro.textContent = `${quadro.indice + 1}`;
  elementos.hudBola.textContent = formatarVelocidade(quadro.bola?.velocidade_ms ?? 0);
  elementos.hudCalibracao.textContent = formatarPercentual(estado.dados.metricas.qualidade_tracking);
  if (!estado.modoVideoReal) {
    desenharVideo(quadro);
  }
  desenharMini(quadro);
  renderizarTabela(quadro);
  desenharLinhaTempo();
}

function renderizarTabela(quadro) {
  elementos.tabelaAtletas.innerHTML = quadro.atletas
    .map(
      (atleta) => `
        <tr>
          <td>${atleta.rotulo}</td>
          <td>${formatarVelocidade(atleta.velocidade_ms)}</td>
          <td>${formatarNumero(atleta.angulo_tronco_graus, "°")}</td>
          <td>${formatarPercentual(atleta.indice_simetria)}</td>
        </tr>
      `,
    )
    .join("");
}

function desenharVideo(quadro) {
  const largura = 1000;
  const altura = 620;
  const pontos = mapaPorNome(quadro.pontos_quadra);
  const ponto = (nome) => `${pontos[nome].x * largura},${pontos[nome].y * altura}`;

  const atletasSvg = quadro.atletas
    .map((atleta) => {
      const x = atleta.caixa.x * largura;
      const y = atleta.caixa.y * altura;
      const w = atleta.caixa.largura * largura;
      const h = atleta.caixa.altura * altura;
      const cor = atleta.id_atleta === "P1" ? "#63f5c2" : "#ff719f";
      const linhas = [
        ["cabeca", "ombro_esquerdo"],
        ["cabeca", "ombro_direito"],
        ["ombro_esquerdo", "quadril_esquerdo"],
        ["ombro_direito", "quadril_direito"],
        ["quadril_esquerdo", "joelho_esquerdo"],
        ["quadril_direito", "joelho_direito"],
        ["joelho_esquerdo", "tornozelo_esquerdo"],
        ["joelho_direito", "tornozelo_direito"],
        ["ombro_esquerdo", "ombro_direito"],
        ["quadril_esquerdo", "quadril_direito"],
      ];
      const marcadores = Object.fromEntries(
        atleta.marcadores.map((marcador) => [marcador.nome, marcador.posicao]),
      );
      const ossatura = linhas
        .map((linha) => {
          const origem = marcadores[linha[0]];
          const destino = marcadores[linha[1]];
          return `<line x1="${origem.x * largura}" y1="${origem.y * altura}" x2="${destino.x * largura}" y2="${destino.y * altura}" stroke="${cor}" stroke-width="2.5" stroke-linecap="round" opacity="0.78" />`;
        })
        .join("");
      const pontosMarcadores = atleta.marcadores
        .map(
          (marcador) => `
            <circle cx="${marcador.posicao.x * largura}" cy="${marcador.posicao.y * altura}" r="4.2" fill="${cor}" />
          `,
        )
        .join("");

      return `
        <g>
          <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="none" stroke="${cor}" stroke-width="3" />
          <rect x="${x}" y="${y - 26}" width="${w + 70}" height="22" rx="11" fill="rgba(5,18,25,0.78)" stroke="rgba(255,255,255,0.1)" />
          <text x="${x + 12}" y="${y - 10}" fill="${cor}" font-size="16" font-family="Bahnschrift, Trebuchet MS, sans-serif">${atleta.rotulo}</text>
          ${ossatura}
          ${pontosMarcadores}
        </g>
      `;
    })
    .join("");

  const bola = quadro.bola
    ? `
      <g>
        <circle cx="${quadro.bola.posicao_video.x * largura}" cy="${quadro.bola.posicao_video.y * altura}" r="8" fill="#ffe85d" />
        <text x="${quadro.bola.posicao_video.x * largura + 16}" y="${quadro.bola.posicao_video.y * altura - 10}" fill="#ffe85d" font-size="18" font-family="Bahnschrift, Trebuchet MS, sans-serif">Bola</text>
      </g>
    `
    : "";

  const marcadoresQuadra = quadro.pontos_quadra
    .map(
      (pontoAtual) => `
        <g>
          <circle cx="${pontoAtual.posicao_video.x * largura}" cy="${pontoAtual.posicao_video.y * altura}" r="5" fill="#ff6f91" />
          <text x="${pontoAtual.posicao_video.x * largura + 8}" y="${pontoAtual.posicao_video.y * altura - 8}" fill="#ffb8c8" font-size="11">${pontoAtual.nome}</text>
        </g>
      `,
    )
    .join("");

  elementos.svgVideo.innerHTML = `
    <defs>
      <linearGradient id="grama" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#8cd8ff" />
        <stop offset="100%" stop-color="#9be7ff" />
      </linearGradient>
      <linearGradient id="quadra" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="${"#749fdc"}" />
        <stop offset="100%" stop-color="${"#537ab6"}" />
      </linearGradient>
    </defs>
    <rect x="0" y="0" width="${largura}" height="${altura}" fill="url(#grama)" />
    <rect x="0" y="0" width="${largura}" height="110" fill="rgba(109,23,39,0.72)" />
    <rect x="0" y="110" width="${largura}" height="54" fill="rgba(60,239,255,0.82)" />
    <rect x="180" y="200" width="640" height="360" fill="url(#quadra)" />
    <polygon points="${ponto("sup_esquerda")} ${ponto("sup_direita")} ${ponto("inf_direita")} ${ponto("inf_esquerda")}" fill="rgba(92,143,212,0.95)" />
    <line x1="${pontos.inf_esquerda.x * largura}" y1="${pontos.inf_esquerda.y * altura}" x2="${pontos.sup_esquerda.x * largura}" y2="${pontos.sup_esquerda.y * altura}" stroke="white" stroke-width="5" />
    <line x1="${pontos.inf_direita.x * largura}" y1="${pontos.inf_direita.y * altura}" x2="${pontos.sup_direita.x * largura}" y2="${pontos.sup_direita.y * altura}" stroke="white" stroke-width="5" />
    <line x1="${pontos.inf_esquerda.x * largura}" y1="${pontos.inf_esquerda.y * altura}" x2="${pontos.inf_direita.x * largura}" y2="${pontos.inf_direita.y * altura}" stroke="white" stroke-width="5" />
    <line x1="${pontos.sup_esquerda.x * largura}" y1="${pontos.sup_esquerda.y * altura}" x2="${pontos.sup_direita.x * largura}" y2="${pontos.sup_direita.y * altura}" stroke="white" stroke-width="5" />
    <line x1="${pontos.rede_esquerda.x * largura}" y1="${pontos.rede_esquerda.y * altura}" x2="${pontos.rede_direita.x * largura}" y2="${pontos.rede_direita.y * altura}" stroke="rgba(255,255,255,0.8)" stroke-width="7" />
    <line x1="${pontos.servico_sup_esquerda.x * largura}" y1="${pontos.servico_sup_esquerda.y * altura}" x2="${pontos.servico_sup_direita.x * largura}" y2="${pontos.servico_sup_direita.y * altura}" stroke="white" stroke-width="4" />
    <line x1="${pontos.servico_inf_esquerda.x * largura}" y1="${pontos.servico_inf_esquerda.y * altura}" x2="${pontos.servico_inf_direita.x * largura}" y2="${pontos.servico_inf_direita.y * altura}" stroke="white" stroke-width="4" />
    <line x1="${pontos.centro_sup.x * largura}" y1="${pontos.centro_sup.y * altura}" x2="${pontos.centro_inf.x * largura}" y2="${pontos.centro_inf.y * altura}" stroke="white" stroke-width="4" />
    ${marcadoresQuadra}
    ${atletasSvg}
    ${bola}
    <rect x="692" y="448" width="255" height="120" rx="20" fill="rgba(7,19,31,0.76)" stroke="rgba(255,255,255,0.12)" />
    <text x="716" y="484" fill="#eff8ff" font-size="20" font-family="Bahnschrift, Trebuchet MS, sans-serif">Jogador 1 vs Jogador 2</text>
    <text x="716" y="514" fill="#9fc2d6" font-size="16">Bola: ${formatarVelocidade(quadro.bola?.velocidade_ms ?? 0)}</text>
    <text x="716" y="540" fill="#9fc2d6" font-size="16">Frame atual: ${quadro.indice + 1}</text>
    <text x="36" y="56" fill="#eff8ff" font-size="38" font-family="Rockwell, Georgia, serif">Biomec TV</text>
    <text x="36" y="92" fill="#63f5c2" font-size="20" font-family="Bahnschrift, Trebuchet MS, sans-serif">Frame ${quadro.indice + 1}</text>
  `;
}

function desenharMini(quadro) {
  const largura = 260;
  const altura = 480;
  const margemX = 42;
  const margemY = 36;
  const escalaX = 176 / 10.97;
  const escalaY = 394 / 23.77;
  const janela = estado.dados.quadros.slice(Math.max(0, estado.indiceQuadro - 10), estado.indiceQuadro + 1);
  const trilha = (idAtleta, cor) =>
    janela
      .map((item, indice) => {
        const atleta = item.atletas.find((valor) => valor.id_atleta === idAtleta);
        const x = margemX + atleta.centro_quadra_m.x * escalaX;
        const y = margemY + atleta.centro_quadra_m.y * escalaY;
        const opacidade = 0.22 + (indice / janela.length) * 0.62;
        return `<circle cx="${x}" cy="${y}" r="${3 + indice * 0.15}" fill="${cor}" opacity="${opacidade}" />`;
      })
      .join("");

  const atletaP1 = quadro.atletas.find((atleta) => atleta.id_atleta === "P1");
  const atletaP2 = quadro.atletas.find((atleta) => atleta.id_atleta === "P2");
  const bola = quadro.bola;

  elementos.svgMini.innerHTML = `
    <rect x="0" y="0" width="${largura}" height="${altura}" rx="32" fill="rgba(8,20,31,0.72)" />
    <rect x="${margemX}" y="${margemY}" width="176" height="394" rx="18" fill="rgba(92,143,212,0.18)" stroke="#dbe7ff" stroke-width="3" />
    <line x1="${margemX}" y1="${margemY + 197}" x2="${margemX + 176}" y2="${margemY + 197}" stroke="#dbe7ff" stroke-width="3" />
    <line x1="${margemX + 88}" y1="${margemY + 98}" x2="${margemX + 88}" y2="${margemY + 296}" stroke="#dbe7ff" stroke-width="2" />
    <line x1="${margemX}" y1="${margemY + 98}" x2="${margemX + 176}" y2="${margemY + 98}" stroke="#dbe7ff" stroke-width="2" />
    <line x1="${margemX}" y1="${margemY + 296}" x2="${margemX + 176}" y2="${margemY + 296}" stroke="#dbe7ff" stroke-width="2" />
    ${trilha("P1", "#63f5c2")}
    ${trilha("P2", "#ff719f")}
    ${
      bola
        ? `<circle cx="${margemX + bola.posicao_quadra_m.x * escalaX}" cy="${margemY + bola.posicao_quadra_m.y * escalaY}" r="7" fill="#ffe85d" />`
        : ""
    }
    <circle cx="${margemX + atletaP1.centro_quadra_m.x * escalaX}" cy="${margemY + atletaP1.centro_quadra_m.y * escalaY}" r="10" fill="#63f5c2" />
    <circle cx="${margemX + atletaP2.centro_quadra_m.x * escalaX}" cy="${margemY + atletaP2.centro_quadra_m.y * escalaY}" r="10" fill="#ff719f" />
    <text x="34" y="26" fill="#9fc2d6" font-size="16">Rastro de 10 quadros</text>
  `;
}

function desenharLinhaTempo() {
  if (!estado.dados) {
    return;
  }
  const largura = 1200;
  const altura = 280;
  const margem = { esquerda: 56, direita: 24, topo: 18, base: 36 };
  const serie = estado.dados.linha_tempo;
  const maxBola = Math.max(...serie.map((item) => item.velocidade_bola_ms), 1);
  const areaLargura = largura - margem.esquerda - margem.direita;
  const areaAltura = altura - margem.topo - margem.base;

  const pontoX = (indice) => margem.esquerda + (indice / Math.max(serie.length - 1, 1)) * areaLargura;
  const pontoY = (valor) => margem.topo + (1 - valor) * areaAltura;
  const path = (campo, transformador) =>
    serie
      .map((item, indice) => `${indice === 0 ? "M" : "L"} ${pontoX(indice)} ${pontoY(transformador(item[campo]))}`)
      .join(" ");

  const linhaP1 = path("qualidade_p1", (valor) => valor);
  const linhaP2 = path("qualidade_p2", (valor) => valor);
  const linhaBola = path("velocidade_bola_ms", (valor) => valor / maxBola);
  const cursorX = pontoX(estado.indiceQuadro);

  const grades = Array.from({ length: 5 }, (_, indice) => {
    const y = margem.topo + (areaAltura / 4) * indice;
    const rotulo = `${100 - indice * 25}%`;
    return `
      <line x1="${margem.esquerda}" y1="${y}" x2="${largura - margem.direita}" y2="${y}" stroke="rgba(255,255,255,0.08)" />
      <text x="8" y="${y + 4}" fill="#9fc2d6" font-size="12">${rotulo}</text>
    `;
  }).join("");

  elementos.svgLinhaTempo.innerHTML = `
    <rect x="0" y="0" width="${largura}" height="${altura}" rx="26" fill="rgba(6,16,24,0.45)" />
    ${grades}
    <path d="${linhaP1}" fill="none" stroke="#63f5c2" stroke-width="4" stroke-linecap="round" />
    <path d="${linhaP2}" fill="none" stroke="#ff719f" stroke-width="4" stroke-linecap="round" />
    <path d="${linhaBola}" fill="none" stroke="#ffe85d" stroke-width="3" stroke-dasharray="8 8" stroke-linecap="round" />
    <line x1="${cursorX}" y1="${margem.topo}" x2="${cursorX}" y2="${altura - margem.base}" stroke="rgba(255,255,255,0.35)" stroke-width="2" />
    <rect x="${largura - 308}" y="22" width="280" height="70" rx="18" fill="rgba(255,255,255,0.04)" />
    <circle cx="${largura - 282}" cy="46" r="6" fill="#63f5c2" />
    <text x="${largura - 266}" y="51" fill="#eff8ff" font-size="14">Estabilidade P1</text>
    <circle cx="${largura - 282}" cy="68" r="6" fill="#ff719f" />
    <text x="${largura - 266}" y="73" fill="#eff8ff" font-size="14">Estabilidade P2</text>
    <circle cx="${largura - 142}" cy="46" r="6" fill="#ffe85d" />
    <text x="${largura - 126}" y="51" fill="#eff8ff" font-size="14">Bola</text>
  `;
}

function aoSelecionarArquivoVideo() {
  const arquivo = elementos.campoVideo.files?.[0];
  estado.arquivoUploadSelecionado = arquivo ?? null;
  estado.calibracaoPronta = false;

  if (!arquivo) {
    estado.calibracao = null;
    elementos.statusUpload.textContent = "Selecione um video para iniciar a calibracao.";
    return;
  }

  iniciarCalibracaoArquivo(arquivo);
}

function iniciarCalibracaoArquivo(arquivo) {
  cancelarFrameServidorPendente();
  if (estado.objetoUrlCalibracao) {
    URL.revokeObjectURL(estado.objetoUrlCalibracao);
  }
  if (estado.objetoUrlFrameServidor) {
    URL.revokeObjectURL(estado.objetoUrlFrameServidor);
  }

  estado.objetoUrlCalibracao = URL.createObjectURL(arquivo);
  estado.objetoUrlFrameServidor = null;
  estado.calibracaoServidorId = null;
  estado.frameServidorImagem = null;
  estado.frameServidorIndexAtual = null;
  estado.frameServidorSeq += 1;
  estado.carregandoFrameCalibracao = true;
  estado.modoCalibracao = "ponto";
  estado.etapaCalibracao = "quadra";
  estado.indicePontoQuadra = 0;
  estado.indiceCentroBaseCalibracao = 0;
  estado.indiceJogadorCalibracao = 0;
  estado.zoomCalibracao = 1;
  estado.panCalibracao = { x: 0.5, y: 0.5 };
  estado.ultimoPonteiroCalibracao = { x: 0.5, y: 0.5 };
  estado.tipoEspecialBola = null;
  estado.previewVelocidadeSaque = null;
  estado.previewVelocidadeSaqueErro = "";
  elementos.rangeZoomCalibracao.value = "1";
  elementos.zoomCalibracao.textContent = "Zoom 1,0x";
  estado.calibracao = {
    version: 1,
    analysis_mode: estado.modoCalibracao,
    requires_serve_metrics: true,
    video: {
      file_name: arquivo.name,
      duration_s: 0,
      width: 0,
      height: 0,
      display_width: 0,
      display_height: 0,
      source_width: 0,
      source_height: 0,
      fps: 0,
      frames_video: 0,
    },
    court_points: {},
    court_missing: {},
    court_aux_points: {},
    court_projection: null,
    players: {
      player_count: Number(elementos.qtdJogadoresCalibracao.value || 2),
      p1: null,
      p2: null,
    },
    ball_tracking: {
      mode: "pretrained_model_render",
      min_marks_required: 0,
      auto_render_detection: true,
      note: "O rastro da bolinha e detectado durante a renderizacao com o modelo pre-treinado. Marcacoes manuais/auto-rastro sao opcionais e funcionam apenas como guias.",
    },
    serve_metrics: {
      required: true,
      curve_factor: 1.03,
      radar_factor: 1.074,
      height_mode: "auto_from_contact_projection",
      note: "Velocidade do saque calculada em 3D entre contato e primeiro toque, com altura estimada automaticamente pela projecao no chao, homografia da quadra e correcao radar para velocidade inicial.",
    },
    ball_marks: [],
  };

  elementos.modalCalibracao.classList.remove("oculto");
  elementos.modalCalibracao.setAttribute("aria-hidden", "false");
  elementos.videoCalibracao.pause();
  elementos.videoCalibracao.removeAttribute("src");
  elementos.videoCalibracao.load();
  elementos.videoCalibracao.src = estado.objetoUrlCalibracao;
  elementos.videoCalibracao.muted = true;
  elementos.videoCalibracao.preload = "auto";
  elementos.videoCalibracao.load();
  elementos.statusUpload.textContent = "Arquivo selecionado. Carregando frames para calibracao...";
  atualizarInterfaceCalibracao();
  desenharCanvasCalibracao();
  prepararCalibracaoServidor(arquivo).catch((erro) => {
    console.warn("Fallback server-side de calibracao indisponivel:", erro);
  });
}

function fecharModalCalibracao() {
  elementos.modalCalibracao.classList.add("oculto");
  elementos.modalCalibracao.setAttribute("aria-hidden", "true");
}

async function prepararCalibracaoServidor(arquivo) {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  const resposta = await fetch("/api/videos/calibracao/preparar", {
    method: "POST",
    body: corpo,
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    throw new Error(dados.detail ?? "Falha ao preparar calibracao no servidor.");
  }
  if (!estado.calibracao || estado.calibracao.video.file_name !== arquivo.name) {
    return;
  }

  estado.calibracaoServidorId = dados.calibracao_id;
  estado.calibracao.video.duration_s = Number(dados.duracao_s || estado.calibracao.video.duration_s || 0);
  estado.calibracao.video.fps = Number(dados.fps || estado.calibracao.video.fps || 0);
  estado.calibracao.video.frames_video = Number(dados.frames_video || estado.calibracao.video.frames_video || 0);
  const larguraServidor = Number(dados.largura || 0);
  const alturaServidor = Number(dados.altura || 0);
  if (larguraServidor > 0) {
    estado.calibracao.video.source_width = larguraServidor;
    estado.calibracao.video.width = estado.calibracao.video.width || larguraServidor;
  }
  if (alturaServidor > 0) {
    estado.calibracao.video.source_height = alturaServidor;
    estado.calibracao.video.height = estado.calibracao.video.height || alturaServidor;
  }

  if (estado.calibracao.video.duration_s > 0) {
    elementos.rangeTempoCalibracao.max = String(estado.calibracao.video.duration_s);
  }
  const larguraVisual = estado.calibracao.video.display_width || estado.calibracao.video.width;
  const alturaVisual = estado.calibracao.video.display_height || estado.calibracao.video.height;
  if (larguraVisual > 0 && alturaVisual > 0) {
    configurarCanvasCalibracao(larguraVisual, alturaVisual);
  }

  const tempo = Number(elementos.rangeTempoCalibracao.value || 0);
  await carregarFrameServidorCalibracao(tempo);
}

function aspectoVisualCalibracao(larguraReferencia = 0, alturaReferencia = 0) {
  const videoCalibracao = estado.calibracao?.video ?? {};
  const largura = Number(
    videoCalibracao.display_width
    || videoCalibracao.width
    || larguraReferencia
    || elementos.videoCalibracao.videoWidth
    || videoCalibracao.source_width
    || 0,
  );
  const altura = Number(
    videoCalibracao.display_height
    || videoCalibracao.height
    || alturaReferencia
    || elementos.videoCalibracao.videoHeight
    || videoCalibracao.source_height
    || 0,
  );
  if (largura > 0 && altura > 0) {
    return largura / altura;
  }
  return 16 / 9;
}

function configurarCanvasCalibracao(larguraOriginal, alturaOriginal) {
  const aspecto = Math.max(aspectoVisualCalibracao(larguraOriginal, alturaOriginal), 1e-6);
  const larguraBase = Number(larguraOriginal || 0) > 0 ? Number(larguraOriginal) : 960;
  const largura = Math.min(1280, Math.max(320, Math.round(larguraBase)));
  const altura = Math.max(120, Math.round(largura / aspecto));
  elementos.canvasCalibracao.width = largura;
  elementos.canvasCalibracao.height = altura;
  atualizarEscalaVisualCanvasCalibracao();
}

function atualizarEscalaVisualCanvasCalibracao() {
  const medidas = medidasVisuaisCanvasCalibracao();
  if (!medidas) {
    elementos.canvasCalibracao?.style.setProperty("--escala-canvas-calibracao", "1");
    return;
  }
  medidas.canvas.style.width = `${Math.max(1, Math.floor(medidas.larguraBase))}px`;
  medidas.canvas.style.height = `${Math.max(1, Math.floor(medidas.alturaBase))}px`;
  estado.panCalibracao = limitarPanCalibracao(estado.panCalibracao, medidas);
  const panX = (0.5 - estado.panCalibracao.x) * medidas.larguraBase * medidas.escala;
  const panY = (0.5 - estado.panCalibracao.y) * medidas.alturaBase * medidas.escala;
  medidas.canvas.style.setProperty("--escala-canvas-calibracao", String(Number(medidas.escala.toFixed(4))));
  medidas.canvas.style.setProperty("--pan-canvas-calibracao-x", `${Number(panX.toFixed(2))}px`);
  medidas.canvas.style.setProperty("--pan-canvas-calibracao-y", `${Number(panY.toFixed(2))}px`);
  if (elementos.overlayCalibracao) {
    elementos.overlayCalibracao.style.width = medidas.canvas.style.width;
    elementos.overlayCalibracao.style.height = medidas.canvas.style.height;
    elementos.overlayCalibracao.style.setProperty("--escala-canvas-calibracao", String(Number(medidas.escala.toFixed(4))));
    elementos.overlayCalibracao.style.setProperty("--pan-canvas-calibracao-x", `${Number(panX.toFixed(2))}px`);
    elementos.overlayCalibracao.style.setProperty("--pan-canvas-calibracao-y", `${Number(panY.toFixed(2))}px`);
  }
}

function prepararVideoCalibracao() {
  const video = elementos.videoCalibracao;
  if (!estado.calibracao) {
    return;
  }

  const duracao = Number.isFinite(video.duration) ? video.duration : 0;
  estado.calibracao.video.duration_s = Number(duracao.toFixed(3));
  estado.calibracao.video.width = video.videoWidth || 0;
  estado.calibracao.video.height = video.videoHeight || 0;
  estado.calibracao.video.display_width = video.videoWidth || 0;
  estado.calibracao.video.display_height = video.videoHeight || 0;

  configurarCanvasCalibracao(video.videoWidth || 960, video.videoHeight || 540);
  elementos.rangeTempoCalibracao.max = String(Math.max(duracao, 0));
  const tempoInicial = duracao > 0.18 ? 0.12 : 0;
  irParaTempoCalibracao(tempoInicial);
  solicitarFrameCalibracao();
  atualizarInterfaceCalibracao();
}

function solicitarFrameCalibracao() {
  if (estado.calibracaoServidorId) {
    return;
  }
  const video = elementos.videoCalibracao;
  const redesenhar = () => {
    estado.carregandoFrameCalibracao = false;
    desenharCanvasCalibracao();
    elementos.statusUpload.textContent = "Frame carregado. Complete a calibracao obrigatoria antes de enviar.";
  };

  if (typeof video.requestVideoFrameCallback === "function") {
    video.requestVideoFrameCallback(redesenhar);
    window.setTimeout(() => {
      if (estado.carregandoFrameCalibracao && video.readyState >= 2) {
        redesenhar();
      }
    }, 320);
    return;
  }

  window.setTimeout(redesenhar, 120);
}

function cancelarFrameServidorPendente() {
  if (estado.frameServidorTimer) {
    window.clearTimeout(estado.frameServidorTimer);
    estado.frameServidorTimer = null;
  }
  if (estado.frameServidorAbortController) {
    estado.frameServidorAbortController.abort();
    estado.frameServidorAbortController = null;
  }
}

function solicitarFrameServidorCalibracao(tempo, imediato = false) {
  if (!estado.calibracaoServidorId) {
    return;
  }
  if (estado.frameServidorTimer) {
    window.clearTimeout(estado.frameServidorTimer);
    estado.frameServidorTimer = null;
  }

  const carregar = () => {
    estado.frameServidorTimer = null;
    carregarFrameServidorCalibracao(tempo).catch((erro) => {
      if (erro?.name === "AbortError") {
        return;
      }
      console.warn("Falha ao carregar frame server-side:", erro);
    });
  };

  if (imediato) {
    carregar();
    return;
  }
  estado.frameServidorTimer = window.setTimeout(carregar, FRAME_SERVIDOR_DEBOUNCE_MS);
}

async function carregarFrameServidorCalibracao(tempo) {
  if (!estado.calibracaoServidorId) {
    return;
  }

  const seq = ++estado.frameServidorSeq;
  if (estado.frameServidorAbortController) {
    estado.frameServidorAbortController.abort();
  }
  const controller = new AbortController();
  estado.frameServidorAbortController = controller;
  estado.carregandoFrameCalibracao = !estado.frameServidorImagem;
  desenharCanvasCalibracao();

  try {
    const tempoSeguro = Math.max(0, Number(tempo) || 0);
    const url = `/api/videos/calibracao/${estado.calibracaoServidorId}/frame?tempo_s=${encodeURIComponent(tempoSeguro.toFixed(3))}&max_width=${FRAME_SERVIDOR_PREVIEW_WIDTH}`;
    const resposta = await fetch(url, { cache: "force-cache", signal: controller.signal });
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({}));
      throw new Error(erro.detail ?? "Falha ao carregar frame de calibracao.");
    }

    const frameIndexResposta = Number(resposta.headers.get("X-Frame-Index"));
    const blob = await resposta.blob();
    if (seq !== estado.frameServidorSeq || controller.signal.aborted) {
      return;
    }
    const objectUrl = URL.createObjectURL(blob);
    const imagem = new Image();
    imagem.src = objectUrl;
    await imagem.decode();
    if (seq !== estado.frameServidorSeq || controller.signal.aborted) {
      URL.revokeObjectURL(objectUrl);
      return;
    }

    if (estado.objetoUrlFrameServidor) {
      URL.revokeObjectURL(estado.objetoUrlFrameServidor);
    }
    estado.objetoUrlFrameServidor = objectUrl;
    estado.frameServidorImagem = imagem;
    estado.frameServidorIndexAtual = Number.isFinite(frameIndexResposta) ? frameIndexResposta : null;
    estado.carregandoFrameCalibracao = false;
    desenharCanvasCalibracao();
    elementos.statusUpload.textContent = "Frame carregado pelo servidor. Complete a calibracao obrigatoria antes de enviar.";
  } finally {
    if (estado.frameServidorAbortController === controller) {
      estado.frameServidorAbortController = null;
    }
  }
}

function irParaTempoCalibracao(tempo) {
  const video = elementos.videoCalibracao;
  const duracao = Number.isFinite(video.duration) && video.duration > 0
    ? video.duration
    : Number(estado.calibracao?.video?.duration_s || 0);
  const seguro = Math.max(0, Math.min(Number(tempo) || 0, duracao || 0));
  estado.frameServidorIndexAtual = null;
  elementos.rangeTempoCalibracao.value = String(seguro);
  elementos.tempoCalibracao.textContent = `${formatarNumero(seguro, " s")}`;
  if (estado.calibracaoServidorId) {
    solicitarFrameServidorCalibracao(seguro);
    if (!estado.frameServidorImagem) {
      estado.carregandoFrameCalibracao = true;
      desenharCanvasCalibracao();
    }
    return;
  }
  if (video.readyState > 0 && Math.abs(video.currentTime - seguro) > 0.015) {
    estado.carregandoFrameCalibracao = true;
    video.currentTime = seguro;
  } else {
    desenharCanvasCalibracao();
  }
}

function modalCalibracaoAberto() {
  return Boolean(
    elementos.modalCalibracao
    && !elementos.modalCalibracao.classList.contains("oculto")
    && elementos.modalCalibracao.getAttribute("aria-hidden") !== "true",
  );
}

function fpsCalibracao() {
  const fps = Number(estado.calibracao?.video?.fps || 0);
  if (Number.isFinite(fps) && fps >= 1) {
    return Math.min(240, fps);
  }
  return 30;
}

function quantizarTempoPorFrameCalibracao(tempo) {
  const fps = fpsCalibracao();
  const seguro = Math.max(0, Number(tempo) || 0);
  return Math.round(seguro * fps) / fps;
}

function tempoFrameServidorAtual() {
  const frame = Number(estado.frameServidorIndexAtual);
  if (!Number.isFinite(frame) || frame < 0) {
    return null;
  }
  return frame / fpsCalibracao();
}

function tempoAtualMarcacaoCalibracao() {
  const tempoFrame = tempoFrameServidorAtual();
  if (tempoFrame !== null && !estado.carregandoFrameCalibracao) {
    return tempoFrame;
  }
  return quantizarTempoPorFrameCalibracao(Number(elementos.rangeTempoCalibracao.value || elementos.videoCalibracao.currentTime || 0));
}

function ajustarTempoCalibracaoPorTecla(delta) {
  const tempoAtual = Number(elementos.rangeTempoCalibracao.value || elementos.videoCalibracao.currentTime || 0);
  const proximoTempo = Math.round((tempoAtual + delta) * 100) / 100;
  irParaTempoCalibracao(proximoTempo);
}

function pontoNormalizadoCanvas(evento) {
  return pontoTelaCanvas(evento);
}

function pontoTelaCanvas(evento) {
  const rect = elementos.canvasCalibracao.getBoundingClientRect();
  const telaX = (evento.clientX - rect.left) / Math.max(rect.width, 1);
  const telaY = (evento.clientY - rect.top) / Math.max(rect.height, 1);
  return {
    x: Math.max(0, Math.min(1, telaX)),
    y: Math.max(0, Math.min(1, telaY)),
  };
}

function pontoInteracaoCanvas(evento) {
  const ponto = pontoTelaCanvas(evento);
  const rectPalco = elementos.canvasCalibracao.parentElement?.getBoundingClientRect();
  const centroX = rectPalco ? rectPalco.left + rectPalco.width / 2 : evento.clientX;
  const centroY = rectPalco ? rectPalco.top + rectPalco.height / 2 : evento.clientY;
  return {
    ...ponto,
    offsetX: evento.clientX - centroX,
    offsetY: evento.clientY - centroY,
  };
}

function viewportCalibracao() {
  return { x: 0, y: 0, w: 1, h: 1 };
}

function medidasVisuaisCanvasCalibracao() {
  const canvas = elementos.canvasCalibracao;
  const palco = canvas?.parentElement;
  if (!canvas || !palco || canvas.width <= 0 || canvas.height <= 0) {
    return null;
  }
  const larguraPalco = palco.clientWidth || 0;
  const alturaPalco = palco.clientHeight || 0;
  if (larguraPalco <= 0 || alturaPalco <= 0) {
    return null;
  }
  const aspectoCanvas = canvas.width / Math.max(canvas.height, 1);
  const escalaContain = Math.min(larguraPalco / Math.max(canvas.width, 1), alturaPalco / Math.max(canvas.height, 1));
  const larguraBase = canvas.width * Math.max(escalaContain, 1e-6);
  const alturaBase = larguraBase / Math.max(aspectoCanvas, 1e-6);
  const escala = Math.max(1, Number(estado.zoomCalibracao) || 1);
  return {
    canvas,
    larguraPalco,
    alturaPalco,
    larguraBase,
    alturaBase,
    escala,
  };
}

function limitarPanCalibracao(pan = estado.panCalibracao, medidas = medidasVisuaisCanvasCalibracao()) {
  if (!medidas) {
    return { x: 0.5, y: 0.5 };
  }
  const meiaJanelaX = Math.min(0.5, medidas.larguraPalco / Math.max(medidas.larguraBase * medidas.escala * 2, 1));
  const meiaJanelaY = Math.min(0.5, medidas.alturaPalco / Math.max(medidas.alturaBase * medidas.escala * 2, 1));
  return {
    x: Math.max(meiaJanelaX, Math.min(1 - meiaJanelaX, Number(pan?.x) || 0.5)),
    y: Math.max(meiaJanelaY, Math.min(1 - meiaJanelaY, Number(pan?.y) || 0.5)),
  };
}

function ajustarZoomCalibracao(valor, manterPan = false, ancoraTela = null) {
  const ancora = ancoraTela ?? estado.ultimoPonteiroCalibracao ?? { x: 0.5, y: 0.5, offsetX: 0, offsetY: 0 };
  const zoom = Math.max(1, Math.min(5, Number(valor) || 1));
  estado.zoomCalibracao = zoom;
  if (!manterPan || zoom === 1) {
    estado.panCalibracao = { x: 0.5, y: 0.5 };
  } else if (ancoraTela && Number.isFinite(ancora.offsetX) && Number.isFinite(ancora.offsetY)) {
    const medidas = medidasVisuaisCanvasCalibracao();
    estado.panCalibracao = {
      x: ancora.x - ancora.offsetX / Math.max((medidas?.larguraBase || 1) * zoom, 1),
      y: ancora.y - ancora.offsetY / Math.max((medidas?.alturaBase || 1) * zoom, 1),
    };
  }
  estado.panCalibracao = limitarPanCalibracao();
  elementos.rangeZoomCalibracao.value = String(zoom);
  elementos.zoomCalibracao.textContent = `Zoom ${formatarNumero(zoom, "x")}`;
  atualizarEscalaVisualCanvasCalibracao();
  desenharCanvasCalibracao();
}

function variarZoomCalibracao(delta, ancoraTela = null) {
  ajustarZoomCalibracao(estado.zoomCalibracao + delta, true, ancoraTela);
}

function iniciarPanCalibracao(evento) {
  estado.ultimoPonteiroCalibracao = pontoInteracaoCanvas(evento);
  if (estado.zoomCalibracao <= 1) {
    return;
  }
  estado.arrastandoCalibracao = true;
  estado.suprimirCliqueCalibracao = false;
  estado.dragCalibracao = {
    x: evento.clientX,
    y: evento.clientY,
    panX: estado.panCalibracao.x,
    panY: estado.panCalibracao.y,
  };
  elementos.canvasCalibracao.setPointerCapture?.(evento.pointerId);
}

function moverPanCalibracao(evento) {
  estado.ultimoPonteiroCalibracao = pontoInteracaoCanvas(evento);
  if (guiaProjecaoSaqueAtiva() || guiaCentrosBaseAtiva()) {
    atualizarOverlayCalibracao();
  }
  if (!estado.arrastandoCalibracao || !estado.dragCalibracao || estado.zoomCalibracao <= 1) {
    return;
  }
  const medidas = medidasVisuaisCanvasCalibracao();
  const dx = evento.clientX - estado.dragCalibracao.x;
  const dy = evento.clientY - estado.dragCalibracao.y;
  if (Math.hypot(evento.clientX - estado.dragCalibracao.x, evento.clientY - estado.dragCalibracao.y) > 4) {
    estado.suprimirCliqueCalibracao = true;
  }
  estado.panCalibracao = limitarPanCalibracao({
    x: estado.dragCalibracao.panX - dx / Math.max((medidas?.larguraBase || 1) * estado.zoomCalibracao, 1),
    y: estado.dragCalibracao.panY - dy / Math.max((medidas?.alturaBase || 1) * estado.zoomCalibracao, 1),
  }, medidas);
  atualizarEscalaVisualCanvasCalibracao();
  atualizarOverlayCalibracao();
}

function finalizarPanCalibracao(evento) {
  if (!estado.arrastandoCalibracao) {
    return;
  }
  estado.arrastandoCalibracao = false;
  estado.dragCalibracao = null;
  elementos.canvasCalibracao.releasePointerCapture?.(evento.pointerId);
}

function registrarCliqueCalibracao(evento) {
  if (estado.suprimirCliqueCalibracao) {
    estado.suprimirCliqueCalibracao = false;
    return;
  }
  if (estado.carregandoFrameCalibracao || (elementos.videoCalibracao.readyState < 2 && !estado.frameServidorImagem)) {
    elementos.progressoCalibracao.textContent = "Aguarde o frame do video carregar antes de marcar pontos.";
    return;
  }
  if (!estado.calibracao) {
    return;
  }

  const ponto = pontoNormalizadoCanvas(evento);
  const tempo = tempoAtualMarcacaoCalibracao();
  if (estado.autoRastroBolaAguardandoInicio) {
    estado.autoRastroBolaAguardandoInicio = false;
    estado.tipoEspecialBola = null;
    estado.etapaCalibracao = "bola";
    estado.calibracao.ball_marks = (estado.calibracao.ball_marks ?? [])
      .filter((marca) => marca.source !== "auto_track" && marca.source !== "manual_auto_seed");
    const seed = {
      x: Number(ponto.x.toFixed(5)),
      y: Number(ponto.y.toFixed(5)),
      time_s: Number(tempo.toFixed(3)),
    };
    registrarMarcaBolaCalibracao(ponto, tempo, {
      role: "trajectory",
      label: "Inicio manual do auto-rastro",
      source: "manual_auto_seed",
      etapa: { id: "auto_seed", label: "Inicio manual do auto-rastro" },
    });
    desenharCanvasCalibracao();
    atualizarInterfaceCalibracao();
    detectarRastroBolaAutomatico(seed).catch((erro) => {
      estado.autoRastroBolaErro = erro.message ?? "Falha ao seguir o rastro automatico.";
      elementos.progressoCalibracao.textContent = estado.autoRastroBolaErro;
      estado.autoRastroBolaEmAndamento = false;
      desenharCanvasCalibracao();
      atualizarInterfaceCalibracao();
      console.error(erro);
    });
    return;
  }
  if (estado.tipoEspecialBola && !quadraProntaParaSaque()) {
    estado.tipoEspecialBola = null;
    elementos.progressoCalibracao.textContent = "Conclua primeiro as medicoes da quadra antes de marcar eventos do saque.";
    atualizarInterfaceCalibracao();
    return;
  }
  if (estado.tipoEspecialBola) {
    const tipoEspecial = estado.tipoEspecialBola;
    const configEspecial = TIPOS_ESPECIAIS_BOLA[tipoEspecial];
    registrarMarcaBolaCalibracao(ponto, tempo, {
      role: tipoEspecial,
      label: configEspecial?.label,
      etapa: etapaBolaPorRole(tipoEspecial),
    });
    estado.tipoEspecialBola = null;
    sugerirTempoAposMarcacaoBola(tempo, { saltoLargo: evento.ctrlKey });
    desenharCanvasCalibracao();
    atualizarInterfaceCalibracao();
    return;
  }

  if (estado.etapaCalibracao === "quadra") {
    estado.calibracao.court_points = estado.calibracao.court_points ?? {};
    estado.calibracao.court_missing = estado.calibracao.court_missing ?? {};
    const alvo = PONTOS_QUADRA_CALIBRACAO[estado.indicePontoQuadra];
    if (!alvo) {
      atualizarInterfaceCalibracao();
      return;
    }
    if (estado.calibracao.court_missing) {
      delete estado.calibracao.court_missing[alvo.id];
    }
    estado.calibracao.court_points[alvo.id] = {
      x: Number(ponto.x.toFixed(5)),
      y: Number(ponto.y.toFixed(5)),
      label: alvo.label,
      time_s: Number(tempo.toFixed(3)),
    };
    invalidarPreviewVelocidadeSaque();
    estado.indicePontoQuadra += 1;
    avancarIndiceQuadraAtePendente();
    if (estado.indicePontoQuadra >= PONTOS_QUADRA_CALIBRACAO.length) {
      resolverFimMarcacaoQuadra();
    }
  } else if (estado.etapaCalibracao === "quadra_centros_base") {
    estado.calibracao.court_aux_points = estado.calibracao.court_aux_points ?? {};
    const alvo = PONTOS_CENTRO_BASE_CALIBRACAO[estado.indiceCentroBaseCalibracao];
    if (!alvo) {
      atualizarInterfaceCalibracao();
      return;
    }
    estado.calibracao.court_aux_points[alvo.id] = {
      x: Number(ponto.x.toFixed(5)),
      y: Number(ponto.y.toFixed(5)),
      label: alvo.label,
      time_s: Number(tempo.toFixed(3)),
    };
    invalidarPreviewVelocidadeSaque();
    estado.indiceCentroBaseCalibracao += 1;
    avancarIndiceCentroBaseAtePendente();
    if (centrosBaseComplementoCompletos()) {
      if (projetarPontosQuadraFaltantes()) {
        estado.etapaCalibracao = "jogadores";
        estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
      } else {
        elementos.progressoCalibracao.textContent = "Nao foi possivel projetar a malha oficial. Marque mais pontos visiveis da quadra antes de seguir.";
      }
    }
  } else if (estado.etapaCalibracao === "jogadores") {
    const total = Number(estado.calibracao.players.player_count || 2);
    const chave = estado.indiceJogadorCalibracao === 0 ? "p1" : "p2";
    estado.calibracao.players[chave] = {
      x: Number(ponto.x.toFixed(5)),
      y: Number(ponto.y.toFixed(5)),
      label: chave === "p1" ? "Jogador 1" : "Jogador 2",
      time_s: Number(tempo.toFixed(3)),
    };
    estado.indiceJogadorCalibracao += 1;
    if (estado.indiceJogadorCalibracao >= total) {
      if (total < 2) {
        estado.calibracao.players.p2 = null;
      }
      estado.etapaCalibracao = "bola";
      sugerirTempoBola();
    }
  } else if (estado.etapaCalibracao === "bola") {
    atualizarParametrosSaqueCalibracao();
    const etapa = proximaEtapaBolaRastreio();
    registrarMarcaBolaCalibracao(ponto, tempo, {
      role: etapa?.role ?? "trajectory",
      label: etapa?.label,
      etapa,
    });
    sugerirTempoAposMarcacaoBola(tempo, { saltoLargo: evento.ctrlKey });
  }

  desenharCanvasCalibracao();
  atualizarInterfaceCalibracao();
}

function sugerirTempoBola() {
  const duracao = Number(elementos.videoCalibracao.duration || estado.calibracao?.video?.duration_s || 0);
  const indice = indiceProximaEtapaBolaRastreio();
  if (!duracao || indice < 0) {
    return;
  }
  const proporcao = TEMPOS_BOLA_SUGERIDOS[Math.min(indice, TEMPOS_BOLA_SUGERIDOS.length - 1)];
  irParaTempoCalibracao(duracao * proporcao);
}

function sugerirTempoAposMarcacaoBola(tempoMarcado, opcoes = {}) {
  const duracao = Number(elementos.videoCalibracao.duration || estado.calibracao?.video?.duration_s || 0);
  if (!duracao) {
    return;
  }
  const salto = opcoes.saltoLargo ? 0.1 : 0.05;
  const proximoTempo = Math.min(duracao, Math.max(0, Number(tempoMarcado) || 0) + salto);
  irParaTempoCalibracao(proximoTempo);
}

function pontoQuadraCalibracaoPorId(id) {
  return estado.calibracao?.court_points?.[id] ?? null;
}

function pontoQuadraManualPorId(id) {
  const ponto = pontoQuadraCalibracaoPorId(id);
  return ponto && !ponto.auto_projected ? ponto : null;
}

function pontoAuxiliarQuadraPorId(id) {
  return estado.calibracao?.court_aux_points?.[id] ?? null;
}

function pontosQuadraParaHomografia(opcoes = {}) {
  const incluirProjetados = opcoes.incluirProjetados !== false;
  const pontosBase = {};
  Object.entries(estado.calibracao?.court_points ?? {}).forEach(([id, ponto]) => {
    if (incluirProjetados || !ponto?.auto_projected) {
      pontosBase[id] = ponto;
    }
  });
  return {
    ...pontosBase,
    ...(estado.calibracao?.court_aux_points ?? {}),
  };
}

function pontosQuadraFaltantes() {
  return IDS_PONTOS_QUADRA_OFICIAIS.filter((id) => !pontoQuadraCalibracaoPorId(id));
}

function pontosQuadraProjetados() {
  return IDS_PONTOS_QUADRA_OFICIAIS.filter((id) => {
    const ponto = estado.calibracao?.court_points?.[id];
    return Boolean(ponto?.auto_projected || String(ponto?.source ?? "").startsWith("projection_"));
  });
}

function cantosBaseFaltantes() {
  return IDS_CANTOS_BASE.filter((id) => !pontoQuadraCalibracaoPorId(id));
}

function cantosBaseProjetados() {
  return IDS_CANTOS_BASE.filter((id) => pontosQuadraProjetados().includes(id));
}

function centrosBaseComplementoCompletos() {
  return PONTOS_CENTRO_BASE_CALIBRACAO.every((ponto) => Boolean(pontoAuxiliarQuadraPorId(ponto.id)));
}

function complementoQuadraPendente() {
  return pontosQuadraFaltantes().length > 0 || totalPontosQuadraPulados() > 0;
}

function algumPontoManualQuadra(ids) {
  return ids.some((id) => Boolean(pontoQuadraManualPorId(id)));
}

function requisitosMalhaOficial() {
  const faltantes = [];
  if (!pontoQuadraManualPorId("servico_sup_esquerda") || !pontoQuadraManualPorId("servico_sup_direita")) {
    faltantes.push("largura do T superior");
  }
  if (!pontoQuadraManualPorId("servico_inf_esquerda") || !pontoQuadraManualPorId("servico_inf_direita")) {
    faltantes.push("largura do T inferior");
  }
  if (!pontoQuadraManualPorId("centro_sup") || !pontoQuadraManualPorId("centro_inf")) {
    faltantes.push("meios do T superior/inferior");
  }
  if (!centrosBaseComplementoCompletos()) {
    faltantes.push("meios das duas linhas de base");
  }
  if (!algumPontoManualQuadra(["sup_esquerda", "inf_esquerda", "rede_esquerda"])) {
    faltantes.push("referencia externa esquerda");
  }
  if (!algumPontoManualQuadra(["sup_direita", "inf_direita", "rede_direita"])) {
    faltantes.push("referencia externa direita");
  }
  return {
    ok: faltantes.length === 0,
    faltantes,
  };
}

function mensagemRequisitosMalhaOficial() {
  const requisitos = requisitosMalhaOficial();
  if (requisitos.ok) {
    return "";
  }
  return `Faltam referencias para projetar a quadra: ${requisitos.faltantes.join(", ")}.`;
}

function avancarIndiceCentroBaseAtePendente() {
  while (
    estado.indiceCentroBaseCalibracao < PONTOS_CENTRO_BASE_CALIBRACAO.length
    && pontoAuxiliarQuadraPorId(PONTOS_CENTRO_BASE_CALIBRACAO[estado.indiceCentroBaseCalibracao].id)
  ) {
    estado.indiceCentroBaseCalibracao += 1;
  }
}

function referenciaLarguraBaseMarcada() {
  const pontos = estado.calibracao?.court_points ?? {};
  const pares = [
    ["superior", "sup_esquerda", "sup_direita", "base_sup_centro"],
    ["inferior", "inf_esquerda", "inf_direita", "base_inf_centro"],
  ];
  for (const [nome, esquerdaId, direitaId, centroId] of pares) {
    if (pontos[esquerdaId] && pontos[direitaId]) {
      return {
        nome,
        esquerda: pontos[esquerdaId],
        direita: pontos[direitaId],
        centro: pontoAuxiliarQuadraPorId(centroId),
      };
    }
  }
  return null;
}

function registrarPontoQuadraProjetado(id, ponto, metodo) {
  if (!estado.calibracao || !ponto) {
    return;
  }
  const alvo = PONTOS_QUADRA_CALIBRACAO.find((item) => item.id === id);
  estado.calibracao.court_points = estado.calibracao.court_points ?? {};
  estado.calibracao.court_missing = estado.calibracao.court_missing ?? {};
  estado.calibracao.court_points[id] = {
    x: Number(Math.max(-0.25, Math.min(1.25, ponto.x)).toFixed(5)),
    y: Number(Math.max(-0.25, Math.min(1.25, ponto.y)).toFixed(5)),
    label: alvo?.label ?? id,
    source: "projection_court_mesh",
    auto_projected: true,
    projection_model: metodo,
  };
  delete estado.calibracao.court_missing[id];
}

function projetarPontosQuadraPorHomografia(idsFaltantes) {
  const matriz = matrizHomografiaVideoParaQuadra({ incluirProjetados: false });
  const inversa = inverterHomografia(matriz);
  if (!inversa) {
    return false;
  }
  return idsFaltantes.every((id) => {
    const destino = PONTOS_QUADRA_REAIS_M[id];
    if (!destino) {
      return false;
    }
    const pontoBruto = aplicarHomografiaXY(inversa, destino[0], destino[1]);
    if (
      !pontoBruto
      || !Number.isFinite(pontoBruto.x)
      || !Number.isFinite(pontoBruto.y)
      || pontoBruto.x < -0.25
      || pontoBruto.x > 1.25
      || pontoBruto.y < -0.25
      || pontoBruto.y > 1.25
    ) {
      return false;
    }
    const ponto = limitarPontoProjetadoQuadra(pontoBruto);
    registrarPontoQuadraProjetado(id, ponto, {
      version: 1,
      metodo: "malha_oficial_homografia",
      centros_base: Object.keys(estado.calibracao?.court_aux_points ?? {}),
      pontos_reais_usados: Object.keys(pontosQuadraParaHomografia({ incluirProjetados: false })),
    });
    return true;
  });
}

function reverterPontosQuadraProjetados() {
  if (!estado.calibracao) {
    return;
  }
  estado.calibracao.court_points = estado.calibracao.court_points ?? {};
  estado.calibracao.court_missing = estado.calibracao.court_missing ?? {};
  pontosQuadraProjetados().forEach((id) => {
    const alvo = PONTOS_QUADRA_CALIBRACAO.find((item) => item.id === id);
    delete estado.calibracao.court_points[id];
    estado.calibracao.court_missing[id] = {
      label: alvo?.label ?? id,
      reason: "not_visible",
      restored_from_projection: true,
    };
  });
  estado.calibracao.court_projection = null;
}

function reverterCantosBaseProjetados() {
  reverterPontosQuadraProjetados();
}

function projetarPontosQuadraFaltantes() {
  const idsFaltantes = pontosQuadraFaltantes();
  if (!idsFaltantes.length) {
    return true;
  }
  if (!centrosBaseComplementoCompletos()) {
    return false;
  }
  reverterPontosQuadraProjetados();
  if (!requisitosMalhaOficial().ok) {
    return false;
  }
  const faltantesAtualizados = pontosQuadraFaltantes();
  const ok = projetarPontosQuadraPorHomografia(faltantesAtualizados);
  if (ok && !pontosQuadraFaltantes().length) {
    estado.calibracao.court_projection = {
      type: "official_court_mesh_completion",
      completed_at: new Date().toISOString(),
      projected_ids: pontosQuadraProjetados(),
      auxiliary_points: Object.keys(estado.calibracao?.court_aux_points ?? {}),
      official_dimensions_m: MEDIDAS_QUADRA_OFICIAIS,
    };
    invalidarPreviewVelocidadeSaque();
    return true;
  }
  return false;
}

function projetarCantosBaseFaltantes() {
  return projetarPontosQuadraFaltantes();
}

function resolverFimMarcacaoQuadra() {
  if (complementoQuadraPendente()) {
    estado.etapaCalibracao = "quadra_centros_base";
    estado.indiceCentroBaseCalibracao = 0;
    avancarIndiceCentroBaseAtePendente();
    if (centrosBaseComplementoCompletos() && projetarPontosQuadraFaltantes()) {
      estado.etapaCalibracao = "jogadores";
      estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
      elementos.progressoCalibracao.textContent = "Linhas invisiveis projetadas pela malha oficial. Agora marque os jogadores.";
    } else {
      elementos.progressoCalibracao.textContent = mensagemRequisitosMalhaOficial() || "Marque o meio das duas linhas de base para projetar as linhas invisiveis da quadra.";
    }
    return;
  }
  estado.etapaCalibracao = "jogadores";
  estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
}

function pontoQuadraResolvido(id) {
  return Boolean(estado.calibracao?.court_points?.[id] || estado.calibracao?.court_missing?.[id]);
}

function totalPontosQuadraMarcados() {
  return Object.keys(estado.calibracao?.court_points ?? {}).length;
}

function totalPontosQuadraPulados() {
  return Object.keys(estado.calibracao?.court_missing ?? {}).length;
}

function totalPontosQuadraResolvidos() {
  return totalPontosQuadraMarcados() + totalPontosQuadraPulados();
}

function quadraProntaParaSaque() {
  return totalPontosQuadraResolvidos() >= PONTOS_QUADRA_CALIBRACAO.length
    && totalPontosQuadraMarcados() >= 4
    && !complementoQuadraPendente();
}

function avancarIndiceQuadraAtePendente() {
  while (
    estado.indicePontoQuadra < PONTOS_QUADRA_CALIBRACAO.length
    && pontoQuadraResolvido(PONTOS_QUADRA_CALIBRACAO[estado.indicePontoQuadra].id)
  ) {
    estado.indicePontoQuadra += 1;
  }
}

function pularPontoQuadraCalibracao() {
  if (!estado.calibracao || estado.etapaCalibracao !== "quadra") {
    return;
  }
  estado.calibracao.court_points = estado.calibracao.court_points ?? {};
  estado.calibracao.court_missing = estado.calibracao.court_missing ?? {};
  const alvo = PONTOS_QUADRA_CALIBRACAO[estado.indicePontoQuadra];
  if (!alvo) {
    atualizarInterfaceCalibracao();
    return;
  }

  const tempo = tempoAtualMarcacaoCalibracao();
  if (estado.calibracao.court_points) {
    delete estado.calibracao.court_points[alvo.id];
  }
  estado.calibracao.court_missing[alvo.id] = {
    label: alvo.label,
    reason: "not_visible",
    time_s: Number(tempo.toFixed(3)),
  };
  invalidarPreviewVelocidadeSaque();
  estado.indicePontoQuadra += 1;
  avancarIndiceQuadraAtePendente();
  if (estado.indicePontoQuadra >= PONTOS_QUADRA_CALIBRACAO.length) {
    resolverFimMarcacaoQuadra();
  }

  desenharCanvasCalibracao();
  atualizarInterfaceCalibracao();
}

function selecionarTipoEspecialBola(tipo) {
  if (!estado.calibracao) {
    return;
  }
  if (!quadraProntaParaSaque()) {
    estado.tipoEspecialBola = null;
    elementos.progressoCalibracao.textContent = "Conclua primeiro as medicoes da quadra. Elas sao obrigatorias para calcular a velocidade do saque.";
    atualizarInterfaceCalibracao();
    return;
  }
  estado.autoRastroBolaAguardandoInicio = false;
  estado.tipoEspecialBola = estado.tipoEspecialBola === tipo ? null : tipo;
  if (estado.tipoEspecialBola === "serve_contact_ground") {
    const contatoSaque = marcaBolaPorRole("serve_contact");
    const tempoContato = Number(contatoSaque?.time_s);
    if (Number.isFinite(tempoContato)) {
      irParaTempoCalibracao(tempoContato);
    }
  }
  const config = TIPOS_ESPECIAIS_BOLA[estado.tipoEspecialBola];
  if (config) {
    elementos.progressoCalibracao.textContent = `Clique no frame para marcar: ${config.label}. Essa marcacao pode ser feita antes do rastreio completo da bolinha.`;
  }
  atualizarInterfaceCalibracao();
  atualizarOverlayCalibracao();
}

function atualizarParametrosSaqueCalibracao() {
  if (!estado.calibracao) {
    return;
  }
  estado.calibracao.serve_metrics = estado.calibracao.serve_metrics ?? {};
  estado.calibracao.serve_metrics.curve_factor = 1.03;
  estado.calibracao.serve_metrics.radar_factor = 1.074;
  estado.calibracao.serve_metrics.height_mode = "auto_from_contact_projection";
  estado.calibracao.serve_metrics.note = "Velocidade do saque calculada em 3D entre contato e primeiro toque, com altura estimada automaticamente pela projecao no chao, homografia da quadra e correcao radar para velocidade inicial.";
}

function avancarEtapaCalibracao() {
  if (!estado.calibracao) {
    return;
  }
  const validacao = validarCalibracao();
  if (estado.etapaCalibracao === "quadra") {
    if (totalPontosQuadraResolvidos() < PONTOS_QUADRA_CALIBRACAO.length) {
      elementos.progressoCalibracao.textContent = "Resolva todos os pontos de quadra: marque os visiveis e pule apenas os que nao aparecem no frame.";
      return;
    }
    resolverFimMarcacaoQuadra();
  } else if (estado.etapaCalibracao === "quadra_centros_base") {
    if (!centrosBaseComplementoCompletos()) {
      elementos.progressoCalibracao.textContent = "Marque os meios das duas linhas de base antes de projetar as linhas invisiveis.";
      return;
    }
    if (!projetarPontosQuadraFaltantes()) {
      elementos.progressoCalibracao.textContent = mensagemRequisitosMalhaOficial() || "Nao foi possivel projetar a malha oficial com as marcacoes atuais.";
      return;
    }
    estado.etapaCalibracao = "jogadores";
    estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
  } else if (estado.etapaCalibracao === "jogadores") {
    if (!jogadoresCalibrados()) {
      elementos.progressoCalibracao.textContent = "Marque o Jogador 1 e, se houver, o Jogador 2.";
      return;
    }
    estado.etapaCalibracao = "bola";
    sugerirTempoBola();
  } else if (!validacao.ok) {
    elementos.progressoCalibracao.textContent = validacao.mensagem;
  }
  atualizarInterfaceCalibracao();
}

function voltarEtapaCalibracao() {
  if (estado.etapaCalibracao === "bola") {
    estado.etapaCalibracao = "jogadores";
    estado.tipoEspecialBola = null;
  } else if (estado.etapaCalibracao === "jogadores") {
    estado.etapaCalibracao = pontosQuadraProjetados().length > 0 ? "quadra_centros_base" : "quadra";
  } else if (estado.etapaCalibracao === "quadra_centros_base") {
    estado.etapaCalibracao = "quadra";
  }
  atualizarInterfaceCalibracao();
}

function desfazerPontoCalibracao() {
  if (!estado.calibracao) {
    return;
  }
  if (estado.etapaCalibracao === "quadra") {
    let indice = Math.min(PONTOS_QUADRA_CALIBRACAO.length - 1, Math.max(0, estado.indicePontoQuadra - 1));
    while (indice > 0 && !pontoQuadraResolvido(PONTOS_QUADRA_CALIBRACAO[indice].id)) {
      indice -= 1;
    }
    const alvo = PONTOS_QUADRA_CALIBRACAO[indice];
    if (alvo && pontoQuadraResolvido(alvo.id)) {
      delete estado.calibracao.court_points[alvo.id];
      if (estado.calibracao.court_missing) {
        delete estado.calibracao.court_missing[alvo.id];
      }
      estado.indicePontoQuadra = indice;
      invalidarPreviewVelocidadeSaque();
    }
  } else if (estado.etapaCalibracao === "quadra_centros_base") {
    estado.calibracao.court_aux_points = estado.calibracao.court_aux_points ?? {};
    if (pontoAuxiliarQuadraPorId("base_inf_centro")) {
      delete estado.calibracao.court_aux_points.base_inf_centro;
      estado.indiceCentroBaseCalibracao = 1;
    } else if (pontoAuxiliarQuadraPorId("base_sup_centro")) {
      delete estado.calibracao.court_aux_points.base_sup_centro;
      estado.indiceCentroBaseCalibracao = 0;
    }
    reverterPontosQuadraProjetados();
    invalidarPreviewVelocidadeSaque();
  } else if (estado.etapaCalibracao === "jogadores") {
    if (estado.calibracao.players.p2) {
      estado.calibracao.players.p2 = null;
      estado.indiceJogadorCalibracao = 1;
    } else if (estado.calibracao.players.p1) {
      estado.calibracao.players.p1 = null;
      estado.indiceJogadorCalibracao = 0;
    }
  } else if (estado.etapaCalibracao === "bola") {
    const removida = estado.calibracao.ball_marks.pop();
    if (marcacaoAfetaVelocidadeSaque(removida?.role ?? "trajectory")) {
      invalidarPreviewVelocidadeSaque();
    }
  }
  desenharCanvasCalibracao();
  atualizarInterfaceCalibracao();
}

function finalizarCalibracao() {
  const validacao = validarCalibracao();
  if (!validacao.ok) {
    elementos.progressoCalibracao.textContent = validacao.mensagem;
    return;
  }
  estado.calibracaoPronta = true;
  fecharModalCalibracao();
  elementos.statusUpload.textContent = "Calibracao pronta. Agora voce pode enviar o video para processamento.";
}

function jogadoresCalibrados() {
  const total = Number(estado.calibracao?.players?.player_count || 2);
  return Boolean(estado.calibracao?.players?.p1) && (total < 2 || Boolean(estado.calibracao?.players?.p2));
}

function marcaBolaPorRole(role) {
  return (estado.calibracao?.ball_marks ?? []).find((marca) => marca.role === role);
}

function etapaBolaResolvida(etapa) {
  if (!etapa) {
    return false;
  }
  const marcas = estado.calibracao?.ball_marks ?? [];
  if (etapa.role && etapa.role !== "trajectory") {
    return Boolean(marcaBolaPorRole(etapa.role));
  }
  return marcas.some((marca) => marca.sequence_id === etapa.id);
}

function proximaEtapaBolaRastreio() {
  return MARCAS_BOLA_RECOMENDADAS.find((etapa) => !etapaBolaResolvida(etapa)) ?? null;
}

function indiceProximaEtapaBolaRastreio() {
  return MARCAS_BOLA_RECOMENDADAS.findIndex((etapa) => !etapaBolaResolvida(etapa));
}

function etapaBolaPorRole(role) {
  return MARCAS_BOLA_RECOMENDADAS.find((etapa) => etapa.role === role) ?? null;
}

function arredondarLog(valor, casas = 4) {
  if (!Number.isFinite(valor)) {
    return null;
  }
  return Number(valor.toFixed(casas));
}

function matrizHomografiaVideoParaQuadra(opcoes = {}) {
  const pontos = pontosQuadraParaHomografia(opcoes);
  const linhas = [];
  const respostas = [];

  Object.entries(PONTOS_HOMOGRAFIA_QUADRA_REAIS_M).forEach(([id, destino]) => {
    const origem = pontos[id];
    if (!origem || !Number.isFinite(Number(origem.x)) || !Number.isFinite(Number(origem.y))) {
      return;
    }
    const x = Number(origem.x);
    const y = Number(origem.y);
    const [xReal, yReal] = destino;
    linhas.push([x, y, 1, 0, 0, 0, -xReal * x, -xReal * y]);
    respostas.push(xReal);
    linhas.push([0, 0, 0, x, y, 1, -yReal * x, -yReal * y]);
    respostas.push(yReal);
  });

  if (linhas.length < 8) {
    return null;
  }

  const normal = Array.from({ length: 8 }, () => Array(8).fill(0));
  const rhs = Array(8).fill(0);
  linhas.forEach((linha, indiceLinha) => {
    for (let i = 0; i < 8; i += 1) {
      rhs[i] += linha[i] * respostas[indiceLinha];
      for (let j = 0; j < 8; j += 1) {
        normal[i][j] += linha[i] * linha[j];
      }
    }
  });

  const solucao = resolverSistemaLinear(normal, rhs);
  return solucao ? [...solucao, 1] : null;
}

function resolverSistemaLinear(matriz, vetor) {
  const n = vetor.length;
  const a = matriz.map((linha, indice) => [...linha, vetor[indice]]);
  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let linha = col + 1; linha < n; linha += 1) {
      if (Math.abs(a[linha][col]) > Math.abs(a[pivot][col])) {
        pivot = linha;
      }
    }
    if (Math.abs(a[pivot][col]) < 1e-10) {
      return null;
    }
    if (pivot !== col) {
      [a[pivot], a[col]] = [a[col], a[pivot]];
    }
    const div = a[col][col];
    for (let j = col; j <= n; j += 1) {
      a[col][j] /= div;
    }
    for (let linha = 0; linha < n; linha += 1) {
      if (linha === col) {
        continue;
      }
      const fator = a[linha][col];
      for (let j = col; j <= n; j += 1) {
        a[linha][j] -= fator * a[col][j];
      }
    }
  }
  return a.map((linha) => linha[n]);
}

function aplicarHomografiaPonto(matriz, ponto) {
  if (!matriz || !ponto) {
    return null;
  }
  return aplicarHomografiaXY(matriz, Number(ponto.x), Number(ponto.y));
}

function aplicarHomografiaXY(matriz, x, y) {
  if (!matriz || !Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }
  const den = matriz[6] * x + matriz[7] * y + matriz[8];
  if (!Number.isFinite(den) || Math.abs(den) < 1e-9) {
    return null;
  }
  return {
    x: (matriz[0] * x + matriz[1] * y + matriz[2]) / den,
    y: (matriz[3] * x + matriz[4] * y + matriz[5]) / den,
  };
}

function inverterHomografia(matriz) {
  if (!matriz || matriz.length !== 9) {
    return null;
  }
  const [a, b, c, d, e, f, g, h, i] = matriz;
  const A = e * i - f * h;
  const B = c * h - b * i;
  const C = b * f - c * e;
  const D = f * g - d * i;
  const E = a * i - c * g;
  const F = c * d - a * f;
  const G = d * h - e * g;
  const H = b * g - a * h;
  const I = a * e - b * d;
  const det = a * A + b * D + c * G;
  if (!Number.isFinite(det) || Math.abs(det) < 1e-10) {
    return null;
  }
  return [A, B, C, D, E, F, G, H, I].map((valor) => valor / det);
}

function limitarPontoNormalizado(ponto) {
  if (!ponto) {
    return null;
  }
  return {
    x: Math.max(0, Math.min(1, Number(ponto.x) || 0)),
    y: Math.max(0, Math.min(1, Number(ponto.y) || 0)),
  };
}

function limitarPontoProjetadoQuadra(ponto) {
  if (!ponto) {
    return null;
  }
  return {
    x: Math.max(-0.25, Math.min(1.25, Number(ponto.x) || 0)),
    y: Math.max(-0.25, Math.min(1.25, Number(ponto.y) || 0)),
  };
}

function limitarPontoQuadraM(pontoM) {
  if (!pontoM) {
    return null;
  }
  return {
    x: Math.max(0, Math.min(MEDIDAS_QUADRA_OFICIAIS.larguraTotalM, pontoM.x)),
    y: Math.max(0, Math.min(MEDIDAS_QUADRA_OFICIAIS.comprimentoM, pontoM.y)),
  };
}

function distanciasLinhasQuadra(pontoM) {
  if (!pontoM) {
    return null;
  }
  const m = MEDIDAS_QUADRA_OFICIAIS;
  return {
    lateral_externa_esquerda_m: arredondarLog(pontoM.x, 3),
    lateral_externa_direita_m: arredondarLog(m.larguraTotalM - pontoM.x, 3),
    lateral_interna_esquerda_m: arredondarLog(pontoM.x - m.lateralInternaEsquerdaXM, 3),
    lateral_interna_direita_m: arredondarLog(m.lateralInternaDireitaXM - pontoM.x, 3),
    linha_central_t_m: arredondarLog(pontoM.x - m.centroXM, 3),
    base_superior_m: arredondarLog(pontoM.y, 3),
    linha_servico_superior_m: arredondarLog(pontoM.y - m.servicoSuperiorYM, 3),
    rede_m: arredondarLog(pontoM.y - m.redeYM, 3),
    linha_servico_inferior_m: arredondarLog(m.servicoInferiorYM - pontoM.y, 3),
    base_inferior_m: arredondarLog(m.comprimentoM - pontoM.y, 3),
  };
}

function resumoJogadorParaLog(chave, matriz, projecao, projecaoM) {
  const jogador = estado.calibracao?.players?.[chave];
  if (!jogador) {
    return null;
  }
  const jogadorM = aplicarHomografiaPonto(matriz, jogador);
  return {
    normalizado: {
      x: arredondarLog(jogador.x),
      y: arredondarLog(jogador.y),
    },
    quadra_m: jogadorM
      ? { x: arredondarLog(jogadorM.x, 3), y: arredondarLog(jogadorM.y, 3) }
      : null,
    delta_imagem_norm: {
      x: arredondarLog(projecao.x - jogador.x),
      y: arredondarLog(projecao.y - jogador.y),
      distancia: arredondarLog(Math.hypot(projecao.x - jogador.x, projecao.y - jogador.y)),
    },
    delta_quadra_m: jogadorM && projecaoM
      ? {
        x: arredondarLog(projecaoM.x - jogadorM.x, 3),
        y: arredondarLog(projecaoM.y - jogadorM.y, 3),
        distancia: arredondarLog(Math.hypot(projecaoM.x - jogadorM.x, projecaoM.y - jogadorM.y), 3),
      }
      : null,
  };
}

function logReferenciaProjecaoSaque() {
  const projecao = marcaBolaPorRole("serve_contact_ground");
  if (!projecao) {
    return;
  }
  const contato = marcaBolaPorRole("serve_contact");
  const matriz = matrizHomografiaVideoParaQuadra();
  const projecaoM = aplicarHomografiaPonto(matriz, projecao);
  const contatoM = aplicarHomografiaPonto(matriz, contato);
  const jogadores = {
    p1: resumoJogadorParaLog("p1", matriz, projecao, projecaoM),
    p2: resumoJogadorParaLog("p2", matriz, projecao, projecaoM),
  };
  const jogadorReferencia = Object.entries(jogadores)
    .filter(([, jogador]) => jogador?.delta_imagem_norm)
    .sort((a, b) => a[1].delta_imagem_norm.distancia - b[1].delta_imagem_norm.distancia)[0]?.[0] ?? null;
  const payload = {
    objetivo: "Referencia manual para futura projecao automatica do contato do saque no chao.",
    usar_para: "Treinar/ajustar uma projecao media baseada em jogador, homografia da quadra e distancias oficiais.",
    frame: {
      tempo_s: arredondarLog(projecao.time_s, 3),
      fps: arredondarLog(fpsCalibracao(), 3),
      frame_index: estado.frameServidorIndexAtual,
      arquivo: estado.calibracao?.video?.file_name ?? null,
    },
    projecao_manual: {
      normalizado: {
        x: arredondarLog(projecao.x),
        y: arredondarLog(projecao.y),
      },
      quadra_m: projecaoM
        ? { x: arredondarLog(projecaoM.x, 3), y: arredondarLog(projecaoM.y, 3) }
        : null,
      percentuais_quadra: projecaoM
        ? {
          x: arredondarLog(projecaoM.x / MEDIDAS_QUADRA_OFICIAIS.larguraTotalM, 4),
          y: arredondarLog(projecaoM.y / MEDIDAS_QUADRA_OFICIAIS.comprimentoM, 4),
        }
        : null,
      distancias_para_linhas: distanciasLinhasQuadra(projecaoM),
    },
    contato_bola: contato
      ? {
        normalizado: { x: arredondarLog(contato.x), y: arredondarLog(contato.y) },
        quadra_m: contatoM ? { x: arredondarLog(contatoM.x, 3), y: arredondarLog(contatoM.y, 3) } : null,
        delta_para_projecao_norm: {
          x: arredondarLog(projecao.x - contato.x),
          y: arredondarLog(projecao.y - contato.y),
          distancia: arredondarLog(Math.hypot(projecao.x - contato.x, projecao.y - contato.y)),
        },
      }
      : null,
    jogadores,
    jogador_referencia_sugerido: jogadorReferencia,
    pontos_quadra_usados: Object.fromEntries(
      Object.entries(estado.calibracao?.court_points ?? {}).map(([id, ponto]) => [
        id,
        { x: arredondarLog(ponto.x), y: arredondarLog(ponto.y) },
      ]),
    ),
  };
  console.info("[Tennis X-Ray] referencia_projecao_saque", payload);
}

function jogadorBaseProjecaoAutomatica() {
  const players = estado.calibracao?.players ?? {};
  return players[REFERENCIA_PROJECAO_SAQUE.jogadorReferencia]
    || players.p1
    || players.p2
    || null;
}

function jogadorBaseProjecaoAutomaticaPorContato(contato) {
  const players = estado.calibracao?.players ?? {};
  const candidatos = [
    ["p1", players.p1],
    ["p2", players.p2],
  ].filter(([, ponto]) => ponto && Number.isFinite(Number(ponto.x)) && Number.isFinite(Number(ponto.y)));
  if (!contato || candidatos.length === 0) {
    const fallback = jogadorBaseProjecaoAutomatica();
    const chaveFallback = Object.entries(players).find(([, ponto]) => ponto === fallback)?.[0]
      || REFERENCIA_PROJECAO_SAQUE.jogadorReferencia;
    return fallback ? { chave: chaveFallback, ponto: fallback, distancia: null } : null;
  }
  const escolhido = candidatos
    .map(([chave, ponto]) => ({
      chave,
      ponto,
      distancia: distanciaPontosNormalizados(contato, ponto),
    }))
    .sort((a, b) => a.distancia - b.distancia)[0];
  return escolhido ?? null;
}

function distanciaPontosNormalizados(a, b) {
  if (!a || !b) {
    return Infinity;
  }
  return Math.hypot((Number(a.x) || 0) - (Number(b.x) || 0), (Number(a.y) || 0) - (Number(b.y) || 0));
}

function pontoNormalizadoParaPixel(ponto) {
  const canvas = elementos.canvasCalibracao;
  const largura = Math.max(1, Number(canvas?.width) || 1);
  const altura = Math.max(1, Number(canvas?.height) || 1);
  return {
    x: Number(ponto?.x || 0) * largura,
    y: Number(ponto?.y || 0) * altura,
  };
}

function pontoPixelParaNormalizado(ponto) {
  const canvas = elementos.canvasCalibracao;
  const largura = Math.max(1, Number(canvas?.width) || 1);
  const altura = Math.max(1, Number(canvas?.height) || 1);
  return limitarPontoNormalizado({
    x: Number(ponto?.x || 0) / largura,
    y: Number(ponto?.y || 0) / altura,
  });
}

function linhaPixelPorPontosNormalizados(a, b) {
  if (!a || !b) {
    return null;
  }
  const p1 = pontoNormalizadoParaPixel(a);
  const p2 = pontoNormalizadoParaPixel(b);
  if (Math.hypot(p2.x - p1.x, p2.y - p1.y) < 2) {
    return null;
  }
  const linha = linhaPorDoisPontos(p1, p2);
  const norma = Math.hypot(linha.a, linha.b);
  if (!Number.isFinite(norma) || norma < 1e-6) {
    return null;
  }
  return {
    a: linha.a / norma,
    b: linha.b / norma,
    c: linha.c / norma,
  };
}

function pontoFugaPorLinhas(linhas) {
  const validas = linhas.filter(Boolean);
  if (validas.length < 2) {
    return null;
  }
  const normal = [
    [0, 0],
    [0, 0],
  ];
  const rhs = [0, 0];
  validas.forEach((linha) => {
    normal[0][0] += linha.a * linha.a;
    normal[0][1] += linha.a * linha.b;
    normal[1][0] += linha.a * linha.b;
    normal[1][1] += linha.b * linha.b;
    rhs[0] += -linha.a * linha.c;
    rhs[1] += -linha.b * linha.c;
  });
  const solucao = resolverSistemaLinear(normal, rhs);
  if (!solucao || !Number.isFinite(solucao[0]) || !Number.isFinite(solucao[1])) {
    return null;
  }
  return { x: solucao[0], y: solucao[1] };
}

function linhasDirecaoQuadra(pares) {
  const pontos = estado.calibracao?.court_points ?? {};
  return pares
    .map(([a, b]) => linhaPixelPorPontosNormalizados(pontos[a], pontos[b]))
    .filter(Boolean);
}

function calcularPontosFugaQuadra() {
  const linhasLargura = linhasDirecaoQuadra([
    ["sup_esquerda", "sup_direita"],
    ["inf_esquerda", "inf_direita"],
    ["rede_esquerda", "rede_direita"],
    ["servico_sup_esquerda", "servico_sup_direita"],
    ["servico_inf_esquerda", "servico_inf_direita"],
  ]);
  const linhasComprimento = linhasDirecaoQuadra([
    ["sup_esquerda", "inf_esquerda"],
    ["sup_direita", "inf_direita"],
    ["servico_sup_esquerda", "servico_inf_esquerda"],
    ["servico_sup_direita", "servico_inf_direita"],
    ["centro_sup", "centro_inf"],
  ]);

  const fugaLargura = pontoFugaPorLinhas(linhasLargura);
  const fugaComprimento = pontoFugaPorLinhas(linhasComprimento);
  if (!fugaLargura || !fugaComprimento) {
    return null;
  }

  const canvas = elementos.canvasCalibracao;
  const centro = {
    x: Math.max(1, Number(canvas?.width) || 1) / 2,
    y: Math.max(1, Number(canvas?.height) || 1) / 2,
  };
  const eixoLargura = {
    x: fugaLargura.x - centro.x,
    y: fugaLargura.y - centro.y,
  };
  const eixoComprimento = {
    x: fugaComprimento.x - centro.x,
    y: fugaComprimento.y - centro.y,
  };
  const foco2 = -((eixoLargura.x * eixoComprimento.x) + (eixoLargura.y * eixoComprimento.y));
  if (!Number.isFinite(foco2) || foco2 <= 1) {
    return {
      largura: fugaLargura,
      comprimento: fugaComprimento,
      vertical: null,
      confiavel: false,
      motivo: "foco_invalido",
    };
  }

  const verticalRel = resolverSistemaLinear(
    [
      [eixoLargura.x, eixoLargura.y],
      [eixoComprimento.x, eixoComprimento.y],
    ],
    [-foco2, -foco2],
  );
  if (!verticalRel || !Number.isFinite(verticalRel[0]) || !Number.isFinite(verticalRel[1])) {
    return {
      largura: fugaLargura,
      comprimento: fugaComprimento,
      vertical: null,
      confiavel: false,
      motivo: "vertical_indefinida",
    };
  }

  const vertical = {
    x: centro.x + verticalRel[0],
    y: centro.y + verticalRel[1],
  };
  return {
    largura: fugaLargura,
    comprimento: fugaComprimento,
    vertical,
    confiavel: true,
    linhas_largura: linhasLargura.length,
    linhas_comprimento: linhasComprimento.length,
  };
}

function calcularProjecaoVisualSaque(contato, jogador) {
  if (!contato || !jogador) {
    return null;
  }
  const dxJogador = Number(jogador.x) - Number(contato.x);
  const dyJogador = Number(jogador.y) - Number(contato.y);
  if (!Number.isFinite(dxJogador) || !Number.isFinite(dyJogador)) {
    return null;
  }

  if (dyJogador > 0.025) {
    const fatorVertical = Math.max(1.55, Math.min(1.9, 2.08 - (2.9 * dyJogador)));
    const deslocamentoY = Math.max(0.075, Math.min(0.31, dyJogador * fatorVertical));
    const deslocamentoX = Math.max(-0.035, Math.min(0.035, dxJogador * 0.15));
    const ponto = limitarPontoNormalizado({
      x: Number(contato.x) + deslocamentoX,
      y: Number(contato.y) + deslocamentoY,
    });
    return ponto
      ? {
        ...ponto,
        quadra_m: null,
        metodo: "referencia_visual_contato_jogador",
        visual_model: {
          version: 1,
          fator_vertical: arredondarLog(fatorVertical, 3),
          delta_jogador_contato: {
            x: arredondarLog(dxJogador),
            y: arredondarLog(dyJogador),
          },
        },
      }
      : null;
  }

  const fallbackJogador = limitarPontoNormalizado({
    x: Number(jogador.x) + REFERENCIA_PROJECAO_SAQUE.deltaJogadorImagemNorm.x,
    y: Number(jogador.y) + REFERENCIA_PROJECAO_SAQUE.deltaJogadorImagemNorm.y,
  });
  return fallbackJogador
    ? {
      ...fallbackJogador,
      quadra_m: null,
      metodo: "referencia_jogador_imagem",
    }
    : null;
}

function limitarNumero(valor, minimo, maximo) {
  return Math.max(minimo, Math.min(maximo, valor));
}

function parametroNaRetaPixel(ponto, origem, direcao, norma2) {
  if (!ponto || !origem || !direcao || !Number.isFinite(norma2) || norma2 < 1e-9) {
    return null;
  }
  return (((ponto.x - origem.x) * direcao.x) + ((ponto.y - origem.y) * direcao.y)) / norma2;
}

function limitarParametroPelaBaseDoSacador(contatoPx, direcao, norma2, parametro, jogador) {
  const pontos = estado.calibracao?.court_points ?? {};
  const linhaVertical = linhaPorDoisPontos(contatoPx, {
    x: contatoPx.x + direcao.x,
    y: contatoPx.y + direcao.y,
  });
  const jogadorPx = jogador ? pontoNormalizadoParaPixel(jogador) : null;
  const pares = [
    {
      lado: "superior",
      base: linhaPixelPorPontosNormalizados(pontos.sup_esquerda, pontos.sup_direita),
      servico: linhaPixelPorPontosNormalizados(pontos.servico_sup_esquerda, pontos.servico_sup_direita),
    },
    {
      lado: "inferior",
      base: linhaPixelPorPontosNormalizados(pontos.inf_esquerda, pontos.inf_direita),
      servico: linhaPixelPorPontosNormalizados(pontos.servico_inf_esquerda, pontos.servico_inf_direita),
    },
  ];

  const candidatos = pares
    .map((par) => {
      if (!par.base || !par.servico) {
        return null;
      }
      const interBase = intersecaoLinhas(linhaVertical, par.base);
      const interServico = intersecaoLinhas(linhaVertical, par.servico);
      const tBase = parametroNaRetaPixel(interBase, contatoPx, direcao, norma2);
      const tServico = parametroNaRetaPixel(interServico, contatoPx, direcao, norma2);
      if (!interBase || !interServico || !Number.isFinite(tBase) || !Number.isFinite(tServico)) {
        return null;
      }
      const distanciaJogador = jogadorPx ? Math.hypot(jogadorPx.x - interBase.x, jogadorPx.y - interBase.y) : Math.abs(tBase);
      return {
        ...par,
        interBase,
        interServico,
        tBase,
        tServico,
        distanciaJogador,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.distanciaJogador - b.distanciaJogador);

  const escolhido = candidatos[0];
  if (!escolhido) {
    return { parametro, baseline_model: null };
  }

  const span = escolhido.tServico - escolhido.tBase;
  if (!Number.isFinite(span) || Math.abs(span) < 1e-5) {
    return { parametro, baseline_model: null };
  }
  const sinal = Math.sign(span) || 1;
  const margemTras = Math.abs(span) * 0.18;
  const avancoMaximo = Math.abs(span) * 0.42;
  const limiteA = escolhido.tBase - (sinal * margemTras);
  const limiteB = escolhido.tBase + (sinal * avancoMaximo);
  const minimo = Math.min(limiteA, limiteB);
  const maximo = Math.max(limiteA, limiteB);
  const ajustado = limitarNumero(parametro, minimo, maximo);

  return {
    parametro: ajustado,
    baseline_model: {
      lado: escolhido.lado,
      t_original: arredondarLog(parametro, 5),
      t_ajustado: arredondarLog(ajustado, 5),
      t_base: arredondarLog(escolhido.tBase, 5),
      t_servico: arredondarLog(escolhido.tServico, 5),
      limite_min: arredondarLog(minimo, 5),
      limite_max: arredondarLog(maximo, 5),
      base_norm: pontoPixelParaNormalizado(escolhido.interBase),
      servico_norm: pontoPixelParaNormalizado(escolhido.interServico),
    },
  };
}

function calcularProjecaoPerpendicularQuadra(contato, estimativaVisual, jogador) {
  if (!contato || !estimativaVisual) {
    return null;
  }
  const fugas = calcularPontosFugaQuadra();
  if (!fugas?.confiavel || !fugas.vertical) {
    return null;
  }
  const contatoPx = pontoNormalizadoParaPixel(contato);
  const visualPx = pontoNormalizadoParaPixel(estimativaVisual);
  const direcao = {
    x: fugas.vertical.x - contatoPx.x,
    y: fugas.vertical.y - contatoPx.y,
  };
  const norma2 = (direcao.x * direcao.x) + (direcao.y * direcao.y);
  if (!Number.isFinite(norma2) || norma2 < 1e-6) {
    return null;
  }
  const deltaVisual = {
    x: visualPx.x - contatoPx.x,
    y: visualPx.y - contatoPx.y,
  };
  const t = ((deltaVisual.x * direcao.x) + (deltaVisual.y * direcao.y)) / norma2;
  const limiteBase = limitarParametroPelaBaseDoSacador(contatoPx, direcao, norma2, t, jogador);
  const parametroFinal = limiteBase.parametro;
  const candidato = pontoPixelParaNormalizado({
    x: contatoPx.x + (direcao.x * parametroFinal),
    y: contatoPx.y + (direcao.y * parametroFinal),
  });
  if (!candidato) {
    return null;
  }

  const distanciaVisual = distanciaPontosNormalizados(candidato, estimativaVisual);
  const distanciaContato = distanciaPontosNormalizados(candidato, contato);
  if (
    distanciaContato < 0.045
    || distanciaContato > 0.34
    || distanciaVisual > 0.09
    || Number(candidato.y) <= Number(contato.y) + 0.025
  ) {
    return null;
  }

  const matriz = matrizHomografiaVideoParaQuadra();
  const candidatoM = aplicarHomografiaPonto(matriz, candidato);
  const margemX = MEDIDAS_QUADRA_OFICIAIS.larguraTotalM * 0.22;
  const margemY = MEDIDAS_QUADRA_OFICIAIS.comprimentoM * 0.16;
  if (
    candidatoM
    && (
      candidatoM.x < -margemX
      || candidatoM.x > MEDIDAS_QUADRA_OFICIAIS.larguraTotalM + margemX
      || candidatoM.y < -margemY
      || candidatoM.y > MEDIDAS_QUADRA_OFICIAIS.comprimentoM + margemY
    )
  ) {
    return null;
  }

  return {
    ...candidato,
    quadra_m: candidatoM
      ? { x: arredondarLog(candidatoM.x, 3), y: arredondarLog(candidatoM.y, 3) }
      : null,
    metodo: "perpendicular_quadra_pontos_fuga",
    geometric_model: {
      version: 1,
      vertical_vanishing_px: {
        x: arredondarLog(fugas.vertical.x, 2),
        y: arredondarLog(fugas.vertical.y, 2),
      },
      width_vanishing_px: {
        x: arredondarLog(fugas.largura.x, 2),
        y: arredondarLog(fugas.largura.y, 2),
      },
      depth_vanishing_px: {
        x: arredondarLog(fugas.comprimento.x, 2),
        y: arredondarLog(fugas.comprimento.y, 2),
      },
      linhas_largura: fugas.linhas_largura,
      linhas_comprimento: fugas.linhas_comprimento,
      distancia_visual_norm: arredondarLog(distanciaVisual),
      baseline_model: limiteBase.baseline_model,
    },
  };
}

function calcularProjecaoAutomaticaSaque(contato) {
  const jogadorReferencia = jogadorBaseProjecaoAutomaticaPorContato(contato);
  const jogador = jogadorReferencia?.ponto;
  if (!contato || !jogador) {
    return null;
  }

  const projecaoVisual = calcularProjecaoVisualSaque(contato, jogador);
  const projecaoQuadra = calcularProjecaoPerpendicularQuadra(contato, projecaoVisual, jogador);
  if (projecaoQuadra) {
    return {
      ...projecaoQuadra,
      jogador_referencia: {
        chave: jogadorReferencia.chave,
        distancia_contato: arredondarLog(jogadorReferencia.distancia),
      },
    };
  }

  if (projecaoVisual) {
    return {
      ...projecaoVisual,
      jogador_referencia: {
        chave: jogadorReferencia.chave,
        distancia_contato: arredondarLog(jogadorReferencia.distancia),
      },
    };
  }

  const fallbackContato = limitarPontoNormalizado({
    x: contato.x + REFERENCIA_PROJECAO_SAQUE.deltaContatoImagemNorm.x,
    y: contato.y + REFERENCIA_PROJECAO_SAQUE.deltaContatoImagemNorm.y,
  });
  return fallbackContato
    ? { ...fallbackContato, quadra_m: null, metodo: "referencia_contato_imagem" }
    : null;
}

function criarOuAtualizarProjecaoAutomaticaSaque(contato, tempo) {
  if (!estado.calibracao || !contato) {
    return;
  }
  const projecao = calcularProjecaoAutomaticaSaque(contato);
  if (!projecao) {
    return;
  }
  estado.calibracao.ball_marks = (estado.calibracao.ball_marks ?? []).filter((marca) => marca.role !== "serve_contact_ground");
  estado.calibracao.ball_marks.push({
    x: Number(projecao.x.toFixed(5)),
    y: Number(projecao.y.toFixed(5)),
    label: "Projecao automatica no chao do contato",
    role: "serve_contact_ground",
    sequence_id: null,
    time_s: Number((tempo ?? contato.time_s ?? 0).toFixed(3)),
    source: "auto_reference",
    auto_projection: true,
    projection_model: {
      version: 1,
      metodo: projecao.metodo,
      referencia: REFERENCIA_PROJECAO_SAQUE,
      jogador_referencia: projecao.jogador_referencia ?? null,
      quadra_m: projecao.quadra_m ?? null,
      visual_model: projecao.visual_model ?? null,
      geometric_model: projecao.geometric_model ?? null,
    },
  });
  logReferenciaProjecaoSaque();
  elementos.progressoCalibracao.textContent = "Projecao automatica criada. Se quiser ajustar, clique em Projecao e marque outro ponto.";
}

function registrarMarcaBolaCalibracao(ponto, tempo, opcoes = {}) {
  estado.calibracao.ball_marks = estado.calibracao.ball_marks ?? [];
  const role = opcoes.role ?? "trajectory";
  const etapa = opcoes.etapa ?? (role !== "trajectory" ? etapaBolaPorRole(role) : proximaEtapaBolaRastreio());
  const label = opcoes.label ?? etapa?.label ?? `Bola ${estado.calibracao.ball_marks.length + 1}`;
  if (role !== "trajectory") {
    estado.calibracao.ball_marks = estado.calibracao.ball_marks.filter((marca) => marca.role !== role);
  }
  estado.calibracao.ball_marks.push({
    x: Number(ponto.x.toFixed(5)),
    y: Number(ponto.y.toFixed(5)),
    label,
    role,
    sequence_id: etapa?.id ?? null,
    time_s: Number(tempo.toFixed(3)),
    source: opcoes.source ?? "manual",
  });
  if (role === "serve_contact") {
    criarOuAtualizarProjecaoAutomaticaSaque(marcaBolaPorRole("serve_contact"), tempo);
  }
  if (role === "serve_contact_ground") {
    logReferenciaProjecaoSaque();
  }
  if (marcacaoAfetaVelocidadeSaque(role)) {
    invalidarPreviewVelocidadeSaque();
  }
}

function podeDetectarRastroBolaAutomatico() {
  return Boolean(
    estado.calibracao
    && estado.calibracaoServidorId
    && quadraProntaParaSaque()
    && jogadoresCalibrados()
    && !estado.autoRastroBolaEmAndamento
    && !estado.autoRastroBolaAguardandoInicio,
  );
}

function prepararCalibracaoParaAutoRastro() {
  const copia = JSON.parse(JSON.stringify(estado.calibracao ?? {}));
  copia.ball_marks = (copia.ball_marks ?? []).filter((marca) => (
    marca.source !== "auto_track"
    && marca.source !== "auto_prediction"
    && marca.source !== "manual_auto_seed"
    && marca.role !== "serve_contact_ground"
  ));
  return copia;
}

function aplicarRastroAutomaticoBola(marcas) {
  estado.calibracao.ball_marks = estado.calibracao.ball_marks ?? [];
  const preservadas = estado.calibracao.ball_marks.filter((marca) => marca.source !== "auto_track" && marca.source !== "auto_prediction");
  const proximidadeManualS = 0.025;
  const novas = (marcas ?? [])
    .map((marca, indice) => ({
      x: Number(Math.max(0, Math.min(1, Number(marca.x))).toFixed(5)),
      y: Number(Math.max(0, Math.min(1, Number(marca.y))).toFixed(5)),
      label: marca.label ?? `Rastro automatico ${indice + 1}`,
      role: "trajectory",
      sequence_id: marca.sequence_id ?? `auto_ball_${String(indice + 1).padStart(3, "0")}`,
      time_s: Number((Number(marca.time_s) || 0).toFixed(3)),
      source: marca.source ?? "auto_track",
      confidence: Number(Number(marca.confidence ?? 0).toFixed(3)),
      frame_index: Number.isFinite(Number(marca.frame_index)) ? Number(marca.frame_index) : null,
      detector_source: marca.detector_source ?? "auto",
    }))
    .filter((marca) => Number.isFinite(marca.x) && Number.isFinite(marca.y) && Number.isFinite(marca.time_s))
    .filter((marca) => !preservadas.some((manual) => Math.abs(Number(manual.time_s ?? -999) - marca.time_s) <= proximidadeManualS));

  estado.calibracao.ball_marks = [...preservadas, ...novas].sort((a, b) => Number(a.time_s ?? 0) - Number(b.time_s ?? 0));
  if (novas.length > 0) {
    estado.etapaCalibracao = "bola";
    estado.tipoEspecialBola = null;
    invalidarPreviewVelocidadeSaque();
  }
  return novas.length;
}

function iniciarFluxoAutoRastroBola() {
  if (estado.autoRastroBolaAguardandoInicio) {
    estado.autoRastroBolaAguardandoInicio = false;
    elementos.progressoCalibracao.textContent = "Auto-rastro cancelado.";
    atualizarInterfaceCalibracao();
    return;
  }
  if (!podeDetectarRastroBolaAutomatico()) {
    elementos.progressoCalibracao.textContent = quadraProntaParaSaque()
      ? "Marque os jogadores antes de detectar o rastro automatico."
      : "Conclua as medidas da quadra antes de detectar o rastro automatico.";
    atualizarInterfaceCalibracao();
    return;
  }

  estado.autoRastroBolaAguardandoInicio = true;
  estado.autoRastroBolaErro = "";
  estado.autoRastroBolaResumo = null;
  estado.tipoEspecialBola = null;
  estado.etapaCalibracao = "bola";
  elementos.progressoCalibracao.textContent = "Clique na posicao inicial real da bolinha. A partir dela o app seguira em passos de 0,03s.";
  atualizarInterfaceCalibracao();
}

async function detectarRastroBolaAutomatico(seed) {
  if (!seed || !Number.isFinite(Number(seed.x)) || !Number.isFinite(Number(seed.y))) {
    estado.autoRastroBolaErro = "Marque primeiro a posicao inicial da bolinha.";
    atualizarInterfaceCalibracao();
    return;
  }

  estado.autoRastroBolaEmAndamento = true;
  estado.autoRastroBolaErro = "";
  estado.autoRastroBolaResumo = null;
  elementos.progressoCalibracao.textContent = "Seguindo a bolinha a partir da marcacao inicial...";
  atualizarInterfaceCalibracao();
  let mensagemFinal = "";

  try {
    const resposta = await fetch(`/api/videos/calibracao/${estado.calibracaoServidorId}/auto-rastro-bola`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        calibracao: prepararCalibracaoParaAutoRastro(),
        seed,
        step_s: AUTO_RASTRO_BOLA_STEP_S,
        min_confidence: AUTO_RASTRO_BOLA_MIN_CONFIDENCE,
        max_points: AUTO_RASTRO_BOLA_MAX_POINTS,
      }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) {
      throw new Error(dados.detail ?? "Nao foi possivel detectar o rastro automaticamente.");
    }

    const inseridas = aplicarRastroAutomaticoBola(dados.marks ?? []);
    const qualidade = dados.quality ?? {};
    estado.autoRastroBolaResumo = qualidade;
    if (inseridas <= 0) {
      estado.autoRastroBolaErro = "Nao encontrei pontos proximos confiaveis apos a marcacao inicial. Tente iniciar em um frame com a bolinha mais nitida.";
      mensagemFinal = estado.autoRastroBolaErro;
    } else {
      const confianca = formatarPercentual(qualidade.confianca_media ?? 0);
      mensagemFinal = `Rastro automatico: ${inseridas} pontos adicionados, confianca media ${confianca}. Revise e corrija se necessario.`;
    }
  } catch (erro) {
    estado.autoRastroBolaErro = erro.message ?? "Falha ao detectar o rastro automatico.";
    mensagemFinal = estado.autoRastroBolaErro;
    console.error(erro);
  } finally {
    estado.autoRastroBolaEmAndamento = false;
    desenharCanvasCalibracao();
    atualizarInterfaceCalibracao();
    if (mensagemFinal) {
      elementos.progressoCalibracao.textContent = mensagemFinal;
    }
  }
}

function saqueEspecialCompleto() {
  return Boolean(
    marcaBolaPorRole("serve_contact")
    && marcaBolaPorRole("serve_contact_ground")
    && marcaBolaPorRole("serve_court_bounce"),
  );
}

function referenciasSaqueFaltantes() {
  const referencias = [
    ["serve_contact", "contato"],
    ["serve_contact_ground", "projecao"],
    ["serve_court_bounce", "toque"],
  ];
  return referencias
    .filter(([role]) => !marcaBolaPorRole(role))
    .map(([, label]) => label);
}

function invalidarPreviewVelocidadeSaque() {
  estado.previewVelocidadeSaque = null;
  estado.previewVelocidadeSaqueErro = "";
  estado.downloadSaqueEmAndamento = false;
  estado.downloadSaqueJobId = null;
  estado.downloadSaqueUrl = null;
  estado.downloadSaqueErro = "";
  if (estado.calibracao) {
    delete estado.calibracao.serve_speed_locked;
  }
}

function roleReferenciaSaque(role) {
  return ["serve_contact", "serve_contact_ground", "serve_court_bounce"].includes(role);
}

function velocidadeTravadaUsaRastro() {
  const info = estado.previewVelocidadeSaque ?? estado.calibracao?.serve_speed_locked;
  if (!info) {
    return false;
  }
  const metodo = String(info.metodo ?? "");
  return metodo.includes("trajetoria") || Number(info.amostras_usadas ?? 0) >= 4;
}

function marcacaoAfetaVelocidadeSaque(role) {
  return roleReferenciaSaque(role) || velocidadeTravadaUsaRastro();
}

function definirResultadoVelocidadeSaque(texto, tipo = "", permitirDownload = false) {
  elementos.textoResultadoVelocidadeSaque.textContent = texto;
  elementos.resultadoVelocidadeSaque.classList.toggle("resultado-saque-ok", tipo === "ok");
  elementos.resultadoVelocidadeSaque.classList.toggle("resultado-saque-erro", tipo === "erro");
  const podeBaixar = permitirDownload && Boolean(estado.previewVelocidadeSaque) && Boolean(estado.downloadSaqueUrl) && !estado.downloadSaqueEmAndamento;
  elementos.botaoDownloadVideoSaque.classList.toggle("oculto", !podeBaixar);
  elementos.botaoDownloadVideoSaque.disabled = !podeBaixar;
}

function textoVelocidadeSaquePreview() {
  const info = estado.previewVelocidadeSaque;
  if (!info) {
    return "";
  }
  return [
    `Velocidade: ${formatarNumero(info.velocidade_kmh ?? 0, " km/h")}`,
    `tempo ate o quique: ${formatarNumero(info.tempo_voo_s ?? 0, " s")}`,
    `trajeto 3D estimado: ${formatarNumero(info.distancia_m ?? 0, " m")}`,
    `confianca: ${formatarPercentual(info.confianca ?? 0)}`,
  ].join(" | ");
}

function atualizarResultadoVelocidadeSaque() {
  const quadraOk = quadraProntaParaSaque();
  const pronto = quadraOk && saqueEspecialCompleto();
  elementos.botaoCalcularVelocidadeSaque.disabled = !pronto;
  if (!quadraOk) {
    definirResultadoVelocidadeSaque("Conclua as medicoes da quadra para liberar o calculo do saque.");
    return;
  }
  if (!pronto) {
    const faltantes = referenciasSaqueFaltantes();
    const prefixo = modoCalibracaoExigeSaque() ? "Falta no saque" : "Velocidade opcional";
    definirResultadoVelocidadeSaque(`${prefixo}: ${faltantes.join(", ")}.`);
    return;
  }
  if (estado.previewVelocidadeSaque) {
    let texto = textoVelocidadeSaquePreview();
    if (estado.downloadSaqueEmAndamento) {
      texto += " | renderizando video...";
    } else if (estado.downloadSaqueUrl) {
      texto += " | video pronto";
    } else if (estado.downloadSaqueErro) {
      texto += " | video ainda nao gerado";
    }
    definirResultadoVelocidadeSaque(texto, "ok", true);
    return;
  }
  if (estado.previewVelocidadeSaqueErro) {
    definirResultadoVelocidadeSaque(estado.previewVelocidadeSaqueErro, "erro");
    return;
  }
  definirResultadoVelocidadeSaque("Pronto para calcular sem renderizar o video.");
}

async function calcularVelocidadeSaquePreview() {
  if (!estado.calibracao || !quadraProntaParaSaque()) {
    estado.previewVelocidadeSaqueErro = "Conclua as medicoes da quadra antes de calcular o saque.";
    atualizarResultadoVelocidadeSaque();
    return;
  }
  if (!saqueEspecialCompleto()) {
    estado.previewVelocidadeSaqueErro = "Marque as 3 referencias do saque antes de calcular.";
    atualizarResultadoVelocidadeSaque();
    return;
  }

  atualizarParametrosSaqueCalibracao();
  elementos.botaoCalcularVelocidadeSaque.disabled = true;
  definirResultadoVelocidadeSaque("Calculando velocidade...");

  const resposta = await fetch("/api/videos/calibracao/velocidade-saque", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(estado.calibracao),
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    throw new Error(dados.detail ?? "Falha ao calcular velocidade do saque.");
  }

  if (!dados.velocidade_saque) {
    estado.previewVelocidadeSaque = null;
    estado.previewVelocidadeSaqueErro = dados.velocidade_saque_status?.mensagem ?? "Nao foi possivel calcular com as marcacoes atuais.";
    delete estado.calibracao.serve_speed_locked;
  } else {
    estado.previewVelocidadeSaque = dados.velocidade_saque;
    estado.calibracao.serve_speed_locked = {
      ...dados.velocidade_saque,
      source: "preview_button",
      locked_at: new Date().toISOString(),
    };
    estado.previewVelocidadeSaqueErro = "";
    estado.downloadSaqueUrl = null;
    estado.downloadSaqueErro = "";
    estado.metadataAnaliseReal = {
      ...(estado.metadataAnaliseReal ?? {}),
      velocidade_saque: dados.velocidade_saque,
      velocidade_saque_status: dados.velocidade_saque_status,
    };
    if (estado.dados?.metricas) {
      renderizarMetricas(estado.dados.metricas, estado.metadataAnaliseReal);
    }
    iniciarRenderizacaoSaqueBackground().catch((erro) => {
      estado.downloadSaqueEmAndamento = false;
      estado.downloadSaqueErro = erro.message ?? "Falha ao renderizar video de velocidade.";
      atualizarResultadoVelocidadeSaque();
      console.error(erro);
    });
  }
  atualizarResultadoVelocidadeSaque();
}

function aplicarVelocidadeTravadaNaCalibracao(copia) {
  if (estado.previewVelocidadeSaque) {
    copia.serve_speed_locked = {
      ...(copia.serve_speed_locked ?? {}),
      ...estado.previewVelocidadeSaque,
      source: "preview_button",
    };
  }
  return copia;
}

function calibracaoParaAnaliseFinal() {
  sincronizarModoCalibracao();
  const copia = JSON.parse(JSON.stringify(estado.calibracao ?? {}));
  copia.analysis_mode = modoCalibracaoAtual();
  copia.requires_serve_metrics = modoCalibracaoExigeSaque();
  copia.min_ball_marks_required = minMarcacoesBolaCalibracao();
  copia.ball_tracking = copia.ball_tracking ?? {};
  copia.ball_tracking.min_marks_required = minMarcacoesBolaCalibracao();
  return aplicarVelocidadeTravadaNaCalibracao(copia);
}

function calibracaoParaRenderizacaoSaque() {
  const copia = calibracaoParaAnaliseFinal();
  copia.render_options = {
    ...(copia.render_options ?? {}),
    modo: "download_saque",
    ocultar_bola_se_apenas_saque: true,
    renderizar_janela_saque: true,
  };
  return copia;
}

function nomeDownloadSaque() {
  const nomeBase = estado.calibracao?.video?.file_name || estado.arquivoUploadSelecionado?.name || "saque";
  const limpo = nomeBase.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 80) || "saque";
  return `${limpo}_velocidade_saque.mp4`;
}

function aguardar(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function aguardarJobVideoDownload(jobId) {
  while (true) {
    const resposta = await fetch(`/api/videos/jobs/${jobId}`);
    const job = await resposta.json();
    if (!resposta.ok) {
      throw new Error(job.detail ?? "Job de renderizacao nao encontrado.");
    }
    const progresso = Number(job.progresso ?? 0);
    if (estado.downloadSaqueJobId !== jobId) {
      return null;
    }
    const textoBase = textoVelocidadeSaquePreview() || "Velocidade calculada";
    definirResultadoVelocidadeSaque(`${textoBase} | renderizando ${formatarNumero(progresso, "%")}`, "ok");
    if (job.status === "concluido") {
      if (!job.url_video_analisado) {
        throw new Error("O video foi processado, mas a API nao retornou o arquivo renderizado.");
      }
      return job;
    }
    if (job.status === "falhou" || job.status === "cancelado") {
      throw new Error(job.mensagem ?? "Renderizacao encerrada antes do download.");
    }
    await aguardar(1400);
  }
}

async function baixarVideoRenderizado(url, nomeArquivo) {
  const resposta = await fetch(`${url}?download=${Date.now()}`);
  if (!resposta.ok) {
    throw new Error("Nao foi possivel baixar o video renderizado.");
  }
  const blob = await resposta.blob();
  const objetoUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objetoUrl;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objetoUrl), 2000);
}

async function iniciarRenderizacaoSaqueBackground() {
  if (!estado.previewVelocidadeSaque || !estado.calibracao) {
    estado.downloadSaqueErro = "Calcule a velocidade antes de renderizar o video.";
    atualizarResultadoVelocidadeSaque();
    return;
  }

  const arquivo = estado.arquivoUploadSelecionado ?? elementos.campoVideo.files?.[0];
  if (!estado.calibracaoServidorId && !arquivo) {
    throw new Error("Selecione o video original antes de renderizar o download.");
  }

  estado.downloadSaqueEmAndamento = true;
  estado.downloadSaqueUrl = null;
  estado.downloadSaqueErro = "";
  elementos.botaoDownloadVideoSaque.disabled = true;
  elementos.botaoDownloadVideoSaque.classList.add("oculto");
  atualizarResultadoVelocidadeSaque();

  const corpo = new FormData();
  if (estado.calibracaoServidorId) {
    corpo.append("calibracao_id", estado.calibracaoServidorId);
  } else {
    corpo.append("arquivo", arquivo);
  }
  corpo.append("calibracao", JSON.stringify(calibracaoParaRenderizacaoSaque()));

  const resposta = await fetch("/api/videos/upload", {
    method: "POST",
    body: corpo,
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    throw new Error(dados.detail ?? "Falha ao iniciar renderizacao do download.");
  }
  if (!dados.job_id) {
    throw new Error("A API nao retornou um job de renderizacao.");
  }

  estado.downloadSaqueJobId = dados.job_id;
  const job = await aguardarJobVideoDownload(dados.job_id);
  if (!job) {
    return;
  }
  if (estado.downloadSaqueJobId !== dados.job_id) {
    return;
  }
  estado.downloadSaqueUrl = job.url_video_analisado;
  estado.downloadSaqueEmAndamento = false;
  atualizarResultadoVelocidadeSaque();
}

async function baixarVideoSaqueRenderizado() {
  if (!estado.downloadSaqueUrl) {
    estado.downloadSaqueErro = "O video ainda esta renderizando. Aguarde o botao de download ser liberado.";
    atualizarResultadoVelocidadeSaque();
    return;
  }
  await baixarVideoRenderizado(estado.downloadSaqueUrl, nomeDownloadSaque());
  atualizarResultadoVelocidadeSaque();
}

function modoCalibracaoAtual() {
  return estado.modoCalibracao === "troca" ? "troca" : "ponto";
}

function modoCalibracaoExigeSaque() {
  return modoCalibracaoAtual() === "ponto";
}

function minMarcacoesBolaCalibracao() {
  return modoCalibracaoAtual() === "troca" ? MIN_MARCACOES_BOLA_TROCA : MIN_MARCACOES_BOLA;
}

function garantirSwitchModoCalibracao() {
  const sidebar = document.querySelector(".calibracao-sidebar");
  const alvoBox = elementos.alvoCalibracao?.closest(".calibracao-box");
  if (!sidebar || !alvoBox) {
    return;
  }

  let grupo = document.querySelector("#modo-calibracao-toggle");
  if (!grupo) {
    grupo = document.createElement("div");
    grupo.id = "modo-calibracao-toggle";
    grupo.className = "modo-calibracao-toggle";
    grupo.setAttribute("role", "group");
    grupo.setAttribute("aria-label", "Tipo de analise");
    grupo.innerHTML = `
      <button id="botao-modo-ponto-calibracao" class="botao secundario modo-calibracao-opcao ativo" type="button" aria-pressed="true">Ponto</button>
      <button id="botao-modo-troca-calibracao" class="botao secundario modo-calibracao-opcao" type="button" aria-pressed="false">Troca</button>
    `;
  }

  if (grupo.parentElement !== sidebar || grupo.previousElementSibling !== alvoBox) {
    sidebar.insertBefore(grupo, alvoBox.nextElementSibling);
  }

  elementos.botaoModoPontoCalibracao = grupo.querySelector("#botao-modo-ponto-calibracao");
  elementos.botaoModoTrocaCalibracao = grupo.querySelector("#botao-modo-troca-calibracao");
  if (grupo.dataset.listenersProntos !== "true") {
    elementos.botaoModoPontoCalibracao?.addEventListener("click", () => definirModoCalibracao("ponto"));
    elementos.botaoModoTrocaCalibracao?.addEventListener("click", () => definirModoCalibracao("troca"));
    grupo.dataset.listenersProntos = "true";
  }
}

function sincronizarModoCalibracao() {
  garantirSwitchModoCalibracao();
  const modo = modoCalibracaoAtual();
  if (estado.calibracao) {
    estado.calibracao.analysis_mode = modo;
    estado.calibracao.requires_serve_metrics = modoCalibracaoExigeSaque();
    estado.calibracao.min_ball_marks_required = minMarcacoesBolaCalibracao();
    estado.calibracao.serve_metrics = estado.calibracao.serve_metrics ?? {};
    estado.calibracao.serve_metrics.required = modoCalibracaoExigeSaque();
    estado.calibracao.ball_tracking = estado.calibracao.ball_tracking ?? {};
    estado.calibracao.ball_tracking.min_marks_required = minMarcacoesBolaCalibracao();
    estado.calibracao.ball_tracking.auto_render_detection = true;
    estado.calibracao.ball_tracking.mode = "pretrained_model_render";
  }
  elementos.botaoModoPontoCalibracao?.classList.toggle("ativo", modo === "ponto");
  elementos.botaoModoTrocaCalibracao?.classList.toggle("ativo", modo === "troca");
  elementos.botaoModoPontoCalibracao?.setAttribute("aria-pressed", String(modo === "ponto"));
  elementos.botaoModoTrocaCalibracao?.setAttribute("aria-pressed", String(modo === "troca"));
}

function definirModoCalibracao(modo) {
  const novoModo = modo === "troca" ? "troca" : "ponto";
  if (estado.modoCalibracao === novoModo) {
    return;
  }
  estado.modoCalibracao = novoModo;
  estado.calibracaoPronta = false;
  sincronizarModoCalibracao();
  atualizarInterfaceCalibracao();
}

function validarCalibracao() {
  if (!estado.calibracao) {
    return { ok: false, mensagem: "Selecione um video e conclua a calibracao." };
  }
  sincronizarModoCalibracao();
  const pontosQuadra = totalPontosQuadraMarcados();
  const pontosPulados = totalPontosQuadraPulados();
  const pontosResolvidos = pontosQuadra + pontosPulados;
  if (pontosResolvidos < PONTOS_QUADRA_CALIBRACAO.length) {
    return { ok: false, mensagem: `Faltam ${PONTOS_QUADRA_CALIBRACAO.length - pontosResolvidos} pontos de quadra marcados ou pulados.` };
  }
  if (complementoQuadraPendente()) {
    if (!centrosBaseComplementoCompletos()) {
      return { ok: false, mensagem: "Falta marcar o meio das duas linhas de base para projetar as linhas invisiveis." };
    }
    const requisitos = requisitosMalhaOficial();
    if (!requisitos.ok) {
      return { ok: false, mensagem: mensagemRequisitosMalhaOficial() };
    }
    return { ok: false, mensagem: "Projete a malha oficial antes de seguir para jogadores e bola." };
  }
  if (pontosQuadra < 4) {
    return { ok: false, mensagem: "Marque pelo menos 4 pontos reais da quadra para o sistema interpolar os pontos pulados." };
  }
  if (!jogadoresCalibrados()) {
    return { ok: false, mensagem: "Marque a posicao inicial do Jogador 1 e do Jogador 2 quando houver dois atletas." };
  }
  const faltantesSaque = referenciasSaqueFaltantes();
  if (modoCalibracaoExigeSaque() && faltantesSaque.length > 0) {
    return { ok: false, mensagem: `Falta marcar no saque: ${faltantesSaque.join(", ")}.` };
  }
  if (!modoCalibracaoExigeSaque() && faltantesSaque.length > 0) {
    return { ok: true, mensagem: "Modo troca: saque opcional." };
  }
  return { ok: true, mensagem: "Calibracao completa." };
}

function atualizarInterfaceCalibracao() {
  if (!estado.calibracao) {
    return;
  }

  estado.calibracao.players.player_count = Number(elementos.qtdJogadoresCalibracao.value || 2);
  atualizarParametrosSaqueCalibracao();
  sincronizarModoCalibracao();
  if (estado.calibracao.players.player_count < 2) {
    estado.calibracao.players.p2 = null;
  }

  const pontosQuadra = totalPontosQuadraMarcados();
  const pontosPulados = totalPontosQuadraPulados();
  const pontosResolvidos = pontosQuadra + pontosPulados;
  const centrosBaseMarcados = PONTOS_CENTRO_BASE_CALIBRACAO.filter((ponto) => pontoAuxiliarQuadraPorId(ponto.id)).length;
  const marcasBola = estado.calibracao.ball_marks?.length ?? 0;
  const contatoSaque = marcaBolaPorRole("serve_contact");
  const projecaoContatoSaque = marcaBolaPorRole("serve_contact_ground");
  const primeiroToqueSaque = marcaBolaPorRole("serve_court_bounce");
  const saqueLiberado = quadraProntaParaSaque();
  const saqueObrigatorio = modoCalibracaoExigeSaque();
  const modoLabel = modoCalibracaoAtual() === "troca" ? "Troca" : "Ponto";
  const marcasAutoBola = (estado.calibracao.ball_marks ?? []).filter((marca) => marca.source === "auto_track").length;
  if (!saqueLiberado && estado.tipoEspecialBola) {
    estado.tipoEspecialBola = null;
  }
  let alvo = "";
  let instrucao = "";

  if (estado.autoRastroBolaAguardandoInicio) {
    alvo = "Bolinha inicial";
    instrucao = "Clique exatamente no primeiro ponto visivel da bolinha.";
  } else if (estado.tipoEspecialBola) {
    const especialSelecionado = TIPOS_ESPECIAIS_BOLA[estado.tipoEspecialBola];
    alvo = especialSelecionado?.label ?? "Evento do saque";
    instrucao = "Clique na bolinha real.";
  } else if (estado.etapaCalibracao === "quadra") {
    avancarIndiceQuadraAtePendente();
    const atual = PONTOS_QUADRA_CALIBRACAO[estado.indicePontoQuadra];
    alvo = atual ? atual.label : "Quadra completa";
    instrucao = "Clique no ponto visivel ou pule se estiver fora do frame.";
  } else if (estado.etapaCalibracao === "quadra_centros_base") {
    avancarIndiceCentroBaseAtePendente();
    const atual = PONTOS_CENTRO_BASE_CALIBRACAO[estado.indiceCentroBaseCalibracao];
    alvo = atual ? atual.label : "Projetando malha oficial";
    instrucao = estado.indiceCentroBaseCalibracao === 0
      ? "Clique no meio visivel da primeira linha de base."
      : "Clique no meio da outra linha de base; a linha tracejada mede o eixo central da quadra.";
  } else if (estado.etapaCalibracao === "jogadores") {
    const total = estado.calibracao.players.player_count;
    alvo = estado.indiceJogadorCalibracao === 0 ? "Clique no Jogador 1" : "Clique no Jogador 2";
    instrucao = total < 2
      ? "Marque o centro do corpo."
      : "Marque o centro do corpo dos atletas.";
  } else {
    const proximaMarca = proximaEtapaBolaRastreio();
    alvo = proximaMarca?.label ?? "Bolinha";
    instrucao = marcasBola > 0
      ? `${marcasBola} ponto(s)-guia da bola. O rastro final sera detectado ao renderizar.`
      : "Rastro automatico no processamento. Marque pontos apenas se quiser guiar.";
  }

  const validacao = validarCalibracao();
  elementos.alvoCalibracao.textContent = alvo;
  elementos.instrucaoCalibracao.textContent = instrucao;
  const statusSaque = [contatoSaque, projecaoContatoSaque, primeiroToqueSaque].filter(Boolean).length;
  const statusSaqueTexto = saqueObrigatorio ? `Saque ${statusSaque}/3` : `Saque opcional ${statusSaque}/3`;
  const statusCentroBase = complementoQuadraPendente() ? ` | Centros ${centrosBaseMarcados}/${PONTOS_CENTRO_BASE_CALIBRACAO.length}` : "";
  const statusBolaTexto = marcasBola > 0 ? `Bola ${marcasBola} guia(s)` : "Bola auto";
  elementos.progressoCalibracao.textContent = `${modoLabel} | Quadra ${pontosResolvidos}/${PONTOS_QUADRA_CALIBRACAO.length}${statusCentroBase} | Jogadores ${jogadoresCalibrados() ? "ok" : "pend."} | ${statusBolaTexto} | ${statusSaqueTexto} | ${validacao.mensagem}`;
  elementos.botaoPularPontoQuadra.disabled = estado.etapaCalibracao !== "quadra" || estado.indicePontoQuadra >= PONTOS_QUADRA_CALIBRACAO.length;
  elementos.botaoContatoRaqueteCalibracao.disabled = !saqueLiberado;
  elementos.botaoProjecaoContatoCalibracao.disabled = !saqueLiberado;
  elementos.botaoPrimeiroToqueCalibracao.disabled = !saqueLiberado;
  elementos.botaoAutoRastroBola.disabled = estado.autoRastroBolaEmAndamento || (!podeDetectarRastroBolaAutomatico() && !estado.autoRastroBolaAguardandoInicio);
  elementos.botaoAutoRastroBola.textContent = estado.autoRastroBolaEmAndamento
    ? "Detectando..."
    : (estado.autoRastroBolaAguardandoInicio ? "Clique na bolinha" : (marcasAutoBola > 0 ? `Guias auto (${marcasAutoBola})` : "Guias opcionais"));
  elementos.botaoAutoRastroBola.classList.toggle("ativo", estado.autoRastroBolaAguardandoInicio);
  elementos.botaoAutoRastroBola.classList.toggle("preenchido", marcasAutoBola > 0);
  elementos.botaoContatoRaqueteCalibracao.classList.toggle("ativo", estado.tipoEspecialBola === "serve_contact");
  elementos.botaoProjecaoContatoCalibracao.classList.toggle("ativo", estado.tipoEspecialBola === "serve_contact_ground");
  elementos.botaoPrimeiroToqueCalibracao.classList.toggle("ativo", estado.tipoEspecialBola === "serve_court_bounce");
  elementos.botaoContatoRaqueteCalibracao.classList.toggle("preenchido", Boolean(contatoSaque));
  elementos.botaoProjecaoContatoCalibracao.classList.toggle("preenchido", Boolean(projecaoContatoSaque));
  elementos.botaoPrimeiroToqueCalibracao.classList.toggle("preenchido", Boolean(primeiroToqueSaque));
  elementos.botaoContatoRaqueteCalibracao.classList.toggle("faltante", saqueObrigatorio && saqueLiberado && !contatoSaque);
  elementos.botaoProjecaoContatoCalibracao.classList.toggle("faltante", saqueObrigatorio && saqueLiberado && !projecaoContatoSaque);
  elementos.botaoPrimeiroToqueCalibracao.classList.toggle("faltante", saqueObrigatorio && saqueLiberado && !primeiroToqueSaque);
  atualizarResultadoVelocidadeSaque();
  elementos.botaoFinalizarCalibracao.disabled = !validacao.ok;
}

function desenharCanvasCalibracao() {
  const canvas = elementos.canvasCalibracao;
  const ctx = canvas.getContext("2d");
  const video = elementos.videoCalibracao;
  atualizarEscalaVisualCanvasCalibracao();
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const podeUsarVideoLocal = video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0 && !estado.carregandoFrameCalibracao;
  const usarFrameServidor = estado.frameServidorImagem && (!podeUsarVideoLocal || estado.calibracaoServidorId);

  if (usarFrameServidor) {
    const imagem = estado.frameServidorImagem;
    ctx.drawImage(imagem, 0, 0, Math.max(imagem.naturalWidth, 1), Math.max(imagem.naturalHeight, 1), 0, 0, canvas.width, canvas.height);
  } else if (podeUsarVideoLocal) {
    try {
      ctx.drawImage(video, 0, 0, Math.max(video.videoWidth, 1), Math.max(video.videoHeight, 1), 0, 0, canvas.width, canvas.height);
    } catch (erro) {
      ctx.fillStyle = "#07131d";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      elementos.progressoCalibracao.textContent = "Nao consegui desenhar o frame deste video no navegador. Tente converter para MP4 H.264 ou selecionar outro arquivo.";
      console.error(erro);
    }
  } else {
    ctx.fillStyle = "#0a1721";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    for (let x = 0; x < canvas.width; x += 48) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 48) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
  }

  atualizarOverlayCalibracao();
}

function criarElementoSvgCalibracao(nome) {
  return document.createElementNS("http://www.w3.org/2000/svg", nome);
}

function escalaCanvasPorPixelVisual() {
  const medidas = medidasVisuaisCanvasCalibracao();
  const canvas = elementos.canvasCalibracao;
  if (!medidas || !canvas || canvas.width <= 0 || canvas.height <= 0) {
    return 1;
  }
  const escalaX = (medidas.larguraBase / canvas.width) * medidas.escala;
  const escalaY = (medidas.alturaBase / canvas.height) * medidas.escala;
  return 1 / Math.max((escalaX + escalaY) / 2, 1e-6);
}

function atualizarOverlayCalibracao() {
  let overlay = elementos.overlayCalibracao;
  const canvas = elementos.canvasCalibracao;
  if (!overlay && canvas?.parentElement) {
    overlay = document.createElement("div");
    overlay.id = "overlay-calibracao";
    overlay.className = "overlay-calibracao";
    overlay.setAttribute("aria-hidden", "true");
    canvas.insertAdjacentElement("afterend", overlay);
    elementos.overlayCalibracao = overlay;
  }
  if (!overlay || !canvas || canvas.width <= 0 || canvas.height <= 0) {
    return;
  }
  atualizarEscalaVisualCanvasCalibracao();

  overlay.replaceChildren();
  const svg = criarElementoSvgCalibracao("svg");
  svg.setAttribute("viewBox", `0 0 ${canvas.width} ${canvas.height}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.classList.add("overlay-calibracao-svg");
  overlay.appendChild(svg);

  desenharLinhasCalibracao(svg);
  desenharGuiaCentrosBase(svg);
  desenharGuiaProjecaoSaque(svg);
  desenharPontosCalibracao(svg);
}

function desenharLinhasCalibracao(svg) {
  const pontos = estado.calibracao?.court_points ?? {};
  const unidadeVisual = escalaCanvasPorPixelVisual();
  desenharLateraisInternasOficiais(svg, pontos, unidadeVisual);
  const pares = [
    ["sup_esquerda", "sup_direita"],
    ["inf_esquerda", "inf_direita"],
    ["rede_esquerda", "rede_direita"],
    ["servico_sup_esquerda", "servico_sup_direita"],
    ["servico_inf_esquerda", "servico_inf_direita"],
    ["centro_sup", "centro_inf"],
    ["sup_esquerda", "inf_esquerda"],
    ["sup_direita", "inf_direita"],
  ];
  pares.forEach(([a, b]) => {
    if (!pontos[a] || !pontos[b]) {
      return;
    }
    const inicio = pontoParaCanvasCalibracao(pontos[a]);
    const fim = pontoParaCanvasCalibracao(pontos[b]);
    const linha = criarElementoSvgCalibracao("line");
    linha.setAttribute("x1", String(inicio.x));
    linha.setAttribute("y1", String(inicio.y));
    linha.setAttribute("x2", String(fim.x));
    linha.setAttribute("y2", String(fim.y));
    linha.setAttribute("stroke", "rgba(180, 255, 103, 0.82)");
    linha.setAttribute("stroke-width", String(2 * unidadeVisual));
    linha.setAttribute("stroke-linecap", "round");
    svg.appendChild(linha);
  });
}

function linhaPorDoisPontos(p1, p2) {
  return {
    a: p1.y - p2.y,
    b: p2.x - p1.x,
    c: p1.x * p2.y - p2.x * p1.y,
  };
}

function segmentoLinhaNoCanvas(p1, p2) {
  const canvas = elementos.canvasCalibracao;
  const largura = Number(canvas?.width || 0);
  const altura = Number(canvas?.height || 0);
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  if (!largura || !altura || Math.hypot(dx, dy) < 1e-6) {
    return null;
  }

  const candidatos = [];
  const adicionar = (x, y) => {
    if (
      Number.isFinite(x)
      && Number.isFinite(y)
      && x >= -1
      && x <= largura + 1
      && y >= -1
      && y <= altura + 1
      && !candidatos.some((ponto) => Math.hypot(ponto.x - x, ponto.y - y) < 1)
    ) {
      candidatos.push({ x: Math.max(0, Math.min(largura, x)), y: Math.max(0, Math.min(altura, y)) });
    }
  };

  if (Math.abs(dx) > 1e-6) {
    let t = (0 - p1.x) / dx;
    adicionar(0, p1.y + (dy * t));
    t = (largura - p1.x) / dx;
    adicionar(largura, p1.y + (dy * t));
  }
  if (Math.abs(dy) > 1e-6) {
    let t = (0 - p1.y) / dy;
    adicionar(p1.x + (dx * t), 0);
    t = (altura - p1.y) / dy;
    adicionar(p1.x + (dx * t), altura);
  }

  if (candidatos.length < 2) {
    return null;
  }

  let melhor = { inicio: candidatos[0], fim: candidatos[1], distancia: -1 };
  for (let i = 0; i < candidatos.length; i += 1) {
    for (let j = i + 1; j < candidatos.length; j += 1) {
      const distancia = Math.hypot(candidatos[i].x - candidatos[j].x, candidatos[i].y - candidatos[j].y);
      if (distancia > melhor.distancia) {
        melhor = { inicio: candidatos[i], fim: candidatos[j], distancia };
      }
    }
  }
  return { inicio: melhor.inicio, fim: melhor.fim };
}

function intersecaoLinhas(l1, l2) {
  const det = l1.a * l2.b - l2.a * l1.b;
  if (Math.abs(det) < 1e-6) {
    return null;
  }
  return {
    x: (l1.b * l2.c - l2.b * l1.c) / det,
    y: (l1.c * l2.a - l2.c * l1.a) / det,
  };
}

function desenharLinhaSvg(svg, inicio, fim, cor, largura, opacidade = 1, dash = "") {
  const linha = criarElementoSvgCalibracao("line");
  linha.setAttribute("x1", String(inicio.x));
  linha.setAttribute("y1", String(inicio.y));
  linha.setAttribute("x2", String(fim.x));
  linha.setAttribute("y2", String(fim.y));
  linha.setAttribute("stroke", cor);
  linha.setAttribute("stroke-width", String(largura));
  linha.setAttribute("stroke-linecap", "round");
  linha.setAttribute("opacity", String(opacidade));
  if (dash) {
    linha.setAttribute("stroke-dasharray", dash);
  }
  svg.appendChild(linha);
}

function desenharLateralInternaProjetada(svg, pontos, superiorId, inferiorId, unidadeVisual) {
  const obrigatorios = ["sup_esquerda", "sup_direita", "inf_esquerda", "inf_direita", superiorId, inferiorId];
  if (!obrigatorios.every((id) => pontos[id])) {
    return;
  }
  const baseSuperior = linhaPorDoisPontos(pontoParaCanvasCalibracao(pontos.sup_esquerda), pontoParaCanvasCalibracao(pontos.sup_direita));
  const baseInferior = linhaPorDoisPontos(pontoParaCanvasCalibracao(pontos.inf_esquerda), pontoParaCanvasCalibracao(pontos.inf_direita));
  const lateralInterna = linhaPorDoisPontos(pontoParaCanvasCalibracao(pontos[superiorId]), pontoParaCanvasCalibracao(pontos[inferiorId]));
  const topo = intersecaoLinhas(baseSuperior, lateralInterna);
  const base = intersecaoLinhas(baseInferior, lateralInterna);
  if (!topo || !base) {
    desenharLinhaSvg(
      svg,
      pontoParaCanvasCalibracao(pontos[superiorId]),
      pontoParaCanvasCalibracao(pontos[inferiorId]),
      "rgba(180, 255, 103, 0.82)",
      2 * unidadeVisual,
    );
    return;
  }
  desenharLinhaSvg(svg, topo, base, "rgba(180, 255, 103, 0.64)", 2 * unidadeVisual);
}

function desenharLateraisInternasOficiais(svg, pontos, unidadeVisual) {
  desenharLateralInternaProjetada(svg, pontos, "servico_sup_esquerda", "servico_inf_esquerda", unidadeVisual);
  desenharLateralInternaProjetada(svg, pontos, "servico_sup_direita", "servico_inf_direita", unidadeVisual);
}

function guiaCentrosBaseAtiva() {
  return estado.etapaCalibracao === "quadra_centros_base"
    && Boolean(
      (pontoQuadraManualPorId("centro_sup") && pontoQuadraManualPorId("centro_inf"))
      || pontoAuxiliarQuadraPorId("base_sup_centro")
      || pontoAuxiliarQuadraPorId("base_inf_centro"),
    );
}

function desenharGuiaCentrosBase(svg) {
  if (!guiaCentrosBaseAtiva()) {
    return;
  }
  const unidadeVisual = escalaCanvasPorPixelVisual();
  const tSuperior = pontoQuadraManualPorId("centro_sup");
  const tInferior = pontoQuadraManualPorId("centro_inf");
  if (tSuperior && tInferior) {
    const eixo = segmentoLinhaNoCanvas(
      pontoParaCanvasCalibracao(tSuperior),
      pontoParaCanvasCalibracao(tInferior),
    );
    if (eixo) {
      desenharLinhaSvg(
        svg,
        eixo.inicio,
        eixo.fim,
        "rgba(34, 139, 120, 0.5)",
        1.4 * unidadeVisual,
        1,
        `${8 * unidadeVisual} ${8 * unidadeVisual}`,
      );
    }
  }
  const supCentro = pontoAuxiliarQuadraPorId("base_sup_centro");
  const infCentro = pontoAuxiliarQuadraPorId("base_inf_centro");
  const cursor = estado.ultimoPonteiroCalibracao;
  const inicio = supCentro || infCentro;
  const destino = supCentro && infCentro
    ? infCentro
    : (cursor && Number.isFinite(cursor.x) && Number.isFinite(cursor.y) ? cursor : null);
  if (!inicio || !destino) {
    return;
  }
  const pontoInicio = pontoParaCanvasCalibracao(inicio);
  const pontoFim = pontoParaCanvasCalibracao(destino);
  desenharLinhaSvg(
    svg,
    pontoInicio,
    pontoFim,
    "rgba(34, 139, 120, 0.78)",
    1.8 * unidadeVisual,
    1,
    `${7 * unidadeVisual} ${7 * unidadeVisual}`,
  );
}

function guiaProjecaoSaqueAtiva() {
  return Boolean(marcaBolaPorRole("serve_contact"))
    && (estado.tipoEspecialBola === "serve_contact_ground" || Boolean(marcaBolaPorRole("serve_contact_ground")));
}

function desenharGuiaProjecaoSaque(svg) {
  if (!guiaProjecaoSaqueAtiva()) {
    return;
  }
  const contato = marcaBolaPorRole("serve_contact");
  const projecao = marcaBolaPorRole("serve_contact_ground");
  const cursor = estado.ultimoPonteiroCalibracao;
  const destino = estado.tipoEspecialBola === "serve_contact_ground" && cursor && Number.isFinite(cursor.x) && Number.isFinite(cursor.y)
    ? cursor
    : projecao;
  if (!destino || !Number.isFinite(destino.x) || !Number.isFinite(destino.y)) {
    return;
  }

  const inicio = pontoParaCanvasCalibracao(contato);
  const fim = pontoParaCanvasCalibracao(destino);
  if (!inicio.visivel && !fim.visivel) {
    return;
  }

  const unidadeVisual = escalaCanvasPorPixelVisual();
  const linha = criarElementoSvgCalibracao("line");
  linha.setAttribute("x1", String(inicio.x));
  linha.setAttribute("y1", String(inicio.y));
  linha.setAttribute("x2", String(fim.x));
  linha.setAttribute("y2", String(fim.y));
  linha.setAttribute("stroke", "rgba(255, 236, 173, 0.72)");
  linha.setAttribute("stroke-width", String(1.6 * unidadeVisual));
  linha.setAttribute("stroke-linecap", "round");
  linha.setAttribute("stroke-dasharray", `${6 * unidadeVisual} ${6 * unidadeVisual}`);
  svg.appendChild(linha);
}

function desenharPontosCalibracao(svg) {
  const pontos = estado.calibracao?.court_points ?? {};
  Object.entries(pontos).forEach(([id, ponto]) => {
    desenharMarcadorCalibracao(svg, ponto, "#b8ff67", id);
  });

  const players = estado.calibracao?.players ?? {};
  if (players.p1) {
    desenharMarcadorCalibracao(svg, players.p1, "#63f5c2", "Jogador 1");
  }
  if (players.p2) {
    desenharMarcadorCalibracao(svg, players.p2, "#ff719f", "Jogador 2");
  }

  Object.entries(estado.calibracao?.court_aux_points ?? {}).forEach(([id, ponto]) => {
    desenharMarcadorCalibracao(svg, ponto, "#55b8a7", id);
  });

  (estado.calibracao?.ball_marks ?? []).forEach((ponto, indice) => {
    const especial = TIPOS_ESPECIAIS_BOLA[ponto.role];
    desenharMarcadorCalibracao(svg, ponto, especial?.cor ?? corMarcacaoBolaCalibracao(ponto), `Bola ${indice + 1}`);
  });
}

function corMarcacaoBolaCalibracao(ponto) {
  if (ponto?.source !== "auto_track") {
    return "#ffe85d";
  }
  const confianca = Number(ponto.confidence ?? 0);
  if (confianca >= 0.78) {
    return "#85f4bd";
  }
  if (confianca >= 0.6) {
    return "#ffe85d";
  }
  return "#ffb45d";
}

function desenharMarcadorCalibracao(svg, ponto, cor, label) {
  const { x, y, visivel } = pontoParaCanvasCalibracao(ponto);
  if (!visivel) {
    return;
  }
  const unidadeVisual = escalaCanvasPorPixelVisual();
  const raioPrincipal = 6 * unidadeVisual;
  const raioExterno = 11 * unidadeVisual;
  const strokePrincipal = 2.4 * unidadeVisual;
  const strokeExterno = 1.4 * unidadeVisual;

  const anel = criarElementoSvgCalibracao("circle");
  anel.setAttribute("cx", String(x));
  anel.setAttribute("cy", String(y));
  anel.setAttribute("r", String(raioExterno));
  anel.setAttribute("fill", "none");
  anel.setAttribute("stroke", "rgba(255,255,255,0.76)");
  anel.setAttribute("stroke-width", String(strokeExterno));
  svg.appendChild(anel);

  const centro = criarElementoSvgCalibracao("circle");
  centro.setAttribute("cx", String(x));
  centro.setAttribute("cy", String(y));
  centro.setAttribute("r", String(raioPrincipal));
  centro.setAttribute("fill", cor);
  centro.setAttribute("stroke", "rgba(0,0,0,0.86)");
  centro.setAttribute("stroke-width", String(strokePrincipal));
  centro.setAttribute("aria-label", label);
  svg.appendChild(centro);
}

function pontoParaCanvasCalibracao(ponto) {
  const canvas = elementos.canvasCalibracao;
  if (!canvas || canvas.width <= 0 || canvas.height <= 0) {
    return { x: 0, y: 0, visivel: false };
  }
  const x = ponto.x * canvas.width;
  const y = ponto.y * canvas.height;
  return {
    x,
    y,
    visivel: x >= -24 && x <= canvas.width + 24 && y >= -24 && y <= canvas.height + 24,
  };
}

async function enviarUpload(evento) {
  evento.preventDefault();
  const arquivo = estado.arquivoUploadSelecionado ?? elementos.campoVideo.files?.[0];
  if (!arquivo) {
    elementos.statusUpload.textContent = "Selecione um vídeo antes de enviar.";
    return;
  }

  const validacao = validarCalibracao();
  if (!estado.calibracaoPronta || !validacao.ok) {
    elementos.statusUpload.textContent = `Conclua a calibracao antes de enviar. ${validacao.mensagem}`;
    elementos.modalCalibracao.classList.remove("oculto");
    elementos.modalCalibracao.setAttribute("aria-hidden", "false");
    atualizarInterfaceCalibracao();
    return;
  }

  const corpo = new FormData();
  if (estado.calibracaoServidorId) {
    corpo.append("calibracao_id", estado.calibracaoServidorId);
  } else {
    corpo.append("arquivo", arquivo);
  }
  corpo.append("calibracao", JSON.stringify(calibracaoParaAnaliseFinal()));

  pararPollingJob();
  desativarVideoReal();
  elementos.statusUpload.textContent = "Enviando arquivo...";
  elementos.botaoCancelarJob.classList.add("oculto");
  const resposta = await fetch("/api/videos/upload", {
    method: "POST",
    body: corpo,
  });
  const dados = await resposta.json();
  if (!resposta.ok) {
    throw new Error(dados.detail ?? "Falha ao processar upload.");
  }

  if (!dados.job_id) {
    throw new Error("A API nao retornou um job de processamento.");
  }

  estado.jobAtual = dados.job_id;
  elementos.botaoCancelarJob.classList.remove("oculto");
  elementos.statusUpload.textContent = `${dados.mensagem} Job: ${dados.job_id.slice(0, 8)}.`;
  acompanharJobVideo(dados.job_id);
}

function acompanharJobVideo(jobId) {
  pararPollingJob();
  estado.falhasConsultaJob = 0;
  const consultar = () => {
    if (estado.pollingJobEmAndamento || estado.jobAtual !== jobId) {
      return;
    }
    estado.pollingJobEmAndamento = true;
    consultarJobVideo(jobId)
      .catch((erro) => tratarFalhaConsultaJob(jobId, erro))
      .finally(() => {
        if (estado.jobAtual === jobId) {
          estado.pollingJobEmAndamento = false;
        }
      });
  };
  estado.pollingJob = window.setInterval(consultar, 1800);
  consultar();
}

async function consultarJobVideo(jobId) {
  const job = await buscarJobVideo(jobId, { resumo: true });
  if (estado.jobAtual !== jobId) {
    return;
  }
  estado.falhasConsultaJob = 0;

  const progresso = Number(job.progresso ?? 0);
  elementos.statusUpload.textContent = `${job.mensagem ?? "Processando video..."} (${formatarNumero(progresso, "%")})`;

  if (job.status === "concluido") {
    pararPollingJob();
    elementos.botaoCancelarJob.classList.add("oculto");
    aplicarAnaliseReal(job);
    estado.jobAtual = null;
    if (!job.analise) {
      carregarAnaliseCompletaJob(jobId);
    }
    return;
  }

  if (job.status === "falhou" || job.status === "cancelado") {
    pararPollingJob();
    elementos.botaoCancelarJob.classList.add("oculto");
    elementos.statusUpload.textContent = job.mensagem ?? "Processamento encerrado.";
  }
}

async function carregarAnaliseCompletaJob(jobId) {
  if (estado.carregandoAnaliseCompletaJob === jobId) {
    return;
  }
  estado.carregandoAnaliseCompletaJob = jobId;
  try {
    const jobCompleto = await buscarJobVideo(jobId, { resumo: false });
    if (estado.jobAtual && estado.jobAtual !== jobId) {
      return;
    }
    aplicarAnaliseReal(jobCompleto, { atualizarVideo: false });
  } catch (erro) {
    if (!estado.jobAtual) {
      elementos.statusUpload.textContent = "Video pronto. Nao foi possivel carregar a analise detalhada agora.";
    }
    console.error(erro);
  } finally {
    if (estado.carregandoAnaliseCompletaJob === jobId) {
      estado.carregandoAnaliseCompletaJob = null;
    }
  }
}

async function buscarJobVideo(jobId, { resumo = false } = {}) {
  const sufixo = resumo ? "?resumo=1" : "";
  const resposta = await fetch(`/api/videos/jobs/${jobId}${sufixo}`);
  let job = {};
  try {
    job = await resposta.json();
  } catch (erro) {
    if (resposta.ok) {
      throw erro;
    }
  }
  if (!resposta.ok) {
    throw new Error(job.detail ?? "Job nao encontrado.");
  }
  return job;
}

function tratarFalhaConsultaJob(jobId, erro) {
  if (estado.jobAtual !== jobId) {
    return;
  }
  estado.falhasConsultaJob += 1;
  const detalhe = erro?.message ? ` ${erro.message}` : "";
  if (estado.falhasConsultaJob < 3) {
    elementos.statusUpload.textContent = "Reconectando ao processamento do video...";
    return;
  }
  elementos.statusUpload.textContent = `Falha ao consultar o processamento do video.${detalhe}`;
  if (/nao encontrado|não encontrado|404/i.test(detalhe)) {
    pararPollingJob();
    elementos.botaoCancelarJob.classList.add("oculto");
  }
  console.error(erro);
}

function aplicarAnaliseReal(job, { atualizarVideo = true } = {}) {
  estado.metadataAnaliseReal = job.metadata ?? null;
  document.body.classList.add("tem-analise");
  if (job.url_video_analisado || job.analise) {
    estado.modoVideoReal = true;
  }
  if (job.analise) {
    estado.dados = job.analise;
    estado.indiceQuadro = 0;
    if (estado.temporizador) {
      window.clearInterval(estado.temporizador);
      estado.temporizador = null;
    }
    renderizarPainel();
  }

  if (atualizarVideo && job.url_video_analisado) {
    elementos.videoUpload.src = `${job.url_video_analisado}?v=${Date.now()}`;
    elementos.videoUpload.load();
    elementos.videoUploadCard.classList.remove("oculto");
    elementos.videoWrap.classList.add("oculto");
  }

  const saqueInfo = job.metadata?.velocidade_saque;
  const saque = saqueInfo?.velocidade_kmh
    ? ` Saque: ${formatarNumero(saqueInfo.velocidade_kmh, " km/h")}.`
    : "";
  elementos.statusUpload.textContent = `Analise pronta.${saque}`;
}

function desativarVideoReal() {
  estado.modoVideoReal = false;
  estado.metadataAnaliseReal = null;
  document.body.classList.remove("tem-analise");
  elementos.videoUpload.pause();
  elementos.videoUpload.removeAttribute("src");
  elementos.videoUpload.load();
  elementos.videoUploadCard.classList.add("oculto");
  elementos.videoWrap.classList.remove("oculto");
}

function pararPollingJob() {
  if (estado.pollingJob) {
    window.clearInterval(estado.pollingJob);
    estado.pollingJob = null;
  }
  estado.pollingJobEmAndamento = false;
  estado.falhasConsultaJob = 0;
}

async function interpretarAnotacao(evento) {
  evento.preventDefault();
  const anotacao = elementos.campoAnotacao.value.trim();
  if (!anotacao) {
    elementos.statusAnotacao.textContent = "Escreva uma anotação para interpretar.";
    return;
  }

  elementos.statusAnotacao.textContent = "Processando anotação...";
  const resposta = await fetch("/api/inteligencia/analisar-anotacao", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ anotacao }),
  });
  const relatorio = await resposta.json();
  elementos.textoRelatorio.textContent = relatorio.resumo;
  elementos.listaAchados.innerHTML = relatorio.achados_principais
    .map((achado) => `<li>${achado}</li>`)
    .join("");
  elementos.statusAnotacao.textContent = `Prioridade clínica: ${formatarPercentual(relatorio.prioridade_clinica)}. Recarregue a demonstração para aplicar a anotação ao painel completo.`;
}

elementos.botaoDemo.addEventListener("click", () => {
  carregarPainel().catch((erro) => {
    console.error(erro);
  });
});

elementos.botaoPausar.addEventListener("click", alternarAnimacao);
elementos.videoUpload.addEventListener("timeupdate", () => {
  if (!estado.modoVideoReal || !estado.dados?.quadros?.length || !elementos.videoUpload.duration) {
    return;
  }
  const proporcao = elementos.videoUpload.currentTime / elementos.videoUpload.duration;
  const novoIndice = Math.min(
    estado.dados.quadros.length - 1,
    Math.max(0, Math.floor(proporcao * estado.dados.quadros.length)),
  );
  if (novoIndice !== estado.indiceQuadro) {
    estado.indiceQuadro = novoIndice;
    renderizarDinamica();
  }
});
elementos.videoUpload.addEventListener("loadedmetadata", () => {
  if (!estado.modoVideoReal) {
    return;
  }
  elementos.statusUpload.textContent = `Video pronto (${formatarNumero(elementos.videoUpload.duration, " s")}).`;
});
elementos.videoUpload.addEventListener("error", () => {
  if (!estado.modoVideoReal) {
    return;
  }
  elementos.statusUpload.textContent = "O video analisado foi gerado, mas o navegador nao conseguiu decodificar o arquivo. Tente reenviar para gerar em H.264.";
});
elementos.botaoCancelarJob.addEventListener("click", () => {
  const jobId = estado.jobAtual;
  if (!jobId) {
    return;
  }
  elementos.statusUpload.textContent = "Solicitando finalizacao do processamento...";
  fetch(`/api/videos/jobs/${jobId}/finalizar`, { method: "POST" }).catch((erro) => {
    elementos.statusUpload.textContent = "Falha ao finalizar o processamento.";
    console.error(erro);
  });
});
elementos.campoVideo.addEventListener("click", () => {
  elementos.campoVideo.value = "";
  estado.calibracaoPronta = false;
});
elementos.campoVideo.addEventListener("change", aoSelecionarArquivoVideo);
elementos.videoCalibracao.addEventListener("loadedmetadata", prepararVideoCalibracao);
elementos.videoCalibracao.addEventListener("loadeddata", solicitarFrameCalibracao);
elementos.videoCalibracao.addEventListener("canplay", solicitarFrameCalibracao);
elementos.videoCalibracao.addEventListener("seeked", solicitarFrameCalibracao);
elementos.videoCalibracao.addEventListener("error", () => {
  estado.carregandoFrameCalibracao = false;
  desenharCanvasCalibracao();
  elementos.statusUpload.textContent = "O navegador nao conseguiu abrir os frames deste video para calibracao. Converta para MP4 H.264 e tente novamente.";
});
elementos.canvasCalibracao.addEventListener("click", registrarCliqueCalibracao);
elementos.canvasCalibracao.addEventListener("pointerdown", iniciarPanCalibracao);
elementos.canvasCalibracao.addEventListener("pointermove", moverPanCalibracao);
elementos.canvasCalibracao.addEventListener("pointerup", finalizarPanCalibracao);
elementos.canvasCalibracao.addEventListener("pointercancel", finalizarPanCalibracao);
elementos.canvasCalibracao.addEventListener("wheel", (evento) => {
  evento.preventDefault();
  const ancora = pontoInteracaoCanvas(evento);
  estado.ultimoPonteiroCalibracao = ancora;
  variarZoomCalibracao(evento.deltaY > 0 ? -0.2 : 0.2, ancora);
}, { passive: false });
elementos.rangeTempoCalibracao.addEventListener("input", (evento) => {
  irParaTempoCalibracao(evento.target.value);
});
elementos.rangeZoomCalibracao.addEventListener("input", (evento) => {
  ajustarZoomCalibracao(evento.target.value, true, estado.ultimoPonteiroCalibracao);
});
elementos.botaoZoomMenosCalibracao.addEventListener("click", () => variarZoomCalibracao(-0.4, estado.ultimoPonteiroCalibracao));
elementos.botaoZoomMaisCalibracao.addEventListener("click", () => variarZoomCalibracao(0.4, estado.ultimoPonteiroCalibracao));
elementos.botaoResetZoomCalibracao.addEventListener("click", () => ajustarZoomCalibracao(1));
window.addEventListener("resize", () => {
  atualizarEscalaVisualCanvasCalibracao();
  atualizarOverlayCalibracao();
});
window.addEventListener("keydown", (evento) => {
  if (!modalCalibracaoAberto() || evento.altKey || evento.metaKey) {
    return;
  }
  if (evento.key !== "ArrowLeft" && evento.key !== "ArrowRight") {
    return;
  }
  evento.preventDefault();
  const passo = evento.ctrlKey ? 0.1 : 0.01;
  ajustarTempoCalibracaoPorTecla(evento.key === "ArrowRight" ? passo : -passo);
});
garantirSwitchModoCalibracao();
elementos.botaoContatoRaqueteCalibracao.addEventListener("click", () => selecionarTipoEspecialBola("serve_contact"));
elementos.botaoProjecaoContatoCalibracao.addEventListener("click", () => selecionarTipoEspecialBola("serve_contact_ground"));
elementos.botaoPrimeiroToqueCalibracao.addEventListener("click", () => selecionarTipoEspecialBola("serve_court_bounce"));
elementos.botaoAutoRastroBola.addEventListener("click", () => {
  iniciarFluxoAutoRastroBola();
});
elementos.botaoCalcularVelocidadeSaque.addEventListener("click", () => {
  calcularVelocidadeSaquePreview().catch((erro) => {
    estado.previewVelocidadeSaque = null;
    estado.previewVelocidadeSaqueErro = erro.message ?? "Falha ao calcular velocidade do saque.";
    atualizarResultadoVelocidadeSaque();
    console.error(erro);
  });
});
elementos.botaoDownloadVideoSaque.addEventListener("click", () => {
  baixarVideoSaqueRenderizado().catch((erro) => {
    console.error(erro);
  });
});
elementos.qtdJogadoresCalibracao.addEventListener("change", () => {
  if (!estado.calibracao) {
    return;
  }
  estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
  if (Number(elementos.qtdJogadoresCalibracao.value) < 2) {
    estado.calibracao.players.p2 = null;
  }
  desenharCanvasCalibracao();
  atualizarInterfaceCalibracao();
});
elementos.botaoFecharCalibracao.addEventListener("click", fecharModalCalibracao);
elementos.botaoVoltarCalibracao.addEventListener("click", voltarEtapaCalibracao);
elementos.botaoDesfazerCalibracao.addEventListener("click", desfazerPontoCalibracao);
elementos.botaoPularPontoQuadra.addEventListener("click", pularPontoQuadraCalibracao);
elementos.botaoProximoCalibracao.addEventListener("click", avancarEtapaCalibracao);
elementos.botaoFinalizarCalibracao.addEventListener("click", finalizarCalibracao);
elementos.formUpload.addEventListener("submit", (evento) => {
  enviarUpload(evento).catch((erro) => {
    elementos.statusUpload.textContent = "Falha ao enviar o arquivo.";
    console.error(erro);
  });
});
elementos.formAnotacao.addEventListener("submit", (evento) => {
  interpretarAnotacao(evento).catch((erro) => {
    elementos.statusAnotacao.textContent = "Falha ao interpretar a anotação.";
    console.error(erro);
  });
});

carregarArquitetura().catch((erro) => {
  console.error("Falha ao carregar arquitetura:", erro);
});

