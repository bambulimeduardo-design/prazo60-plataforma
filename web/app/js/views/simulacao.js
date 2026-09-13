// Prazo60 - Simulador de Encaminhamento (AMBIENTE DE SIMULACAO), fluxo em 4 etapas.

(function (P60) {
  const u = P60.u;
  const st = { municipio: '', contexto: null, cenario: 'redistribuicao_regional', parametros: {}, preSelecao: '' };

  function irPara(etapa) {
    u.$$('.sim-etapa').forEach((el) => { el.hidden = Number(el.dataset.etapa) !== etapa; });
    u.$$('#sim-stepper li').forEach((li) => {
      const n = Number(li.dataset.etapa);
      li.classList.toggle('ativo', n === etapa);
      li.classList.toggle('feito', n < etapa);
    });
    u.$('#sim-stepper').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  // ---------------- etapa 1
  async function carregarContexto(ibge) {
    st.municipio = ibge;
    st.contexto = null;
    u.$('#sim-ir-2').disabled = true;
    if (!ibge) { u.html(u.$('#sim-contexto'), ''); return; }
    u.html(u.$('#sim-contexto'), P60.ui.estado('carregando', 'Lendo fluxos reais do município…'));
    try {
      const c = await P60.api.get('simulacao/contexto', { municipio: ibge });
      if (st.municipio !== ibge) return;
      st.contexto = c;
      st.parametros = { utilizacao_base: c.premissas_padrao.utilizacao_base, fracao_fila: c.premissas_padrao.fracao_fila, destino: c.destino_sugerido, cnes: c.unidade_principal.cnes };
      u.html(u.$('#sim-contexto'), `<div class="contexto-sim grade g2">
        <div><p class="cartao-pergunta">Onde as residentes tratam hoje (${c.periodo_base.join('–')}) ${P60.ui.selo('real')}</p>
          <table class="tabela"><thead><tr><th>Unidade</th><th class="num">%</th><th class="num">Distância</th></tr></thead>
          <tbody>${c.unidades_atuais.map((x) => `<tr><td>${u.esc(x.nome)}</td><td class="num">${u.pct(x.percentual)}</td><td class="num">${u.km(x.distancia_km)}</td></tr>`).join('')}</tbody></table>
          <p class="nota">${u.num(c.origem.casos_periodo)} casos de residentes no período · ${u.esc(c.origem.drs_nome)}</p></div>
        <div><p class="cartao-pergunta">Alternativas compatíveis mais próximas ${P60.ui.selo('real')} ${P60.ui.selo('estimativa', 'Distância')}</p>
          <table class="tabela"><thead><tr><th>Unidade</th><th class="num">Distância</th><th class="num">Casos/ano</th></tr></thead>
          <tbody>${c.alternativas.map((a) => `<tr><td>${u.esc(a.nome)} ${a.sugerida ? '<span class="tag tag-media">sugerida</span>' : ''}</td><td class="num">${u.km(a.distancia_km)}</td><td class="num">${u.num(a.volume_anual, 0)}</td></tr>`).join('') || '<tr><td colspan="3">Nenhuma alternativa com volume suficiente.</td></tr>'}</tbody></table>
          <p class="nota">Alternativas: habilitação confirmada ou ≥ 30 casos C50, com ≥ 50 casos no período base.</p></div>
      </div>`);
      u.$('#sim-ir-2').disabled = false;
    } catch (erro) {
      u.html(u.$('#sim-contexto'), P60.ui.estado('erro', erro.message));
    }
  }

  // ---------------- etapa 2
  function renderizarCenarios() {
    const c = st.contexto;
    u.html(u.$('#sim-cenarios'), c.cenarios.map((x) => `<label class="cenario"><input type="radio" name="sim-cenario" value="${x.id}" ${x.id === st.cenario ? 'checked' : ''}><strong>${u.esc(x.nome)}</strong><span>${u.esc(x.descricao)}</span></label>`).join(''));
    renderizarParametros();
    const rho = u.$('#sim-rho'), fila = u.$('#sim-fila');
    rho.value = Math.round(st.parametros.utilizacao_base * 100);
    fila.value = Math.round(st.parametros.fracao_fila * 100);
    atualizarPremissas();
  }

  function renderizarParametros() {
    const c = st.contexto;
    const p = st.parametros;
    const alvo = u.$('#sim-parametros');
    const faixa = (id, rotulo, min, max, valor, sufixo) => `<label class="deslizante filtro-largo"><span>${rotulo}: <b data-saida="${id}">${valor}${sufixo}</b></span><input type="range" data-param="${id}" min="${min}" max="${max}" step="5" value="${valor}"></label>`;
    const opcoes = (lista, selecionado) => lista.map((x) => `<option value="${x.cnes}" ${x.cnes === selecionado ? 'selected' : ''}>${u.esc(x.nome)} (${u.km(x.distancia_km)})</option>`).join('');
    let html = '';
    if (st.cenario === 'demanda_elevada') html = faixa('aumento_pct', 'Aumento de casos entre residentes do município', 5, 60, p.aumento_pct ?? 20, '%');
    if (st.cenario === 'aumento_demanda') html = faixa('aumento_pct', `Aumento de casos em toda a ${u.esc(u.semDrs(c.origem.drs_nome))}`, 5, 60, p.aumento_pct ?? 15, '%');
    if (st.cenario === 'unidade_indisponivel') html = `<label class="filtro filtro-largo"><span>Unidade indisponível</span><select data-param="cnes">${opcoes(c.unidades_atuais, p.cnes)}</select></label><p class="nota">As residentes dessa unidade vão para as 3 alternativas mais próximas, proporcionalmente ao porte e inversamente à distância.</p>`;
    if (st.cenario === 'redistribuicao_regional') html = faixa('percentual', `Parte das residentes hoje na unidade principal (${u.esc(c.unidade_principal.nome)})`, 10, 100, p.percentual ?? 30, '%') + `<label class="filtro filtro-largo"><span>Unidade de destino</span><select data-param="destino">${opcoes(c.alternativas, p.destino)}</select></label>`;
    if (st.cenario === 'capacidade_normal') html = '<p class="nota">Sem parâmetros: mostra a linha de base do modelo ao lado dos valores reais observados.</p>';
    alvo.innerHTML = `<div class="parametros">${html}</div>`;
  }

  function atualizarPremissas() {
    st.parametros.utilizacao_base = Number(u.$('#sim-rho').value) / 100;
    st.parametros.fracao_fila = Number(u.$('#sim-fila').value) / 100;
    u.$('#sim-rho-valor').textContent = u.$('#sim-rho').value + '%';
    u.$('#sim-fila-valor').textContent = u.$('#sim-fila').value + '%';
  }

  function corpoRequisicao() {
    const p = st.parametros;
    const corpo = { municipio: st.municipio, cenario: st.cenario, utilizacao_base: p.utilizacao_base, fracao_fila: p.fracao_fila };
    if (['demanda_elevada', 'aumento_demanda'].includes(st.cenario)) corpo.aumento_pct = Number(p.aumento_pct ?? (st.cenario === 'demanda_elevada' ? 20 : 15));
    if (st.cenario === 'unidade_indisponivel') corpo.cnes = p.cnes;
    if (st.cenario === 'redistribuicao_regional') { corpo.percentual = Number(p.percentual ?? 30); corpo.destino = p.destino; }
    return corpo;
  }

  // ---------------- etapa 3
  function renderizarRevisao() {
    const c = st.contexto;
    const corpo = corpoRequisicao();
    const cen = c.cenarios.find((x) => x.id === st.cenario);
    const nome = (cnes) => ([...c.unidades_atuais, ...c.alternativas].find((x) => x.cnes === cnes) || {}).nome || cnes;
    const detalhes = [];
    if (corpo.aumento_pct !== undefined) detalhes.push(['Aumento de demanda', corpo.aumento_pct + '%']);
    if (corpo.cnes) detalhes.push(['Unidade indisponível', nome(corpo.cnes)]);
    if (corpo.percentual !== undefined) detalhes.push(['Redistribuir', `${corpo.percentual}% de ${c.unidade_principal.nome}`], ['Destino', nome(corpo.destino)]);
    u.html(u.$('#sim-revisao'), `<dl class="revisao">
      <dt>Município de origem</dt><dd>${u.esc(c.origem.nome)} · ${u.esc(c.origem.drs_nome)}</dd>
      <dt>Período base (dado real)</dt><dd>${c.periodo_base.join('–')} · ${u.num(c.origem.casos_periodo)} casos</dd>
      <dt>Cenário</dt><dd>${u.esc(cen.nome)}</dd>
      ${detalhes.map(([k, v]) => `<dt>${k}</dt><dd>${u.esc(v)}</dd>`).join('')}
      <dt>Premissa: utilização de base</dt><dd>${Math.round(corpo.utilizacao_base * 100)}%</dd>
      <dt>Premissa: espera sensível à fila</dt><dd>${Math.round(corpo.fracao_fila * 100)}%</dd>
    </dl><div class="aviso aviso-simulacao" style="margin-top:16px">O resultado é um cenário hipotético para comparar alternativas. Não confirma vaga, não prevê a realidade operacional e não substitui a regulação.</div>`);
  }

  // ---------------- etapa 4
  function renderizarResultado(r) {
    const o = r.resultado_origem;
    const ic = (v, suf, inv) => P60.ui.variacao(v, { sufixo: suf, casas: 1, inverter: inv });
    u.html(u.$('#sim-resultado'), `
      <div class="resultado-topo">
        <div class="cenario-bloco"><h4>Cenário atual ${P60.ui.selo('real')}</h4>
          <div class="valor-duplo"><div><b>${u.dias(o.real_observado.mediana_dias)}</b><span>dias (mediana)</span></div><div><b>${u.pct(o.real_observado.pct_fora_60)}</b><span>acima de 60 dias</span></div></div>
          <p class="nota">${u.num(o.real_observado.n)} residentes de ${u.esc(r.origem.nome)}, ${r.periodo_base.join('–')}. Linha de base do modelo: ${u.dias(o.modelo_base.mediana_dias)} dias · ${u.pct(o.modelo_base.pct_fora_60)}.</p></div>
        <div class="cenario-bloco simulado"><h4>Cenário simulado ${P60.ui.selo('simulacao')}</h4>
          <div class="valor-duplo"><div><b>${u.dias(o.modelo_simulado.mediana_dias)}</b><span>dias (mediana)</span></div><div><b>${u.pct(o.modelo_simulado.pct_fora_60)}</b><span>acima de 60 dias</span></div></div>
          <p class="nota">${u.esc(r.cenario.nome)}</p></div>
        <div class="cenario-bloco impacto"><h4>Impacto estimado ${P60.ui.selo('estimativa')}</h4>
          <div class="valor-duplo"><div><b>${ic(o.variacao_mediana_dias, ' d')}</b><span>mediana vs base do modelo</span></div><div><b>${ic(o.variacao_pct_fora_pp, ' p.p.')}</b><span>acima de 60 dias</span></div></div>
          <p class="nota">${o.pacientes_redistribuidos_ano ? `${u.num(o.pacientes_redistribuidos_ano, 1)} pacientes/ano mudam de unidade · ` : ''}deslocamento médio ${u.km(o.deslocamento_medio_base_km)} → ${u.km(o.deslocamento_medio_simulado_km)}</p></div>
      </div>
      <div class="cartao"><p class="cartao-pergunta">Leitura do resultado</p><ul class="leitura">${r.leitura.map((l) => `<li>${u.esc(l)}</li>`).join('')}</ul></div>
      <div class="grade g2">
        <div class="cartao"><p class="cartao-pergunta">Como a demanda das residentes seria distribuída?</p><div class="grafico grafico-medio"><canvas id="graf-sim-distribuicao"></canvas></div></div>
        <div class="cartao"><p class="cartao-pergunta">Premissas e fontes</p>
          <table class="tabela"><tbody>${r.premissas.map((p) => `<tr><td><strong>${u.esc(p.nome)}</strong><br><span class="nota">${u.esc(p.explicacao)}</span></td><td class="num">${u.esc(p.valor)}<br>${P60.ui.selo(p.tipo === 'PREMISSA' ? 'premissa' : 'real', p.tipo === 'PREMISSA' ? 'Premissa' : 'Dado real')}</td></tr>`).join('')}</tbody></table></div>
      </div>
      <div class="cartao"><p class="cartao-pergunta">Carga estimada por unidade ${P60.ui.selo('simulacao')}</p>
        <div class="tabela-rolagem"><table class="tabela"><thead><tr><th>Unidade</th><th class="num">Distância</th><th class="num">Casos/ano (base → sim.)</th><th class="num">Residentes/ano</th><th>Utilização estimada</th><th class="num">Mediana (base → sim.)</th></tr></thead>
        <tbody>${r.unidades.map((x) => `<tr class="${x.saturada ? 'destaque' : ''}"><td>${u.esc(x.nome)} ${x.indisponivel ? '<span class="tag">indisponível</span>' : ''}${x.saturada ? '<span class="tag tag-forte" style="background:var(--alert-soft);color:var(--alert)">saturação</span>' : ''}</td>
          <td class="num">${u.km(x.distancia_km)}</td><td class="num">${u.num(x.volume_anual_base, 0)} → ${u.num(x.volume_anual_simulado, 0)}</td><td class="num">${u.num(x.residentes_ano_base, 1)} → ${u.num(x.residentes_ano_simulado, 1)}</td>
          <td>${x.indisponivel ? '—' : `<div class="barra-carga" title="${u.pct(x.utilizacao_simulada)}"><i style="width:${x.utilizacao_simulada}%;background:${x.utilizacao_simulada >= 95 ? 'var(--alert)' : x.utilizacao_simulada > x.utilizacao_base ? 'var(--warn)' : 'var(--success)'}"></i></div><span class="nota">${u.pct(x.utilizacao_base, 0)} → ${u.pct(x.utilizacao_simulada, 0)}</span>`}</td>
          <td class="num">${u.dias(x.mediana_base_dias)} → ${x.mediana_simulada_dias === null ? '—' : u.dias(x.mediana_simulada_dias)}</td></tr>`).join('')}</tbody></table></div>
      </div>
      <div class="grade g2">
        <div class="cartao"><p class="cartao-pergunta">Limitações desta simulação</p><ul class="leitura">${r.limitacoes.map((l) => `<li>${u.esc(l)}</li>`).join('')}</ul></div>
        <div class="cartao"><p class="cartao-pergunta">Dados necessários para tornar a recomendação operacional</p><ul class="leitura">${r.dados_necessarios.map((l) => `<li>${u.esc(l)}</li>`).join('')}</ul></div>
      </div>`);
    const d = r.distribuicao;
    P60.graficos.barras('graf-sim-distribuicao', {
      rotulos: d.map((x) => x.nome.length > 34 ? x.nome.slice(0, 32) + '…' : x.nome),
      series: [
        { rotulo: 'Cenário atual', dados: d.map((x) => x.antes_pct), cor: P60.graficos.COR.neutro },
        { rotulo: 'Cenário simulado', dados: d.map((x) => x.depois_pct), cor: P60.graficos.COR.aviso },
      ],
      horizontal: true,
      tooltipSufixo: '% das residentes',
    });
  }

  async function executar() {
    const botao = u.$('#sim-executar');
    botao.disabled = true;
    botao.textContent = 'Simulando…';
    irPara(4);
    u.html(u.$('#sim-resultado'), `<div class="cartao">${P60.ui.estado('carregando', 'Executando simulação…')}</div>`);
    try {
      renderizarResultado(await P60.api.post('simulacao', corpoRequisicao()));
    } catch (erro) {
      u.html(u.$('#sim-resultado'), `<div class="cartao">${P60.ui.estado('erro', erro.message)}</div>`);
    } finally {
      botao.disabled = false;
      botao.textContent = 'Executar simulação';
    }
  }

  P60.views.simulacao = {
    titulo: 'Simulação',
    iniciar() {
      const muns = P60.dados.opcoes.municipios.filter((m) => m.simulavel);
      const [a, b] = P60.dados.opcoes.periodo_base_simulacao;
      u.$('#sim-municipio').innerHTML = '<option value="">Selecione…</option>' + muns.map((m) => `<option value="${m.ibge}">${u.esc(m.nome)} · ${u.esc(u.semDrs(P60.dados.nomeDrs(m.drs)))}</option>`).join('');
      u.html(u.$('#sim-nota-municipios'), `Disponível para ${muns.length} municípios com pelo menos 20 casos de residentes em ${a}–${b}, para que o cenário tenha base estatística mínima.`);
      u.$('#sim-municipio').addEventListener('change', (e) => carregarContexto(e.target.value));
      u.$('#sim-ir-2').addEventListener('click', () => { renderizarCenarios(); irPara(2); });
      u.$('#sim-cenarios').addEventListener('change', (e) => { if (e.target.name === 'sim-cenario') { st.cenario = e.target.value; renderizarParametros(); } });
      u.$('#sim-parametros').addEventListener('input', (e) => {
        const campo = e.target.dataset.param;
        if (!campo) return;
        st.parametros[campo] = e.target.value;
        const saida = u.$(`[data-saida="${campo}"]`);
        if (saida) saida.textContent = e.target.value + '%';
      });
      ['#sim-rho', '#sim-fila'].forEach((s) => u.$(s).addEventListener('input', atualizarPremissas));
      u.$('#sim-ir-3').addEventListener('click', () => { renderizarRevisao(); irPara(3); });
      u.$('#sim-executar').addEventListener('click', executar);
      u.$('.pagina-simulacao').addEventListener('click', (e) => { const v = e.target.closest('[data-voltar]'); if (v) irPara(Number(v.dataset.voltar)); });
    },
    ativar() {
      const alvo = st.preSelecao || (P60.estado.filtros.municipio && (P60.dados.municipio(P60.estado.filtros.municipio) || {}).simulavel ? P60.estado.filtros.municipio : '');
      st.preSelecao = '';
      if (alvo && alvo !== st.municipio && u.$(`#sim-municipio option[value="${alvo}"]`)) {
        u.$('#sim-municipio').value = alvo;
        irPara(1);
        carregarContexto(alvo);
      }
    },
    preSelecionar(ibge) { st.preSelecao = ibge; },
  };
})(window.P60);
