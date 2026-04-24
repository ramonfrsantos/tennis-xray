# Plataforma Biomecânica de Tênis

Projeto novo do zero, totalmente em português-BR, para análise biomecânica de movimentos e tracking visual de vídeos de tênis. A arquitetura foi inspirada na referência enviada, mas foi redirecionada para um produto de biomecânica esportiva com cinco camadas:

1. Visão e tracking.
2. Motor bayesiano de consistência biomecânica.
3. Ponte de sessão e contexto operacional.
4. Inteligência contextual baseada em anotações.
5. Motor de diagnóstico e recomendações.

## O que o projeto entrega agora

- Backend em FastAPI com endpoints de demo, arquitetura, análise contextual e upload.
- Painel web visual com quadro principal, boxes, marcadores corporais, minimapa, timeline e cards de métricas.
- Simulação determinística para demonstrar tracking, HUD técnico e alertas biomecânicos sem depender de pesos de visão computacional.
- Estrutura pronta para substituir o modo demo por YOLO, pose estimation e homografia reais.

## Estrutura

```text
tennis-project/
├── backend/
│   └── app/
│       ├── api/
│       │   └── rotas_analise.py
│       ├── servicos/
│       │   ├── camada_visao.py
│       │   ├── inteligencia_contextual.py
│       │   ├── motor_bayesiano.py
│       │   ├── motor_diagnostico.py
│       │   ├── orquestrador.py
│       │   └── ponte_sessao.py
│       ├── main.py
│       └── modelos.py
├── uploads/
├── web/
│   ├── assets/
│   │   ├── app.js
│   │   └── estilos.css
│   └── index.html
├── requirements.txt
├── requirements-visao.txt
└── README.md
```

## Como executar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Endpoints principais

- `GET /api/saude`
- `GET /api/arquitetura`
- `GET /api/painel/demo`
- `POST /api/inteligencia/analisar-anotacao`
- `POST /api/videos/upload`

## Evolução para produção

Para conectar o projeto ao pipeline real da referência:

- Trocar `VisaoQuadra.gerar_quadro_demo()` por inferência com YOLO e pose estimation.
- Adicionar homografia da quadra para coordenadas reais em metros.
- Persistir sessões, atletas, protocolos e versões de análise.
- Processar uploads em fila assíncrona.
- Usar `requirements-visao.txt` para instalar a pilha pesada de visão computacional.

## Observação importante

O projeto foi adaptado para biomecânica e tracking esportivo. Os componentes de mercado/apostas da referência foram substituídos por contexto de sessão, inteligência clínica e diagnóstico de movimento para ficar alinhado ao objetivo solicitado.
