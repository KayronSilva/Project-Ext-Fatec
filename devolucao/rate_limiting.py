"""
Rate Limiting - Proteção contra abuso de endpoints AJAX.

Este módulo fornece decorators pré-configurados para limitar requisições
por usuário em endpoints críticos.

Instalado: django-ratelimit 4.1.0

Exemplo:
    from devolucao.rate_limiting import rate_limit_ajax

    @rate_limit_ajax('60/h')  # 60 por hora por usuário
    @login_required
    def buscar_cliente(request):
        ...
"""

from django_ratelimit.decorators import ratelimit
from django.http import JsonResponse
from functools import wraps
from devolucao.logging_utils import log_error


# Configurações padrão por endpoint
RATE_LIMITS = {
    'buscar_cliente': '60/h',          # 60 buscas/hora
    'buscar_notas_cliente': '120/h',   # 120 buscas/hora
    'buscar_itens_nota': '120/h',      # 120 buscas/hora
    'perfil': '30/h',                  # 30 acessos/hora (alta privacidade)
    'perfil_salvar': '10/h',           # 10 atualizações/hora (proteção contra spam)
}


def rate_limit_ajax(rate_str, key='user'):
    """
    Decorator para rate limiting em endpoints AJAX.

    Args:
        rate_str (str): Taxa de limite (ex: '60/h', '10/m')
        key (str): Chave para rate limiting ('user', 'ip')

    Returns:
        Função decorada que retorna 429 se ultrapassar limite

    Exemplo:
        @rate_limit_ajax('60/h')
        @login_required
        def meu_endpoint(request):
            ...
    """
    def decorator(view_func):
        @ratelimit(key=key, rate=rate_str, method='GET')
        def wrapped_view(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as exc:
                # Log de erro
                log_error('ajax_endpoint.error',
                    error=exc,
                    endpoint=view_func.__name__,
                    usuario_id=request.user.id if request.user.is_authenticated else None,
                )
                # Retornar erro genérico (não expor detalhes)
                return JsonResponse(
                    {'erro': 'Erro ao processar requisição'},
                    status=500
                )

        return wrapped_view

    return decorator


def rate_limit_write(rate_str, key='user'):
    """
    Decorator para rate limiting em requisições POST/PUT/DELETE.

    Args:
        rate_str (str): Taxa de limite (ex: '10/h')
        key (str): Chave para rate limiting ('user', 'ip')
    """
    def decorator(view_func):
        @ratelimit(key=key, rate=rate_str, method=['POST', 'PUT', 'DELETE'])
        def wrapped_view(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as exc:
                log_error('write_endpoint.error',
                    error=exc,
                    endpoint=view_func.__name__,
                    method=request.method,
                    usuario_id=request.user.id if request.user.is_authenticated else None,
                )
                return JsonResponse(
                    {'erro': 'Erro ao processar requisição'},
                    status=500
                )

        return wrapped_view

    return decorator


# Decorators pré-configurados por endpoint
def protect_buscar_cliente(view_func):
    """Protege endpoint buscar_cliente."""
    return rate_limit_ajax(RATE_LIMITS['buscar_cliente'])(view_func)


def protect_buscar_notas(view_func):
    """Protege endpoint buscar_notas_cliente."""
    return rate_limit_ajax(RATE_LIMITS['buscar_notas_cliente'])(view_func)


def protect_buscar_itens(view_func):
    """Protege endpoint buscar_itens_nota."""
    return rate_limit_ajax(RATE_LIMITS['buscar_itens_nota'])(view_func)


def protect_perfil_get(view_func):
    """Protege GET ao perfil."""
    return rate_limit_ajax(RATE_LIMITS['perfil'])(view_func)


def protect_perfil_save(view_func):
    """Protege POST ao perfil (salvamento)."""
    return rate_limit_write(RATE_LIMITS['perfil_salvar'])(view_func)


# ─────────────────────────────────────────────────────
# GUIA DE INTEGRAÇÃO EM VIEWS
# ─────────────────────────────────────────────────────

"""
PASSO 1: Importar decorators

    from devolucao.rate_limiting import (
        protect_buscar_cliente,
        protect_buscar_notas,
        protect_buscar_itens,
        protect_perfil_get,
        protect_perfil_save,
    )

PASSO 2: Adicionar ao topo de cada view protegida

    @protect_buscar_cliente
    @login_required
    def buscar_cliente(request):
        ...

    @protect_buscar_notas
    @login_required
    def buscar_notas_cliente(request):
        ...

    @protect_perfil_get
    @login_required
    def perfil(request):
        ...

PASSO 3: Testar

    # Fazer 61 requisições em 1 hora → receber 429 Too Many Requests
    for i in range(61):
        response = requests.get('/ajax/buscar-cliente/?documento=123')
        print(response.status_code)  # Último será 429

COMPORTAMENTO:

    Status 200: Requisição aceita, dentro do limite
    Status 429: Rate limit excedido, esperar antes de tentar novamente

    Header de resposta:
    - X-RateLimit-Limit: 60
    - X-RateLimit-Remaining: 45
    - X-RateLimit-Reset: 1646409600

CONFIGURAÇÕES RECOMENDADAS:

    Leitura (GET):
    - buscar_cliente: 60/h (1 por minuto)
    - buscar_notas: 120/h (2 por minuto)
    - buscar_itens: 120/h (2 por minuto)

    Escrita (POST/PUT):
    - perfil_salvar: 10/h (10 atualizações/hora = 1 a cada 6 min)
    - criar_devolucao: 20/h (20 devoluções/hora = 1 a cada 3 min)

CUSTOMIZAR:

    Se quiser outras taxas, modifique RATE_LIMITS:

    RATE_LIMITS = {
        'seu_endpoint': '50/h',  # 50 requisições por hora
        'outro_endpoint': '5/m',  # 5 requisições por minuto
    }

    Ou use @rate_limit_ajax() diretamente:

    @rate_limit_ajax('30/h')
    @login_required
    def seu_endpoint(request):
        ...
"""
