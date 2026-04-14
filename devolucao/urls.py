from django.urls import path
from . import views

urlpatterns = [
    # ── Autenticação ──────────────────────────────────────
    path('login/',       views.login_cliente_view, name='login'),
    path('admin-login/', views.login_admin_view,   name='login_admin'),
    path('cadastro/',    views.cadastro_view,       name='cadastro'),
    path('logout/',      views.logout_view,         name='logout'),

    # ── App principal (cliente) ───────────────────────────
    path('',           views.acompanhar_devolucoes, name='acompanhar_devolucoes'),
    path('devolucao/', views.tela_devolucao,        name='tela_devolucao'),
    path('devolucao/<int:devolucao_id>/excluir/', views.excluir_devolucao_cliente, name='excluir_devolucao_cliente'),
    path('minhas-compras/', views.minhas_compras, name='minhas_compras'),
    

    # ── AJAX ──────────────────────────────────────────────
    path('ajax/perfil/',               views.perfil_dados,         name='perfil_dados'),
    path('ajax/perfil/salvar/',        views.perfil_salvar,        name='perfil_salvar'),
    path('ajax/buscar-cliente/',       views.buscar_cliente,       name='buscar_cliente'),
    path('ajax/buscar-notas-cliente/', views.buscar_notas_cliente, name='buscar_notas_cliente'),
    path('ajax/buscar-itens-nota/',    views.buscar_itens_nota,    name='buscar_itens_nota'),
    
    # ── AJAX (Nova API com ClienteVinculado) ──────────────
    path('ajax/buscar-cliente-vinculado/',                  views.buscar_cliente_vinculado,                  name='buscar_cliente_vinculado'),
    path('ajax/buscar-notas-cliente-vinculado/',            views.buscar_notas_cliente_vinculado,            name='buscar_notas_cliente_vinculado'),
    path('ajax/buscar-itens-nota-cliente-vinculado/',       views.buscar_itens_nota_cliente_vinculado,       name='buscar_itens_nota_cliente_vinculado'),
    path('ajax/buscar-notas-filtro-cliente-vinculado/',     views.buscar_notas_por_filtro_cliente_vinculado, name='buscar_notas_filtro_cliente_vinculado'),
    path('ajax/nota/<int:nota_id>/detalhes/', views.ajax_detalhes_nota, name='ajax_detalhes_nota'),
    
    # ── Painel Administrativo ─────────────────────────────
    path('painel/',                                      views.painel_admin,               name='painel_admin'),
    path('painel/devolucao/<int:devolucao_id>/status/', views.atualizar_status_devolucao, name='atualizar_status_devolucao'),
    path('painel/configuracoes/salvar/',                views.salvar_configuracoes,       name='salvar_configuracoes'),
    path('painel/devolucao/<int:devolucao_id>/obs-interna/',
     views.salvar_observacao_interna,
     name='salvar_observacao_interna'),
    path('painel/vendas/', views.portal_vendas, name='portal_vendas'),

    # ── Gestão de Usuários ────────────────────────────────
    path('painel/usuarios/',                          views.gestao_usuarios, name='gestao_usuarios'),
    path('painel/usuarios/criar/',                    views.usuario_criar,   name='usuario_criar'),
    path('painel/usuarios/<int:usuario_id>/editar/',  views.usuario_editar,  name='usuario_editar'),
    path('painel/usuarios/<int:usuario_id>/excluir/', views.usuario_excluir, name='usuario_excluir'),

    # ── Gerenciamento de Clientes Vinculados ──────────────
    path('ajax/usuarios/<int:usuario_id>/clientes-vinculados/',       views.ajax_listar_clientes_vinculados,    name='ajax_listar_clientes_vinculados'),
    path('ajax/usuarios/<int:usuario_id>/clientes-disponiveis/',      views.ajax_listar_clientes_disponiveis,   name='ajax_listar_clientes_disponiveis'),
    path('ajax/usuarios/<int:usuario_id>/vincular-cliente/',          views.ajax_vincular_cliente,              name='ajax_vincular_cliente'),
    path('ajax/usuarios/<int:usuario_id>/clientes-vinculados/<int:cliente_vinculado_id>/remover/', views.ajax_desvinculador_cliente, name='ajax_desvinculador_cliente'),
    path('ajax/usuarios/<int:usuario_id>/clientes-vinculados/<int:cliente_vinculado_id>/toggle/', views.ajax_toggle_cliente_ativo, name='ajax_toggle_cliente_ativo'),

    # ── Importação de Notas Fiscais ───────────────────────
    path('painel/importar/',              views.importar_notas,     name='importar_notas'),
    path('painel/importar/preview-xml/',  views.preview_xml,        name='preview_xml'),
    path('painel/importar/xml/',          views.importar_xml,       name='importar_xml'),
    path('painel/importar/erp/testar/',   views.testar_conexao_erp, name='testar_conexao_erp'),
    path('painel/importar/erp/buscar/',   views.buscar_nota_erp,    name='buscar_nota_erp'),
    path('painel/importar/erp/importar/', views.importar_erp,       name='importar_erp'),

    # ── Busca Avançada (NEW) ──────────────────────────────
    path('painel/busca-avancada/',        views.busca_avancada,     name='busca_avancada'),
    path('ajax/busca-avancada/',          views.busca_avancada_ajax, name='busca_avancada_ajax'),

    # ── Chat Simples (NEW) ────────────────────────────────
    path('devolucao/<int:devolucao_id>/chat/',    views.chat_view,        name='chat_view'),
    path('ajax/chat/<int:devolucao_id>/enviar/',  views.enviar_mensagem,  name='enviar_mensagem'),
    path('ajax/chat/<int:devolucao_id>/carregar/', views.carregar_mensagens, name='carregar_mensagens'),
]

