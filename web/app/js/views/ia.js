// Prazo60 AI - interface de perguntas em linguagem natural via backend -> Oracle Select AI.
// Sem integracao configurada, a tela informa isso: nenhuma resposta e simulada.

(function (P60) {
  const u = P60.u;
  const SUGESTOES = [
    'Quais municípios possuem maior percentual acima de 60 dias?',
    'Qual região apresentou pior evolução?',
    'Onde existe maior pressão entre demanda e oferta?',
    'Quais unidades estão próximas de municípios críticos?',
    'Como a situação mudou nos últimos meses?',
  ];
  const APIS = [
    ['API de dados', '/api/painel', 'Indicadores agregados com filtros e supressão de grupos pequenos', 'real', 'Ativa'],
    ['API de localização', '/api/localizador', 'Unidades compatíveis e distância estimada a partir do município', 'real', 'Ativa'],
    ['API de simulação', '/api/simulacao', 'Cenários de redistribuição com premissas explícitas', 'simulacao', 'Ativa · simulação'],
    ['API CNES', '—', 'Nome, endereço e habilitação atualizados das unidades (CNES/DATASUS)', 'demonstracao', 'Roadmap'],
    ['API Oracle', 'server/oracle', 'Mesmo contrato da API de dados lendo do Prazo60DB', 'estimativa', 'Preparada'],
    ['API Select AI', '/api/ia/perguntar', 'Perguntas em linguagem natural via DBMS_CLOUD_AI', 'estimativa', 'Preparada'],
    ['API Power BI', 'POWERBI_EMBED_URL', 'Incorporação configurável; token de embed exige Power BI Embedded', 'estimativa', 'Preparada'],
  ];

  function mensagem(classe, html) {
    const hist = u.$('#ia-historico');
    const div = document.createElement('div');
    div.className = 'chat-msg ' + classe;
    div.innerHTML = html;
    hist.appendChild(div);
    hist.scrollTop = hist.scrollHeight;
    return div;
  }

  async function perguntar(texto) {
    const pergunta = texto.trim();
    if (pergunta.length < 5) { P60.ui.toast('Escreva uma pergunta com pelo menos 5 caracteres.'); return; }
    const botao = u.$('#ia-form button');
    botao.disabled = true;
    mensagem('chat-usuario', u.esc(pergunta));
    const pendente = mensagem('chat-resposta', 'Consultando o banco… pode levar até 1 minuto.');
    try {
      const r = await P60.api.post('ia/perguntar', { pergunta });
      const unico = r.linhas.length === 1 && r.colunas.length === 1;
      const valor = (v) => (typeof v === 'number' ? u.num(v, Number.isInteger(v) ? 0 : 1) : u.esc(v ?? '—'));
      const resultado = r.linhas.length === 0
        ? '<p>A consulta rodou, mas não retornou nenhuma linha.</p>'
        : unico
          ? `<p class="resposta-unica"><span>${u.esc(r.colunas[0])}</span><b>${valor(r.linhas[0][0])}</b></p>`
          : `<div class="tabela-rolagem"><table class="tabela"><thead><tr>${r.colunas.map((c) => `<th>${u.esc(c)}</th>`).join('')}</tr></thead>
             <tbody>${r.linhas.map((l) => `<tr>${l.map((v) => `<td class="${typeof v === 'number' ? 'num' : ''}">${valor(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
             ${r.truncado ? '<p class="nota">Mostrando as primeiras 50 linhas.</p>' : ''}`;
      pendente.innerHTML = `${P60.ui.selo('real', 'Resultado do banco')}${resultado}
        <details open><summary>SQL gerado pela IA</summary><pre>${u.esc(r.sql_gerado)}</pre></details>
        <p class="nota">${u.esc(r.fonte)}. Confira o SQL: a IA pode interpretar a pergunta de forma diferente.</p>`;
    } catch (erro) {
      pendente.classList.add('indisponivel');
      const corpo = erro.corpo || {};
      pendente.innerHTML = corpo.status === 'nao_configurado'
        ? `<strong>Integração Oracle Select AI: roadmap técnico.</strong><p>${u.esc(corpo.detail)}</p><p class="nota">Para ativar: ${corpo.requisitos.map(u.esc).join(' · ')}</p>`
        : `<strong>Não foi possível responder.</strong><p>${u.esc(erro.message)}</p>`;
    } finally {
      botao.disabled = false;
    }
  }

  P60.views.ia = {
    titulo: 'Inteligência Artificial',
    iniciar() {
      const cfg = P60.dados.config.select_ai;
      u.$('#ia-selo-status').textContent = cfg.habilitado ? 'Integração ativa' : 'Roadmap técnico';
      u.$('#ia-selo-status').className = 'selo ' + (cfg.habilitado ? 'selo-real' : 'selo-projecao');
      u.html(u.$('#ia-status'), cfg.habilitado
        ? `<strong>Select AI conectado</strong> ao perfil <code>${u.esc(cfg.perfil)}</code>. O modelo de linguagem ${u.esc(cfg.provedor)} gera o SQL; a consulta roda no Oracle Autonomous Database sobre a base completa, sem acesso a data de nascimento. Confira sempre o SQL gerado.`
        : `<strong>Integração Oracle Select AI: roadmap técnico.</strong> A funcionalidade depende do backend (já preparado em <code>/api/ia/perguntar</code>) e da configuração do ambiente Oracle: credenciais e wallet no servidor, perfil <code>${u.esc(cfg.perfil)}</code> com a base completa de 45.416 casos. Até lá, nenhuma resposta é gerada.`);

      u.html(u.$('#ia-sugestoes'), SUGESTOES.map((s) => `<button type="button">${u.esc(s)}</button>`).join(''));
      u.$('#ia-sugestoes').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { u.$('#ia-pergunta').value = b.textContent; u.$('#ia-pergunta').focus(); } });
      u.$('#ia-form').addEventListener('submit', (e) => { e.preventDefault(); perguntar(u.$('#ia-pergunta').value); u.$('#ia-pergunta').value = ''; });

      const ev = P60.dados.referencia.select_ai_evidencia;
      u.html(u.$('#ia-evidencia-escopo'), `${u.esc(ev.status)} · ${u.esc(ev.banco)} · perfil ${u.esc(ev.perfil_ai)}. Escopo: ${u.esc(ev.escopo_atual)}. Os números abaixo referem-se a esse escopo, não à base completa.`);
      u.html(u.$('#ia-evidencias'), ev.consultas.map((c) => `<article class="cartao evidencia-ia">
        <h4>“${u.esc(c.pergunta)}”</h4>
        <pre>${u.esc(c.sql_gerado)}</pre>
        <p><strong>Resultado:</strong> ${u.esc(c.resultado)}</p>
        <p class="nota">${u.esc(c.insight)}</p>
      </article>`).join(''));

      u.html(u.$('#ia-apis'), `<thead><tr><th>API</th><th>Ponto de integração</th><th>Função</th><th>Status</th></tr></thead><tbody>${APIS.map(([n, e, d, s, r]) => `<tr><td><strong>${n}</strong></td><td><code>${u.esc(e)}</code></td><td>${u.esc(d)}</td><td>${P60.ui.selo(s, r)}</td></tr>`).join('')}</tbody>`);
    },
  };
})(window.P60);
