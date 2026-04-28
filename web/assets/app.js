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
  resultadoVelocidadeSaque: document.querySelector("#resultado-velocidade-saque"),
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
  arquivoUploadSelecionado: null,
  objetoUrlCalibracao: null,
  objetoUrlFrameServidor: null,
  calibracaoServidorId: null,
  frameServidorImagem: null,
  frameServidorSeq: 0,
  frameServidorTimer: null,
  frameServidorAbortController: null,
  calibracao: null,
  calibracaoPronta: false,
  etapaCalibracao: "quadra",
  indicePontoQuadra: 0,
  indiceJogadorCalibracao: 0,
  zoomCalibracao: 1,
  panCalibracao: { x: 0.5, y: 0.5 },
  arrastandoCalibracao: false,
  dragCalibracao: null,
  suprimirCliqueCalibracao: false,
  carregandoFrameCalibracao: false,
  tipoEspecialBola: null,
  previewVelocidadeSaque: null,
  previewVelocidadeSaqueErro: "",
};

const PONTOS_QUADRA_CALIBRACAO = [
  { id: "sup_esquerda", label: "Linha de base superior - canto esquerdo" },
  { id: "sup_direita", label: "Linha de base superior - canto direito" },
  { id: "inf_esquerda", label: "Linha de base inferior - canto esquerdo" },
  { id: "inf_direita", label: "Linha de base inferior - canto direito" },
  { id: "rede_esquerda", label: "Rede - base inferior na linha externa esquerda" },
  { id: "rede_direita", label: "Rede - base inferior na linha externa direita" },
  { id: "servico_sup_esquerda", label: "Linha interna superior esquerda" },
  { id: "servico_sup_direita", label: "Linha interna superior direita" },
  { id: "servico_inf_esquerda", label: "Linha interna inferior esquerda" },
  { id: "servico_inf_direita", label: "Linha interna inferior direita" },
  { id: "centro_sup", label: "T superior / centro da zona de saque" },
  { id: "centro_inf", label: "T inferior / centro da zona de saque" },
];

const MIN_MARCACOES_BOLA = 12;
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
          `Janela overlay: ${formatarNumero(saqueInfo.overlay_duracao_s ?? 0.7, " s")}.`,
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
  estado.frameServidorSeq += 1;
  estado.carregandoFrameCalibracao = true;
  estado.etapaCalibracao = "quadra";
  estado.indicePontoQuadra = 0;
  estado.indiceJogadorCalibracao = 0;
  estado.zoomCalibracao = 1;
  estado.panCalibracao = { x: 0.5, y: 0.5 };
  estado.tipoEspecialBola = null;
  estado.previewVelocidadeSaque = null;
  estado.previewVelocidadeSaqueErro = "";
  elementos.rangeZoomCalibracao.value = "1";
  elementos.zoomCalibracao.textContent = "Zoom 1,0x. Arraste a imagem para reposicionar.";
  estado.calibracao = {
    version: 1,
    video: {
      file_name: arquivo.name,
      duration_s: 0,
      width: 0,
      height: 0,
    },
    court_points: {},
    court_missing: {},
    players: {
      player_count: Number(elementos.qtdJogadoresCalibracao.value || 2),
      p1: null,
      p2: null,
    },
    ball_tracking: {
      mode: "visual_confirmed",
      note: "Usar marcacoes densas como keyframes do rastreador, com pontos obrigatorios no apice do saque, contato, rede e fundo da quadra. Nao usar busca livre fora do trecho calibrado.",
    },
    serve_metrics: {
      curve_factor: 1.03,
      radar_factor: 1.30,
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
  estado.calibracao.video.width = Number(dados.largura || estado.calibracao.video.width || 0);
  estado.calibracao.video.height = Number(dados.altura || estado.calibracao.video.height || 0);

  if (estado.calibracao.video.duration_s > 0) {
    elementos.rangeTempoCalibracao.max = String(estado.calibracao.video.duration_s);
  }
  if (estado.calibracao.video.width > 0 && estado.calibracao.video.height > 0) {
    configurarCanvasCalibracao(estado.calibracao.video.width, estado.calibracao.video.height);
  }

  const tempo = Number(elementos.rangeTempoCalibracao.value || 0);
  await carregarFrameServidorCalibracao(tempo);
}

function configurarCanvasCalibracao(larguraOriginal, alturaOriginal) {
  const largura = Math.min(960, larguraOriginal || 960);
  const altura = Math.max(220, Math.round(largura * ((alturaOriginal || 540) / Math.max(larguraOriginal || 960, 1))));
  elementos.canvasCalibracao.width = largura;
  elementos.canvasCalibracao.height = altura;
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

function pontoNormalizadoCanvas(evento) {
  const rect = elementos.canvasCalibracao.getBoundingClientRect();
  const view = viewportCalibracao();
  const telaX = (evento.clientX - rect.left) / Math.max(rect.width, 1);
  const telaY = (evento.clientY - rect.top) / Math.max(rect.height, 1);
  return {
    x: Math.max(0, Math.min(1, view.x + telaX * view.w)),
    y: Math.max(0, Math.min(1, view.y + telaY * view.h)),
  };
}

function viewportCalibracao() {
  const zoom = Math.max(1, Number(estado.zoomCalibracao) || 1);
  const largura = 1 / zoom;
  const altura = 1 / zoom;
  const metadeW = largura / 2;
  const metadeH = altura / 2;
  const centroX = Math.max(metadeW, Math.min(1 - metadeW, estado.panCalibracao.x));
  const centroY = Math.max(metadeH, Math.min(1 - metadeH, estado.panCalibracao.y));
  estado.panCalibracao = { x: centroX, y: centroY };
  return {
    x: centroX - metadeW,
    y: centroY - metadeH,
    w: largura,
    h: altura,
  };
}

function ajustarZoomCalibracao(valor, manterPan = false) {
  const zoom = Math.max(1, Math.min(5, Number(valor) || 1));
  estado.zoomCalibracao = zoom;
  if (!manterPan || zoom === 1) {
    estado.panCalibracao = { x: 0.5, y: 0.5 };
  } else {
    viewportCalibracao();
  }
  elementos.rangeZoomCalibracao.value = String(zoom);
  elementos.zoomCalibracao.textContent = `Zoom ${formatarNumero(zoom, "x")}. Arraste a imagem para reposicionar.`;
  desenharCanvasCalibracao();
}

function variarZoomCalibracao(delta) {
  ajustarZoomCalibracao(estado.zoomCalibracao + delta, true);
}

function iniciarPanCalibracao(evento) {
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
  if (!estado.arrastandoCalibracao || !estado.dragCalibracao || estado.zoomCalibracao <= 1) {
    return;
  }
  const rect = elementos.canvasCalibracao.getBoundingClientRect();
  const dx = (evento.clientX - estado.dragCalibracao.x) / Math.max(rect.width, 1);
  const dy = (evento.clientY - estado.dragCalibracao.y) / Math.max(rect.height, 1);
  if (Math.hypot(evento.clientX - estado.dragCalibracao.x, evento.clientY - estado.dragCalibracao.y) > 4) {
    estado.suprimirCliqueCalibracao = true;
  }
  estado.panCalibracao = {
    x: estado.dragCalibracao.panX - dx / estado.zoomCalibracao,
    y: estado.dragCalibracao.panY - dy / estado.zoomCalibracao,
  };
  viewportCalibracao();
  desenharCanvasCalibracao();
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
  const tempo = Number(elementos.rangeTempoCalibracao.value || elementos.videoCalibracao.currentTime || 0);
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
    if (estado.indicePontoQuadra >= PONTOS_QUADRA_CALIBRACAO.length && totalPontosQuadraMarcados() >= 4) {
      estado.etapaCalibracao = "jogadores";
      estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
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
    sugerirTempoBola();
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
  return totalPontosQuadraResolvidos() >= PONTOS_QUADRA_CALIBRACAO.length && totalPontosQuadraMarcados() >= 4;
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

  const tempo = Number(elementos.rangeTempoCalibracao.value || elementos.videoCalibracao.currentTime || 0);
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
  if (estado.indicePontoQuadra >= PONTOS_QUADRA_CALIBRACAO.length && totalPontosQuadraMarcados() >= 4) {
    estado.etapaCalibracao = "jogadores";
    estado.indiceJogadorCalibracao = estado.calibracao.players.p1 ? 1 : 0;
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
  estado.tipoEspecialBola = estado.tipoEspecialBola === tipo ? null : tipo;
  const config = TIPOS_ESPECIAIS_BOLA[estado.tipoEspecialBola];
  if (config) {
    elementos.progressoCalibracao.textContent = `Clique no frame para marcar: ${config.label}. Essa marcacao pode ser feita antes do rastreio completo da bolinha.`;
  }
  atualizarInterfaceCalibracao();
}

function atualizarParametrosSaqueCalibracao() {
  if (!estado.calibracao) {
    return;
  }
  estado.calibracao.serve_metrics = estado.calibracao.serve_metrics ?? {};
  estado.calibracao.serve_metrics.curve_factor = 1.03;
  estado.calibracao.serve_metrics.radar_factor = 1.30;
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
    if (totalPontosQuadraMarcados() < 4) {
      elementos.progressoCalibracao.textContent = "Marque pelo menos 4 pontos reais da quadra antes de avancar; os pulados dependem desses pontos para interpolacao.";
      return;
    }
    estado.etapaCalibracao = "jogadores";
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
  } else if (estado.etapaCalibracao === "jogadores") {
    if (estado.calibracao.players.p2) {
      estado.calibracao.players.p2 = null;
      estado.indiceJogadorCalibracao = 1;
    } else if (estado.calibracao.players.p1) {
      estado.calibracao.players.p1 = null;
      estado.indiceJogadorCalibracao = 0;
    }
  } else if (estado.etapaCalibracao === "bola") {
    estado.calibracao.ball_marks.pop();
    invalidarPreviewVelocidadeSaque();
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
  });
  invalidarPreviewVelocidadeSaque();
}

function saqueEspecialCompleto() {
  return Boolean(
    marcaBolaPorRole("serve_contact")
    && marcaBolaPorRole("serve_contact_ground")
    && marcaBolaPorRole("serve_court_bounce"),
  );
}

function invalidarPreviewVelocidadeSaque() {
  estado.previewVelocidadeSaque = null;
  estado.previewVelocidadeSaqueErro = "";
}

function atualizarResultadoVelocidadeSaque() {
  const quadraOk = quadraProntaParaSaque();
  const pronto = quadraOk && saqueEspecialCompleto();
  elementos.botaoCalcularVelocidadeSaque.disabled = !pronto;
  if (!quadraOk) {
    elementos.resultadoVelocidadeSaque.textContent = "Conclua as medicoes da quadra para liberar o calculo do saque.";
    elementos.resultadoVelocidadeSaque.classList.remove("resultado-saque-ok", "resultado-saque-erro");
    return;
  }
  if (!pronto) {
    elementos.resultadoVelocidadeSaque.textContent = "Marque contato, projecao no chao e primeiro toque para calcular.";
    elementos.resultadoVelocidadeSaque.classList.remove("resultado-saque-ok", "resultado-saque-erro");
    return;
  }
  if (estado.previewVelocidadeSaque) {
    const info = estado.previewVelocidadeSaque;
    elementos.resultadoVelocidadeSaque.textContent = `${formatarNumero(info.velocidade_kmh ?? 0, " km/h")} | voo ${formatarNumero(info.tempo_voo_s ?? 0, " s")} | 3D ${formatarNumero(info.distancia_m ?? 0, " m")} | conf ${formatarPercentual(info.confianca ?? 0)}`;
    elementos.resultadoVelocidadeSaque.classList.add("resultado-saque-ok");
    elementos.resultadoVelocidadeSaque.classList.remove("resultado-saque-erro");
    return;
  }
  if (estado.previewVelocidadeSaqueErro) {
    elementos.resultadoVelocidadeSaque.textContent = estado.previewVelocidadeSaqueErro;
    elementos.resultadoVelocidadeSaque.classList.add("resultado-saque-erro");
    elementos.resultadoVelocidadeSaque.classList.remove("resultado-saque-ok");
    return;
  }
  elementos.resultadoVelocidadeSaque.textContent = "Pronto para calcular sem renderizar o video.";
  elementos.resultadoVelocidadeSaque.classList.remove("resultado-saque-ok", "resultado-saque-erro");
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
  elementos.resultadoVelocidadeSaque.textContent = "Calculando velocidade...";
  elementos.resultadoVelocidadeSaque.classList.remove("resultado-saque-ok", "resultado-saque-erro");

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
  } else {
    estado.previewVelocidadeSaque = dados.velocidade_saque;
    estado.previewVelocidadeSaqueErro = "";
    estado.metadataAnaliseReal = {
      ...(estado.metadataAnaliseReal ?? {}),
      velocidade_saque: dados.velocidade_saque,
      velocidade_saque_status: dados.velocidade_saque_status,
    };
    if (estado.dados?.metricas) {
      renderizarMetricas(estado.dados.metricas, estado.metadataAnaliseReal);
    }
  }
  atualizarResultadoVelocidadeSaque();
}

function validarCalibracao() {
  if (!estado.calibracao) {
    return { ok: false, mensagem: "Selecione um video e conclua a calibracao." };
  }
  const pontosQuadra = totalPontosQuadraMarcados();
  const pontosPulados = totalPontosQuadraPulados();
  const pontosResolvidos = pontosQuadra + pontosPulados;
  if (pontosResolvidos < PONTOS_QUADRA_CALIBRACAO.length) {
    return { ok: false, mensagem: `Faltam ${PONTOS_QUADRA_CALIBRACAO.length - pontosResolvidos} pontos de quadra marcados ou pulados.` };
  }
  if (pontosQuadra < 4) {
    return { ok: false, mensagem: "Marque pelo menos 4 pontos reais da quadra para o sistema interpolar os pontos pulados." };
  }
  if (!jogadoresCalibrados()) {
    return { ok: false, mensagem: "Marque a posicao inicial do Jogador 1 e do Jogador 2 quando houver dois atletas." };
  }
  if ((estado.calibracao.ball_marks ?? []).length < MIN_MARCACOES_BOLA) {
    return { ok: false, mensagem: `Marque a bolinha em pelo menos ${MIN_MARCACOES_BOLA} frames diferentes.` };
  }
  return { ok: true, mensagem: "Calibracao completa." };
}

function atualizarInterfaceCalibracao() {
  if (!estado.calibracao) {
    return;
  }

  estado.calibracao.players.player_count = Number(elementos.qtdJogadoresCalibracao.value || 2);
  atualizarParametrosSaqueCalibracao();
  if (estado.calibracao.players.player_count < 2) {
    estado.calibracao.players.p2 = null;
  }

  const pontosQuadra = totalPontosQuadraMarcados();
  const pontosPulados = totalPontosQuadraPulados();
  const pontosResolvidos = pontosQuadra + pontosPulados;
  const marcasBola = estado.calibracao.ball_marks?.length ?? 0;
  const contatoSaque = marcaBolaPorRole("serve_contact");
  const projecaoContatoSaque = marcaBolaPorRole("serve_contact_ground");
  const primeiroToqueSaque = marcaBolaPorRole("serve_court_bounce");
  const etapasBolaResolvidas = MARCAS_BOLA_RECOMENDADAS.filter((etapa) => etapaBolaResolvida(etapa)).length;
  const saqueLiberado = quadraProntaParaSaque();
  if (!saqueLiberado && estado.tipoEspecialBola) {
    estado.tipoEspecialBola = null;
  }
  let alvo = "";
  let instrucao = "";

  if (estado.tipoEspecialBola) {
    const especialSelecionado = TIPOS_ESPECIAIS_BOLA[estado.tipoEspecialBola];
    alvo = `Clique na bolinha real: ${especialSelecionado?.label ?? "marcacao do saque"}`;
    instrucao = "Este clique sera salvo como evento do saque e tambem sera reaproveitado pelo rastreio da bolinha quando corresponder a uma etapa do fluxo. Depois, voce volta automaticamente para a etapa anterior.";
  } else if (estado.etapaCalibracao === "quadra") {
    avancarIndiceQuadraAtePendente();
    const atual = PONTOS_QUADRA_CALIBRACAO[estado.indicePontoQuadra];
    alvo = atual ? atual.label : "Quadra completa";
    instrucao = "Clique apenas nos pontos visiveis. Nos pontos da rede, marque a base inferior da rede no chao, sobre as linhas externas de duplas; o centro da rede nao precisa ser clicado, ele e inferido pelo sistema. Se o ponto pedido estiver fora do frame ou encoberto, use Pular ponto da quadra para o backend estimar por interpolacao.";
  } else if (estado.etapaCalibracao === "jogadores") {
    const total = estado.calibracao.players.player_count;
    alvo = estado.indiceJogadorCalibracao === 0 ? "Clique no Jogador 1" : "Clique no Jogador 2";
    instrucao = total < 2
      ? "Marque o centro do corpo do unico jogador visivel no frame."
      : "Marque o centro do corpo do Jogador 1 e depois do Jogador 2. O backend usa esses pontos como ancora e ignora pessoas fora da quadra, como juiz de cadeira e ball kids.";
  } else {
    const proximaMarca = proximaEtapaBolaRastreio();
    alvo = `Clique na bolinha real: ${proximaMarca?.label ?? "mais um frame real da bola"} (${marcasBola}/${MIN_MARCACOES_BOLA})`;
    instrucao = "O fluxo ja salva automaticamente contato/saida da raquete e primeiro toque na quadra como eventos do saque. Use o botao de projecao no chao do contato separadamente para estimar a altura e liberar o calculo da velocidade.";
  }

  const validacao = validarCalibracao();
  elementos.alvoCalibracao.textContent = alvo;
  elementos.instrucaoCalibracao.textContent = instrucao;
  elementos.progressoCalibracao.textContent = `${pontosResolvidos}/${PONTOS_QUADRA_CALIBRACAO.length} pontos de quadra resolvidos (${pontosQuadra} marcados, ${pontosPulados} pulados), ${jogadoresCalibrados() ? "jogadores ok" : "jogadores pendentes"}, ${marcasBola}/${MIN_MARCACOES_BOLA} pontos da bola (${etapasBolaResolvidas}/${MARCAS_BOLA_RECOMENDADAS.length} etapas guiadas), saque: ${contatoSaque ? "contato ok" : "contato pendente"} / ${projecaoContatoSaque ? "projecao ok" : "projecao para altura pendente"} / ${primeiroToqueSaque ? "toque ok" : "toque pendente"}. ${validacao.mensagem}`;
  elementos.botaoPularPontoQuadra.disabled = estado.etapaCalibracao !== "quadra" || estado.indicePontoQuadra >= PONTOS_QUADRA_CALIBRACAO.length;
  elementos.botaoContatoRaqueteCalibracao.disabled = !saqueLiberado;
  elementos.botaoProjecaoContatoCalibracao.disabled = !saqueLiberado;
  elementos.botaoPrimeiroToqueCalibracao.disabled = !saqueLiberado;
  elementos.botaoContatoRaqueteCalibracao.classList.toggle("ativo", estado.tipoEspecialBola === "serve_contact");
  elementos.botaoProjecaoContatoCalibracao.classList.toggle("ativo", estado.tipoEspecialBola === "serve_contact_ground");
  elementos.botaoPrimeiroToqueCalibracao.classList.toggle("ativo", estado.tipoEspecialBola === "serve_court_bounce");
  elementos.botaoContatoRaqueteCalibracao.classList.toggle("preenchido", Boolean(contatoSaque));
  elementos.botaoProjecaoContatoCalibracao.classList.toggle("preenchido", Boolean(projecaoContatoSaque));
  elementos.botaoPrimeiroToqueCalibracao.classList.toggle("preenchido", Boolean(primeiroToqueSaque));
  atualizarResultadoVelocidadeSaque();
  elementos.botaoFinalizarCalibracao.disabled = !validacao.ok;
}

function desenharCanvasCalibracao() {
  const canvas = elementos.canvasCalibracao;
  const ctx = canvas.getContext("2d");
  const video = elementos.videoCalibracao;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const podeUsarVideoLocal = video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0 && !estado.carregandoFrameCalibracao;
  const usarFrameServidor = estado.frameServidorImagem && (!podeUsarVideoLocal || estado.calibracaoServidorId);

  if (usarFrameServidor) {
    const imagem = estado.frameServidorImagem;
    const view = viewportCalibracao();
    const origemX = view.x * Math.max(imagem.naturalWidth, 1);
    const origemY = view.y * Math.max(imagem.naturalHeight, 1);
    const origemW = view.w * Math.max(imagem.naturalWidth, 1);
    const origemH = view.h * Math.max(imagem.naturalHeight, 1);
    ctx.drawImage(imagem, origemX, origemY, origemW, origemH, 0, 0, canvas.width, canvas.height);
  } else if (podeUsarVideoLocal) {
    const view = viewportCalibracao();
    const origemX = view.x * Math.max(video.videoWidth, 1);
    const origemY = view.y * Math.max(video.videoHeight, 1);
    const origemW = view.w * Math.max(video.videoWidth, 1);
    const origemH = view.h * Math.max(video.videoHeight, 1);
    try {
      ctx.drawImage(video, origemX, origemY, origemW, origemH, 0, 0, canvas.width, canvas.height);
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

  desenharLinhasCalibracao(ctx);
  desenharPontosCalibracao(ctx);
}

function desenharLinhasCalibracao(ctx) {
  const pontos = estado.calibracao?.court_points ?? {};
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
  ctx.save();
  ctx.strokeStyle = "rgba(180, 255, 103, 0.82)";
  ctx.lineWidth = 2;
  pares.forEach(([a, b]) => {
    if (!pontos[a] || !pontos[b]) {
      return;
    }
    const inicio = pontoParaCanvasCalibracao(pontos[a], ctx);
    const fim = pontoParaCanvasCalibracao(pontos[b], ctx);
    ctx.beginPath();
    ctx.moveTo(inicio.x, inicio.y);
    ctx.lineTo(fim.x, fim.y);
    ctx.stroke();
  });
  ctx.restore();
}

function desenharPontosCalibracao(ctx) {
  const pontos = estado.calibracao?.court_points ?? {};
  Object.entries(pontos).forEach(([id, ponto]) => {
    desenharMarcadorCalibracao(ctx, ponto, "#b8ff67", id);
  });

  const players = estado.calibracao?.players ?? {};
  if (players.p1) {
    desenharMarcadorCalibracao(ctx, players.p1, "#63f5c2", "Jogador 1");
  }
  if (players.p2) {
    desenharMarcadorCalibracao(ctx, players.p2, "#ff719f", "Jogador 2");
  }

  (estado.calibracao?.ball_marks ?? []).forEach((ponto, indice) => {
    const especial = TIPOS_ESPECIAIS_BOLA[ponto.role];
    desenharMarcadorCalibracao(ctx, ponto, especial?.cor ?? "#ffe85d", `Bola ${indice + 1}`);
  });
}

function desenharMarcadorCalibracao(ctx, ponto, cor, label) {
  const { x, y, visivel } = pontoParaCanvasCalibracao(ponto, ctx);
  if (!visivel) {
    return;
  }
  ctx.save();
  ctx.fillStyle = cor;
  ctx.strokeStyle = "rgba(0,0,0,0.85)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(x, y, 7, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.strokeStyle = "rgba(255,255,255,0.72)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(x, y, 12, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function pontoParaCanvasCalibracao(ponto, ctx) {
  const view = viewportCalibracao();
  const x = ((ponto.x - view.x) / view.w) * ctx.canvas.width;
  const y = ((ponto.y - view.y) / view.h) * ctx.canvas.height;
  return {
    x,
    y,
    visivel: x >= -18 && x <= ctx.canvas.width + 18 && y >= -18 && y <= ctx.canvas.height + 18,
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
  corpo.append("calibracao", JSON.stringify(estado.calibracao));

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
  estado.pollingJob = window.setInterval(() => {
    consultarJobVideo(jobId).catch((erro) => {
      elementos.statusUpload.textContent = "Falha ao consultar o processamento do video.";
      console.error(erro);
    });
  }, 1800);
  consultarJobVideo(jobId).catch((erro) => {
    elementos.statusUpload.textContent = "Falha ao consultar o processamento do video.";
    console.error(erro);
  });
}

async function consultarJobVideo(jobId) {
  const resposta = await fetch(`/api/videos/jobs/${jobId}`);
  const job = await resposta.json();
  if (!resposta.ok) {
    throw new Error(job.detail ?? "Job nao encontrado.");
  }

  const progresso = Number(job.progresso ?? 0);
  elementos.statusUpload.textContent = `${job.mensagem ?? "Processando video..."} (${formatarNumero(progresso, "%")})`;

  if (job.status === "concluido") {
    pararPollingJob();
    elementos.botaoCancelarJob.classList.add("oculto");
    aplicarAnaliseReal(job);
    return;
  }

  if (job.status === "falhou" || job.status === "cancelado") {
    pararPollingJob();
    elementos.botaoCancelarJob.classList.add("oculto");
    elementos.statusUpload.textContent = job.mensagem ?? "Processamento encerrado.";
  }
}

function aplicarAnaliseReal(job) {
  estado.metadataAnaliseReal = job.metadata ?? null;
  if (job.analise) {
    estado.dados = job.analise;
    estado.indiceQuadro = 0;
    estado.modoVideoReal = true;
    if (estado.temporizador) {
      window.clearInterval(estado.temporizador);
      estado.temporizador = null;
    }
    renderizarPainel();
  }

  if (job.url_video_analisado) {
    elementos.videoUpload.src = `${job.url_video_analisado}?v=${Date.now()}`;
    elementos.videoUpload.load();
    elementos.videoUploadCard.classList.remove("oculto");
    elementos.videoWrap.classList.add("oculto");
  }

  const detector = job.metadata?.detector ? ` Detector: ${job.metadata.detector}.` : "";
  const frames = job.metadata?.frames_processados ? ` Frames analisados: ${job.metadata.frames_processados}.` : "";
  const resolucao = job.metadata?.largura_saida && job.metadata?.altura_saida
    ? ` Resolucao: ${job.metadata.largura_saida}x${job.metadata.altura_saida}.`
    : "";
  const codec = job.metadata?.codec_saida ? ` Codec: ${job.metadata.codec_saida}.` : "";
  const crf = job.metadata?.qualidade_h264_crf ? ` CRF: ${job.metadata.qualidade_h264_crf}.` : "";
  const saqueInfo = job.metadata?.velocidade_saque;
  const saque = saqueInfo?.velocidade_kmh
    ? ` Saque 3D: ${formatarNumero(saqueInfo.velocidade_kmh, " km/h")} (${saqueInfo.metodo}, conf. ${formatarPercentual(saqueInfo.confianca ?? 0)}).`
    : "";
  elementos.statusUpload.textContent = `Analise real carregada.${detector}${frames}${resolucao}${codec}${crf}${saque}`;
}

function desativarVideoReal() {
  estado.modoVideoReal = false;
  estado.metadataAnaliseReal = null;
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
  elementos.statusUpload.textContent = `Video analisado pronto para reproducao (${formatarNumero(elementos.videoUpload.duration, " s")}).`;
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
  variarZoomCalibracao(evento.deltaY > 0 ? -0.2 : 0.2);
}, { passive: false });
elementos.rangeTempoCalibracao.addEventListener("input", (evento) => {
  irParaTempoCalibracao(evento.target.value);
});
elementos.rangeZoomCalibracao.addEventListener("input", (evento) => {
  ajustarZoomCalibracao(evento.target.value, true);
});
elementos.botaoZoomMenosCalibracao.addEventListener("click", () => variarZoomCalibracao(-0.4));
elementos.botaoZoomMaisCalibracao.addEventListener("click", () => variarZoomCalibracao(0.4));
elementos.botaoResetZoomCalibracao.addEventListener("click", () => ajustarZoomCalibracao(1));
elementos.botaoContatoRaqueteCalibracao.addEventListener("click", () => selecionarTipoEspecialBola("serve_contact"));
elementos.botaoProjecaoContatoCalibracao.addEventListener("click", () => selecionarTipoEspecialBola("serve_contact_ground"));
elementos.botaoPrimeiroToqueCalibracao.addEventListener("click", () => selecionarTipoEspecialBola("serve_court_bounce"));
elementos.botaoCalcularVelocidadeSaque.addEventListener("click", () => {
  calcularVelocidadeSaquePreview().catch((erro) => {
    estado.previewVelocidadeSaque = null;
    estado.previewVelocidadeSaqueErro = erro.message ?? "Falha ao calcular velocidade do saque.";
    atualizarResultadoVelocidadeSaque();
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

Promise.all([carregarArquitetura(), carregarPainel()]).catch((erro) => {
  console.error("Falha ao inicializar o painel:", erro);
});

