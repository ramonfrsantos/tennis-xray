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
  const anotacao = elementos.campoAnotacao.value.trim();
  const url = new URL("/api/painel/demo", window.location.origin);
  url.searchParams.set("quadros", "90");
  if (anotacao) {
    url.searchParams.set("anotacao", anotacao);
  }

  const resposta = await fetch(url);
  estado.dados = await resposta.json();
  estado.indiceQuadro = 0;
  renderizarPainel();
  iniciarAnimacao();
}

function iniciarAnimacao() {
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

  renderizarMetricas(metricas);
  renderizarListas(relatorio, diagnostico);
  desenharLinhaTempo();
  renderizarDinamica();
}

function renderizarMetricas(metricas) {
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
      valor: formatarNumero(metricas.velocidade_media_bola_ms, " m/s"),
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

  elementos.gradeMetricas.innerHTML = itens
    .map(
      (item) => `
        <article class="cartao-metrica">
          <span class="rotulo-fato">${item.titulo}</span>
          <div class="valor">${item.valor}</div>
          <p class="descricao">${item.descricao}</p>
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
  elementos.hudBola.textContent = `${formatarNumero(quadro.bola?.velocidade_ms ?? 0, " m/s")}`;
  elementos.hudCalibracao.textContent = formatarPercentual(estado.dados.metricas.qualidade_tracking);
  desenharVideo(quadro);
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
          <td>${formatarNumero(atleta.velocidade_ms, " m/s")}</td>
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
    <text x="716" y="514" fill="#9fc2d6" font-size="16">Bola: ${formatarNumero(quadro.bola?.velocidade_ms ?? 0, " m/s")}</text>
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

async function enviarUpload(evento) {
  evento.preventDefault();
  const arquivo = elementos.campoVideo.files?.[0];
  if (!arquivo) {
    elementos.statusUpload.textContent = "Selecione um vídeo antes de enviar.";
    return;
  }

  const corpo = new FormData();
  corpo.append("arquivo", arquivo);

  elementos.statusUpload.textContent = "Enviando arquivo...";
  const resposta = await fetch("/api/videos/upload", {
    method: "POST",
    body: corpo,
  });
  const dados = await resposta.json();
  elementos.statusUpload.textContent = `${dados.mensagem} Arquivo: ${dados.arquivo}.`;
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

