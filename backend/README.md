# SentriX — backend VideoMAE en GPU

## EN-4: eventos confirmados con inicio y fin

El stream abre un único evento por sesión tras dos ventanas consecutivas de la
misma clase criminal sobre su threshold (comparación >=). Tres ventanas
consecutivas Normal cierran ese evento. Guarda las detecciones de apertura/cierre,
timestamps del video, duración y estado active/closed/interrupted. Desconexiones,
fallos, ventanas perdidas y reinicios interrumpen el evento sin inventar un regreso
a Normal. Los eventos comparten el archivo SQLite de EN-3.

Thresholds provisionales: Hurto .50, Robo .60, Agresión física .60, Vandalismo .55.
`SENTRIX_ALERT_THRESHOLDS` acepta JSON con las cuatro clases. La política del
stream usa clase/confianza originales sin suavizado; reemplaza el umbral global
y el cierre por ausencia de candidato de la política anterior. El modelo y su
preprocesamiento permanecen iguales. Ejecutar un único proceso del backend.

`GET /alerts` permite filtrar por camera/status y paginar; `GET /alerts/{id}`
devuelve el evento persistido. POST /predict continúa siendo independiente y
no evalúa intervalos temporales. El mock de stream sí permite probar la política.

## TA-4: logs operativos persistentes

El servicio registra inicio/cierre, carga del modelo, conexiones de fuentes,
errores e inferencias con sus tiempos en `backend/data/inference_logs.sqlite3`.
`SENTRIX_LOG_DB` permite configurar otra ruta. Este historial es independiente
de EN-3 y no contiene frames ni clips; respaldar el archivo para conservarlo.
No hay limpieza automática ni reintento durable de logs que fallen al escribirse.
Una falla de logs no interrumpe la inferencia, y la consulta devuelve 503 si
el almacenamiento no está disponible.

Consulta: `GET /inference-logs` y `GET /inference-logs/{log_id}`. Incluye filtros
por cámara, evento, nivel y fechas con zona horaria, además de paginación.

El backend carga el modelo ONNX de `../modelo` una vez al arrancar y ejecuta
una inferencia de calentamiento antes de aceptar conexiones. El modo predeterminado
es `videomae` con `cuda`; una carga fallida impide arrancar. No se sustituye
el modelo real por CPU ni por MockPredictor automáticamente.

**Conexión actual: LiveKit.** El backend se suscribe al video de Gabriel y Mari
consulta los resultados por las mismas rutas HTTP. Configurar `backend/.env` con
las variables `LIVEKIT_*` (URL, sala, identidad del emisor y credenciales). La conexión WebRTC directa
se conserva como alternativa explícita para pruebas.

## Instalar y arrancar

Desde la raíz del repositorio, PowerShell:

```powershell
python -m venv .venv
Copy-Item backend/.env.example backend/.env
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-gpu.txt
.\backend\start_gpu.ps1
```

Instalar las dependencias en cada equipo. Mantener juntos `.onnx` y
`.onnx.data`. No instalar simultáneamente onnxruntime CPU y onnxruntime-gpu.
Si hay un servidor anterior en el puerto 8000, detenerlo con Ctrl+C primero.
El script fuerza GPU. Equivalente manual:

```powershell
$env:SENTRIX_PREDICTOR = 'videomae'
$env:SENTRIX_PROVIDER = 'cuda'
$env:SENTRIX_VIDEO_TRANSPORT = 'livekit'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Esperar `Application startup complete`. Consultar http://localhost:8000/health:
debe informar `model_loaded: true`, `gpu_active: true` y
`CUDAExecutionProvider` en `providers`. Swagger: http://localhost:8000/docs.
El servicio continúa usando la red privada Tailscale y CORS configurable por
`FRONTEND_ORIGINS`. Todas las rutas excepto `/health`, `/docs`, `/redoc` y
`/openapi.json` exigen el encabezado `X-API-Key` con el valor de
`SENTRIX_CONTROL_API_KEY`; en Swagger se envía con Authorize.

Para ejecutar CPU deliberadamente, cambiar `SENTRIX_PROVIDER=cpu` en el comando
manual. Para pruebas con el simulador, `SENTRIX_PREDICTOR=mock`; /health declara
`model_loaded: false` y las predicciones `simulated: true`.
`start_gpu.ps1` siempre selecciona el modelo real, CUDA y recepción LiveKit.

## Flujo de video e inferencia

En modo LiveKit, Gabriel publica video en la sala y el backend se suscribe a su
identidad. Mari recibe el video desde LiveKit. Se mantienen GET /webrtc/sessions
y GET /webrtc/sessions/{session_id}, con latest_result de esa fuente.
La conexión WebRTC directa anterior está disponible solo con
SENTRIX_VIDEO_TRANSPORT=webrtc; en ese modo mantiene ofertas y hasta cuatro espectadores.

- Se seleccionan frames recibidos 0,4,...,60. La segunda ventana usa
  64,68,...,124. No se asume un FPS fijo ni se duplican frames.
- Se preserva el aspecto al redimensionar, se aplica center crop 224×224,
  RGB, escala /255 y mean/std originales. Entrada float32 NCTHW [1,3,16,224,224].
- Preparación e inferencia corren en un hilo, fuera del bucle de recepción.
  Una cola limitada conserva ventanas recientes; `TA2_QUEUE_SIZE` admite 1–4
  y vale 2 por defecto. La inferencia del modelo compartido está serializada.
- `TA2_FPS`, `TA2_WIDTH`, `TA2_HEIGHT` y `TA2_WINDOW_SIZE` del simulador no
  se aplican al modelo real; se usan los metadatos entregados.
- Regresiones de tiempo, saltos mayores a un segundo y timestamps inválidos
  reinician la ventana parcial y política. Resultados de la línea temporal
  anterior no se publican. Los fallos o descartes reinician la confirmación
  antes de la siguiente ventana exitosa.
- EN-4: thresholds por clase, confirmación de dos ventanas de la misma clase
  y cierre tras tres ventanas consecutivas Normal, sin suavizado.
- Cada sesión tiene su propia política, cola y resultados; reconectar limpia el estado.

A 25 FPS, la primera ventana comprende 2.4 s entre sus extremos y la cadencia
es 2.56 s por ventana. A 30 FPS son 2 s y 2.13 s, antes de sumar recepción y
procesamiento. La confirmación necesita dos ventanas candidatas de la misma
clase. Inferencia de ~73 ms no equivale a latencia de detección.

## POST /predict

Se conserva JSON con `timestamp` y frames THWC RGB normalizados en [0,1].
En modo real exige exactamente 16 frames ya muestreados; dimensiones 1–224,
con tres canales. Aplica preprocesamiento VideoMAE y devuelve clasificación
sin política temporal, porque cada petición es independiente.
422 para entrada inválida, 413 si supera 2 MiB, 503 si falla el modelo.
Clips completos de 224×224 en JSON normalmente exceden el límite de 2 MiB.
Para transmisión usar WebRTC, que procesa frames directamente en memoria.
No enviar píxeles JSON desde el frontend para el stream.

## Validación

Desde `backend/`:

```powershell
..\.venv\Scripts\python.exe -m pytest tests -q
# Prueba adicional con GPU real y video enviado por WebRTC:
$env:SENTRIX_TEST_GPU = '1'
$env:SENTRIX_PROVIDER = 'cuda'
# Opcional: ruta absoluta o relativa al directorio actual:
$env:SENTRIX_TEST_VIDEO = 'C:/ruta/a/video-de-prueba.mp4'
..\.venv\Scripts\python.exe -m pytest tests/test_videomae.py::test_gpu_webrtc_end_to_end -q
```

La suite normal usa mocks explícitos, prueba compatibilidad WebRTC, muestreo,
paridad exacta del preprocesamiento con Piero, confirmación/liberación y
aislamiento de alertas. La prueba GPU exige CUDA, envía el video elegido por WebRTC,
espera dos ventanas reales y verifica probabilidades, alertas y cierre.
Es una prueba local; falta repetirla entre computadoras del equipo.

Las pruebas del emisor directo seleccionan explícitamente transporte=webrtc.
Prueba adicional del adaptador LiveKit con SDK y GPU real, sin sala remota:

```powershell
$env:SENTRIX_TEST_GPU = '1'
..\.venv\Scripts\python.exe -m pytest tests/test_livekit.py -q
```

El 3 de octubre de 2026 pasaron 33 pruebas de la suite normal y la prueba
adicional GPU/WebRTC con `prueba3.mp4` (34 en total). La prueba GPU confirmó
modelo cargado, CUDA activo, dos ventanas con simulated=false, probabilidades
válidas, política de alertas y limpieza de la sesión. No se modificaron archivos
del frontend ni se reinició un servidor que pudiera estar ejecutándose.

Después de integrar LiveKit, la suite completa con SENTRIX_TEST_GPU=1 pasó
48 pruebas. Incluye el adaptador LiveKit con frames nativos e inferencia GPU,
además de reconexión, selección de emisor y compatibilidad HTTP con Mari.
La sala de LiveKit se simula en las pruebas: sigue pendiente la conexión real.

## EN-3: persistencia de detecciones

Cada inferencia exitosa de HTTP, LiveKit o WebRTC se guarda en SQLite,
incluyendo clasificaciones Normal y resultados por debajo del umbral de alertas.
Se guarda el resultado original del modelo antes del suavizado y la política
 temporal. No se escriben frames, clips ni archivos de video.

El archivo predeterminado es `backend/data/detections.sqlite3`, independiente
 del directorio desde el que se arranca el servicio. `SENTRIX_DETECTION_DB` permite
 elegir otra ruta (preferiblemente absoluta). La carpeta se crea automáticamente;
el proceso necesita permisos de escritura. Conservar este archivo y respaldarlo
para mantener el historial al reiniciar o trasladar el backend.

- `GET /detections/{id}` recupera un registro; devuelve 404 si no existe.
- `GET /detections?camera=camara_mari&limit=100&offset=0` consulta el historial
  más reciente primero. Cámara es opcional; limit admite 1–500, offset >= 0.
- `POST /predict` acepta `source_id` opcional (por defecto `camara_mari`) y
  devuelve el identificador persistido en la cabecera `X-Detection-ID`, accesible
  desde el navegador mediante CORS. Su cuerpo de respuesta conserva el contrato.
- `latest_result.detection_id` identifica el registro de cada ventana del stream.

Cada registro contiene `id`, `camera` (source_id), `fecha_hora` (instante UTC
 de almacenamiento en ISO 8601), `clase`, `confianza` y `timestamp` (segundos
 de la línea temporal del video, no fecha Unix). También conserva `simulated`,
`probabilities` cuando el modelo las entrega y `session_id`/`window_id` para
las ventanas del stream; estos dos últimos son null en peticiones HTTP.
Las detecciones sobreviven al cierre de la sesión y a la reconexión. Las
inferencias ya terminadas se conservan incluso si su ventana deja de publicarse
por un cambio de línea temporal; la política de alertas sigue descartándolas.
Las ventanas descartadas antes de inferir no generan detecciones.

Una falla de almacenamiento devuelve 503 en HTTP; en el stream se registra
como error de procesamiento y no publica esa ventana como procesada con éxito.
No se incluye una cola de reintento durable. Las pruebas usan bases temporales
para evitar escribir detecciones simuladas en el historial de operación.

## PostgreSQL

Configurar `SENTRIX_DATABASE_URL` en `backend/.env`. Detecciones, alertas y logs
usan PostgreSQL.
