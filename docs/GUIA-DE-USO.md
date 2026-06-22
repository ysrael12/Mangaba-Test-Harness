# Guia de Uso — Mangaba Test Harness (MTH)

Guia prático e didático do software de testes do framework **Mangaba AI**. Se você
só quer rodar os testes, comece pelo [Quickstart](#2-quickstart). Se quer
escrever ou estender testes, vá para [Escrevendo testes](#7-escrevendo-um-novo-teste).

> Resumo da ideia: o MTH testa o framework `mangaba` em **camadas** (de tipos
> básicos até orquestração de crews), **sem precisar de chave de API** no dia a
> dia (usa um LLM falso determinístico), e quando você quer validar contra
> modelos reais, declara **provedor + modelo** numa CLI. Tudo foi desenhado para
> rodar em **várias versões do mangaba** sem quebrar.

---

## Índice

1. [Conceitos essenciais](#1-conceitos-essenciais)
2. [Quickstart](#2-quickstart)
3. [Instalação](#3-instalação)
4. [Os comandos da CLI](#4-os-comandos-da-cli)
5. [Níveis e modos de execução](#5-níveis-e-modos-de-execução)
6. [Testando contra modelos reais (planos)](#6-testando-contra-modelos-reais-planos)
7. [Escrevendo um novo teste](#7-escrevendo-um-novo-teste)
8. [O MockLLMProvider](#8-o-mockllmprovider)
9. [Asserções comportamentais e LLM-judge](#9-asserções-comportamentais-e-llm-judge)
10. [Relatórios](#10-relatórios)
11. [Estendendo o harness](#11-estendendo-o-harness)
12. [Como funciona a resiliência a versões](#12-como-funciona-a-resiliência-a-versões)
13. [CI / fluxo de contribuição](#13-ci--fluxo-de-contribuição)
14. [FAQ e troubleshooting](#14-faq-e-troubleshooting)

---

## 1. Conceitos essenciais

| Conceito | O que é |
|---|---|
| **Provider `mock`** | Um LLM falso e determinístico (`MockLLMProvider`). Devolve respostas roteirizadas, incluindo chamadas de ferramenta. É o que permite testar agentes/crews **sem rede e sem chave**. |
| **Níveis** | `unit` (1 módulo), `contract` (todo provider cumpre a interface), `integration` (módulos fiados com mock), `e2e` (modelos reais). |
| **Camadas (L0→L6)** | A ordem real de dependências entre módulos do framework. O modo iterativo respeita essa ordem. |
| **Plano (TestPlan)** | A matriz `provedor × modelo` usada nos níveis de integração/e2e. Vem de um arquivo YAML/JSON ou das flags `--provider/--model`. |
| **compat** | Camada que importa o `mangaba` de forma tolerante: se um símbolo não existir na versão instalada, o teste é **pulado**, não quebra. |

---

## 2. Quickstart

Na raiz do repositório (`mangaba_ai/`):

```bash
# 1. Ver o que o ambiente tem (chaves e SDKs por provedor)
python -m mangaba_test doctor

# 2. Rodar tudo de forma iterativa, camada por camada (offline, sem chave)
python -m mangaba_test run --iterative

# 3. Rodar só os testes de um módulo
python -m mangaba_test run --module guardrails
```

Saída típica do passo 2 (resumida):

```
[mth] === layer L0-foundation (types, events) ===
6 passed
[mth] === layer L1-primitives (tools, guardrails, ...) ===
16 passed
...
[mth] all layers passed [OK]
```

> No Windows, se `python` abrir a Microsoft Store, use o launcher `py` no lugar:
> `py -m mangaba_test ...`.

---

## 3. Instalação

O harness vive dentro do repositório do framework, no pacote `mangaba_test/`. Para
ter as dependências de teste e o atalho `mth`:

```bash
pip install -e ".[test]"
```

Depois disso, `mth` vira um comando:

```bash
mth doctor
mth run --iterative
```

Ao longo do guia uso `python -m mangaba_test` (funciona sem instalar nada além das
deps), mas `mth` é equivalente.

**Dependências:** o núcleo do harness usa só biblioteca padrão (`argparse`, `json`,
`xml`). `PyYAML` é **opcional** — necessário apenas para planos `.yaml` (planos
`.json` funcionam sem ele).

---

## 4. Os comandos da CLI

### `doctor` — diagnóstico do ambiente
```bash
python -m mangaba_test doctor
```
Mostra a versão do `mangaba`, se o cliente LLM está disponível, e para cada
provedor: se há **chave** no ambiente e se o **SDK** está instalado. Nunca imprime
o valor das chaves.

### `list-providers` — provedores conhecidos
```bash
python -m mangaba_test list-providers
```

### `list-models` — catálogo de modelos
```bash
python -m mangaba_test list-models --category code
```
Lista o catálogo de modelos HuggingFace do framework, marcando quais suportam
`tools` (function calling) e quais não.

### `run` — execução offline (unit / módulo / iterativo)
```bash
python -m mangaba_test run --suite unit          # todas as unit
python -m mangaba_test run --module tools         # 1 módulo
python -m mangaba_test run --modules agent,crew   # vários módulos
python -m mangaba_test run --iterative            # camadas L0->L6
python -m mangaba_test run --suite integration -k tool   # filtro pytest -k
```

### `integration` / `e2e` — matriz provedor × modelo
```bash
python -m mangaba_test integration --provider mock --model mock-x
python -m mangaba_test e2e --config mangaba_test/plan.ci.json --report reports
```
Rodam a suíte uma vez **por alvo** do plano e imprimem uma tabela agregada.

Flags úteis (em `run`, `integration`, `e2e`):

| Flag | Efeito |
|---|---|
| `-k <expr>` | filtro pytest por nome de teste |
| `-m <expr>` | filtro pytest por marcador |
| `--maxfail <n>` | para após N falhas |
| `--cov` | habilita cobertura |
| `--report <dir>` | persiste artefatos (XML/JSON/HTML) |
| `--format table\|json\|html` | formato do relatório de matriz |
| `--breakdown` | imprime quebra por módulo no console |

---

## 5. Níveis e modos de execução

### Níveis (o que cada um valida)

```
unit         -> comportamento de 1 módulo, sem rede
contract     -> todo provider cumpre a interface BaseLLMProvider
integration  -> módulos fiados (agent+reasoning+tools...) com mock
e2e          -> execução real ponta a ponta por (provedor, modelo)
```

### Modos (como combinar)

- **Por módulo:** `run --module <nome>` — desenvolvendo um módulo, rode só o dele.
- **Conjunto:** `run --suite integration` ou `run --modules a,b,c`.
- **Iterativo:** `run --iterative` — roda L0→L6 e **para na primeira camada que
  falhar**. É o jeito mais rápido de localizar onde uma regressão entrou.

As camadas (definidas em [`runner.py`](../runner.py)):

```
L0 foundation     types, events
L1 primitives     tools, guardrails, output_parsers, memory,
                  vectorstores, protocols, assertions
L2 providers      llm (contract)
L3 reasoning      reasoning (ReAct)
L4 agent          agent
L6 orchestration  crew
```

---

## 6. Testando contra modelos reais (planos)

Os níveis `integration` e `e2e` aceitam um **plano**: a matriz de provedores e
modelos. Você pode declará-la de duas formas.

### 6.1 Atalho por flags (um alvo)
```bash
python -m mangaba_test e2e --provider anthropic --model claude-3-haiku-20240307
```
Para fallback do OpenRouter, passe uma lista separada por vírgula:
```bash
python -m mangaba_test e2e --provider openrouter \
  --model "google/gemini-2.5-flash,anthropic/claude-3.5-sonnet"
```

### 6.2 Arquivo de plano (vários alvos)

`plano.yaml` (veja [`plan.example.yaml`](../plan.example.yaml)):
```yaml
defaults:
  temperature: 0.0
  max_output_tokens: 512

providers:
  - name: openai
    api_key_env: OPENAI_API_KEY
    models: [gpt-4o-mini]
  - name: huggingface
    api_key_env: HF_TOKEN
    models:
      - Qwen/Qwen2.5-7B-Instruct             # suporta tools
      - meta-llama/Meta-Llama-3-8B-Instruct  # NÃO suporta -> testes de tool são pulados
```

```bash
python -m mangaba_test e2e --config plano.yaml --report reports
```

> O mesmo arquivo em `.json` funciona sem PyYAML — veja
> [`plan.ci.json`](../plan.ci.json).

### 6.3 Chaves de API

O harness lê as chaves do ambiente, na mesma convenção do `config.py` do projeto:

| Provedor | Variáveis aceitas (em ordem) |
|---|---|
| google | `GOOGLE_API_KEY`, `GEMINI_API_KEY` |
| openai | `OPENAI_API_KEY` |
| anthropic | `ANTHROPIC_API_KEY` |
| huggingface | `HUGGINGFACE_API_KEY`, `HUGGINGFACE_TOKEN`, `HF_TOKEN`, `HUGGINGFACEHUB_API_TOKEN` |
| openrouter | `OPENROUTER_API_KEY` |

Se a chave de um alvo não existir, **aquele alvo é pulado** (skip), não falha. Isso
mantém o pipeline verde mesmo quando você só tem chave de um provedor.

---

## 7. Escrevendo um novo teste

Regras de ouro, válidas para qualquer suíte:

1. **Nunca** importe `mangaba` diretamente. Use `from mangaba_test import compat`.
2. Comece checando disponibilidade e pulando se faltar: `compat.require(...)`.
3. Marque o nível com `pytestmark` (`unit`/`integration`/`contract`/`e2e`).

### 7.1 Teste unitário (sem LLM)

`mangaba_test/suites/unit/test_meu_modulo.py`:
```python
import pytest
from mangaba_test import compat

pytestmark = pytest.mark.unit

def test_calculadora_soma():
    if compat.CalculatorTool is None:
        pytest.skip(compat.missing("CalculatorTool"))
    assert "5" in str(compat.CalculatorTool().run(expression="2 + 3"))
```

### 7.2 Teste de integração (com LLM mock determinístico)

Use a fixture `mock_client` para roteirizar o LLM:
```python
import pytest
from mangaba_test import compat

pytestmark = pytest.mark.integration

def test_agente_usa_ferramenta(mock_client):
    if not compat.require("Agent", "CalculatorTool"):
        pytest.skip(compat.missing("Agent", "CalculatorTool"))

    client = mock_client(script=[
        # 1ª resposta do "LLM": pede para chamar a calculadora
        {"tool_calls": [{"tool_name": "calculator",
                         "arguments": {"expression": "21*2"}}]},
        # 2ª resposta: resposta final
        {"text": "O resultado é 42."},
    ])
    agent = compat.Agent(role="Mat", goal="contas", backstory="...",
                         tools=[compat.CalculatorTool()], llm=client)
    assert "42" in agent.execute_task("Quanto é 21 x 2?")
```

### 7.3 Teste e2e (modelo real)

Use a fixture `llm_client` (construída a partir do alvo ativo) e proteja contra
execução offline:
```python
import pytest
from mangaba_test import compat
from mangaba_test.assertions import assert_contains_any
from mangaba_test.plan import Target

pytestmark = pytest.mark.e2e

def test_resposta_real(llm_client, active_target: Target):
    if active_target.provider == "mock":
        pytest.skip("e2e exige provedor real")
    if compat.Agent is None:
        pytest.skip(compat.missing("Agent"))
    agent = compat.Agent(role="Assistente", goal="responder",
                         backstory="...", llm=llm_client)
    resp = agent.execute_task("Capital da França? Uma palavra.")
    assert_contains_any(resp, ["paris"])
```

### 7.4 Fixtures disponíveis (em [`suites/conftest.py`](../suites/conftest.py))

| Fixture | Para que serve |
|---|---|
| `mock_client(script=...)` | fábrica de LLM mock roteirizado |
| `llm_client` | cliente do alvo ativo (mock por padrão; real no e2e) |
| `active_target` | o `Target` (provedor+modelo) atual |
| `event_collector` | coleta eventos do EventBus durante o teste |
| `skip_without_tools` | pula o teste se o modelo não tem function calling |
| `llm_judge` | juiz LLM opcional (requer `MTH_JUDGE`) |
| `_reset_event_bus` | (automático) isola o EventBus entre testes |

---

## 8. O MockLLMProvider

É o coração do determinismo. Cada item do `script` vira uma resposta do LLM:

```python
# resposta de texto (encerra o raciocínio)
{"text": "resposta final"}

# pedido de chamada de ferramenta (dispara o ReAct)
{"tool_calls": [{"tool_name": "calculator", "arguments": {"expression": "2+2"}}]}
```

Se o script acabar, devolve `default_text`. Para simular falhas de provedor:

```python
from mangaba_test.fixtures.mock_provider import make_mock_client
from mangaba_test import compat

client = make_mock_client(raise_error=compat.RateLimitError("rate limited"))
```

O mock também registra tudo que recebeu em `client._provider.calls` — útil para
asserções finas. Para a maioria dos casos, prefira a fixture `mock_client`.

---

## 9. Asserções comportamentais e LLM-judge

Saída de LLM é não-determinística, então não use igualdade. Use as asserções
tolerantes de [`assertions/behavioral.py`](../assertions/behavioral.py):

```python
from mangaba_test.assertions import (
    assert_contains_any, assert_is_valid_json, assert_matches_schema,
    assert_tool_was_called, assert_no_pii_leaked,
    assert_tokens_under, measure_latency, assert_latency_under,
)

assert_contains_any(resp, ["paris", "parís"])     # contém algum
data = assert_is_valid_json(resp)                  # extrai e valida JSON
assert_tool_was_called(event_collector, "calculator")  # leu o EventBus
assert_no_pii_leaked(resp)                         # sem e-mail/segredo/cartão

with measure_latency() as w:
    resp = agent.execute_task("...")
assert_latency_under(10.0, w)
```

### LLM-as-judge (opcional)

Avalia qualidade com nota 0..1 segundo uma rubrica. Configure o juiz:
```bash
export MTH_JUDGE=anthropic:claude-3-haiku-20240307
```
No teste, a fixture `llm_judge` é injetada (e o teste é **pulado** se `MTH_JUDGE`
não estiver setado ou faltar chave):
```python
def test_qualidade(llm_client, active_target, llm_judge):
    ...
    resp = agent.execute_task("Por que o céu é azul? Uma frase.")
    llm_judge.assert_min_score(
        task="Explique por que o céu é azul.",
        response=resp,
        rubric="Menciona espalhamento de luz (Rayleigh) e é conciso.",
        min_score=0.5,
    )
```

---

## 10. Relatórios

Os níveis de matriz (`integration`/`e2e`) agregam resultados:

```bash
python -m mangaba_test e2e --config plano.json --report reports --format html --breakdown
```

Produz:
- **Tabela no console** — uma linha por alvo (`pass/fail/skip/err/status`);
- **`--breakdown`** — quebra por módulo dentro de cada alvo;
- **`reports/<nível>__matrix.json`** — dados agregados (com `modules` aninhados);
- **`reports/<nível>__report.html`** — matriz `alvo × módulo` colorida + lista de
  falhas, ideal para anexar num PR;
- **`reports/<nível>__<alvo>.xml`** — JUnit por alvo (consumível por qualquer CI).

`skip` (ex.: alvo sem chave) **não conta como falha** na coluna de status.

---

## 11. Estendendo o harness

### Adicionar a suíte de um novo módulo
1. Crie o arquivo de teste, ex. `suites/unit/test_planner.py`.
2. Registre em [`runner.py`](../runner.py), no dicionário `MODULE_SUITES`:
   ```python
   "planner": ["unit/test_planner.py"],
   ```
3. (Opcional) coloque-o na camada certa em `LAYERS` para o modo iterativo.

### Expor um novo símbolo do framework
Adicione uma linha em [`compat.py`](../compat.py):
```python
Planner = _imp("mangaba.core.planner", "Planner")
```
Pronto — os testes podem fazer `compat.Planner` e `compat.require("Planner")`.

### Suportar um novo provedor
Se o framework registrar um provedor novo em `PROVIDERS`, o contrato
parametrizado ([`test_provider_matrix.py`](../suites/contract/test_provider_matrix.py))
já o cobre automaticamente. Para a matriz, basta citá-lo no plano.

---

## 12. Como funciona a resiliência a versões

O requisito é rodar a mesma base de testes em **várias versões do mangaba**. O
mecanismo:

- Nenhuma suíte faz `import mangaba...` direto. Tudo passa por `compat.py`.
- `compat._imp(modulo, nome)` tenta importar e devolve `None` se falhar.
- Os testes começam com `if not compat.require("X"): pytest.skip(compat.missing("X"))`.

Resultado: numa versão antiga que não tem, digamos, `OpenRouterConfig`, o teste
correspondente é **pulado** com mensagem clara, em vez de quebrar a suíte inteira
com `ImportError`. Você vê exatamente o que aquela versão suporta.

```python
from mangaba_test import compat

print(compat.version)            # "3.3.0"
print(compat.version_tuple())    # (3, 3, 0)
compat.require("Agent", "Crew")  # True/False
compat.missing("Agent")          # texto para pytest.skip(...)
```

---

## 13. CI / fluxo de contribuição

Dois workflows em `.github/workflows/`:

- **`mth-offline.yml`** (gate de PR) — roda em todo push/PR, Python 3.10–3.12,
  **sem chaves**: `doctor` → `run --iterative` → `contract` → `integration` (mock).
  Determinístico e rápido.
- **`mth-e2e.yml`** — manual (`workflow_dispatch`) e semanal (cron). Usa secrets por
  provedor atrás do environment protegido `llm-providers` e roda a matriz de
  `plan.ci.json`. Alvos sem secret são pulados.

Fluxo sugerido para um PR da comunidade:
1. O gate offline precisa passar.
2. Se algo quebrar, `run --iterative` mostra **em qual camada** foi.
3. Um mantenedor dispara a lane e2e antes do merge e anexa o HTML matriz.

---

## 14. FAQ e troubleshooting

**`python` abre a Microsoft Store (Windows).** Use `py -m mangaba_test ...`.

**Por que meus testes e2e ficam "skipped"?** Provavelmente falta a chave do
provedor no ambiente, ou o alvo é `mock`. Rode `doctor` para confirmar. Skip é o
comportamento correto — o pipeline continua verde.

**Um teste de tool-calling aparece como skipped num modelo HF.** Aquele modelo não
tem function calling nativo (ex.: Llama 3 8B). A fixture `skip_without_tools`
pula automaticamente. Use `list-models` para ver quais suportam `tools`.

**Por que o harness ignora o `--cov-fail-under=80` do repo?** O `runner` limpa o
`addopts` do `pytest.ini`/`pyproject.toml` para que runs parciais não falhem por
cobertura. Use `--cov` se quiser cobertura de propósito.

**Posso rodar com o `pytest` direto?** Pode, para depurar:
```bash
python -m pytest mangaba_test/suites/unit -o addopts= -p no:cov -q
```
O `-o addopts=` é importante para neutralizar a config de cobertura do repo.

**Erro de Unicode no console do Windows.** Os textos impressos pelo harness são
ASCII justamente por isso; se ver algo assim em testes próprios, evite emojis em
`print`.

---

Para a referência rápida de comandos, veja o [README](../README.md). Para a
especificação completa do desenho, veja [`docs/SPEC-Test-Harness.md`](../../docs/SPEC-Test-Harness.md).
