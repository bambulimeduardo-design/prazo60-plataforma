// Prazo60 - Power BI: incorporacao configurada no servidor (POWERBI_EMBED_URL). Sem iframe falso.

(function (P60) {
  const u = P60.u;
  let montado = false;

  function vazio() {
    return `<div class="pbi-vazio">
      ${P60.ui.selo('demonstracao', 'Aguardando configuração')}
      <h3>Relatório Power BI ainda não incorporado</h3>
      <p>A área está pronta. Para exibir o relatório existente, defina <code>POWERBI_EMBED_URL</code> nas variáveis de ambiente do servidor com o link de incorporação do Power BI Service e reinicie o serviço.</p>
      <p class="nota">Nenhum relatório de exemplo é exibido para não confundir dado demonstrativo com análise real.</p>
    </div>`;
  }

  function montar(cfg) {
    const area = u.$('#pbi-area');
    u.$('#pbi-titulo').textContent = cfg.titulo || 'Relatório Power BI';
    if (!cfg.url) { area.innerHTML = vazio(); return; }
    if (cfg.modo === 'seguro') {
      const nota = document.createElement('p');
      nota.className = 'nota';
      nota.textContent = 'Incorporação segura: o relatório pede login Microsoft com uma conta que tenha acesso a ele no Power BI. Se aparecer “Entrar”, clique e autentique na janela que abrir.';
      area.parentElement.insertBefore(nota, area);
    }
    area.innerHTML = P60.ui.estado('carregando', 'Carregando relatório Power BI…');
    const iframe = document.createElement('iframe');
    iframe.title = cfg.titulo || 'Relatório Power BI Prazo60';
    iframe.src = cfg.url;
    iframe.setAttribute('allowfullscreen', 'true');
    iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    iframe.hidden = true;
    const limite = setTimeout(() => {
      if (!iframe.hidden) return;
      iframe.hidden = false;
      area.querySelector('.estado')?.remove();
      P60.ui.toast('O relatório está demorando. Se não aparecer, verifique as permissões de compartilhamento.');
    }, 15000);
    iframe.addEventListener('load', () => { clearTimeout(limite); area.querySelector('.estado')?.remove(); iframe.hidden = false; });
    area.appendChild(iframe);
    const abrir = u.$('#pbi-abrir');
    abrir.href = cfg.url;
    abrir.hidden = false;
  }

  P60.views.powerbi = {
    titulo: 'Power BI',
    async ativar() {
      if (!montado) { montado = true; montar(P60.dados.config.powerbi); }
      try {
        const p = await P60.dados.painel({ ano: '', mes: '', drs: '', municipio: '', cnes: '', tipo: '', situacao: '' });
        u.html(u.$('#pbi-indicadores'), [
          P60.ui.kpi({ rotulo: 'Casos na base da plataforma', valor: u.num(p.kpis.n), rodape: P60.ui.selo('real') + ' referência para conferir o relatório' }),
          P60.ui.kpi({ rotulo: 'Acima de 60 dias', valor: u.pct(p.kpis.pct_fora_60), classe: 'alerta', rodape: P60.ui.selo('real') }),
          P60.ui.kpi({ rotulo: 'Mediana até o tratamento', valor: u.dias(p.kpis.mediana_dias), unidade: 'dias', rodape: P60.ui.selo('real') }),
        ].join(''));
      } catch (erro) {
        u.html(u.$('#pbi-indicadores'), P60.ui.estado('erro', erro.message));
      }
    },
  };
})(window.P60);
