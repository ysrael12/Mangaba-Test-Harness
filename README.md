# Mangaba Test Harness (MTH)

Software de testes **modular** e **agnóstico de versão** para o framework
`mangaba`. Implementa a Fase 1 da [spec](../docs/SPEC-Test-Harness.md).

> 📖 **Aprendendo a usar?** Leia o [Guia de Uso](docs/GUIA-DE-USO.md) — tutorial
> passo a passo (quickstart, comandos, como escrever testes, planos, relatórios,
> CI e troubleshooting). Este README é a referência rápida.

> Roda offline por padrão (provider `mock` determinístico). Provedores reais só
> são acionados no nível `e2e`, com chave de API.

## Resiliência a versões

A harness **nunca importa o `mangaba` diretamente** nas suítes. Tudo passa por
[`compat.py`](compat.py), que resolve cada símbolo em runtime e devolve `None`
quando ele não existe na versão instalada. As suítes consultam
`compat.require(...)` e dão `skip` — então o mesmo conjunto de testes roda em
várias versões do framework sem quebrar.

## Uso

```bash
# diagnóstico de ambiente (chaves + SDKs por provedor)
py -m mangaba_test doctor

# suítes unitárias (offline)
py -m mangaba_test run --suite unit

# um módulo só
py -m mangaba_test run --module guardrails

# modo iterativo: camadas L0->L6, para na primeira que falhar
py -m mangaba_test run --iterative

# integração (mock determinístico) de um subconjunto de módulos
py -m mangaba_test run --suite integration

# matriz real ponta a ponta a partir de um plano (tabela agregada provider×model)
py -m mangaba_test e2e --config mangaba_test/plan.example.yaml --report ./reports

# atalho sem arquivo de plano
py -m mangaba_test e2e --provider anthropic --model claude-3-haiku-20240307

# integração em matriz com saída JSON
py -m mangaba_test integration --config plan.json --format json --report ./reports

# relatório HTML (matriz alvo×módulo) + breakdown por módulo no console
py -m mangaba_test e2e --config plan.json --format html --report ./reports --breakdown
```

O `integration`/`e2e` rodam a suíte uma vez por alvo, emitem um **JUnit XML por
alvo** (nativo do pytest, sem dependência extra) e imprimem uma **tabela
agregada** `provider × model` com pass/fail/skip/err. `skip` (ex.: sem chave) não
conta como falha — o lane offline da comunidade continua verde. Com `--report` os
artefatos XML + um `*__matrix.json` são persistidos.

Após `pip install -e .[test]`, o entry point `mth` fica disponível
(`mth run --iterative`, etc.).

## Estrutura

```
mangaba_test/
├── compat.py          # camada de compatibilidade (detecção de símbolos)
├── capabilities.py    # tool_calling/streaming por (provider, model)
├── factory.py         # build do LLMClient + resolução de chaves do env
├── plan.py            # TestPlan: matriz provider×model (YAML/JSON)
├── runner.py          # orquestra pytest por módulo/suíte/camada
├── doctor.py          # diagnóstico de ambiente
├── cli.py             # CLI `mth`
├── fixtures/
│   └── mock_provider.py   # MockLLMProvider scriptável (BaseLLMProvider)
├── assertions/
│   ├── behavioral.py      # asserções tolerantes para saída de LLM
│   └── judge.py           # LLM-as-judge (score 0..1 + rubrica)
└── suites/
    ├── conftest.py    # fixtures version-aware (llm_client, mock_client, ...)
    ├── unit/          # L0-L1, sem rede
    ├── contract/      # conformidade BaseLLMProvider
    ├── integration/   # fiação reasoning/agent/crew (mock)
    └── e2e/           # provedores reais (gated por chave + capacidade)
```

## Níveis

| Nível | LLM | Chave | Comando |
|---|---|---|---|
| unit | nenhum | não | `run --suite unit` |
| contract | mock (+real no e2e) | opcional | `run --suite contract` |
| integration | mock | não | `run --suite integration` |
| e2e | real | sim | `e2e --config plan.yaml` |

## Fases

- **Fase 1 (concluída):** mock determinístico, runner por módulo/suíte/camada, CLI.
- **Fase 2 (concluída):** contract parametrizado por classe de provider + converters
  de schema; relatório matriz agregado (JUnit XML + JSON).
- **Fase 3 (concluída):** breakdown por módulo dentro de cada alvo + relatório HTML
  standalone (matriz alvo×módulo, cores ok/fail/skip, seção de falhas).
- **Fase 4 (concluída):** asserções comportamentais (`assertions/behavioral.py`:
  contains_any, json válido, schema pydantic, tool_was_called, no_pii, latência,
  tokens) + LLM-judge opcional (`assertions/judge.py`, configurável via
  `MTH_JUDGE=provider:model`).
- **Fase 5 (concluída):** workflows de CI (`.github/workflows/`) — lane offline em
  todo push/PR (gate) e lane e2e manual/agendada com secrets.

## CI / gating de PR

- **`mth-offline.yml`** roda em todo push e PR, em Python 3.10/3.11/3.12, **sem
  chaves**: `doctor` → `run --iterative` → `contract` → `integration` (alvo mock).
  É o **gate de PR** — determinístico e rápido. Sobe os relatórios como artifact.
- **`mth-e2e.yml`** é manual (`workflow_dispatch`) e semanal (cron). Usa secrets
  por provedor (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `HF_TOKEN`,
  `OPENROUTER_API_KEY`) atrás de um *environment* protegido `llm-providers`, e roda
  a matriz de [`plan.ci.json`](plan.ci.json). Alvos sem secret são **skip** (não
  falham), então a lane fica verde mesmo com cobertura parcial de provedores.

Fluxo de contribuição: o PR passa pelo gate offline; `run --iterative` aponta a
camada que regrediu; um mantenedor dispara a lane e2e antes do merge e anexa o
relatório HTML matriz ao PR.

## Asserções comportamentais

Saídas de LLM variam — então as asserções são tolerantes a intenção, não igualdade:

```python
from mangaba_test.assertions import (
    assert_contains_any, assert_is_valid_json, assert_matches_schema,
    assert_tool_was_called, assert_no_pii_leaked, assert_tokens_under,
    measure_latency, assert_latency_under,
)

assert_contains_any(answer, ["paris"])
assert_tool_was_called(event_collector, "calculator")   # lê o EventBus
assert_no_pii_leaked(answer)
```

LLM-judge (opt-in): defina `MTH_JUDGE=anthropic:claude-3-haiku-20240307`; a fixture
`llm_judge` constrói o juiz e pula se não configurado/sem chave.
