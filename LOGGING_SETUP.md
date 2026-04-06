# GUIA DE INTEGRAÇÃO: LOGGING ESTRUTURADO NAS VIEWS
# ================================================
#
# Este arquivo mostra como adicionar logging estruturado às views existentes.
#
# PASSO 1: Importar as utilities de logging
# -------------------------------------------
# No topo do arquivo devolucao/views.py, adicione:
#
#    from devolucao.logging_utils import log_action, log_error, get_client_ip


# EXEMPLO 1: Logar ações de criação de devolução
# -----------------------------------------------
# Em _handle_enviar(), após criar a devolução, adicione:
#
#    from devolucao.logging_utils import log_action
#
#    # Após: devolucao = Devolucao.objects.create(...)
#    log_action('devolucao.criada',
#        devolucao_id=devolucao.pk,
#        cliente_id=cliente.id,
#        nota_id=nota.pk,
#        quantidade_itens=len(produtos),
#        usuario_id=request.user.id,
#        ip=get_client_ip(request),
#    )


# EXEMPLO 2: Logar buscas de cliente
# ------------------------------------
# Em buscar_cliente(), após encontrar o cliente, adicione:
#
#    from devolucao.logging_utils import log_action
#
#    log_action('cliente.buscado',
#        documento=documento[:4] + '***',  # Mascarar sensitive data
#        usuario_id=request.user.id,
#        ip=get_client_ip(request),
#        encontrado=True,
#    )


# EXEMPLO 3: Logar erros
# -----------------------
# Em qualquer ponto de erro, use:
#
#    from devolucao.logging_utils import log_error
#
#    try:
#        # alguma operação
#    except ValueError as e:
#        log_error('validacao.falhou',
#            error=e,
#            campo='quantidade',
#            usuario_id=request.user.id,
#        )


# EXEMPLO 4: Logar atualização de perfil
# ----------------------------------------
# Em perfil_salvar(), adicione:
#
#    log_action('usuario.perfil.atualizado',
#        usuario_id=request.user.id,
#        campos_alterados=['email', 'telefone'],
#        ip=get_client_ip(request),
#    )


# EXEMPLO 5: Logar login e logout
# ---------------------------------
# Em login_view(), após autentar:
#
#    log_action('usuario.login',
#        usuario_id=user.id,
#        email=user.email[:4] + '***@...',  # Mascarar
#        ip=get_client_ip(request),
#    )
#
# Em logout_view():
#
#    log_action('usuario.logout',
#        usuario_id=request.user.id,
#        ip=get_client_ip(request),
#    )


# VISUALIZAR LOGS
# ===============
#
# Logs estruturados em JSON estarão em:
#    - logs/app.log       (todos os eventos INFO+)
#    - logs/errors.log    (apenas erros)
#
# Exemplo de log em app.log:
# {
#     "event": "devolucao.criada",
#     "timestamp": "2026-03-04T22:30:15.123456Z",
#     "devolucao_id": 42,
#     "cliente_id": 12,
#     "usuario_id": 5,
#     "quantidade_itens": 3
# }


# QUERYING LOGS COM JQ (Linux/Mac)
# ==================================
#
# Buscar todas as devoluções criadas:
#    cat logs/app.log | jq 'select(.event == "devolucao.criada")'
#
# Buscar erros de um usuário específico:
#    cat logs/errors.log | jq 'select(.usuario_id == 5)'
#
# Contar devoluções por dia:
#    cat logs/app.log | jq -r '.timestamp | split("T")[0]' | sort | uniq -c


# BOAS PRÁTICAS
# ==============
#
# 1. Sempre mascare dados sensíveis:
#    RUIM:  log_action('user.login', email=user.email)
#    BOM:   log_action('user.login', email=user.email[:4] + '***')
#
# 2. Use event names descritivos e hierárquicos:
#    RUIM:  'evento'
#    BOM:   'devolucao.criada', 'cliente.buscado', 'usuario.perfil.atualizado'
#
# 3. Inclua context relevante mas não excessivo:
#    RUIM:  log_action('devolucao.criada', **dict(request.POST))
#    BOM:   log_action('devolucao.criada', devolucao_id=..., usuario_id=...)
#
# 4. Use try/except com log_error para operações críticas:
#    try:
#        resultado = operacao_critica()
#    except Exception as e:
#        log_error('operacao_critica.falhou', error=e, contexto=...)
#        # Tratar erro
#
# 5. Inclua IP do cliente para auditoria:
#    log_action('evento.importante', ip=get_client_ip(request), ...)


# PRÓXIMAS ETAPAS
# ================
#
# 1. Adicione log_action calls em todos os endpoints AJAX (buscar_*, perfil_*)
# 2. Adicione log_error calls em handlers de erro
# 3. Configure rotação de logs em produção (já configurado em settings.py)
# 4. Configure ferramenta de harvesting de logs (Datadog, ELK, etc)
