// Prazo60 - mapa SVG dos 17 DRS (malha IBGE agregada) com camadas de municipios e unidades.
// Posicao dos municipios: sedes municipais projetadas no mesmo sistema do SVG (ver etl/relatorio_validacao.md).

(function (P60) {
  const u = P60.u;
  const ESCALA = ['#FBE3EC', '#F3B6CC', '#E07BA3', '#C2185B', '#7A1040'];
  const ROTULOS = {
    pct_fora_60: { nome: '% acima de 60 dias', formato: (v) => u.pct(v) },
    mediana_dias: { nome: 'Mediana de dias', formato: (v) => u.dias(v) + ' dias' },
    n: { nome: 'Casos', formato: (v) => u.num(v) },
    pressao_casos_por_estabelecimento: { nome: 'Casos por estabelecimento', formato: (v) => u.num(v, 1) },
  };

  function quebras(valores) {
    const v = valores.filter((x) => x !== null && x !== undefined).sort((a, b) => a - b);
    if (!v.length) return [];
    return [0.2, 0.4, 0.6, 0.8].map((q) => v[Math.min(v.length - 1, Math.floor(q * v.length))]);
  }

  function corPara(valor, limites) {
    if (valor === null || valor === undefined) return '#E9E2E5';
    const i = limites.findIndex((l) => valor <= l);
    return ESCALA[i === -1 ? ESCALA.length - 1 : i];
  }

  P60.mapa = {
    ROTULOS,
    desenhar(svg, opcoes) {
      const { porDrs, metrica, municipios = [], unidades = [], mostrarMunicipios, mostrarUnidades, selecionado, destacados } = opcoes;
      const ref = P60.dados.referencia;
      svg.setAttribute('viewBox', ref.mapa.viewBox);
      const porNumero = Object.fromEntries(porDrs.map((d) => [String(d.drs), d]));
      const limites = quebras(porDrs.map((d) => d[metrica]));

      let html = Object.entries(ref.mapa.paths).map(([num, caminho]) => {
        const d = porNumero[num];
        const classes = ['drs-path'];
        if (String(selecionado) === num) classes.push('selecionado');
        if (destacados && !destacados.has(Number(num))) classes.push('esmaecido');
        return `<path class="${classes.join(' ')}" data-drs="${num}" d="${caminho}" fill="${corPara(d ? d[metrica] : null, limites)}" tabindex="0" role="button" aria-label="${u.esc(d ? d.nome : 'DRS ' + num)}"></path>`;
      }).join('');

      if (mostrarMunicipios) {
        const maximo = Math.max(1, ...municipios.map((m) => m.n || 0));
        html += municipios
          .filter((m) => !m.suprimido && m.n && m.x !== null)
          .sort((a, b) => b.n - a.n)
          .map((m) => `<circle class="mun-ponto" cx="${m.x}" cy="${m.y}" r="${(1.5 + 16 * Math.sqrt(m.n / maximo)).toFixed(1)}"></circle>`)
          .join('');
      }
      if (mostrarUnidades) {
        const vistos = new Set();
        unidades.forEach((un) => {
          const mun = ref.municipios[un.municipio_ibge];
          if (!mun || mun.x === null || un.suprimido || !un.n || un.n < 30) return;
          const chave = un.municipio_ibge;
          const desloc = vistos.has(chave) ? 3 : 0;
          vistos.add(chave);
          html += `<rect class="uni-ponto" x="${(mun.x - 3 + desloc).toFixed(1)}" y="${(mun.y - 3 - desloc).toFixed(1)}" width="6" height="6" transform="rotate(45 ${mun.x + desloc} ${mun.y - desloc})"></rect>`;
        });
      }
      svg.innerHTML = html;

      const rotulo = ROTULOS[metrica];
      const faixas = [null, ...limites];
      return `<span class="legenda-escala"><span>${u.esc(rotulo.nome)}:</span>${ESCALA.map((c) => `<i style="background:${c}"></i>`).join('')}<span>${limites.length ? rotulo.formato(limites[0]) + ' → ' + rotulo.formato(limites[limites.length - 1]) + '+' : ''}</span></span>
        ${mostrarMunicipios ? '<span class="legenda-simbolo"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="rgba(255,255,255,.6)" stroke="#8E1446"/></svg>Município (área ∝ casos; &lt;10 omitidos)</span>' : ''}
        ${mostrarUnidades ? '<span class="legenda-simbolo"><svg viewBox="0 0 16 16"><rect x="5" y="5" width="6" height="6" transform="rotate(45 8 8)" fill="#2A2629"/></svg>Unidade tratante (≥ 30 casos)</span>' : ''}
        <span class="legenda-simbolo">${faixas.length > 1 ? 'Quintis entre as 17 regiões' : ''}</span>`;
    },
  };
})(window.P60);
