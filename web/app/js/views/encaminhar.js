// Prazo60 - Para onde encaminhar: localizador de unidades a partir do municipio de origem.
// Mostra onde existe servico nos dados oficiais. Nunca afirma disponibilidade de vaga.

(function (P60) {
  const u = P60.u;
  const SBC = '354870';
  let carregado = null;

  function preencherMunicipios() {
    const drs = u.$('#enc-drs').value;
    const select = u.$('#enc-municipio');
    const atual = select.value;
    const lista = P60.dados.opcoes.municipios.filter((m) => (!drs || String(m.drs) === drs));
    select.innerHTML = '<option value="">Selecione…</option>' + lista.map((m) => `<option value="${m.ibge}">${u.esc(m.nome)}${m.casos ? '' : ' (sem casos na base)'}</option>`).join('');
    if (lista.some((m) => m.ibge === atual)) select.value = atual;
  }

  function linkCnes(un) {
    return `https://cnes.datasus.gov.br/pages/estabelecimentos/ficha/index.jsp?coUnidade=${encodeURIComponent(un.municipio_ibge + un.cnes)}`;
  }

  function cartaoUnidade(un) {
    const compat = un.compatibilidade === 'confirmada'
      ? `<span class="tag tag-forte">Habilitação confirmada (CIB-SP)${un.habilitacao ? ': ' + u.esc(un.habilitacao) : ''}</span>`
      : '<span class="tag tag-media">Atende câncer de mama na base (≥ 30 casos)</span>';
    const residentes = un.residentes_origem_atendidos;
    return `<article class="unidade ${un.mesmo_municipio ? 'mesmo-municipio' : ''}">
      <div class="unidade-distancia"><b>${u.km(un.distancia_km)}</b><small>${u.esc(un.faixa_distancia)}</small></div>
      <div>
        <h4>${u.esc(un.nome)} ${un.nome_confirmado ? '' : '<span class="tag">nome a confirmar no CNES</span>'}</h4>
        <p class="unidade-meta">${u.esc(un.municipio)} · ${u.esc(u.semDrs(un.drs_nome))} · CNES ${u.esc(un.cnes)}${un.gestao ? ' · gestão ' + u.esc(un.gestao) : ''}</p>
        <div class="unidade-tags">
          ${compat}
          ${un.mesmo_municipio ? '<span class="tag">No próprio município</span>' : un.mesma_regiao ? '<span class="tag">Mesma DRS</span>' : '<span class="tag">Outra DRS</span>'}
          ${residentes && residentes !== 0 ? `<span class="tag">Já atendeu ${residentes === '<10' ? '&lt;10' : u.num(residentes)} residentes da origem</span>` : ''}
          <span class="tag">Endereço e disponibilidade: não disponíveis nas bases carregadas</span>
        </div>
      </div>
      <div class="unidade-numeros">
        <span><b>${un.casos_c50_base === null ? '&lt;10' : u.num(un.casos_c50_base)}</b>casos C50</span>
        <span><b>${u.pct(un.pct_fora_60)}</b>acima 60 d</span>
        <span><b>${u.dias(un.mediana_dias)}</b>mediana (dias)</span>
        <a href="${linkCnes(un)}" target="_blank" rel="noopener noreferrer">Consultar ficha no CNES ↗</a>
      </div>
    </article>`;
  }

  function renderizar(r) {
    const o = r.origem;
    const atuais = r.onde_tratam_hoje;
    u.html(u.$('#enc-resultado'), `
      <div class="cartao">
        <div class="origem-resumo">
          <div><p class="eyebrow">Município de origem ${P60.ui.selo('real')}</p><h3>${u.esc(o.nome)}</h3><p class="nota">${u.esc(o.drs_nome)}</p></div>
          <div><p class="kpi-rotulo">Casos de residentes</p><p class="kpi-valor">${u.casos(o)}</p></div>
          <div><p class="kpi-rotulo">Acima de 60 dias</p><p class="kpi-valor ${o.pct_fora_60 >= 60 ? 'alerta' : ''}">${u.pct(o.pct_fora_60)}</p></div>
          <div><p class="kpi-rotulo">Mediana (dias)</p><p class="kpi-valor">${u.dias(o.mediana_dias)}</p></div>
          <div><p class="kpi-rotulo">Tratadas fora do município</p><p class="kpi-valor">${u.pct(o.pct_tratado_fora_do_municipio)}</p></div>
        </div>
      </div>
      ${atuais.length ? `<div class="cartao"><p class="cartao-pergunta">Onde as residentes já iniciam tratamento hoje? ${P60.ui.selo('real')}</p>
        <div class="tabela-rolagem"><table class="tabela"><thead><tr><th>Unidade</th><th class="num">Casos</th><th class="num">% das residentes</th><th class="num">Distância</th><th class="num">Acima de 60 dias</th><th class="num">Mediana</th></tr></thead>
        <tbody>${atuais.map((a) => `<tr><td>${u.esc(a.nome)}</td><td class="num">${u.num(a.casos)}</td><td class="num">${u.pct(a.percentual)}</td><td class="num">${u.km(a.distancia_km)}</td><td class="num ${a.pct_fora_60 >= 70 ? 'ruim' : ''}">${u.pct(a.pct_fora_60)}</td><td class="num">${u.dias(a.mediana_dias)}</td></tr>`).join('')}</tbody></table></div>
        <p class="nota">Apenas unidades com ≥ 10 residentes atendidas. Percentuais e medianas referem-se às residentes deste município naquela unidade.</p></div>` : ''}
      <div class="cartao">
        <div class="cartao-cabecalho">
          <p class="cartao-pergunta">Unidades compatíveis mais próximas ${P60.ui.selo('real')} ${P60.ui.selo('estimativa', 'Distância estimada')}</p>
          <span><button class="botao-info" data-indicador="distancia">Distância</button> <button class="botao-info" data-indicador="compatibilidade">Compatibilidade</button></span>
        </div>
        ${r.unidades.length ? `<div class="unidades-lista">${r.unidades.map(cartaoUnidade).join('')}</div>` : P60.ui.estado('vazio', 'Nenhuma unidade compatível com coordenadas conhecidas.')}
        <p class="nota"><strong>Ordenação:</strong> ${r.ordenacao.map((x, i) => `${i + 1}. ${u.esc(x)}`).join(' · ')}. Exibindo ${r.unidades.length} de ${r.total_compativeis} unidades compatíveis; ${r.unidades_com_poucos_casos_omitidas} unidades com menos de 30 casos e sem habilitação confirmada foram omitidas.</p>
      </div>
      <div class="aviso aviso-limite">${u.esc(r.aviso_disponibilidade)} Para transformar esta lista em encaminhamento real seria necessário: ocupação e agenda por unidade (ex.: CROSS-SP), habilitação vigente por modalidade e regras de regulação pactuadas.</div>
      <div class="linha-acoes"><a class="botao botao-primario" href="#/simulacao" data-simular="${o.ibge}">Simular redistribuição para ${u.esc(o.nome)} →</a></div>`);
  }

  async function carregar(ibge) {
    if (!ibge) { u.html(u.$('#enc-resultado'), P60.ui.estado('vazio', 'Selecione um município de origem.')); return; }
    carregado = ibge;
    u.html(u.$('#enc-resultado'), P60.ui.estado('carregando', 'Buscando unidades próximas…'));
    try {
      const r = await P60.api.get('localizador', { municipio: ibge, limite: 12 });
      if (carregado === ibge) renderizar(r);
    } catch (erro) {
      u.html(u.$('#enc-resultado'), P60.ui.estado('erro', erro.message));
    }
  }

  function selecionar(ibge) {
    const m = P60.dados.municipio(ibge);
    if (!m) return;
    u.$('#enc-drs').value = String(m.drs);
    preencherMunicipios();
    u.$('#enc-municipio').value = ibge;
    carregar(ibge);
  }

  P60.views.encaminhar = {
    titulo: 'Para onde encaminhar?',
    iniciar() {
      u.$('#enc-drs').innerHTML += P60.dados.opcoes.drs.map((d) => `<option value="${d.numero}">${u.esc(d.nome)}</option>`).join('');
      preencherMunicipios();
      u.$('#enc-drs').addEventListener('change', preencherMunicipios);
      u.$('#enc-municipio').addEventListener('change', (e) => carregar(e.target.value));
      u.$('#enc-exemplo').addEventListener('click', () => selecionar(SBC));
      u.$('#enc-resultado').addEventListener('click', (e) => {
        const link = e.target.closest('[data-simular]');
        if (link) P60.views.simulacao.preSelecionar(link.dataset.simular);
      });
    },
    ativar() {
      const doFiltro = P60.estado.filtros.municipio;
      if (!carregado && doFiltro) selecionar(doFiltro);
    },
    selecionar,
  };
})(window.P60);
