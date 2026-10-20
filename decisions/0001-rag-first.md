## 3. `DECISIONS/0001-rag-first.md`

```markdown
# ADR 0001: RAG before finetuning

## Status

Accepted

## Context

OrgMind doit répondre à des questions sur des documents organisationnels privés (rapports annuels, briefs sécurité, lessons learned). Le turnover du personnel fait que la mémoire factuelle est perdue. Le modèle (Llama 3.3 70B via Groq, ou openai/gpt-oss-20b actuellement) n'a pas ces informations dans ses poids.

## Decision

Construire un système RAG en premier. Ne pas finetuner tant que prompting + RAG échouent sur des problèmes comportementaux (format, style, rôle).

## Consequences

- RAG est évaluable : hit rate @5, precision @5, faithfulness, correctness.
- Les faits restent dans les documents, pas dans les poids. Mettre à jour un document met à jour les réponses.
- Finetuning reste une option pour plus tard (Semaines 8+), pas le point de départ.
- Les documents changent souvent (rapports annuels, briefs) → RAG s'adapte sans réentraînement.

## Alternatives considérées

- **Finetuning direct** : rejeté car les documents changent souvent et le finetuning ne met pas à jour les faits.
- **Prompt engineering seul** : rejeté car le modèle n'a pas les documents dans ses poids, et le contexte est trop long pour tenir dans le prompt.
```
