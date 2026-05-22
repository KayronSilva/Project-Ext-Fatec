"""
Utilitários para logging estruturado com structlog.

Exemplo de uso:
    from devolucao.logging_utils import log_action, log_error

    log_action('cliente.criado', cliente_id=123, email='user@example.com')
    log_error('pagamento.falha', erro='Timeout', usuario_id=456)
"""

import structlog
import json
from functools import wraps
from django.http import JsonResponse

logger = structlog.get_logger()


def log_action(event_name, **context):
    """
    Log uma ação estruturada.

    Args:
        event_name (str): Nome do evento (ex: 'cliente.criado', 'devolucao.aprovada')
        **context: Dados contextuais a serem registrados

    Exemplo:
        log_action('devolucao.criada',
            devolucao_id=123,
            cliente_id=456,
            quantidade_itens=5,
            usuario_id=789
        )
    """
    logger.info(event_name, **context)


def log_error(event_name, error=None, **context):
    """
    Log um erro estruturado.

    Args:
        event_name (str): Nome do evento
        error (Exception ou str): Detalhes do erro
        **context: Dados contextuais adicionais

    Exemplo:
        log_error('pdf.extraction.failed',
            error='Regex não encontrou padrão',
            arquivo='nota_001.pdf',
            usuario_id=123
        )
    """
    if isinstance(error, Exception):
        context['error'] = str(error)
        context['error_type'] = type(error).__name__
    else:
        context['error'] = error

    logger.error(event_name, **context)


def log_view_request(view_func):
    """
    Decorator para logar requisições HTTP em pontos críticos.

    Uso:
        @log_view_request
        @login_required
        def minha_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Log da requisição
        user_id = request.user.id if request.user.is_authenticated else None
        log_action(f'view.{view_func.__name__}.requested',
            method=request.method,
            path=request.path,
            usuario_id=user_id,
            ip=get_client_ip(request),
        )

        # Executar view
        try:
            response = view_func(request, *args, **kwargs)

            # Log de sucesso
            status_code = response.status_code if hasattr(response, 'status_code') else 200
            log_action(f'view.{view_func.__name__}.success',
                method=request.method,
                path=request.path,
                usuario_id=user_id,
                status_code=status_code,
            )

            return response

        except Exception as exc:
            log_error(f'view.{view_func.__name__}.error',
                error=exc,
                method=request.method,
                path=request.path,
                usuario_id=user_id,
            )
            raise

    return wrapper


def get_client_ip(request):
    """
    Obter IP do cliente da requisição.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_model_action(action, model_name, instance_id, **context):
    """
    Log de ações em modelos (CREATE, UPDATE, DELETE).

    Uso:
        log_model_action('CREATE', 'Devolucao', devolucao.id,
            cliente_id=cliente.id, usuario_id=request.user.id)
    """
    event_name = f'model.{model_name.lower()}.{action.lower()}'
    log_action(event_name, instance_id=instance_id, **context)


# Alias para compatibilidade
info = log_action
error = log_error
