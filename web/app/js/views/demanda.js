// Prazo60 - Demanda & Oferta: pressao assistencial, rankings e fluxos entre regioes.

(function (P60) {
  const u = P60.u;
  const G = () => P60.graficos;
  let rankingAtivo = 'demanda';
  let ultimo = null;

  function kpis(p) {
    const f = P60.estado.filtros;
    const regioes = f.drs ? p.por_drs.filter((d) => String(d.drs) === String(f.drs)) : p.por_drs;
    const ano = regioes[0] ? regioes[0].ano_oferta : '';
    const casosAno = regioes.reduce((s, d) => s + d.casos_ano_oferta, 0);
    const estab = regioes.reduce((s, d) => s + d.estabelecimentos_cacon_unacon, 0);
    const mamo = regioes.reduce((s, d) => s + d.mamografias_rastreio, 0);
    const escopo = f.drs ? u.semDrs(P60.dados.nomeDrs(f.drs)) : 'Estado de SP';
    const pressoes = p.por_drs.map((d) => d.pressao_casos_por_estabelecimento);
    const medianaEstado = u.mediana(pressoes);
    const pressao = estab ? casosAno / estab : null;
    u.html(u.$('#do-kpis'), [
      P60.ui.kpi({ rotulo: `Demanda · casos em ${ano}`, valor: u.num(casosAno), rodape: `${escopo} · ${f.dimensao === 'residencia' ? 'por residência' : 'por local de tratamento'} · ${u.casos(p.kpis)} no recorte total` }),
      P60.ui.kpi({ rotulo: `Oferta · estabelecimentos CACON/UNACON (${ano})`, valor: u.num(estab), rodape: `${escopo} · ${u.num(mamo)} mamografias de rastreio no ano` }),
      P60.ui.kpi({ rotulo: 'Pressão assistencial', valor: u.num(pressao, 1), unidade: 'casos/estab.', indicador: 'pressao', classe: pressao > medianaEstado * 1.25 ? 'alerta' : '', rodape: `Mediana entre as 17 DRS: ${u.num(medianaEstado, 1)}` }),
    ].join(''));
  }

  function graficos(p) {
    const f = P60.estado.filtros;
    const lista = p.por_drs.filter((d) => d.n && !d.suprimido);
    const maximo = Math.max(...lista.map((d) => d.n));
    const C = G().COR;
    G().dispersao('graf-do-dispersao', {
      pontos: lista.map((d) => ({
        x: d.pressao_casos_por_estabelecimento, y: d.pct_fora_60, r: 5 + 18 * Math.sqrt(d.n / maximo), nome: d.nome, n: d.n,
        destaque: String(d.drs) === String(f.drs),
        cor: d.pct_fora_60 >= 70 ? 'rgba(179,38,30,0.6)' : d.pct_fora_60 < 55 ? 'rgba(47,122,82,0.55)' : 'rgba(194,24,91,0.45)',
      })),
      eixoX: 'Casos por estabelecimento habilitado (ano de referência)',
      eixoY: '% acima de 60 dias (recorte)',
      rotuloTooltip: (r) => `${u.semDrs(r.nome)}: ${u.num(r.x, 1)} casos/estab. · ${u.pct(r.y)} acima de 60 dias · ${u.num(r.n)} casos`,
    });

    const ordenado = lista.slice().sort((a, b) => b.n - a.n);
    G().barras('graf-do-barras', {
      rotulos: ordenado.map((d) => u.semDrs(d.nome)),
      series: [{ rotulo: 'Casos', dados: ordenado.map((d) => d.n), cor: ordenado.map((d) => (String(d.drs) === String(f.drs) ? C.primarioEscuro : C.primarioSuave)) }],
      horizontal: true,
      aoClicar: (i) => P60.estado.definir({ drs: String(f.drs) === String(ordenado[i].drs) ? '' : String(ordenado[i].drs), municipio: '' }),
    });
  }

  function ranking(p) {
    const min = P60.dados.opcoes.limites.min_ranking;
    const residencia = P60.estado.filtros.dimensao === 'residencia';
    const muns = p.por_municipio.filter((m) => !m.suprimido && m.n);
    const drsCel = (n) => u.esc(u.semDrs(P60.dados.nomeDrs(n)));
    let cabecalho, linhas, nota;

    if (rankingAtivo === 'demanda') {
      const top = muns.slice().sort((a, b) => b.n - a.n).slice(0, 15);
      const max = top[0] ? top[0].n : 1;
      cabecalho = '<th>Município</th><th>DRS</th><th class="num">Casos</th><th class="num">Acima de 60 dias</th><th class="num">Tratadas fora do município</th><th class="num">Unidades tratantes no município</th>';
      linhas = top.map((m) => `<tr><td>${u.esc(m.nome)}</td><td>${drsCel(m.drs)}</td><td class="num"><span class="celula-barra"><i style="width:${(60 * m.n / max).toFixed(0)}px"></i>${u.num(m.n)}</span></td><td class="num ${m.pct_fora_60 >= 70 ? 'ruim' : ''}">${u.pct(m.pct_fora_60)}</td><td class="num">${u.pct(m.pct_tratado_fora_do_municipio)}</td><td class="num">${m.unidades_tratantes_no_municipio}</td></tr>`);
      nota = `Municípios com mais casos no recorte (${residencia ? 'por residência' : 'por local de tratamento'}).`;
    } else if (rankingAtivo === 'oferta') {
      const top = muns.filter((m) => m.n >= min && m.unidades_tratantes_no_municipio === 0).sort((a, b) => b.n - a.n).slice(0, 15);
      cabecalho = '<th>Município</th><th>DRS</th><th class="num">Casos de residentes</th><th class="num">Acima de 60 dias</th><th class="num">Mediana (dias)</th>';
      linhas = top.map((m) => `<tr><td>${u.esc(m.nome)}</td><td>${drsCel(m.drs)}</td><td class="num">${u.num(m.n)}</td><td class="num ${m.pct_fora_60 >= 70 ? 'ruim' : ''}">${u.pct(m.pct_fora_60)}</td><td class="num">${u.dias(m.mediana_dias)}</td></tr>`);
      nota = residencia
        ? `Municípios com ≥ ${min} casos e nenhuma unidade tratante observada no próprio município: todas as residentes precisam se deslocar. Oferta municipal = unidades que iniciaram tratamento C50 na base (não é habilitação oficial).`
        : 'Este ranking só faz sentido pela residência da paciente. Troque “Localização por” para Residência.';
      if (!residencia) linhas = [];
    } else if (rankingAtivo === 'pressao') {
      const top = p.por_drs.slice().sort((a, b) => (b.pressao_casos_por_estabelecimento || 0) - (a.pressao_casos_por_estabelecimento || 0));
      cabecalho = '<th>DRS</th><th class="num">Casos no ano</th><th class="num">CACON/UNACON</th><th class="num">Casos por estabelecimento</th><th class="num">Acima de 60 dias</th>';
      linhas = top.map((d) => `<tr class="${String(d.drs) === String(P60.estado.filtros.drs) ? 'destaque' : ''}"><td>${u.esc(d.nome)}</td><td class="num">${u.num(d.casos_ano_oferta)}</td><td class="num">${d.estabelecimentos_cacon_unacon}</td><td class="num"><b>${u.num(d.pressao_casos_por_estabelecimento, 1)}</b></td><td class="num ${d.pct_fora_60 >= 70 ? 'ruim' : ''}">${u.pct(d.pct_fora_60)}</td></tr>`);
      nota = `Ano de referência da oferta: ${top[0] ? top[0].ano_oferta : ''}. Pressão alta não significa ausência de vaga.`;
    } else {
      const top = muns.filter((m) => m.n >= min).sort((a, b) => b.pct_fora_60 - a.pct_fora_60).slice(0, 15);
      cabecalho = '<th>Município</th><th>DRS</th><th class="num">Casos</th><th class="num">Acima de 60 dias</th><th class="num">Mediana (dias)</th>';
      linhas = top.map((m) => `<tr><td>${u.esc(m.nome)}</td><td>${drsCel(m.drs)}</td><td class="num">${u.num(m.n)}</td><td class="num ruim">${u.pct(m.pct_fora_60)}</td><td class="num">${u.dias(m.mediana_dias)}</td></tr>`);
      nota = `Apenas municípios com ≥ ${min} casos no recorte, para evitar percentuais instáveis.`;
    }
    u.html(u.$('#do-ranking'), linhas.length ? `<thead><tr>${cabecalho}</tr></thead><tbody>${linhas.join('')}</tbody>` : `<tbody><tr><td>${P60.ui.estado('vazio')}</td></tr></tbody>`);
    u.html(u.$('#do-ranking-nota'), nota);
  }

  function sankey(p) {
    const fl = p.fluxos;
    const svg = u.$('#do-sankey');
    if (!fl.links.length) {
      svg.innerHTML = '';
      u.html(u.$('#do-sankey-legenda'), 'Nenhum fluxo entre regiões com pelo menos 10 casos neste recorte.');
      return;
    }
    u.html(u.$('#do-sankey-legenda'), `${u.num(fl.total_fora_da_regiao)} de ${u.num(fl.total_casos)} casos (${u.pct(100 * fl.total_fora_da_regiao / fl.total_casos)}) iniciaram tratamento fora da região de residência. Os ${fl.links.length} maiores fluxos exibidos somam ${u.num(fl.soma_exibida)} casos. Cor = região de origem.`);
    G().sankey(svg, fl.links);
  }

  P60.views['demanda-oferta'] = {
    titulo: 'Demanda & Oferta',
    usaFiltros: true,
    iniciar() {
      u.$$('#do-abas button').forEach((b) => b.addEventListener('click', () => {
        rankingAtivo = b.dataset.ranking;
        u.$$('#do-abas button').forEach((x) => x.classList.toggle('ativo', x === b));
        if (ultimo) ranking(ultimo);
      }));
    },
    renderizar(p) {
      ultimo = p;
      kpis(p);
      graficos(p);
      ranking(p);
      sankey(p);
    },
  };
})(window.P60);
