# Colocar o Prazo60 online (Render)

Resultado: um endereço HTTPS público, por exemplo `https://prazo60.onrender.com`, que abre a
tela de login. Só entra quem tiver o usuário **DATAHOLICS** e a senha definida pelo grupo.

> Quem executa estes passos é alguém do grupo. Criação de conta, login e publicação são
> ações pessoais e não são feitas por ferramentas automáticas.

## 1. Subir o código para o GitHub (repositório **privado**)

A pasta `server/data` contém a base minimizada (sem identificação, mas em nível de caso).
Por isso o repositório deve ser **privado**.

```bash
cd C:\Projetos\prazo60-plataforma
git add .
git commit -m "Plataforma Prazo60 v2"
git remote add origin https://github.com/<usuario>/prazo60-plataforma.git
git push -u origin main
```

## 2. Criar o serviço no Render

1. Entre em https://dashboard.render.com com a conta do GitHub.
2. **New > Blueprint** e selecione o repositório `prazo60-plataforma`.
3. O Render lê o `render.yaml` e cria o serviço `prazo60`:
   - instala `requirements.txt`;
   - gera um `SESSION_SECRET` aleatório automaticamente;
   - usa `/api/saude` como verificação de saúde.
4. Clique em **Apply**. O primeiro deploy leva de 2 a 4 minutos.
5. Abra a URL exibida no topo do serviço. Deve aparecer a tela de login.

## 3. Conferir a segurança após publicar

| Verificação | Como |
|---|---|
| HTTPS ativo | O endereço começa com `https://` (o Render emite o certificado) |
| Login obrigatório | Abrir `https://.../app/` em aba anônima redireciona para `/login` |
| API protegida | `https://.../api/painel` em aba anônima responde 401 |
| Senha errada | 5 tentativas erradas bloqueiam novas tentativas por 15 minutos |
| Não indexado | Cabeçalho `X-Robots-Tag: noindex` e `/robots.txt` bloqueando tudo |

## 4. Variáveis de ambiente (painel Environment)

| Variável | Obrigatória | Uso |
|---|---|---|
| `SESSION_SECRET` | sim (gerada) | Assina o cookie de sessão. Trocar desloga todos. |
| `PRAZO60_AMBIENTE` | sim | `producao` ativa cookie Secure, HSTS e esconde a documentação da API |
| `APP_USER` | não | Padrão `DATAHOLICS` |
| `APP_PASSWORD_HASH` | não | Troca a senha sem mexer no código (ver abaixo) |
| `SESSION_MAX_HOURS` | não | Duração da sessão, padrão 8 |
| `POWERBI_EMBED_URL` | não | Link de incorporação do relatório Power BI |
| `SELECT_AI_HABILITADO` + `ORACLE_*` | não | Liga o Prazo60 AI (ver `docs/INTEGRACOES.md`) |

### Trocar a senha

```bash
python scripts/gerar_hash_senha.py
```

Cole o resultado em `APP_PASSWORD_HASH` no painel do Render e salve. O serviço reinicia sozinho.

## 5. Plano gratuito: o que esperar

- O serviço hiberna após 15 minutos sem acesso; o primeiro acesso seguinte leva cerca de 30 a 50 segundos.
  **Antes de uma apresentação, abra o site alguns minutos antes.**
- Para ficar sempre ligado, basta mudar o plano do serviço para *Starter* no painel.

## 6. Domínio próprio (opcional)

Em **Settings > Custom Domains**, adicione, por exemplo, `prazo60.seudominio.com.br` e crie o
registro CNAME indicado no seu provedor de DNS. O certificado HTTPS é emitido automaticamente.

## 7. Atualizar o site

Todo `git push` na branch `main` gera um novo deploy automático. Para atualizar os dados:

```bash
python etl/build_data.py      # recalcula server/data e o relatório de validação
python -m pytest -q           # confere números, segurança e fluxos
git add server/data etl/relatorio_validacao.md && git commit -m "Atualiza dados" && git push
```
