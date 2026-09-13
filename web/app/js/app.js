// Prazo60 - inicializacao: sessao, filtros globais, roteamento por hash e Modo Apresentacao.

(function (P60) {
  const u = P60.u;

  const ROTAS = [
    ['inicio', 'Entender'], ['executiva', 'Entender'], ['panorama', 'Entender'],
    ['demanda-oferta', 'Localizar'], ['mapa', 'Localizar'], ['gargalos', 'Localizar'],
    ['encaminhar', 'Agir'], ['simulacao', 'Agir'],
    ['powerbi', 'Aprofundar'], ['ia', 'Aprofundar'], ['dados', 'Aprofundar'], ['sobre', 'Aprofundar'],
  ];
  const GRUPO = Object.fromEntries(ROTAS);

  const APRESENTACAO = [
    ['inicio', 'Problema'], ['executiva', 'Impacto'], ['dados', 'Dados'], ['panorama', 'Diagnóstico'],
    ['demanda-oferta', 'Demanda & Oferta'], ['gargalos', 'Gargalos'], ['encaminhar', 'Localizador'], ['simulacao', 'Simulação'],
    ['powerbi', 'Power BI'], ['ia', 'Inteligência Artificial'], ['mapa', 'Solução: onde agir'], ['sobre', 'Impacto esperado'],
  ];

  let rotaAtual = null;
  let pedido = 0;
  const iniciadas = new Set();

  // ------------------------------------------------------------------ filtros globais
  const ROTULOS_FILTRO = {
    ano: (v) => `Ano: ${v}`,
    mes: (v) => `Mês: ${u.mes(Number(v))}`,
    drs: (v) => `Região: ${u.semDrs(P60.dados.nomeDrs(v))}`,
    municipio: (v) => `Município: ${(P60.dados.municipio(v) || {}).nome || v}`,
    cnes: (v) => `Estabelecimento: ${(P60.dados.opcoes.unidades.find((x) => x.cnes === v) || {}).nome || v}`,
    tipo: (v) => `Tratamento: ${v}`,
    situacao: (v) => ({ dentro: 'Dentro do prazo', limite: 'Próximo do limite', acima: 'Acima de 60 dias' })[v],
  };

  function montarFiltros() {
    const o = P60.dados.opcoes;
    const opt = (valor, texto) => `<option value="${u.esc(valor)}">${u.esc(texto)}</option>`;
    u.$('#f-ano').innerHTML += o.anos.map((a) => opt(a, o.anos_parciais.includes(a) ? `${a} (parcial)` : a)).join('');
    u.$('#f-mes').innerHTML += Array.from({ length: 12 }, (_, i) => opt(i + 1, u.mes(i + 1))).join('');
    u.$('#f-drs').innerHTML += o.drs.map((d) => opt(d.numero, d.nome)).join('');
    u.$('#f-cnes').innerHTML += o.unidades.map((x) => opt(x.cnes, `${x.nome}${x.municipio ? ' · ' + x.municipio : ''}`)).join('');
    u.$('#f-tipo').innerHTML += o.tipos_tratamento.map((t) => opt(t, t)).join('');
    u.$('#lista-municipios').innerHTML = o.municipios.filter((m) => m.casos).map((m) => `<option value="${u.esc(m.nome)}"></option>`).join('');

    ['ano', 'mes', 'drs', 'cnes', 'tipo', 'situacao'].forEach((campo) => {
      u.$('#f-' + campo).addEventListener('change', (e) => {
        const parcial = { [campo]: e.target.value };
        if (campo === 'drs' && P60.estado.filtros.municipio) {
          const m = P60.dados.municipio(P60.estado.filtros.municipio);
          if (m && e.target.value && String(m.drs) !== e.target.value) parcial.municipio = '';
        }
        P60.estado.definir(parcial);
      });
    });
    const campoMun = u.$('#f-municipio');
    campoMun.addEventListener('change', () => {
      const nome = campoMun.value.trim().toLowerCase();
      if (!nome) { P60.estado.definir({ municipio: '' }); return; }
      const m = o.municipios.find((x) => x.nome.toLowerCase() === nome);
      if (!m) { P60.ui.toast('Município não encontrado. Escolha um nome da lista.'); sincronizarFiltros(); return; }
      P60.estado.definir({ municipio: m.ibge, drs: String(m.drs) });
    });
    u.$('#f-dimensao').addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (b) P60.estado.definir({ dimensao: b.dataset.valor });
    });
    u.$('#limpar-filtros').addEventListener('click', () => P60.estado.limpar());
    u.$('#chips-filtros').addEventListener('click', (e) => {
      const b = e.target.closest('[data-remover]');
      if (b) P60.estado.definir({ [b.dataset.remover]: '' });
    });
  }

  function sincronizarFiltros() {
    const f = P60.estado.filtros;
    ['ano', 'mes', 'drs', 'cnes', 'tipo', 'situacao'].forEach((c) => { u.$('#f-' + c).value = f[c]; });
    u.$('#f-municipio').value = f.municipio ? (P60.dados.municipio(f.municipio) || {}).nome || '' : '';
    u.$$('#f-dimensao button').forEach((b) => b.classList.toggle('ativo', b.dataset.valor === f.dimensao));
    const ativos = P60.estado.ativos();
    u.html(u.$('#chips-filtros'), ativos.map(([k, v]) => `<span class="chip">${u.esc(ROTULOS_FILTRO[k](v))}<button type="button" data-remover="${k}" aria-label="Remover filtro">×</button></span>`).join(''));
    u.$('#limpar-filtros').hidden = ativos.length === 0;
  }

  // ------------------------------------------------------------------ roteamento
  async function renderizarDados(nome) {
    const view = P60.views[nome];
    const secao = u.$(`[data-pagina="${nome}"]`);
    const id = ++pedido;
    secao.classList.add('carregando-overlay');
    secao.setAttribute('aria-busy', 'true');
    u.$('.aviso-erro', secao)?.remove();
    try {
      const painel = await P60.dados.painel();
      if (id !== pedido || rotaAtual !== nome) return;
      view.renderizar(painel);
    } catch (erro) {
      if (erro.status === 401) return;
      const aviso = document.createElement('div');
      aviso.className = 'aviso aviso-erro';
      aviso.setAttribute('role', 'alert');
      aviso.textContent = `Não foi possível carregar os dados: ${erro.message}`;
      u.$('.pagina-cabecalho', secao)?.after(aviso);
    } finally {
      if (id === pedido) { secao.classList.remove('carregando-overlay'); secao.removeAttribute('aria-busy'); }
    }
  }

  function navegar() {
    const nome = (location.hash.match(/^#\/([\w-]+)/) || [])[1];
    const destino = GRUPO[nome] ? nome : 'inicio';
    if (!GRUPO[nome]) { history.replaceState(null, '', '#/inicio'); }
    const view = P60.views[destino] || {};
    const trocou = rotaAtual !== destino;
    rotaAtual = destino;

    u.$$('.pagina').forEach((s) => { s.hidden = s.dataset.pagina !== destino; });
    u.$$('.menu a').forEach((a) => { const ativo = a.dataset.rota === destino; a.classList.toggle('ativo', ativo); if (ativo) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    const titulo = u.$(`.menu a[data-rota="${destino}"]`).textContent.trim();
    document.title = `${titulo} · Prazo60`;
    u.html(u.$('#migalhas'), destino === 'inicio' ? '<b>Início</b>' : `<a href="#/inicio">Prazo60</a> › ${GRUPO[destino]} › <b>${u.esc(titulo)}</b>`);
    u.$('#barra-filtros').hidden = !view.usaFiltros;
    document.body.classList.remove('menu-aberto');
    u.$('#botao-menu').setAttribute('aria-expanded', 'false');
    if (trocou) { window.scrollTo({ top: 0 }); u.$('#conteudo').focus({ preventScroll: true }); }

    if (view.iniciar && !iniciadas.has(destino)) { iniciadas.add(destino); view.iniciar(); }
    if (view.ativar) view.ativar();
    if (view.usaFiltros) renderizarDados(destino);
    atualizarApresentacao();
  }

  // ------------------------------------------------------------------ modo apresentacao
  function atualizarApresentacao() {
    if (!document.body.classList.contains('modo-apresentacao')) return;
    const i = Math.max(0, APRESENTACAO.findIndex(([r]) => r === rotaAtual));
    u.$('#apr-passo').textContent = `${i + 1} / ${APRESENTACAO.length}`;
    u.$('#apr-titulo').textContent = APRESENTACAO[i][1];
    u.$('#apr-anterior').disabled = i === 0;
    u.$('#apr-proximo').disabled = i === APRESENTACAO.length - 1;
  }

  function passo(delta) {
    const i = APRESENTACAO.findIndex(([r]) => r === rotaAtual);
    const alvo = APRESENTACAO[Math.max(0, Math.min(APRESENTACAO.length - 1, (i < 0 ? -1 : i) + delta))];
    location.hash = '#/' + alvo[0];
  }

  function alternarApresentacao(ativar) {
    document.body.classList.toggle('modo-apresentacao', ativar);
    u.$('#apresentacao').hidden = !ativar;
    if (ativar) {
      document.documentElement.requestFullscreen?.().catch(() => {});
      // A apresentacao sempre conta a historia desde o inicio: Problema -> ... -> Impacto esperado.
      if (rotaAtual === 'inicio') atualizarApresentacao();
      else location.hash = '#/inicio';
    } else if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
  }

  // ------------------------------------------------------------------ eventos gerais
  function configurarEventos() {
    window.addEventListener('hashchange', navegar);
    P60.estado.ouvir(() => {
      sincronizarFiltros();
      if ((P60.views[rotaAtual] || {}).usaFiltros) renderizarDados(rotaAtual);
    });
    u.$('#botao-menu').addEventListener('click', () => {
      const aberto = document.body.classList.toggle('menu-aberto');
      u.$('#botao-menu').setAttribute('aria-expanded', String(aberto));
    });
    u.$('#botao-sair').addEventListener('click', async () => {
      try { await P60.api.post('auth/logout'); } finally { try { sessionStorage.clear(); } catch (e) { /* ok */ } location.replace('/login'); }
    });
    u.$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') P60.ui.fecharModal(); });
    u.$('#modal-fechar').addEventListener('click', P60.ui.fecharModal);
    u.$('#botao-apresentacao').addEventListener('click', () => alternarApresentacao(true));
    u.$('#apr-sair').addEventListener('click', () => alternarApresentacao(false));
    u.$('#apr-anterior').addEventListener('click', () => passo(-1));
    u.$('#apr-proximo').addEventListener('click', () => passo(1));
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (!u.$('#modal').hidden) { P60.ui.fecharModal(); return; }
        if (document.body.classList.contains('modo-apresentacao')) alternarApresentacao(false);
      }
      if (!document.body.classList.contains('modo-apresentacao') || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') passo(1);
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') passo(-1);
    });
    document.addEventListener('fullscreenchange', () => {
      if (!document.fullscreenElement && document.body.classList.contains('modo-apresentacao')) alternarApresentacao(false);
    });
  }

  async function iniciar() {
    try {
      const [sessao] = await Promise.all([P60.api.get('auth/sessao'), P60.dados.carregarBase()]);
      u.$('#topo-usuario').textContent = sessao.usuario;
      const cob = P60.dados.referencia.cobertura;
      u.$('#topo-fonte').textContent = `${u.num(cob.casos)} casos · ${cob.anos[0]}–${cob.anos.at(-1)}`;
      montarFiltros();
      sincronizarFiltros();
      configurarEventos();
      navegar();
    } catch (erro) {
      if (erro.status === 401) return;
      u.html(u.$('#conteudo'), `<div class="pagina">${P60.ui.estado('erro', 'Não foi possível iniciar a plataforma: ' + erro.message)}</div>`);
    }
  }

  document.addEventListener('DOMContentLoaded', iniciar);
})(window.P60);
