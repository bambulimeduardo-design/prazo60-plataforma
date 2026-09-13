// Prazo60 - Mapa de Atendimento: coropletico por DRS com detalhe lateral sincronizado aos filtros.

(function (P60) {
  const u = P60.u;
  let ultimo = null;

  const ROTULOS_CLASSE = { CRITICO: 'Crítico', ATENCAO: 'Atenção', MONITORAR: 'Monitorar', OPORTUNIDADE: 'Oportunidade', DADOS_INSUFICIENTES: 'Dados insuficientes' };

  function detalhe(p, numero) {
    const alvo = u.$('#mapa-detalhe');
    const d = p.por_drs.find((x) => String(x.drs) === String(numero));
    if (!d) {
      alvo.innerHTML = P60.ui.estado('vazio', 'Passe o mouse ou clique em uma região do mapa.');
      return;
    }
    const alerta = p.alertas.find((a) => a.drs === d.drs) || {};
    const selecionada = String(P60.estado.filtros.drs) === String(d.drs);
    const criticos = selecionada
      ? p.por_municipio.filter((m) => m.drs === d.drs && !m.suprimido && m.n >= P60.dados.opcoes.limites.min_ranking).sort((a, b) => b.pct_fora_60 - a.pct_fora_60).slice(0, 4)
      : [];
    const unidades = p.por_unidade.filter((x) => x.drs === d.drs && !x.suprimido && x.n >= P60.dados.opcoes.limites.min_ranking).length;
    alvo.innerHTML = `
      <p class="eyebrow">DRS ${d.drs} ${alerta.classificacao ? `· <span class="cls-${alerta.classificacao.toLowerCase()}">${ROTULOS_CLASSE[alerta.classificacao]}</span>` : ''}</p>
      <h3>${u.esc(u.semDrs(d.nome))}</h3>
      ${d.suprimido ? P60.ui.estado('vazio', 'Menos de 10 casos neste recorte.') : `
      <dl class="detalhe-lista">
        <dt>Demanda (casos no recorte)</dt><dd>${u.casos(d)}</dd>
        <dt>Acima de 60 dias</dt><dd class="${d.pct_fora_60 >= 70 ? 'fator-ruim' : ''}">${u.pct(d.pct_fora_60)}</dd>
        <dt>Mediana · média (dias)</dt><dd>${u.dias(d.mediana_dias)} · ${u.num(d.media_dias, 1)}</dd>
        <dt>Acima de 120 dias</dt><dd>${u.pct(d.pct_121_mais)}</dd>
        <dt>Oferta CACON/UNACON (${d.ano_oferta})</dt><dd>${d.estabelecimentos_cacon_unacon}</dd>
        <dt>Pressão (casos/estab.)</dt><dd>${u.num(d.pressao_casos_por_estabelecimento, 1)}</dd>
        <dt>Tratadas fora da região</dt><dd>${u.pct(d.pct_tratado_fora_da_regiao)}</dd>
        <dt>Unidades com ≥ 30 casos</dt><dd>${unidades}</dd>
        <dt>Variação ${alerta.ano_anterior || ''}→${alerta.ano_recente || ''}</dt><dd>${u.pp(alerta.variacao_pp)}</dd>
      </dl>`}
      ${criticos.length ? `<p class="cartao-pergunta">Municípios com maior % acima de 60 dias</p><ul class="passos-verticais">${criticos.map((m) => `<li><strong>${u.esc(m.nome)} · ${u.pct(m.pct_fora_60)}</strong>${u.num(m.n)} casos · mediana ${u.dias(m.mediana_dias)} dias</li>`).join('')}</ul>` : ''}
      <div class="linha-acoes">
        <button class="botao botao-secundario" type="button" data-filtrar-drs="${d.drs}">${selecionada ? 'Remover filtro' : 'Filtrar plataforma'}</button>
        <a class="botao botao-primario" href="#/gargalos">Ver gargalos</a>
      </div>`;
  }

  function desenhar() {
    if (!ultimo) return;
    const f = P60.estado.filtros;
    const svg = u.$('#mapa-svg');
    const legenda = P60.mapa.desenhar(svg, {
      porDrs: ultimo.por_drs,
      metrica: u.$('#mapa-metrica').value,
      municipios: ultimo.por_municipio,
      unidades: ultimo.por_unidade,
      mostrarMunicipios: u.$('#mapa-camada-municipios').checked,
      mostrarUnidades: u.$('#mapa-camada-unidades').checked,
      selecionado: f.drs,
      destacados: f.drs ? new Set([Number(f.drs)]) : null,
    });
    u.html(u.$('#mapa-legenda'), legenda);
    u.html(u.$('#mapa-nota'), `Regiões coloridas por ${f.dimensao === 'residencia' ? 'residência da paciente' : 'local de tratamento'}. Posição dos municípios aproximada pela sede municipal (${P60.dados.referencia.meta.projecao_mapa.taxa_acerto}% das sedes caem dentro do polígono da própria DRS nesta malha simplificada).`);
    detalhe(ultimo, f.drs);
  }

  P60.views.mapa = {
    titulo: 'Mapa de Atendimento',
    usaFiltros: true,
    iniciar() {
      ['#mapa-metrica', '#mapa-camada-municipios', '#mapa-camada-unidades'].forEach((s) => u.$(s).addEventListener('change', desenhar));
      const svg = u.$('#mapa-svg');
      const dica = u.$('#mapa-dica');
      const area = u.$('.mapa-area');
      svg.addEventListener('mousemove', (e) => {
        const path = e.target.closest('.drs-path');
        if (!path || !ultimo) { dica.hidden = true; return; }
        const d = ultimo.por_drs.find((x) => String(x.drs) === path.dataset.drs);
        const metrica = u.$('#mapa-metrica').value;
        const caixa = area.getBoundingClientRect();
        dica.innerHTML = `<strong>${u.esc(u.semDrs(d.nome))}</strong><br>${P60.mapa.ROTULOS[metrica].nome}: ${P60.mapa.ROTULOS[metrica].formato(d[metrica])}<br>${u.pct(d.pct_fora_60)} acima de 60 dias · ${u.casos(d)} casos`;
        dica.hidden = false;
        dica.style.left = Math.min(e.clientX - caixa.left + 14, caixa.width - 240) + 'px';
        dica.style.top = (e.clientY - caixa.top + 12) + 'px';
        if (!P60.estado.filtros.drs) detalhe(ultimo, path.dataset.drs);
      });
      svg.addEventListener('mouseleave', () => { dica.hidden = true; });
      const alternar = (numero) => P60.estado.definir({ drs: String(P60.estado.filtros.drs) === String(numero) ? '' : String(numero), municipio: '' });
      svg.addEventListener('click', (e) => { const path = e.target.closest('.drs-path'); if (path) alternar(path.dataset.drs); });
      svg.addEventListener('keydown', (e) => { const path = e.target.closest('.drs-path'); if (path && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); alternar(path.dataset.drs); } });
      u.$('#mapa-detalhe').addEventListener('click', (e) => { const b = e.target.closest('[data-filtrar-drs]'); if (b) alternar(b.dataset.filtrarDrs); });
    },
    renderizar(p) {
      ultimo = p;
      desenhar();
    },
  };
})(window.P60);
