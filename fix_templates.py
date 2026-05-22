import re
from pathlib import Path

# Mapeamento: como está na view -> como realmente é na pasta templates
MAPEAMENTO = {
    "'gestao_usuarios.html'": "'admin/gestao_usuarios.html'",
    "'gestao_usuarios_form.html'": "'admin/gestao_usuarios_form.html'",
    "'Painel_admin.html'": "'admin/Painel_admin.html'",
    "'importar_notas.html'": "'admin/importar_notas.html'",
    "'portal_vendas.html'": "'admin/portal_vendas.html'",
    "'login_admin.html'": "'auth/login_admin.html'",
    "'login_cliente.html'": "'auth/login_cliente.html'",
    "'Cadastro.html'": "'auth/Cadastro.html'",
    "'devolucao.html'": "'cliente/devolucao.html'",
    "'acompanhar_devolucoes.html'": "'cliente/acompanhar_devolucoes.html'",
    "'minhas_compras.html'": "'cliente/minhas_compras.html'",
    "'500.html'": "'500.html'",
}

views_dir = Path("devolucao/views")
corrigidos = 0

for view_file in views_dir.glob("*.py"):
    content = view_file.read_text(encoding="utf-8")
    original = content
    
    for errado, certo in MAPEAMENTO.items():
        content = content.replace(errado, certo)
    
    if content != original:
        view_file.write_text(content, encoding="utf-8")
        corrigidos += 1
        print(f"✅ Corrigido: {view_file}")

print(f"\n{corrigidos} arquivo(s) corrigido(s).")
