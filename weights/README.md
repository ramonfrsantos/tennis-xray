# Pesos de modelos de visao

Coloque aqui os pesos opcionais usados pelo pipeline de visao.

## YOLO fine-tuned para bolinha

A abordagem recomendada, baseada no projeto `abdullahtarek/tennis_analysis`, e usar um detector separado treinado especificamente para tennis ball. Por padrao, a aplicacao tenta carregar automaticamente `best.pt` do Hugging Face:

- repo: `RJTPP/tennis-ball-detection`
- arquivo: `best.pt`

Para usar sem baixar manualmente, instale `huggingface_hub` e mantenha `TENNIS_XRAY_YOLO_BALL_HF_ENABLED=1`.

Se preferir pesos locais, coloque o arquivo em um destes caminhos:

- `weights/tennis_ball_yolo.pt` (recomendado)
- `weights/yolo5_last.pt` (compatibilidade com o nome usado no projeto de referencia)
- caminho definido por `TENNIS_XRAY_YOLO_BALL_MODEL`

Variaveis uteis:

- `TENNIS_XRAY_USE_BALL_YOLO=0` desativa esse detector e usa TrackNet/OpenCV/beam.
- `TENNIS_XRAY_YOLO_BALL_MODEL=C:\modelos\tennis_ball_yolo.pt` aponta para outro peso.
- `TENNIS_XRAY_YOLO_BALL_MODEL=RJTPP/tennis-ball-detection` carrega esse repo remoto.
- `TENNIS_XRAY_YOLO_BALL_HF_REPO=RJTPP/tennis-ball-detection` troca o repo remoto padrao.
- `TENNIS_XRAY_YOLO_BALL_HF_FILENAME=best.pt` troca o arquivo dentro do repo.
- `TENNIS_XRAY_YOLO_BALL_HF_ENABLED=0` desativa download/cache remoto.
- `TENNIS_XRAY_YOLO_BALL_CONF=0.06` confianca minima do detector de bolinha.
- `TENNIS_XRAY_YOLO_BALL_IMGSZ=1536` tamanho de inferencia; valores maiores ajudam bolas pequenas no fundo.

Sem esse peso especializado, a aplicacao continua funcionando com TrackNet opcional e fallback OpenCV/beam, mas a precisao em bolas pequenas/distantes tende a ser limitada.

## TrackNet para rastreio da bolinha

O detector temporal TrackNet e usado automaticamente quando um arquivo de peso e encontrado em um destes caminhos:

- `weights/tracknet_tennis.pt`
- `weights/tracknet_tennis.pth`
- caminho definido por `TENNIS_XRAY_TRACKNET_WEIGHTS`

Variaveis uteis:

- `TENNIS_XRAY_TRACKNET_ENABLED=0` desativa TrackNet e usa apenas o fallback YOLO/OpenCV.
- `TENNIS_XRAY_TRACKNET_WEIGHTS=C:\modelos\tracknet_tennis.pt` aponta para outro arquivo de pesos.
- `TENNIS_XRAY_TRACKNET_DEVICE=cpu` forca CPU mesmo quando CUDA estiver disponivel.
- `TENNIS_XRAY_TRACKNET_WIDTH=640` largura de entrada do heatmap.
- `TENNIS_XRAY_TRACKNET_HEIGHT=360` altura de entrada do heatmap.
- `TENNIS_XRAY_TRACKNET_MIN_CONF=0.16` confianca minima do pico do heatmap.

Formatos aceitos:

- TorchScript `.pt`, recomendado.
- Modulo PyTorch serializado.
- `state_dict` compativel com a arquitetura TrackNet V1 fallback.

Se nenhum peso for encontrado, a aplicacao continua funcionando com o rastreador atual.
