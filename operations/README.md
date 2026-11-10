# Operação do MiroFish no Codex Cloud

Auxiliares para preparar e iniciar o aplicativo sem alterar seu código original.
Repositório associado: https://github.com/rodafacilapp-ops/MiroFish.
Estes três arquivos não contêm credenciais e podem ser versionados:
`control.py`, `setup.sh`, `README.md`.

## Preparar uma tarefa

Na raiz do checkout (o caminho validado foi `/workspace/MiroFish`):

```bash
bash operations/setup.sh
python3 operations/control.py start
python3 operations/control.py status
```

Pré-requisitos: npm, uv, Python 3 do ambiente e Node 20.19+, 22.12+ ou 24+.
O setup instala Python gerenciado 3.11 e as dependências oficiais com `npm ci`
e `uv sync --locked`. Não altera manifests ou lockfiles. Não inicia serviços,
não chama OpenAI/Zep e não executa simulações. A instalação inicial inclui
pacotes grandes de PyTorch/CUDA por exigência das dependências oficiais.

O setup pode ser repetido: reutiliza as dependências Node se os lockfiles e a
versão do runtime corresponderem; o uv reconcilia a .venv usando o lockfile.
Para reinstalar Node após corrupção manual, remova somente o marcador
`root.node-fingerprint` ou `frontend.node-fingerprint` no diretório de runtime
e rode o setup novamente.

Python, caches, marcadores, PID, log do iniciador e relatórios baixados ficam em
`/workspace/.mirofish-runtime/MiroFish` por padrão: fora do checkout e fora de
`/tmp`. Para outro caminho de checkout, usa-se
`<pasta-pai>/.mirofish-runtime/<nome-do-checkout>`.
`MIROFISH_RUNTIME_DIR` pode definir outro diretório absoluto, externo ao Git;
use o mesmo valor no setup e no controle.

Uma publicação do ambiente pode preservar a instalação preparada no snapshot.
Isso evita instalar tudo novamente em tarefas restauradas desse snapshot.
Um clone Git limpo contém os auxiliares, mas precisa executar o setup ao menos
uma vez. Não se presume que processos, autenticação de runtime ou dados criados
depois da publicação sobrevivam entre tarefas. A restauração de uma nova tarefa
precisa ser confirmada depois de publicar; a validação local não a comprova.

## Configurações seguras

Mantenha no ambiente, nunca em Git, .env, argumentos ou frontend:

| Binding | Destino HTTPS |
|---|---|
| LLM_API_KEY | api.openai.com |
| ZEP_API_KEY | api.getzep.com |

Variáveis não secretas: `LLM_BASE_URL=https://api.openai.com/v1` e
`LLM_MODEL_NAME=gpt-5.6-luna`. O iniciador remove espaços e quebras de linha nas
extremidades de LLM_BASE_URL para seu processo; rejeita outro endpoint.
Isso não corrige o campo salvo nas configurações do ambiente.

Os valores dos bindings podem ser placeholders substituídos pelo proxy seguro
apenas nas rotas HTTPS autorizadas. Preserve as variáveis herdadas de proxy e
certificados, com TLS verificado. Não tente exportar os valores reais.

O iniciador define `PYTHON_DOTENV_DISABLED=1` para impedir que o carregamento
original de .env com override substitua os bindings seguros. Isso é suportado
pelo python-dotenv 1.2.1 do lockfile atual.
O Zep SDK 3.25.0 original preserva `Authorization: Api-Key ...` e
`User-Agent: zep-cloud/3.25.0`; não substitua por Bearer ou pelo User-Agent urllib.

## Serviços e controle

`start` executa o comando oficial `npm run dev` na raiz do checkout, separado
da sessão do terminal. Depois de iniciar, aguarde alguns segundos e use `status`.
O comando de status retorna código diferente de zero se algum serviço não
responder HTTP 200. O backend fica em 127.0.0.1:5001, sem debug.
O frontend Vite usa a porta 3000 e `VITE_API_BASE_URL=/`, aproveitando o proxy
`/api` para o backend. Nenhuma hospedagem externa é configurada.

```bash
python3 operations/control.py status
python3 operations/control.py reports
python3 operations/control.py download REPORT_ID
python3 operations/control.py stop
```

`stop` sinaliza somente o grupo de processos registrado pelo auxiliar e confere
comando, grupo e identidade temporal do PID antes de sinalizá-lo. Não adota
serviços iniciados por outros meios. Ao migrar do auxiliar antigo fora do Git,
pare aquele serviço com o controle antigo antes de iniciar por este.

Logs: `<runtime>/dev.log`; relatórios baixados:
`<runtime>/artifacts/REPORT_ID.md`. Download recupera somente relatório existente;
não gera relatório nem chama IA. Sem relatório real, o sucesso do download
continua pendente de validação; o erro 404 foi validado na etapa operacional.

Dados internos do aplicativo continuam nos caminhos originais ignorados pelo
Git: `backend/uploads/` (incluindo simulations e reports) e `backend/logs/`.
Não os adicione ao commit. Não faça upload de arquivos .env, caches, PID, logs,
artefatos privados ou diretórios de runtime ao GitHub.

## Interface e execução por tarefas

Dentro do navegador do próprio ambiente, a interface atende em localhost:3000.
O ambiente declara Desktop compartilhado, mas seu acesso interativo não foi
confirmado: ferramentas de controle/abertura do Desktop não foram oferecidas
nesta sessão. Se disponível no cliente, use **New tab (+) → Desktop** e abra a
interface no Chrome do ambiente. O localhost do computador do usuário não é o
localhost do Codex Cloud. Não foram criados túneis ou previews externos.

Sem Desktop, uma tarefa do Codex pode usar a API local para monitorar serviços
e recuperar relatórios com os comandos acima. Não existe comando de simulação
no helper. Depois de autorização específica, a tarefa pode conduzir o fluxo
original, consultando os contratos em backend/app/api:

| Operação futura | Rota |
|---|---|
| Ontologia / grafo (usa IA/Zep) | POST /api/graph/ontology/generate e /api/graph/build |
| Progresso do grafo | GET /api/graph/task/TASK_ID |
| Criar / preparar simulação | POST /api/simulation/create e /api/simulation/prepare |
| Progresso da preparação | POST /api/simulation/prepare/status |
| Iniciar / interromper execução | POST /api/simulation/start e /api/simulation/stop |
| Monitorar execução | GET /api/simulation/SIMULATION_ID/run-status |
| Gerar relatório (usa IA) | POST /api/report/generate |
| Progresso do relatório | POST /api/report/generate/status |
| Baixar relatório | GET /api/report/REPORT_ID/download |

Antes da primeira simulação, definir arquivos, objetivo, plataforma e max_rounds.
Não usar force sem necessidade; deixar enable_graph_memory_update=false salvo
solicitação. Gerar relatório somente após o término e as barreiras de ingestão.
Estas ações não fazem parte do setup e não foram executadas nesta validação.

## Incorporar ao ambiente Codex Cloud

Script de instalação do ambiente:

```bash
set -euo pipefail
cd /workspace/MiroFish
bash operations/setup.sh
```

Instruções de início para futuras tarefas: usar o checkout existente sem criar
worktree, conferir `python3 operations/control.py status`, executar `start` se
os serviços não estiverem ativos, e repetir `status` até confirmar prontidão.
Se o interpretador ou as dependências não existirem, executar setup antes.
Manter os bindings seguros e nunca iniciar simulações automaticamente.

Salvar esses campos no rascunho não executa nem publica a configuração.
Publicar o ambiente e enviar um commit ao GitHub são operações distintas.
O versionamento permanente no GitHub exige commit/push autorizado dos três
arquivos; um patch apenas local não comprova persistência remota.

## Resultado da preparação em 10/11/2026

Setup executado e repetido com sucesso; a repetição reutilizou Node e Python e
conferiu 148 pacotes Python sem reinstalação. Frontend, backend e proxy retornaram
HTTP 200, e a listagem de relatórios retornou sucesso sem chamadas externas.
Os valores dos bindings seguros não foram encontrados nos arquivos candidatos.

A leitura do rascunho do ambiente falhou duas vezes, e a tentativa de salvar
`install_script` e `start_skill` retornou `INVALID_ARGUMENT`, sem confirmação
de persistência. O conteúdo proposto está na seção anterior para incorporação
às configurações do ambiente. Não considerar essa integração concluída até
o serviço confirmar a gravação. Não houve commit, push ou publicação nesta etapa.
