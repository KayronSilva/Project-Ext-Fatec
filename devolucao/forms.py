import re
from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError

from .models import Usuario, Cliente, ItemDevolucao, validar_cpf, validar_cnpj

PDF_MAX_BYTES = 5 * 1024 * 1024   # 5 MB


def _only_digits(value: str) -> str:
    return re.sub(r'\D', '', value or '')


# ════════════════════════════════════════════════════════
# Formulário de Cadastro (clientes)
# ════════════════════════════════════════════════════════

class CadastroForm(forms.Form):
    TIPO_CHOICES = [('PF', 'Pessoa Física (CPF)'), ('PJ', 'Pessoa Jurídica (CNPJ)')]

    tipo            = forms.ChoiceField(choices=TIPO_CHOICES, widget=forms.RadioSelect)
    email           = forms.EmailField(max_length=254)
    senha           = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirmar_senha = forms.CharField(widget=forms.PasswordInput)
    telefone        = forms.CharField(max_length=20)
    endereco        = forms.CharField(max_length=200)

    # Pessoa Física
    nome = forms.CharField(max_length=100, required=False)
    cpf  = forms.CharField(
        max_length=14, required=False,
        widget=forms.TextInput(attrs={'placeholder': '000.000.000-00'}),
    )

    # Pessoa Jurídica
    razao_social = forms.CharField(max_length=100, required=False)
    cnpj         = forms.CharField(
        max_length=18, required=False,
        widget=forms.TextInput(attrs={'placeholder': '00.000.000/0000-00'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Usuario.objects.filter(email=email).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email

    def clean(self):
        data = super().clean()
        tipo = data.get('tipo')

        if data.get('senha') != data.get('confirmar_senha'):
            self.add_error('confirmar_senha', 'As senhas não coincidem.')

        if tipo == 'PF':
            cpf = _only_digits(data.get('cpf', ''))
            if not cpf:
                self.add_error('cpf', 'CPF é obrigatório.')
            else:
                try:
                    validar_cpf(cpf)
                except ValidationError as e:
                    self.add_error('cpf', e)
                else:
                    if Cliente.objects.filter(cpf=cpf).exists():
                        self.add_error('cpf', 'CPF já cadastrado.')
                    data['cpf'] = cpf

            if not data.get('nome', '').strip():
                self.add_error('nome', 'Nome é obrigatório para Pessoa Física.')

        elif tipo == 'PJ':
            cnpj = _only_digits(data.get('cnpj', ''))
            if not cnpj:
                self.add_error('cnpj', 'CNPJ é obrigatório.')
            else:
                try:
                    validar_cnpj(cnpj)
                except ValidationError as e:
                    self.add_error('cnpj', e)
                else:
                    if Cliente.objects.filter(cnpj=cnpj).exists():
                        self.add_error('cnpj', 'CNPJ já cadastrado.')
                    data['cnpj'] = cnpj

            if not data.get('razao_social', '').strip():
                self.add_error('razao_social', 'Razão Social é obrigatória para Pessoa Jurídica.')

        return data

    def save(self):
        from django.db import transaction
        data = self.cleaned_data
        tipo = data['tipo']

        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                email=data['email'],
                password=data['senha'],
            )
            cliente_kwargs = dict(
                usuario=usuario,
                tipo=tipo,
                email=data['email'],
                telefone=data['telefone'],
                endereco=data['endereco'],
            )
            if tipo == 'PF':
                cliente_kwargs.update(nome=data['nome'], cpf=data['cpf'])
            else:
                cliente_kwargs.update(razao_social=data['razao_social'], cnpj=data['cnpj'])

            cliente = Cliente(**cliente_kwargs)
            cliente.save(skip_validation=True)

        return usuario


# ════════════════════════════════════════════════════════
# Formulário de Login
# ════════════════════════════════════════════════════════

class LoginForm(forms.Form):
    email = forms.EmailField(max_length=254)
    senha = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, request=None, **kwargs):
        self.request  = request
        self._usuario = None
        super().__init__(*args, **kwargs)

    def clean(self):
        data  = super().clean()
        email = data.get('email', '').lower()
        senha = data.get('senha', '')

        if email and senha:
            usuario = authenticate(self.request, username=email, password=senha)
            if usuario is None:
                raise ValidationError('E-mail ou senha incorretos.')
            if not usuario.is_active:
                raise ValidationError('Esta conta está desativada.')
            self._usuario = usuario

        return data

    @property
    def usuario(self):
        return self._usuario


# ════════════════════════════════════════════════════════
# Formulário para criar administrador
# ════════════════════════════════════════════════════════

class AdminCriarForm(forms.Form):
    email           = forms.EmailField(max_length=254)
    senha           = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirmar_senha = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Usuario.objects.filter(email=email).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email

    def clean(self):
        data = super().clean()
        if data.get('senha') != data.get('confirmar_senha'):
            self.add_error('confirmar_senha', 'As senhas não coincidem.')
        return data

    def save(self, is_superuser=False):
        return Usuario.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['senha'],
            is_staff=True,
            is_superuser=is_superuser,
        )


# ════════════════════════════════════════════════════════
# Formulário de identificação do cliente na devolução
# ════════════════════════════════════════════════════════

class ClienteForm(forms.Form):
    documento = forms.CharField(
        max_length=14,
        widget=forms.TextInput(attrs={
            'id':          'id_documento',
            'placeholder': 'CPF ou CNPJ (somente números)',
            'maxlength':   '14',
        }),
    )
    nome_exibicao = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'id':          'id_nome_exibicao',
            'placeholder': 'Preenchido automaticamente',
            'readonly':    'readonly',
        }),
    )
    tipo = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_tipo_cliente'}),
    )


# ════════════════════════════════════════════════════════
# Formulário de nota fiscal
# ════════════════════════════════════════════════════════

class NotaForm(forms.Form):
    numero_nota = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'placeholder': 'Digite o número da nota',
            'id':          'id_numero_nota',
        }),
    )
    arquivo_pdf = forms.FileField(required=False, label='Anexar PDF')

    def clean_arquivo_pdf(self):
        f = self.cleaned_data.get('arquivo_pdf')
        if f and f.size > PDF_MAX_BYTES:
            raise forms.ValidationError('O PDF não pode exceder 5 MB.')
        return f


# ════════════════════════════════════════════════════════
# Formulário de item de devolução
# ════════════════════════════════════════════════════════

class DevolucaoForm(forms.ModelForm):
    class Meta:
        model  = ItemDevolucao
        fields = ['quantidade_devolvida', 'motivo', 'observacao']
        labels = {
            'quantidade_devolvida': 'Quantidade Devolvida',
            'motivo':               'Motivo da Devolução',
            'observacao':           'Observação',
        }
        widgets = {
            'observacao': forms.TextInput(
                attrs={'placeholder': 'Descreva o motivo, se necessário.'}
            ),
        }