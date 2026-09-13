// Prazo60 - Visao Executiva: KPIs, tendencia, distancia ate a meta e recomendacoes.

(function (P60) {
  const u = P60.u;
  const G = () => P60.graficos;

  const TIPOS_REC = { ATENCAO: 'Atenção', RISCO: 'Risco', OPORTUNIDADE: 'Oportunidade', ACAO_SUGERIDA: 'Ação sugerida' };
  const DESTINOS = { gargalos: 'Ver gargalos', 'demanda-oferta': 'Ver demanda & oferta', simulacao: 'Testar no simulador' };

  function cartaoRecomendacao(r) {
    return `<article class="rec rec-${r.tipo.toLowerCase()}">
      <span class="rec-tipo">${TIPOS_REC[r.tipo]}</span>
      <h4>${u.esc(r.titulo)}</h4>
      <p>${u.esc(r.texto)}</p>
      <details><summary>Fundamento</summary><p>${u.esc(r.fundamento)}</p></details>
      <a class="botao-link" href="#/${r.destino}">${DESTINOS[r.destino] || 'Ver detalhes'} →</a>
    </article>`;
  }
  P60.views.cartaoRecomendacao = cartaoRecomendacao;

  function renderizarKpis(p) {
    const k = p.kpis;
    const c = p.comparacao;
    const v = c.variacao;
    const ref = c.anterior ? `${c.ano_referencia} vs ${c.ano_anterior}` : '';
    const anuais = p.serie_anual.filter((a) => !a.parcial);

    if (k.suprimido || !k.n) {
      u.html(u.$('#exec-kpis'), `<div class="cartao" style="grid-column:1/-1">${P60.ui.estado('vazio', k.suprimido ? 'Recorte com menos de 10 casos: indicadores suprimidos para proteger a privacidade.' : undefined)}</div>`);
      return false;
    }
    u.html(u.$('#exec-kpis'), [
      P60.ui.kpi({ rotulo: 'Pacientes analisadas', valor: u.num(k.n), indicador: 'casos_analisados', spark: 'spark-casos', rodape: v ? `${P60.ui.variacao(v.casos_pct, { sufixo: '%', neutro: true })} ${ref}` : '' }),
      P60.ui.kpi({ rotulo: 'Dentro do prazo (≤ 60 dias)', valor: u.pct(k.pct_dentro_60), classe: 'sucesso', indicador: 'pct_dentro_60', spark: 'spark-dentro', rodape: v ? `${P60.ui.variacao(-v.pct_fora_pp, { inverter: true })} ${ref}` : '' }),
      P60.ui.kpi({ rotulo: 'Acima de 60 dias', valor: u.pct(k.pct_fora_60), classe: 'alerta', indicador: 'pct_fora_60', spark: 'spark-fora', rodape: v ? `${P60.ui.variacao(v.pct_fora_pp)} ${ref}` : '' }),
      P60.ui.kpi({ rotulo: 'Mediana até o tratamento', valor: u.dias(k.mediana_dias), unidade: 'dias', indicador: 'mediana_dias', spark: 'spark-mediana', rodape: v ? `${P60.ui.variacao(v.mediana_dias, { sufixo: ' dias', casas: 0 })} ${ref}` : '' }),
      P60.ui.kpi({ rotulo: 'Tempo médio', valor: u.num(k.media_dias, 1), unidade: 'dias', indicador: 'media_dias', rodape: 'Sensível a esperas extremas' }),
      P60.ui.kpi({ rotulo: 'Maior tempo registrado', valor: u.num(k.maior_tempo_dias), unidade: 'dias', indicador: 'maior_tempo_dias', rodape: `${u.num(k.maior_tempo_dias / 30.4, 0)} meses` }),
      P60.ui.kpi({ rotulo: 'Municípios analisados', valor: u.num(k.municipios), indicador: 'municipios', rodape: 'de 645 municípios de SP' }),
      P60.ui.kpi({ rotulo: 'Estabelecimentos analisados', valor: u.num(k.estabelecimentos), indicador: 'estabelecimentos', rodape: 'CNES que iniciaram tratamento' }),
    ].join(''));

    if (anuais.length > 1) {
      const C = G().COR;
      G().spark('spark-casos', anuais.map((a) => a.n), C.primario);
      G().spark('spark-dentro', anuais.map((a) => a.pct_dentro_60), C.sucesso);
      G().spark('spark-fora', anuais.map((a) => a.pct_fora_60), C.alerta);
      G().spark('spark-mediana', anuais.map((a) => a.mediana_dias), C.tintaSuave);
    }
    return true;
  }

  function renderizarSerie(p) {
    const serie = p.serie_mensal;
    const parcial = serie.map((s) => s.parcial);
    G().linha('graf-exec-mensal', {
      rotulos: serie.map((s) => `${u.mes(s.mes)}/${String(s.ano).slice(2)}`),
      series: [
        { rotulo: '% acima de 60 dias', dados: serie.map((s) => s.pct_fora_60), cor: G().COR.alerta, preenchimento: 'rgba(179,38,30,0.06)',
          segment: { borderDash: (ctx) => (parcial[ctx.p1DataIndex] ? [5, 4] : undefined) } },
      ],
      eixoY: { pct: true },
      tooltipSufixo: '%',
    });
    const suprimidos = serie.filter((s) => s.suprimido).length;
    u.html(u.$('#exec-nota-serie'), `Trecho tracejado: ${P60.dados.opcoes.anos_parciais.join(', ')} (ano parcial).${suprimidos ? ` ${suprimidos} mês(es) com menos de 10 casos foram suprimidos.` : ''} Anos recentes tendem a subestimar atrasos (casos com espera longa ainda não iniciaram tratamento).`);

    const anual = p.serie_anual;
    G().barras('graf-exec-anual', {
      rotulos: anual.map((a) => (a.parcial ? `${a.ano}*` : String(a.ano))),
      series: [
        { rotulo: 'Até 60 dias', dados: anual.map((a) => a.pct_dentro_60), cor: G().COR.sucesso },
        { rotulo: 'Acima de 60 dias', dados: anual.map((a) => a.pct_fora_60), cor: G().COR.alerta },
      ],
      empilhado: true,
      pct: true,
      tooltipSufixo: '%',
    });
  }

  function renderizarComparacao(p) {
    const c = p.comparacao;
    const alvo = u.$('#exec-comparacao');
    if (!c.anterior || !c.variacao) {
      alvo.innerHTML = `<p class="cartao-pergunta">Comparação entre períodos</p>${P60.ui.estado('vazio', 'Sem ano anterior comparável para este recorte.')}`;
      return;
    }
    const a = c.atual, b = c.anterior;
    const linha = (rotulo, x, y, varHtml) => `<div class="comparacao-linha"><span>${rotulo}</span><span class="num">${x}</span><span class="num">${y}</span><span class="num">${varHtml}</span></div>`;
    alvo.innerHTML = `<p class="cartao-pergunta">O que mudou em ${c.ano_referencia}? ${c.parcial ? P60.ui.selo('demonstracao', 'Ano parcial') : ''}</p>
      <div class="comparacao-linha cabecalho"><span>Indicador</span><span class="num">${c.ano_anterior}</span><span class="num">${c.ano_referencia}</span><span class="num">Variação</span></div>
      ${linha('Casos', u.num(b.n), u.num(a.n), P60.ui.variacao(c.variacao.casos_pct, { sufixo: '%', neutro: true }))}
      ${linha('% acima de 60 dias', u.pct(b.pct_fora_60), u.pct(a.pct_fora_60), P60.ui.variacao(c.variacao.pct_fora_pp))}
      ${linha('Mediana (dias)', u.dias(b.mediana_dias), u.dias(a.mediana_dias), P60.ui.variacao(c.variacao.mediana_dias, { sufixo: '', casas: 0 }))}
      ${linha('Média (dias)', u.num(b.media_dias, 1), u.num(a.media_dias, 1), P60.ui.variacao(Math.round((a.media_dias - b.media_dias) * 10) / 10, { sufixo: '' }))}
      <p class="nota">Queda no número de casos em anos recentes pode refletir atraso de registro, não redução real de demanda.</p>`;
  }

  P60.views.executiva = {
    titulo: 'Visão Executiva',
    usaFiltros: true,
    renderizar(p) {
      const ok = renderizarKpis(p);
      u.html(u.$('#exec-gauge'), ok ? `${G().gauge(p.kpis.pct_dentro_60)}<p class="gauge-legenda">Faltam <strong>${u.num(p.kpis.pct_fora_60, 1)} p.p.</strong> para que todas as pacientes do recorte iniciem o tratamento no prazo legal. São <strong>${u.num(Math.round(p.kpis.n * p.kpis.pct_fora_60 / 100))}</strong> casos acima de 60 dias.</p>` : '');
      renderizarSerie(p);
      renderizarComparacao(p);
      u.html(u.$('#exec-recomendacoes'), p.recomendacoes.length ? p.recomendacoes.map(cartaoRecomendacao).join('') : `<div class="cartao" style="grid-column:1/-1">${P60.ui.estado('vazio', 'Sem dados suficientes (≥ 30 casos por região nos dois últimos anos fechados) para gerar recomendações neste recorte.')}</div>`);
    },
  };
})(window.P60);
