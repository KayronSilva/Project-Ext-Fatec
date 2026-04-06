from django.shortcuts import render, redirect
from .forms import VerificacaoForm, DevolucaoForm
from .models import NotaFiscal, Devolucao, Produto, ItemNotaFiscal


def verificar_e_devolver(request):
    """
    View principal responsável por gerenciar o fluxo de **verificação de nota fiscal**
    e **registro de devoluções**.

    Essa função é o coração do processo de devolução: ela controla desde a 
    validação da nota fiscal, até a adição de produtos para devolução, 
    exclusão temporária de itens e gravação definitiva no banco de dados.

    ---
    Fluxo Geral:
        1. Verifica se uma nota fiscal é válida (CNPJ + número da nota)
        2. Exibe os itens associados à nota
        3. Permite selecionar produtos para devolução
        4. Armazena temporariamente os itens escolhidos na sessão
        5. Permite descartar ou confirmar o registro da devolução

    ---
    Parameters
    ----------
    request : HttpRequest
        Objeto padrão do Django que representa a requisição HTTP atual.
        Contém informações como método (GET/POST), dados de formulário,
        sessão do usuário, e variáveis de query string.

    ---
    Returns
    -------
    HttpResponse
    
        Retorna a renderização do template `verificar_e_devolver.html` com:
        - formulários de verificação e devolução
        - mensagens de status (sucesso/erro)
        - lista de itens da nota fiscal
        - lista temporária de devoluções (sessão)
    """

    # --- Reinicia a sessão se o usuário clicar no botão "resetar" ---
    # Remove da sessão os dados da nota e da lista temporária, reiniciando o fluxo.
    if request.GET.get("resetar") == "1":
        request.session.pop('nota_id', None)
        request.session.pop('itens_temp', None)
        return redirect("verificar_e_devolver")

    # Variáveis de controle usadas ao longo da view
    mensagens = []          # Lista de mensagens para feedback ao usuário
    nota = None             # Objeto da nota fiscal atual
    lista_temp = request.session.get('itens_temp', [])  # Itens temporários em sessão
    itens_nota = []         # Itens da nota fiscal consultada

    # --- Limpa a sessão se for o primeiro acesso (GET sem POST) ---
    if request.method == "GET" and not request.POST:
        request.session.pop('nota_id', None)
        request.session.pop('itens_temp', None)

    # --- Identifica qual ação o usuário executou através do botão clicado ---
    acao = (
        'verificacao-verificar' if 'verificacao-verificar' in request.POST else
        'adicionar-item' if 'adicionar-item' in request.POST else
        'descartar-itens' if 'descartar-itens' in request.POST else
        'finalizar' if 'finalizar' in request.POST else
        'registrar-devolucao' if 'registrar-devolucao' in request.POST else
        None
    )

    # ================================================================
    # ETAPA 1: Verificação da Nota Fiscal
    # ================================================================
    if acao == 'verificacao-verificar':
        # Cria o formulário de verificação com os dados enviados
        verificacao_form = VerificacaoForm(request.POST, prefix='verificacao')

        # Se o formulário for válido, armazena a nota e o cliente na sessão
        if verificacao_form.is_valid():
            nota = verificacao_form.cleaned_data['nota_fiscal']
            request.session['nota_id'] = nota.id
            request.session['itens_temp'] = []  # Limpa lista temporária

            # Busca os itens vinculados à nota
            itens_nota = ItemNotaFiscal.objects.filter(nota_fiscal=nota).select_related('produto')

            # Inicializa o formulário de devolução já vinculado à nota
            devolucao_form = DevolucaoForm(prefix='devolucao', nota_fiscal=nota)

            mensagens.append(
                f"Nota {nota.numero_nota} verificada com sucesso. "
                f"{itens_nota.count()} itens encontrados."
            )

        else:
            devolucao_form = None

    # ================================================================
    # ETAPA 2+: Fluxos seguintes (adicionar, descartar, registrar)
    # ================================================================
    else:
        # Recupera a nota armazenada na sessão, se houver
        nota_id = None
        if request.method == "POST" and acao != "verificacao-verificar":
            nota_id = request.session.get('nota_id')

        nota = NotaFiscal.objects.filter(id=nota_id).first() if nota_id else None

        # Formulário de verificação é exibido vazio (não revalida)
        verificacao_form = VerificacaoForm(prefix='verificacao')

        # Formulário de devolução — pode conter dados POST ou não
        devolucao_form = DevolucaoForm(request.POST or None, prefix='devolucao', nota_fiscal=nota)

        # Carrega os itens da nota fiscal, se existir uma nota associada
        itens_nota = ItemNotaFiscal.objects.filter(nota_fiscal=nota).select_related('produto') if nota else []

        # ------------------------------------------------------------
        # Ação: Adicionar item à lista temporária
        # ------------------------------------------------------------
        if acao == 'adicionar-item' and nota:
            if devolucao_form.is_valid():
                # Monta o dicionário do item para armazenar em sessão
                item = {
                    'produto_id': devolucao_form.cleaned_data['produto'].id,
                    'produto_nome': str(devolucao_form.cleaned_data['produto']),
                    'quantidade': devolucao_form.cleaned_data['quantidade_devolvida'],
                    'motivo': devolucao_form.cleaned_data['motivo'],
                    'observacao': devolucao_form.cleaned_data['observacao'],
                }

                # Adiciona o item à lista temporária da sessão
                lista_temp.append(item)
                request.session['itens_temp'] = lista_temp

                mensagens.append(f"Produto {item['produto_nome']} adicionado à lista.")
                devolucao_form = DevolucaoForm(prefix='devolucao', nota_fiscal=nota)
            else:
                mensagens.append('Erro ao adicionar produto à lista.')

        # ------------------------------------------------------------
        # Ação: Descartar itens selecionados
        # ------------------------------------------------------------
        elif acao == 'descartar-itens':
            # Obtém os índices dos itens marcados no formulário
            itens_marcados = request.POST.getlist('itens_marcados')

            # Remove da lista temporária os itens marcados
            lista_temp = [item for i, item in enumerate(lista_temp) if str(i) not in itens_marcados]
            request.session['itens_temp'] = lista_temp

            mensagens.append('Itens selecionados foram descartados.')

        # ------------------------------------------------------------
        # Ação: Registrar devolução no banco de dados
        # ------------------------------------------------------------
        elif acao == 'registrar-devolucao':
            if nota and lista_temp:
                for item in lista_temp:
                    Devolucao.objects.create(
                        nota_fiscal=nota,
                        produto=Produto.objects.get(id=item['produto_id']),
                        quantidade_devolvida=item['quantidade'],
                        motivo=item['motivo'],
                        observacao=item['observacao'],
                    )

                # Limpa a lista temporária da sessão
                request.session['itens_temp'] = []
                mensagens.append('Devolução registrada com sucesso!')
            else:
                mensagens.append('Nenhum item para registrar.')
        # ------------------------------------------------------------

    # ================================================================
    # Retorno final — renderização do template
    # ================================================================
    return render(request, 'verificar_e_devolver.html', {
        'verificacao_form': verificacao_form,                     # Form de verificação
        'devolucao_form': devolucao_form or DevolucaoForm(prefix='devolucao'),
        'nota': nota,                                             # Nota fiscal atual
        'mensagens': mensagens,                                   # Feedback ao usuário
        'lista_temp': lista_temp,                                 # Itens temporários
        'itens_nota': itens_nota,                                 # Itens originais da nota
    })
