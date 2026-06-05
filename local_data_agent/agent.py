from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from .config import ConfigStore, LocalConnection
from .connectors import DataContext, DatabaseConnector, FolderConnector, get_connector
from .exports import ExportFormat, export_rows

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - dependency is optional at runtime
    ChatOpenAI = None  # type: ignore[assignment]


@dataclass(slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(slots=True)
class AgentResponse:
    message: str
    downloads: list[dict[str, str]]
    context: dict[str, Any]


class OfflineChatModel(BaseChatModel):
    """Deterministic fallback model used when no LLM credentials are configured."""

    @property
    def _llm_type(self) -> str:
        return "offline-local-data-agent"

    def _generate(self, messages: list[Any], stop: list[str] | None = None, run_manager: Any | None = None, **kwargs: Any) -> ChatResult:
        user_message = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        content = (
            "Estoy funcionando en modo local sin API key. Puedo describir la estructura detectada, "
            "generar reportes básicos y preparar exportaciones locales. Pedido recibido: " + user_message
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def build_llm() -> BaseChatModel:
    if os.environ.get("OPENAI_API_KEY") and ChatOpenAI is not None:
        return ChatOpenAI(model=os.environ.get("LOCAL_DATA_AGENT_MODEL", "gpt-4o-mini"), temperature=0.1)
    return OfflineChatModel()


class LocalDataAgent:
    """LangChain-powered orchestration over local data sources."""

    def __init__(self, store: ConfigStore | None = None, llm: BaseChatModel | None = None) -> None:
        self.store = store or ConfigStore()
        self.llm = llm or build_llm()

    def answer(self, prompt: str, history: list[ChatMessage] | None = None, export_format: ExportFormat | None = None) -> AgentResponse:
        connection = self.store.load_connection()
        if connection is None:
            return AgentResponse(
                message="Primero configurá una base de datos o carpeta local desde el formulario inicial.",
                downloads=[],
                context={},
            )
        connector = get_connector(connection)
        data_context = connector.describe()
        downloads: list[dict[str, str]] = []
        computed = self._compute_local_answer(prompt, connector, data_context)
        if export_format:
            rows = self._rows_for_export(connector, data_context)
            export_path = export_rows(rows, export_format, self.store.exports_dir)
            downloads.append({"name": export_path.name, "url": f"/api/downloads/{export_path.name}"})
        llm_message = self._invoke_llm(prompt, history or [], connection, data_context, computed)
        return AgentResponse(message=llm_message, downloads=downloads, context={"summary": data_context.summary, "computed": computed})

    def _invoke_llm(
        self,
        prompt: str,
        history: list[ChatMessage],
        connection: LocalConnection,
        data_context: DataContext,
        computed: dict[str, Any],
    ) -> str:
        safe_payload = {
            "connection": connection.public_dict(),
            "data_context": asdict(data_context),
            "local_computations": computed,
        }
        messages: list[Any] = [
            SystemMessage(
                content=(
                    "Sos un agente analista de datos local. Nunca pidas ni reveles contraseñas, URIs completas "
                    "o rutas absolutas. Explicá en español claro. Si hacen falta consultas, proponé SQL SELECT "
                    "seguro o pasos locales. Contexto sanitizado: " + json.dumps(safe_payload, ensure_ascii=False)[:12000]
                )
            )
        ]
        for item in history[-8:]:
            messages.append(HumanMessage(content=item.content) if item.role == "user" else SystemMessage(content="Respuesta previa: " + item.content))
        messages.append(HumanMessage(content=prompt))
        result = self.llm.invoke(messages)
        return str(result.content)

    def _compute_local_answer(self, prompt: str, connector: DatabaseConnector | FolderConnector, context: DataContext) -> dict[str, Any]:
        lowered = prompt.lower()
        computed: dict[str, Any] = {}
        if "estructura" in lowered or "schema" in lowered or "tablas" in lowered:
            computed["structure"] = context.details
        if isinstance(connector, DatabaseConnector) and ("iva" in lowered or "impuesto" in lowered):
            computed["iva"] = self._sum_numeric_column(connector, context, "iva")
        if isinstance(connector, FolderConnector) and ("muestra" in lowered or "resumen" in lowered or "sirve" in lowered):
            computed["samples"] = connector.sample_text()
        return computed

    def _sum_numeric_column(self, connector: DatabaseConnector, context: DataContext, column_hint: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for table in context.details.get("tables", []):
            columns = [column["name"] for column in table.get("columns", [])]
            matches = [column for column in columns if column_hint in column.lower()]
            for column in matches:
                table_name = table["name"]
                rows = connector.run_readonly_query(f'SELECT SUM("{column}") AS total_{column} FROM "{table_name}"', limit=1)
                results.append({"table": table_name, "column": column, "rows": rows})
        return results

    def _rows_for_export(self, connector: DatabaseConnector | FolderConnector, context: DataContext) -> list[dict[str, Any]]:
        if isinstance(connector, DatabaseConnector):
            for table in context.details.get("tables", []):
                return connector.run_readonly_query(f'SELECT * FROM "{table["name"]}"', limit=5000)
            return []
        return context.details.get("files", [])


@tool
def sanitize_secret(text: str) -> str:
    """Remove obvious passwords and tokens from text before any LLM prompt."""
    return re.sub(r"(password|token|secret)=([^\s&]+)", r"\1=***", text, flags=re.IGNORECASE)
