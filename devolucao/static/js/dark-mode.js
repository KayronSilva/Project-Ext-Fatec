// Dark Mode Toggle (NEW)
// Permite alternar entre tema claro e escuro com persistência em localStorage

document.addEventListener('DOMContentLoaded', function() {
    // 1. Verificar preferência salva em localStorage
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    
    // 2. Aplicar modo escuro se estava ativo antes
    if (isDarkMode) {
        document.body.classList.add('dark-mode');
    }
    
    // 3. Criar botão toggle se não existir
    if (!document.querySelector('.dark-mode-toggle')) {
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'dark-mode-toggle';
        toggleBtn.innerHTML = isDarkMode ? '☀️' : '🌙';
        toggleBtn.type = 'button';
        toggleBtn.title = 'Alternar modo escuro/claro';
        toggleBtn.setAttribute('aria-label', 'Alternar modo escuro');
        document.body.appendChild(toggleBtn);
        
        // 4. Adicionar event listener
        toggleBtn.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');
            const isNowDark = document.body.classList.contains('dark-mode');
            
            // 5. Salvar preferência em localStorage
            localStorage.setItem('darkMode', isNowDark);
            
            // 6. Atualizar ícone
            toggleBtn.innerHTML = isNowDark ? '☀️' : '🌙';
            
            // 7. Log para debug
            console.log('Dark Mode:', isNowDark ? 'enabled' : 'disabled');
        });
    }
});
