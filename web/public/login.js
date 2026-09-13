// Prazo60 - tela de login. A senha e validada somente no servidor (hash PBKDF2).
(function () {
  const form = document.getElementById('form-login');
  const usuario = document.getElementById('usuario');
  const senha = document.getElementById('senha');
  const erro = document.getElementById('login-erro');
  const botao = document.getElementById('botao-entrar');
  const alternar = document.getElementById('alternar-senha');
  const avisoCaps = document.getElementById('aviso-caps');

  function mostrarErro(texto) {
    erro.textContent = texto;
    erro.hidden = !texto;
  }

  alternar.addEventListener('click', () => {
    const visivel = senha.type === 'text';
    senha.type = visivel ? 'password' : 'text';
    alternar.textContent = visivel ? 'Mostrar' : 'Ocultar';
    alternar.setAttribute('aria-pressed', String(!visivel));
    senha.focus();
  });

  senha.addEventListener('keyup', (e) => {
    avisoCaps.hidden = !(e.getModifierState && e.getModifierState('CapsLock'));
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    mostrarErro('');
    if (!usuario.value.trim() || !senha.value) {
      mostrarErro('Informe usuário e senha.');
      return;
    }
    botao.disabled = true;
    botao.textContent = 'Verificando…';
    try {
      const resposta = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'prazo60' },
        body: JSON.stringify({ usuario: usuario.value.trim(), senha: senha.value }),
      });
      if (resposta.ok) {
        window.location.replace('/app/');
        return;
      }
      const corpo = await resposta.json().catch(() => ({}));
      if (resposta.status === 401) mostrarErro('Usuário ou senha inválidos.');
      else if (resposta.status === 429) mostrarErro(corpo.detail || 'Muitas tentativas. Aguarde alguns minutos.');
      else mostrarErro('Não foi possível entrar agora. Tente novamente.');
      senha.value = '';
      senha.focus();
    } catch (falha) {
      mostrarErro('Sem conexão com o servidor. Verifique sua internet.');
    } finally {
      botao.disabled = false;
      botao.textContent = 'Entrar';
    }
  });
})();
