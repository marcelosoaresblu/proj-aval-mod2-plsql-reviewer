"""
Módulo de observabilidade para o agente revisor de PL/SQL.

Fornece:
- Logs estruturados (JSON)
- Rastreamento (trace) com correlation IDs
- Métricas de desempenho
- Registros de auditoria

Esses sinais são correlacionados por correlation_id para facilitar debugging.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Contexto global para correlation_id
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class ObservabilityConfig:
    """Configurações de observabilidade."""

    LOG_LEVEL = logging.INFO
    METRICS_ENABLED = True
    AUDIT_LOG_ENABLED = True
    TRACE_ENABLED = True

    # Níveis de severidade para auditoria
    AUDIT_LEVELS = {
        "INFO": "INFO",
        "SUCCESS": "SUCCESS",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
    }


def set_correlation_id(correlation_id: str) -> None:
    """Define o correlation_id para a thread/atual execução."""
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Obtém o correlation_id atual."""
    return _correlation_id_var.get()


def generate_correlation_id() -> str:
    """Gera um novo correlation_id único."""
    return str(uuid.uuid4())


class StructuredLogger:
    """Logger estruturado em JSON com metadata."""

    def __init__(self, name: str = "plsql_reviewer"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(ObservabilityConfig.LOG_LEVEL)

        # Handler console
        handler = logging.StreamHandler()
        handler.setLevel(ObservabilityConfig.LOG_LEVEL)

        # Formatador simples (não usa placeholders para evitar conflitos com context vars)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)

        if not self.logger.handlers:
            self.logger.addHandler(handler)

    def _build_log(self, level: str, message: str, metadata: dict[str, Any] = None) -> dict[str, Any]:
        """Constrói um log estruturado."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "logger": "plsql_reviewer",
            "correlation_id": get_correlation_id(),
            "message": message,
            "metadata": metadata or {},
        }

    def info(self, message: str, metadata: dict[str, Any] = None) -> None:
        """Log de informação."""
        log_entry = self._build_log("INFO", message, metadata)
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))

    def warning(self, message: str, metadata: dict[str, Any] = None) -> None:
        """Log de aviso."""
        log_entry = self._build_log("WARNING", message, metadata)
        self.logger.warning(json.dumps(log_entry, ensure_ascii=False))

    def error(self, message: str, metadata: dict[str, Any] = None) -> None:
        """Log de erro."""
        log_entry = self._build_log("ERROR", message, metadata)
        self.logger.error(json.dumps(log_entry, ensure_ascii=False))

    def debug(self, message: str, metadata: dict[str, Any] = None) -> None:
        """Log de debug."""
        log_entry = self._build_log("DEBUG", message, metadata)
        self.logger.debug(json.dumps(log_entry, ensure_ascii=False))


class TraceManager:
    """Gerenciador de traces para rastreamento distribuído."""

    def __init__(self):
        self.spans: dict[str, dict[str, Any]] = {}
        self.logger = StructuredLogger("trace_manager")

    def start_span(self, operation: str, parent_span_id: str = None) -> str:
        """Inicia um novo span de trace."""
        span_id = str(uuid.uuid4())[:8]  # Short ID

        self.spans[span_id] = {
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "operation": operation,
            "start_time": time.time(),
            "end_time": None,
            "duration_ms": None,
            "status": "running",
            "attributes": {},
        }

        self.logger.debug(
            "Span started",
            metadata={"operation": operation, "span_id": span_id}
        )

        return span_id

    def end_span(self, span_id: str, status: str = "success", error: str = None) -> None:
        """Finaliza um span."""
        if span_id not in self.spans:
            return

        span = self.spans[span_id]
        span["end_time"] = time.time()
        span["duration_ms"] = round((span["end_time"] - span["start_time"]) * 1000, 2)
        span["status"] = status

        if error:
            span["error"] = error

        self.logger.debug(
            "Span ended",
            metadata={
                "operation": span["operation"],
                "span_id": span_id,
                "duration_ms": span["duration_ms"],
                "status": status,
            }
        )

    def get_trace(self, correlation_id: str = None) -> dict[str, Any]:
        """Obtém o trace completo."""
        correlation_id = correlation_id or get_correlation_id()

        return {
            "correlation_id": correlation_id,
            "spans": list(self.spans.values()),
        }

    def to_json(self) -> str:
        """Converte o trace para JSON."""
        return json.dumps(self.get_trace(get_correlation_id()), indent=2)


class MetricsCollector:
    """Coletor de métricas de desempenho."""

    def __init__(self):
        self.metrics: dict[str, dict[str, Any]] = {}
        self.logger = StructuredLogger("metrics")

    def count(self, name: str, value: int = 1) -> None:
        """Incrementa um contador."""
        if name not in self.metrics:
            self.metrics[name] = {"count": 0}
        self.metrics[name]["count"] += value
        self.logger.debug("Metric incremented", metadata={"name": name, "value": self.metrics[name]["count"]})

    def timing(self, name: str, duration_ms: float) -> None:
        """Registra uma métrica de tempo."""
        if name not in self.metrics:
            self.metrics[name] = {"durations": []}
        self.metrics[name]["durations"].append(duration_ms)

        self.logger.debug(
            "Timing recorded",
            metadata={"name": name, "duration_ms": duration_ms}
        )

    def gauge(self, name: str, value: float) -> None:
        """Registra um valor instantâneo."""
        self.metrics[name] = {"value": value}
        self.logger.debug("Gauge set", metadata={"name": name, "value": value})

    def get_metrics(self) -> dict[str, Any]:
        """Obtém todas as métricas."""
        result = {}

        for name, data in self.metrics.items():
            if "count" in data:
                result[name] = {"type": "counter", "value": data["count"]}
            elif "durations" in data:
                durations = data["durations"]
                result[name] = {
                    "type": "histogram",
                    "count": len(durations),
                    "sum_ms": round(sum(durations), 2),
                    "avg_ms": round(sum(durations) / len(durations), 2) if durations else 0,
                }
            elif "value" in data:
                result[name] = {"type": "gauge", "value": data["value"]}

        return result

    def to_json(self) -> str:
        """Converte métricas para JSON."""
        return json.dumps(self.get_metrics(), indent=2)


class AuditLogger:
    """Logger de auditoria para eventos de segurança."""

    def __init__(self):
        self.logger = StructuredLogger("audit")

    def log_event(
        self,
        event_type: str,
        user: str = "system",
        resource: str = None,
        action: str = None,
        status: str = "SUCCESS",
        details: dict[str, Any] = None,
    ) -> None:
        """Registra um evento de auditoria."""
        correlation_id = get_correlation_id()

        audit_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": correlation_id,
            "event_type": event_type,
            "user": user,
            "resource": resource,
            "action": action,
            "status": status,
            "details": details or {},
        }

        self.logger.info(
            f"Audit event: {event_type}",
            metadata=audit_entry
        )

    def log_security_event(
        self,
        event_type: str,
        details: dict[str, Any] = None,
    ) -> None:
        """Registra um evento de segurança."""
        self.log_event(
            event_type=event_type,
            user="system",
            resource="security",
            action=event_type,
            status="SUCCESS",
            details=details,
        )

    def log_access_denied(
        self,
        user: str,
        resource: str,
        reason: str,
    ) -> None:
        """Registra acesso negado."""
        self.log_event(
            event_type="ACCESS_DENIED",
            user=user,
            resource=resource,
            action="access",
            status="ERROR",
            details={"reason": reason},
        )

    def log_api_access(self, api_name: str, status: str) -> None:
        """Registra acesso a API externa."""
        self.log_event(
            event_type="API_ACCESS",
            user="system",
            resource=f"api:{api_name}",
            action="call",
            status=status,
            details={"api_name": api_name},
        )


# Instâncias globais
logger = StructuredLogger()
trace_manager = TraceManager()
metrics = MetricsCollector()
audit = AuditLogger()


def get_observability_context() -> dict[str, Any]:
    """Obtém o contexto completo de observabilidade."""
    return {
        "correlation_id": get_correlation_id(),
        "trace": trace_manager.get_trace(),
        "metrics": metrics.get_metrics(),
    }


def reset_observability() -> None:
    """Reseta o contexto de observabilidade."""
    _correlation_id_var.set(generate_correlation_id())
    trace_manager.spans.clear()
    metrics.metrics.clear()
