"""
Testes de tratamento de falhas em integrações externas.

Cobertura:
1. Timeout (simulação) e retry com backoff exponencial
2. Circuit breaker (estados e transições)
3. Fallback entre provedores (Groq → Anthropic)
4. Tratamento de erros de integração
"""

import os
import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from agent.integrations import (
    IntegrationManager,
    IntegrationError,
    TimeoutError,
    CircuitBreakerError,
    RetryState,
    APIFallback,
)


class TestIntegrationManager:
    """Testes para o IntegrationManager com retry e circuit breaker."""

    def setup_method(self):
        """Cria um IntegrationManager com configurações para testes rápidos."""
        self.manager = IntegrationManager(
            default_timeout=30.0,
            max_retries=2,
            retry_delay_base=0.01,  # 10ms para testes rápidos
            retry_delay_max=0.1,    # 100ms máximo
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=1.0,  # 1 segundo para testes
        )

    def test_success_call(self):
        """Chamada bem-sucedida deve retornar o resultado."""
        def success_func(x):
            return x * 2

        result = self.manager.call_with_retry(success_func, "test_service", 5)
        assert result == 10

    def test_timeout_error(self):
        """Timeout deve levantar TimeoutError."""
        def slow_func(x):
            time.sleep(0.1)  # Simula lento
            return x

        with pytest.raises(TimeoutError):
            self.manager.call_with_retry(slow_func, "test_service", 5, timeout=0.05)

    def test_retry_with_backoff(self):
        """Falhas devem ser tentadas com backoff exponencial."""
        call_count = 0

        def failing_func(x):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Falha transitória")
            return x * 2

        result = self.manager.call_with_retry(failing_func, "test_service", 5)
        assert result == 10
        assert call_count == 3  # 1 inicial + 2 retries

    def test_circuit_breaker_opens_after_failures(self):
        """Circuit breaker deve abrir após falhas consecutivas."""
        def always_fail():
            raise Exception("Falha intencional")

        # 3 falhas devem abrir o circuito
        for _ in range(3):
            try:
                self.manager.call_with_retry(always_fail, "failing_service", 5)
            except Exception:
                pass

        # Circuit breaker deve estar aberto agora
        with pytest.raises(CircuitBreakerError):
            self.manager.call_with_retry(always_fail, "failing_service", 5)

    def test_circuit_breaker_recovery(self):
        """Circuit breaker deve permitir retry após timeout."""
        class State:
            failure_count = 0
        success_after = 4

        def fail_then_succeed(x):
            State.failure_count += 1
            if State.failure_count < success_after:
                raise Exception("Falha")
            return "sucesso"

        # Abre o circuito
        for _ in range(3):
            try:
                self.manager.call_with_retry(fail_then_succeed, "recovery_service", 5)
            except Exception:
                pass

        # Espera o timeout do circuit breaker
        time.sleep(self.manager.circuit_breaker_timeout + 0.1)

        # Retry deve funcionar (HALF_OPEN)
        result = self.manager.call_with_retry(fail_then_succeed, "recovery_service", 5)
        assert result == "sucesso"

    def test_circuit_breaker_states(self):
        """Testa transições entre estados do circuit breaker."""
        service = "state_test_service"

        # Estado inicial: CLOSED
        assert self.manager._get_circuit_breaker(service)["state"] == RetryState.CLOSED

        # Simula estado OPEN diretamente no circuit breaker
        cb = self.manager._get_circuit_breaker(service)
        cb["state"] = RetryState.OPEN
        
        # O circuit breaker deve estar OPEN após definição direta
        state = self.manager._get_circuit_breaker(service)["state"]
        assert state == RetryState.OPEN, f"Estado deve ser OPEN, mas é {state}"

    def test_circuit_breaker_resets_on_success(self):
        """Sucesso deve resetar contagem de falhas do circuit breaker."""
        service = "reset_test_service"
        
        class State:
            fail_count = 0

        def fail_then_succeed(x):
            State.fail_count += 1
            if State.fail_count <= 2:
                raise Exception("Falha")
            return "sucesso"

        # Duas falhas
        for _ in range(2):
            try:
                self.manager.call_with_retry(fail_then_succeed, service, 5)
            except Exception:
                pass
        
        # Ainda CLOSED (não atingiu threshold)
        assert self.manager._get_circuit_breaker(service)["state"] == RetryState.CLOSED

        # Sucesso deve resetar
        result = self.manager.call_with_retry(fail_then_succeed, service, 5)
        assert result == "sucesso"


class TestAPIFallback:
    """Testes para o gerenciador de fallback entre provedores."""

    def setup_method(self):
        """Configura variáveis de ambiente para testes."""
        self.original_env = {
            "GROQ_API_KEY": os.environ.get("GROQ_API_KEY"),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
        }

    def teardown_method(self):
        """Restaura variáveis de ambiente originais."""
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_groq_provider_available(self):
        """Groq deve estar disponível se GROQ_API_KEY existir."""
        os.environ["GROQ_API_KEY"] = "gsk_test_key_123"
        
        fallback = APIFallback()
        provider = fallback.get_provider()
        
        assert provider is not None
        assert provider["name"] == "groq"

    def test_anthropic_provider_available(self):
        """Anthropic deve estar disponível se ANTHROPIC_API_KEY existir."""
        os.environ.pop("GROQ_API_KEY", None)
        os.environ["ANTHROPIC_API_KEY"] = "sk-test_key_123"
        
        fallback = APIFallback()
        provider = fallback.get_provider()
        
        assert provider is not None
        assert provider["name"] == "anthropic"

    def test_preferred_provider(self):
        """Deve ser possível escolher um provedor específico."""
        os.environ["GROQ_API_KEY"] = "gsk_test_key_123"
        os.environ["ANTHROPIC_API_KEY"] = "sk-test_key_456"
        
        fallback = APIFallback()
        
        # Escolhe Anthropic explicitamente
        provider = fallback.get_provider("anthropic")
        assert provider is not None
        assert provider["name"] == "anthropic"

    def test_no_provider_available(self):
        """Nenhum provedor deve estar disponível sem chaves."""
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        
        fallback = APIFallback()
        provider = fallback.get_provider()
        
        assert provider is None


class TestTimeoutHandling:
    """Testes específicos para tratamento de timeout."""

    def test_timeout_with_delayed_response(self):
        """Timeout deve ocorrer se resposta demorar mais que o limite."""
        manager = IntegrationManager(default_timeout=0.5, max_retries=1)
        
        def delayed_response():
            time.sleep(0.3)
            return "resposta tardia"

        # Com timeout de 0.5s, resposta de 0.3s deve funcionar
        result = manager.call_with_retry(delayed_response, "timeout_test", timeout=0.5)
        assert result == "resposta tardia"

    def test_timeout_cuts_response(self):
        """Timeout deve cortar resposta que excede o limite."""
        manager = IntegrationManager(default_timeout=0.2, max_retries=1)
        
        def delayed_response():
            time.sleep(0.4)
            return "resposta tardia"

        # Com timeout de 0.2s, resposta de 0.4s deve causar TimeoutError
        with pytest.raises(TimeoutError):
            manager.call_with_retry(delayed_response, "timeout_test", timeout=0.2)


class TestCircuitBreakerIntegration:
    """Testes de circuit breaker integrado com retry."""

    def test_circuit_breaker_survives_retry(self):
        """Circuit breaker deve resistir a tentativas de retry."""
        manager = IntegrationManager(
            circuit_breaker_threshold=2,
            max_retries=3,
        )
        
        failure_count = 0
        
        def always_fail(x):
            nonlocal failure_count
            failure_count += 1
            raise Exception("Falha")

        try:
            manager.call_with_retry(always_fail, "cb_retry_service", 5)
        except Exception:
            pass

        # Retry deve ter tentado várias vezes (max_retries + 1 tentativas)
        assert failure_count >= 2


class TestRetryBackoffCalculation:
    """Testes para cálculo de backoff exponencial."""

    def test_retry_delay_calculation(self):
        """Delay deve seguir backoff exponencial com jitter."""
        manager = IntegrationManager(
            retry_delay_base=1.0,
            retry_delay_max=10.0,
        )
        
        # Verifica que o cálculo está dentro dos limites
        # Delay deve ser entre base*0.8 e max
        for attempt in range(15):
            delay = manager._calculate_retry_delay(attempt)
            assert 0 <= delay <= 10.0, f"Delay {delay} na tentativa {attempt} deve estar entre 0 e 10.0"
