// Prazo60 - Onde estao os gargalos: alertas por regra, municipios criticos, fatores e recomendacoes.

(function (P60) {
  const u = P60.u;
  const CLASSES = [
    ['CRITICO', 'Crítico', '≥ 70% e piorando'],
    ['ATENCAO', 'Atenção', 'piora > 5 p.p.'],
    ['MONITORAR', 'Monitorar', 'sem sinal agudo'],
    ['OPORTUNIDADE', 'Oportunidade', '< 55% e melhorando'],
  ];
  const ROTULO = Object.fromEntries(CLASSES.map(([k, r]) => [k, r]));
  ROTULO.DADOS_INSUFICIENTES = 'Dados insuficientes';
  const ORDEM = { CRITICO: 0, ATENCAO: 1, MONITORAR: 2, OPORTUNIDADE: 3, DADOS_INSUFICIENTES: 4 };
  let classeAtiva = null;
  let ultimo = null;

  function contadores(p) {
    u.html(u.$('#garg-contadores'), CLASSES.map(([k, r, regra]) => {
      const qtd = p.alertas.filter((a) => a.classificacao === k).length;
      return `<button type="button" class="contador cls-${k.toLowerCase()} ${classeAtiva === k ? 'selecionado' : ''}" data-classe="${k}" aria-pressed="${classeAtiva === k}"><b>${qtd}</b><span>${r}</span><small>${regra}</small></button>`;
    }).join(''));
  }

  function listaRegioes(p) {
    const f = P60.estado.filtros;
    const lista = p.alertas.filter((a) => !classeAtiva || a.classificacao === classeAtiva).sort((a, b) => ORDEM[a.classificacao] - ORDEM[b.classificacao] || (b.pct_fora_recente || 0) - (a.pct_fora_recente || 0));
    u.html(u.$('#garg-lista'), lista.length ? lista.map((a) => `
      <div class="alerta-item ${String(f.drs) === String(a.drs) ? 'selecionado' : ''}">
        <span class="alerta-tag cls-${a.classificacao.toLowerCase()}"><span>${ROTULO[a.classificacao]}</span></span>
        <div><h4>${u.esc(a.nome)}</h4><p>${a.casos_ano_recente ? `${u.num(a.casos_ano_recente)} casos em ${a.ano_recente} · mediana ${u.dias(a.mediana_recente)} dias · ${u.pct(a.pct_fora_anterior)} em ${a.ano_anterior}` : 'Menos de 30 casos em um dos anos comparados'}</p></div>
        <div class="alerta-valor"><b>${u.pct(a.pct_fora_recente)}</b>${P60.ui.variacao(a.variacao_pp)}</div>
      </div>`).join('') : P60.ui.estado('vazio', 'Nenhuma região nesta classificação.'));
  }

  function municipios(p) {
    const lista = p.alertas_municipios.filter((m) => (classeAtiva ? m.classificacao === classeAtiva : m.classificacao === 'CRITICO')).slice(0, 10);
    u.html(u.$('#garg-municipios'), lista.length ? lista.map((m) => `
      <div class="alerta-item">
        <div style="grid-column: span 2"><h4>${u.esc(m.nome)}</h4><p>${u.esc(u.semDrs(m.drs_nome))} · ${u.num(m.casos_ano_recente)} casos · mediana ${u.dias(m.mediana_recente)} dias</p></div>
        <div class="alerta-valor"><b class="cls-${m.classificacao.toLowerCase()}">${u.pct(m.pct_fora_recente)}</b>${P60.ui.variacao(m.variacao_pp)}</div>
      </div>`).join('') : P60.ui.estado('vazio', `Nenhum município ${classeAtiva ? 'nesta classificação' : 'crítico'} com ≥ 30 casos nos dois anos.`));
  }

  function fatores(p) {
    const regioes = p.por_drs.filter((d) => !d.suprimido && d.n);
    const med = (campo) => u.mediana(regioes.map((d) => d[campo]));
    const ref = { pct_fora_60: med('pct_fora_60'), mediana_dias: med('mediana_dias'), pressao_casos_por_estabelecimento: med('pressao_casos_por_estabelecimento'), pct_tratado_fora_da_regiao: med('pct_tratado_fora_da_regiao'), pct_121_mais: med('pct_121_mais') };
    const alertas = Object.fromEntries(p.alertas.map((a) => [a.drs, a]));
    const cel = (d, campo, fmt) => `<td class="num ${d[campo] !== null && ref[campo] !== null && d[campo] > ref[campo] ? 'fator-ruim' : ''}">${fmt(d[campo])}</td>`;
    const ordenadas = regioes.slice().sort((a, b) => ORDEM[(alertas[a.drs] || {}).classificacao] - ORDEM[(alertas[b.drs] || {}).classificacao] || b.pct_fora_60 - a.pct_fora_60);
    const residencia = P60.estado.filtros.dimensao === 'residencia';
    u.html(u.$('#garg-fatores'), `<thead><tr><th>DRS</th><th>Classificação</th><th class="num">Acima de 60 dias</th><th class="num">Acima de 120 dias</th><th class="num">Mediana (dias)</th><th class="num">Casos por estab.</th><th class="num">Tratadas fora da região</th></tr></thead>
      <tbody>${ordenadas.map((d) => `<tr class="${String(P60.estado.filtros.drs) === String(d.drs) ? 'destaque' : ''}"><td>${u.esc(u.semDrs(d.nome))}</td><td><span class="cls-${((alertas[d.drs] || {}).classificacao || '').toLowerCase()}">${ROTULO[(alertas[d.drs] || {}).classificacao] || '—'}</span></td>
        ${cel(d, 'pct_fora_60', u.pct)}${cel(d, 'pct_121_mais', u.pct)}${cel(d, 'mediana_dias', u.dias)}${cel(d, 'pressao_casos_por_estabelecimento', (v) => u.num(v, 1))}${residencia ? cel(d, 'pct_tratado_fora_da_regiao', u.pct) : '<td class="num suprimido">só residência</td>'}</tr>`).join('')}
        <tr><td><b>Mediana estadual</b></td><td></td><td class="num">${u.pct(ref.pct_fora_60)}</td><td class="num">${u.pct(ref.pct_121_mais)}</td><td class="num">${u.dias(ref.mediana_dias)}</td><td class="num">${u.num(ref.pressao_casos_por_estabelecimento, 1)}</td><td class="num">${residencia ? u.pct(ref.pct_tratado_fora_da_regiao) : ''}</td></tr>
      </tbody>`);
  }

  function renderizarTudo() {
    const p = ultimo;
    contadores(p);
    listaRegioes(p);
    municipios(p);
  }

  P60.views.gargalos = {
    titulo: 'Onde estão os gargalos?',
    usaFiltros: true,
    iniciar() {
      u.$('#garg-contadores').addEventListener('click', (e) => {
        const b = e.target.closest('[data-classe]');
        if (!b || !ultimo) return;
        classeAtiva = classeAtiva === b.dataset.classe ? null : b.dataset.classe;
        renderizarTudo();
      });
    },
    renderizar(p) {
      ultimo = p;
      const a = p.alertas[0] || {};
      u.html(u.$('#garg-lead'), `Classificação automática das 17 regiões comparando ${a.ano_recente} com ${a.ano_anterior} (anos fechados), por ${P60.estado.filtros.dimensao === 'residencia' ? 'residência da paciente' : 'local de tratamento'}. Filtros de ano e mês não se aplicam a esta comparação.`);
      renderizarTudo();
      fatores(p);
      u.html(u.$('#garg-recomendacoes'), p.recomendacoes.length ? p.recomendacoes.map(P60.views.cartaoRecomendacao).join('') : P60.ui.estado('vazio', 'Sem dados suficientes para gerar recomendações neste recorte.'));
    },
  };
})(window.P60);
