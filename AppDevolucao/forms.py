# Importa funcionalidades de formulários do Django.
from django import forms
# Importa os modelos usados por esses forms: Cliente, ItemNotaFiscal, NotaFiscal e Devolucao.
from .models import Cliente, ItemNotaFiscal, NotaFiscal, Devolucao, Produto
# Importa o sistema de mensagens do Django (não usado no arquivo, mas foi importado no original).
from django.contrib import messages


# Define um ModelForm para o modelo Cliente.
class clienteForm(forms.ModelForm):
    # Classe Meta informa ao ModelForm qual modelo usar e quais campos incluir.
    class Meta:
        # Associa o form ao modelo Cliente.
        model = Cliente
        # Lista de campos do modelo que serão exibidos/edítaveis no form.
        fields = ['cnpj', 'razao_social']
        # Labels amigáveis para cada campo (texto exibido no template).
        labels = {
            'cnpj': 'CNPJ',
            'razao_social': 'Razão Social',
        }
        # Widgets permitem customizar o HTML gerado para cada campo.
        widgets = {
            # Para 'cnpj' usa um TextInput com placeholder orientando a entrada.
            'cnpj': forms.TextInput(attrs={'placeholder': 'Digite o CNPJ (somente números)'}),
            # Para 'razao_social' usa um TextInput com placeholder.
            'razao_social': forms.TextInput(attrs={'placeholder': 'Digite a razão social'}),
        }


# Define um ModelForm para o modelo NotaFiscal.
class NotaForm(forms.ModelForm):
    # Define um campo extra no form que não faz parte diretamente do model:
    # 'arquivo_pdf' permite anexar um PDF no momento do form (opcional).
    arquivo_pdf = forms.FileField(
        required=False,  # Não é obrigatório enviar arquivo.
        label='Anexar PDF',  # Texto exibido no template para o campo.
        help_text='Envie o arquivo PDF da nota fiscal (opcional).'  # Texto auxiliar.
    )

    class Meta:
        # Associa o form ao modelo NotaFiscal.
        model = NotaFiscal
        # Campos do modelo que serão usados no form.
        fields = ['cliente', 'numero_nota', 'arquivo_pdf']
        # Labels legíveis para os campos do form.
        labels = {
            'cliente': 'Cliente',
            'numero_nota': 'Número da Nota Fiscal',
        }


# Define um ModelForm para o modelo ItemNotaFiscal (itens ligados à nota).
class ItemNotaFiscalForm(forms.ModelForm):
    class Meta:
        # Associa o form ao modelo ItemNotaFiscal.
        model = ItemNotaFiscal
        # Campos do model que serão exibidos.
        fields = ['nota_fiscal', 'produto', 'quantidade']
        # Labels legíveis para cada campo.
        labels = {
            'nota_fiscal': 'Nota Fiscal',
            'produto': 'Produto',
            'quantidade': 'Quantidade',
        }
        # Widgets customizam como o campo é renderizado no HTML.
        widgets = {
            # 'quantidade' usa um NumberInput com valor mínimo 1 (evita 0 ou negativos no front-end).
            'quantidade': forms.NumberInput(attrs={'min': 1}),
        }


# Define um Form simples (não ModelForm) para verificar se uma nota existe para um CNPJ.
class VerificacaoForm(forms.Form):
    # Campo de texto para CNPJ (máx 18 caracteres para conter pontos/traços caso desejado).
    cnpj = forms.CharField(
        label='CNPJ',
        max_length=18,
        widget=forms.TextInput(attrs={'placeholder': 'Digite o CNPJ (somente números)'})
    )
    # Campo de texto para número da nota.
    numero_nota = forms.CharField(
        label='Número da Nota Fiscal',
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'Digite o número da nota'})
    )

    # Método clean faz validações que dependem de múltiplos campos (validação cruzada).
    def clean(self):
        # Primeiro chama a limpeza padrão para popular cleaned_data.
        cleaned_data = super().clean()
        # Recupera valores limpos para uso na validação.
        cnpj = cleaned_data.get('cnpj')
        numero_nota = cleaned_data.get('numero_nota')

        # Validação de cliente: tenta buscar o cliente pelo CNPJ.
        cliente = Cliente.objects.filter(cnpj=cnpj).first()
        # Se não encontrar cliente, lança erro de validação global do form.
        if not cliente:
            # Levanta ValidationError que será exibida ao usuário.
            raise forms.ValidationError('Cliente não encontrado para o CNPJ informado.')

        # Validação de nota: tenta buscar a nota com o número e associada ao cliente.
        nota = NotaFiscal.objects.filter(numero_nota=numero_nota, cliente=cliente).first()
        # Se não encontrar a nota, lança erro de validação.
        if not nota:
            raise forms.ValidationError('Nota fiscal não encontrada para este cliente.')

        # Caso ambos existam, guarda os objetos no cleaned_data para a view acessar depois.
        cleaned_data['cliente'] = cliente
        cleaned_data['nota_fiscal'] = nota
        # Retorna cleaned_data atualizado para que o form seja considerado válido.
        return cleaned_data


# Define um ModelForm para criar registros de Devolucao (baseado no modelo Devolucao).
class DevolucaoForm(forms.ModelForm):
    class Meta:
        # Associa o form ao modelo Devolucao.
        model = Devolucao
        # Campos que serão mostrados/guardados pelo form.
        fields = ['produto', 'quantidade_devolvida', 'motivo', 'observacao']
        # Widgets customizados para os campos (apenas 'observacao' aqui).
        widgets = {
            'observacao': forms.TextInput(attrs={
                'placeholder': 'Descreva o motivo, se necessário.'
            }),
        }

# --- Construtor do formulário DevolucaoForm ---
# Ele é executado automaticamente toda vez que o formulário é criado na view.
# A função principal aqui é receber a nota fiscal (caso já tenha sido verificada)
# e limitar o campo "produto" apenas aos produtos que pertencem a essa nota.

    def __init__(self, *args, **kwargs):
        # Extrai a nota fiscal passada pela view (caso exista).
        # A view envia o argumento "nota_fiscal=nota" ao instanciar o formulário.
        # O método pop remove 'nota_fiscal' de kwargs para não ser repassado ao super().
        self.nota_fiscal = kwargs.pop('nota_fiscal', None)

        #Chama o construtor original da classe pai (Form) para configurar o formulário normalmente.
        super().__init__(*args, **kwargs)

        # --- Lógica de filtragem dos produtos exibidos ---
        if self.nota_fiscal:
            #  Busca todos os itens da nota fiscal (ItemNotaFiscal)
            # e extrai apenas os IDs dos produtos associados a ela.
            produtos_ids = ItemNotaFiscal.objects.filter(
                nota_fiscal=self.nota_fiscal
            ).values_list('produto_id', flat=True)

            # Define que o campo 'produto' mostrará SOMENTE os produtos
            # cujos IDs estão nessa lista (ou seja, produtos que fazem parte da nota).
            self.fields['produto'].queryset = Produto.objects.filter(id__in=produtos_ids)
        else:
            # Caso ainda não exista uma nota fiscal associada (ex: antes de verificar),
            # o campo 'produto' deve ficar vazio (sem opções).
            self.fields['produto'].queryset = Produto.objects.none()


    # Método clean para validação cruzada envolvendo produto, quantidade e a nota.
    def clean(self):
        # Inicializa cleaned_data padrão.
        cleaned_data = super().clean()
        # Recupera produto e quantidade devolvida dos dados limpos.
        produto = cleaned_data.get('produto')
        qtd_dev = cleaned_data.get('quantidade_devolvida')
        # Recupera a nota_fiscal que veio no __init__ (deve ser um objeto NotaFiscal).
        nota = self.nota_fiscal

        # Se não houver nota associada ao form ou produto não informado, erro.
        if not nota or not produto:
            # Erro global porque dependemos da nota passada pela view.
            raise forms.ValidationError('Produto ou nota inválida.')

        # Busca o ItemNotaFiscal correspondente à nota e produto informados.
        item_nota = ItemNotaFiscal.objects.filter(nota_fiscal=nota, produto=produto).first()
        # Se nenhum item corresponder, significa que o produto não pertence à nota.
        if not item_nota:
            raise forms.ValidationError('O produto não pertence à nota fiscal.')

        # Valida se a quantidade devolvida não excede a quantidade originalmente faturada.
        if qtd_dev > item_nota.quantidade:
            # Mensagem clara informando o limite.
            raise forms.ValidationError(
                f'A quantidade devolvida ({qtd_dev}) é maior que a quantidade da nota ({item_nota.quantidade}).'
            )
        # Retorna os dados limpos se tudo estiver ok.
        return cleaned_data

        # Sobrescreve save para associar automaticamente a devolução à nota_fiscal passada.
    def save(self, commit=True):
            # Cria a instância de Devolucao sem salvar ainda (commit=False).
            devolucao = super().save(commit=False)
            # Atribui a nota_fiscal (campo do modelo Devolucao) usando o objeto guardado no __init__.
            devolucao.nota_fiscal = self.nota_fiscal
            # Se commit True, salva no banco de dados.
            if commit:
                devolucao.save()
            # Retorna a instância (salva ou não).
            return devolucao
