# Local Data Agent

Aplicación local de tipo escritorio/web (FastAPI) para chatear con un agente LangChain sobre una base de datos o una carpeta de archivos sin enviar credenciales ni rutas sensibles al LLM.

## Funcionalidad principal

- Onboarding para elegir una conexión local:
  - Base de datos mediante URI SQLAlchemy.
  - Carpeta de archivos mediante selector/ruta local.
- Las credenciales y rutas quedan guardadas en `~/.local_data_agent/config.json` y se usan solo del lado servidor local.
- Chat estilo ChatGPT para preguntas como:
  - ¿Cómo está estructurada la base de datos?
  - ¿Para qué sirve o qué hace este conjunto de datos?
  - Informes y reportes sobre los datos.
  - Extracción de datasets.
  - Descarga en CSV, Excel o PDF.
  - Cálculos como total de IVA a pagar en facturas.
- Preparado para uso por audio:
  - Dictado usando Web Speech API del navegador.
  - Lectura de respuestas con speech synthesis.
  - Botón de modo manos libres.

## Ejecución

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn local_data_agent.main:app --reload
```

Abrí `http://127.0.0.1:8000`.

## Configuración de LLM

La app usa LangChain. Si configurás `OPENAI_API_KEY`, usa `ChatOpenAI`; si no hay API key, responde con un modelo local determinístico de respaldo para que la aplicación siga funcionando durante desarrollo.

```bash
export OPENAI_API_KEY=...
export LOCAL_DATA_AGENT_MODEL=gpt-4o-mini
```

## Seguridad y privacidad

- El formulario guarda conexión/ruta en almacenamiento local del servidor, no en el navegador.
- No se envían al LLM URIs de base de datos, contraseñas, rutas absolutas ni secretos.
- El agente trabaja con resúmenes sanitizados: nombres de tablas, columnas, tipos, conteos y muestras limitadas.
- Las exportaciones se generan localmente en `~/.local_data_agent/exports`.

## Tests

```bash
python -m pytest
```
