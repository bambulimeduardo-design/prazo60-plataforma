// Prazo60 - camada de visualizacao (Chart.js local + SVG). Cada grafico responde a uma pergunta.

(function (P60) {
  const u = P60.u;
  const COR = {
    primario: '#C2185B', primarioEscuro: '#8E1446', primarioSuave: '#F3B6CC',
    alerta: '#B3261E', alertaSuave: '#E8A39E', aviso: '#B86E00', sucesso: '#2F7A52', info: '#3F63A8',
    tinta: '#2A2629', tintaSuave: '#6E6269', grade: '#EDE3E7', neutro: '#CFC3C9',
  };
  // Sequencial para distribuicao de dias: verde (no prazo) -> ambar (limite) -> vermelhos (acima)
  const COR_FAIXAS = ['#2F7A52', '#6FA886', '#D69A2D', '#E07A5F', '#C0392B', '#7E1F17'];

  if (window.Chart) {
    Chart.defaults.font.family = "'IBM Plex Sans', system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = COR.tintaSuave;
    Chart.defaults.borderColor = COR.grade;
    Chart.defaults.animation.duration = 350;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.boxHeight = 10;
    Chart.defaults.plugins.tooltip.backgroundColor = COR.tinta;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
  }

  // Linha de referencia horizontal (ex.: limite legal de 60 dias)
  const pluginReferencia = {
    id: 'referencia',
    afterDatasetsDraw(chart, _args, opcoes) {
      if (!opcoes || opcoes.valor === undefined) return;
      const eixo = chart.scales[opcoes.eixo || 'y'];
      if (!eixo) return;
      const { ctx, chartArea } = chart;
      const pos = eixo.getPixelForValue(opcoes.valor);
      ctx.save();
      ctx.strokeStyle = opcoes.cor || COR.alerta;
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      if (eixo.isHorizontal()) { ctx.moveTo(pos, chartArea.top); ctx.lineTo(pos, chartArea.bottom); } else { ctx.moveTo(chartArea.left, pos); ctx.lineTo(chartArea.right, pos); }
      ctx.stroke();
      if (opcoes.rotulo) {
        ctx.setLineDash([]);
        ctx.fillStyle = opcoes.cor || COR.alerta;
        ctx.font = "600 11px 'IBM Plex Sans', sans-serif";
        if (eixo.isHorizontal()) ctx.fillText(opcoes.rotulo, pos + 4, chartArea.top + 12);
        else ctx.fillText(opcoes.rotulo, chartArea.right - ctx.measureText(opcoes.rotulo).width - 4, pos - 5);
      }
      ctx.restore();
    },
  };
  if (window.Chart) Chart.register(pluginReferencia);

  const instancias = {};

  function criar(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    if (instancias[id]) instancias[id].destroy();
    instancias[id] = new Chart(canvas, config);
    return instancias[id];
  }

  const eixoPct = (extra = {}) => ({ min: 0, max: 100, grid: { color: COR.grade }, ticks: { callback: (v) => v + '%' }, ...extra });

  P60.graficos = {
    COR,
    COR_FAIXAS,
    criar,
    destruir(id) { if (instancias[id]) { instancias[id].destroy(); delete instancias[id]; } },

    linha(id, { rotulos, series, eixoY = {}, referencia, tooltipSufixo = '' }) {
      return criar(id, {
        type: 'line',
        data: {
          labels: rotulos,
          datasets: series.map((s) => ({
            label: s.rotulo, data: s.dados, borderColor: s.cor || COR.primario, backgroundColor: s.preenchimento || 'transparent',
            fill: Boolean(s.preenchimento), borderWidth: 2, pointRadius: s.pontos ?? 0, pointHoverRadius: 4, tension: 0.3, spanGaps: false,
            borderDash: s.tracejado ? [5, 4] : undefined, segment: s.segment, yAxisID: s.eixo || 'y',
          })),
        },
        options: {
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { display: series.length > 1, position: 'bottom' },
            tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y === null ? 'suprimido' : u.num(c.parsed.y, 1) + tooltipSufixo}` } },
            referencia,
          },
          scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 16 } }, y: eixoY.pct ? eixoPct(eixoY) : { grid: { color: COR.grade }, beginAtZero: true, ...eixoY } },
        },
      });
    },

    barras(id, { rotulos, series, horizontal = false, empilhado = false, pct = false, referencia, tooltipSufixo = '', aoClicar }) {
      const grafico = criar(id, {
        type: 'bar',
        data: {
          labels: rotulos,
          datasets: series.map((s) => ({ label: s.rotulo, data: s.dados, backgroundColor: s.cor || COR.primario, borderRadius: 4, maxBarThickness: 36 })),
        },
        options: {
          indexAxis: horizontal ? 'y' : 'x',
          plugins: {
            legend: { display: series.length > 1, position: 'bottom' },
            tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${u.num(horizontal ? c.parsed.x : c.parsed.y, pct ? 1 : 0)}${tooltipSufixo}` } },
            referencia,
          },
          scales: {
            [horizontal ? 'x' : 'y']: pct ? eixoPct({ stacked: empilhado }) : { grid: { color: COR.grade }, beginAtZero: true, stacked: empilhado },
            [horizontal ? 'y' : 'x']: { grid: { display: false }, stacked: empilhado, ticks: { autoSkip: false } },
          },
          onClick: undefined,
        },
      });
      if (grafico && aoClicar) {
        grafico.canvas.onclick = (evt) => {
          const pontos = grafico.getElementsAtEventForMode(evt, 'nearest', { intersect: true }, true);
          if (pontos.length) aoClicar(pontos[0].index);
        };
        grafico.canvas.style.cursor = 'pointer';
      }
      return grafico;
    },

    dispersao(id, { pontos, eixoX, eixoY, referenciaY, rotuloTooltip }) {
      return criar(id, {
        type: 'bubble',
        data: {
          datasets: [{
            label: 'DRS',
            data: pontos,
            backgroundColor: pontos.map((p) => p.cor || 'rgba(194, 24, 91, 0.55)'),
            borderColor: pontos.map((p) => (p.destaque ? COR.tinta : '#fff')),
            borderWidth: pontos.map((p) => (p.destaque ? 2 : 1)),
          }],
        },
        options: {
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => rotuloTooltip(c.raw) } }, referencia: referenciaY },
          scales: {
            x: { title: { display: true, text: eixoX }, grid: { color: COR.grade }, beginAtZero: true },
            y: { title: { display: true, text: eixoY }, ...eixoPct() },
          },
        },
      });
    },

    spark(id, valores, cor) {
      return criar(id, {
        type: 'line',
        data: { labels: valores.map((_, i) => i), datasets: [{ data: valores, borderColor: cor, borderWidth: 2, pointRadius: (c) => (c.dataIndex === valores.length - 1 ? 2.5 : 0), pointBackgroundColor: cor, tension: 0.35, fill: false }] },
        options: { animation: false, events: [], plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } },
      });
    },

    // Semicirculo: percentual dentro do prazo vs meta legal de 100%
    gauge(valor) {
      const v = Math.max(0, Math.min(100, valor || 0));
      const ang = Math.PI * (1 - v / 100);
      const x = 100 + 80 * Math.cos(ang);
      const y = 100 - 80 * Math.sin(ang);
      const grande = v > 50 ? 0 : 0;
      return `<svg viewBox="0 0 200 118" role="img" aria-label="${u.num(v, 1)}% dentro do prazo, meta legal 100%">
        <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="${COR.alertaSuave}" stroke-width="18" stroke-linecap="round"/>
        <path d="M20 100 A80 80 0 ${grande} 1 ${x.toFixed(2)} ${y.toFixed(2)}" fill="none" stroke="${COR.sucesso}" stroke-width="18" stroke-linecap="round"/>
        <text x="100" y="86" text-anchor="middle" font-family="Poppins, sans-serif" font-size="30" font-weight="600" fill="${COR.tinta}">${u.num(v, 1)}%</text>
        <text x="100" y="106" text-anchor="middle" font-size="10.5" fill="${COR.tintaSuave}">dentro do prazo</text>
        <text x="20" y="116" text-anchor="middle" font-size="9" fill="${COR.tintaSuave}">0%</text>
        <text x="180" y="116" text-anchor="middle" font-size="9" fill="${COR.tintaSuave}">meta 100%</text>
      </svg>`;
    },

    // Sankey simples em SVG (sem dependencia externa)
    sankey(svg, links) {
      const L = 960, A = 560, larguraNo = 12, margemTexto = 210, gap = 12, topo = 14;
      const xE = margemTexto, xD = L - margemTexto - larguraNo;
      const origens = {}, destinos = {};
      links.forEach((l) => { origens[l.origem] = (origens[l.origem] || 0) + l.valor; destinos[l.destino] = (destinos[l.destino] || 0) + l.valor; });
      const total = links.reduce((s, l) => s + l.valor, 0);
      const n = Math.max(Object.keys(origens).length, Object.keys(destinos).length);
      const escala = (A - topo * 2 - gap * n) / total;
      const paleta = ['#C2185B', '#3F63A8', '#B86E00', '#2F7A52', '#8E1446', '#6B45A8', '#2E8B8B', '#B5651D', '#6E6269', '#D06C93'];
      const ordemOrigem = Object.keys(origens).sort((a, b) => origens[b] - origens[a]);
      const cor = Object.fromEntries(ordemOrigem.map((o, i) => [o, paleta[i % paleta.length]]));
      const indice = Object.fromEntries(ordemOrigem.map((o, i) => [o, i]));
      const baricentro = {};
      Object.keys(destinos).forEach((d) => {
        const rel = links.filter((l) => l.destino === d);
        baricentro[d] = rel.reduce((s, l) => s + indice[l.origem] * l.valor, 0) / rel.reduce((s, l) => s + l.valor, 0);
      });
      const coluna = (nomes, mapa) => {
        let y = topo;
        const pos = {};
        nomes.forEach((nome) => { const h = mapa[nome] * escala; pos[nome] = { y0: y, h, cursor: y, valor: mapa[nome] }; y += h + gap; });
        return pos;
      };
      const pO = coluna(ordemOrigem, origens);
      const pD = coluna(Object.keys(destinos).sort((a, b) => baricentro[a] - baricentro[b]), destinos);
      let html = '';
      links.slice().sort((a, b) => indice[a.origem] - indice[b.origem]).forEach((l) => {
        const e = l.valor * escala, o = pO[l.origem], d = pD[l.destino];
        const x0 = xE + larguraNo, x1 = xD, xm = (x0 + x1) / 2;
        html += `<path class="sankey-link" fill="${cor[l.origem]}" d="M${x0},${o.cursor} C${xm},${o.cursor} ${xm},${d.cursor} ${x1},${d.cursor} L${x1},${d.cursor + e} C${xm},${d.cursor + e} ${xm},${o.cursor + e} ${x0},${o.cursor + e} Z"><title>${u.esc(l.origem)} → ${u.esc(l.destino)}: ${u.num(l.valor)} casos</title></path>`;
        o.cursor += e; d.cursor += e;
      });
      const nos = (pos, x, lado, corFn) => Object.entries(pos).forEach(([nome, p]) => {
        const xt = lado === 'end' ? x - 8 : x + larguraNo + 8, yt = p.y0 + p.h / 2;
        html += `<rect x="${x}" y="${p.y0}" width="${larguraNo}" height="${Math.max(p.h, 1)}" rx="2" fill="${corFn(nome)}"></rect>`;
        html += `<text x="${xt}" y="${yt - 2}" text-anchor="${lado}">${u.esc(u.semDrs(nome))}</text><text class="valor" x="${xt}" y="${yt + 12}" text-anchor="${lado}">${u.num(p.valor)} casos</text>`;
      });
      nos(pO, xE, 'end', (nome) => cor[nome]);
      nos(pD, xD, 'start', () => COR.tinta);
      svg.innerHTML = html;
    },
  };
})(window.P60);
