// Prazo60 - Panorama dos 60 dias: regua temporal, situacao do prazo e distribuicao por faixa.

(function (P60) {
  const u = P60.u;
  const G = () => P60.graficos;

  const SITUACOES = [
    ['dentro', 'Dentro do prazo', '0 a 45 dias'],
    ['limite', 'Próximo do limite', '46 a 60 dias'],
    ['acima', 'Acima do prazo', 'mais de 60 dias'],
  ];

  P60.views.panorama = {
    titulo: 'Panorama dos 60 Dias',
    usaFiltros: true,
    renderizar(p) {
      const s = p.situacao;
      const vazio = !p.kpis.n && !p.kpis.suprimido;
      u.html(u.$('#pan-situacao'), vazio ? P60.ui.estado('vazio') : SITUACOES.map(([chave, nome, faixa]) => `
        <div class="situacao situacao-${chave}">
          <span>${nome}</span>
          <b>${p.kpis.suprimido ? '—' : u.pct(s[chave].percentual)}</b>
          <small>${p.kpis.suprimido ? 'Recorte com menos de 10 casos' : u.num(s[chave].quantidade) + ' casos · ' + faixa}</small>
        </div>`).join(''));

      const faixas = p.kpis.suprimido ? [] : p.faixas;
      G().barras('graf-pan-faixas', {
        rotulos: faixas.map((f) => f.faixa + ' dias'),
        series: [{ rotulo: '% dos casos', dados: faixas.map((f) => f.percentual), cor: G().COR_FAIXAS }],
        pct: false,
        tooltipSufixo: '%',
      });

      const anos = p.faixas_por_ano.filter((a) => a.faixas.some((f) => f.quantidade));
      const totalAno = (a) => a.faixas.reduce((t, f) => t + f.quantidade, 0);
      const anosValidos = anos.filter((a) => totalAno(a) >= P60.dados.opcoes.limites.min_exibicao);
      G().barras('graf-pan-anos', {
        rotulos: anosValidos.map((a) => (a.parcial ? `${a.ano}*` : String(a.ano))),
        series: (anosValidos[0] ? anosValidos[0].faixas : []).map((f, i) => ({
          rotulo: f.faixa, cor: G().COR_FAIXAS[i],
          dados: anosValidos.map((a) => a.faixas[i].percentual),
        })),
        empilhado: true,
        pct: true,
        tooltipSufixo: '%',
      });
      u.html(u.$('#pan-nota-anos'), `* Ano parcial. ${P60.estado.filtros.situacao ? 'Com o filtro de situação ativo, a distribuição mostra apenas a faixa escolhida.' : 'Faixas em verde estão dentro do prazo legal.'}`);

      const linhas = p.tipos_tratamento.filter((t) => t.n || t.suprimido);
      u.html(u.$('#pan-tipos'), linhas.length ? `<thead><tr><th>Primeiro tratamento</th><th class="num">Casos</th><th class="num">Acima de 60 dias</th><th class="num">Mediana (dias)</th><th class="num">Média (dias)</th></tr></thead>
        <tbody>${linhas.map((t) => `<tr><td>${u.esc(t.tipo)}</td><td class="num">${u.casos(t)}</td><td class="num ${t.pct_fora_60 >= 70 ? 'ruim' : ''}">${u.pct(t.pct_fora_60)}</td><td class="num">${u.dias(t.mediana_dias)}</td><td class="num">${u.num(t.media_dias, 1)}</td></tr>`).join('')}</tbody>` : `<tbody><tr><td>${P60.ui.estado('vazio')}</td></tr></tbody>`);
    },
  };
})(window.P60);
