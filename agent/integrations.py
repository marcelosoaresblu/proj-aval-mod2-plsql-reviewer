"""
Módulo de gerenciamento de integrações externas com tratamento de falhas.

Fornece:
- Timeout configurável para chamadas externas
- Retry limitado com backoff exponencial
- Fallback para APIs alternativas
- Circuit breaker pattern

O tratamento de falhas é aplicado às integrações:
- API Groq (LLM)
- API Anthropic (LLM alternativo)
- RAG (recuperação de contexto)
- Best practices (base local/serviço externo)
"""

import os
import time
import random
from typing import Callable, Any, Optional, Type, Union
from functools import wraps
from enum import IntEnum
from typing import Dict, List


class RetryState(IntEnum):
    """Estados do circuit breaker."""
    CLOSED = 0      # Normal, requisições passam
    OPEN = 1        # Falhou, requisições bloqueadas
    HALF_OPEN = 2   # Testando se recuperou


class IntegrationError(Exception):
    """Erro específico de integração externa."""
    pass


class TimeoutError(IntegrationError):
    """Erro de timeout na integração externa."""
    pass


class CircuitBreakerError(IntegrationError):
    """Erro quando circuit breaker está aberto."""
    pass


class IntegrationManager:
    """Gerenciador de integrações externas com tratamento de falhas."""
    
    def __init__(
        self,
        default_timeout: float = 30.0,  # 30 segundos
        max_retries: int = 2,
        retry_delay_base: float = 1.0,  # 1 segundo
        retry_delay_max: float = 10.0,  # 10 segundos
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 60.0,  # 60 segundos
    ):
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.retry_delay_max = retry_delay_max
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        
        # Estados dos circuit breakers por serviço
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
    
    def _get_circuit_breaker(self, service: str) -> Dict[str, Any]:
        """Obtém o estado do circuit breaker para um serviço."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = {
                "state": RetryState.CLOSED,
                "failure_count": 0,
                "last_failure_time": None,
                "half_open_test": False,
            }
        return self._circuit_breakers[service]
    
    def _check_circuit_breaker(self, service: str) -> bool:
        """Verifica se o circuit breaker permite a requisição."""
        cb = self._get_circuit_breaker(service)
        
        if cb["state"] == RetryState.CLOSED:
            return True
        
        if cb["state"] == RetryState.OPEN:
            # Verifica se já passou o timeout
            if cb["last_failure_time"]:
                elapsed = time.time() - cb["last_failure_time"]
                if elapsed >= self.circuit_breaker_timeout:
                    cb["state"] = RetryState.HALF_OPEN
                    cb["half_open_test"] = False
                    return True
            return False
        
        if cb["state"] == RetryState.HALF_OPEN:
            # Permite uma requisição de teste
            if not cb["half_open_test"]:
                cb["half_open_test"] = True
                return True
            return False
        
        return False
    
    def _record_success(self, service: str) -> None:
        """Registra sucesso no circuit breaker."""
        cb = self._get_circuit_breaker(service)
        cb["failure_count"] = 0
        if cb["state"] == RetryState.HALF_OPEN:
            cb["state"] = RetryState.CLOSED
            cb["half_open_test"] = False
    
    def _record_failure(self, service: str) -> None:
        """Registra falha no circuit breaker."""
        cb = self._get_circuit_breaker(service)
        cb["failure_count"] += 1
        cb["last_failure_time"] = time.time()
        
        if cb["failure_count"] >= self.circuit_breaker_threshold:
            cb["state"] = RetryState.OPEN
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calcula delay com backoff exponencial."""
        delay = self.retry_delay_base * (2 ** attempt)
        delay = min(delay, self.retry_delay_max)
        # Adiciona jitter para evitar thundering herd
        delay *= (0.8 + random.uniform(0, 0.4))
        return delay
    
    def call_with_retry(
        self,
        func: Callable,
        service: str,
        *args,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Any:
        """Chama uma função com retry e circuit breaker."""
        
        # Verifica circuit breaker
        if not self._check_circuit_breaker(service):
            raise CircuitBreakerError(
                f"Circuit breaker aberto para serviço '{service}'"
            )
        
        timeout = timeout or self.default_timeout
        
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                
                # Aplica timeout
                if timeout:
                    # Simulação de timeout (em produção, usar threading/async)
                    result = func(*args, **kwargs)
                    
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        raise TimeoutError(
                            f"Timeout excedido ({elapsed:.1f}s > {timeout}s)"
                        )
                else:
                    result = func(*args, **kwargs)
                
                # Sucesso
                self._record_success(service)
                return result
                
            except TimeoutError:
                self._record_failure(service)
                last_error = TimeoutError(f"Timeout na chamada ao serviço '{service}'")
                
            except Exception as e:
                self._record_failure(service)
                last_error = e
            
            # Se não for a última tentativa, espera antes de retry
            if attempt < self.max_retries:
                delay = self._calculate_retry_delay(attempt)
                time.sleep(delay)
        
        # Todas as tentativas falharam
        raise last_error


# Instância global do gerenciador
integration_manager = IntegrationManager()


def with_retry(service: str, timeout: Optional[float] = None):
    """Decorador para adicionar retry e circuit breaker a funções."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return integration_manager.call_with_retry(
                func, service, *args, timeout=timeout, **kwargs
            )
        return wrapper
    return decorator


# Fallback para múltiplos provedores de API

class APIFallback:
    """Gerenciador de fallback entre múltiplos provedores de API."""
    
    def __init__(self):
        self.providers: List[Dict[str, Any]] = []
        self._load_providers()
    
    def _load_providers(self) -> None:
        """Carrega provedores disponíveis."""
        # Groq (padrão)
        if os.getenv("GROQ_API_KEY"):
            self.providers.append({
                "name": "groq",
                "enabled": True,
                "api_key": os.getenv("GROQ_API_KEY"),
                "model": os.getenv("REVIEWER_MODEL", "llama-3.3-70b-versatile"),
            })
        
        # Anthropic (fallback)
        if os.getenv("ANTHROPIC_API_KEY"):
            self.providers.append({
                "name": "anthropic",
                "enabled": True,
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
                "model": "claude-3-5-sonnet-20240620",
            })
    
    def get_provider(self, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Obtém um provedor disponível."""
        if name:
            for provider in self.providers:
                if provider["name"] == name and provider["enabled"]:
                    return provider
            return None
        
        # Retorna o primeiro provedor disponível
        for provider in self.providers:
            if provider["enabled"]:
                return provider
        return None
    
    def get_all_providers(self) -> List[Dict[str, Any]]:
        """Obtém todos os provedores disponíveis."""
        return self.providers.copy()


api_fallback = APIFallback()
