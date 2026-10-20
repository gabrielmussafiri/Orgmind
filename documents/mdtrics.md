# OrgMind — Evaluation Metrics

## Key Metrics

| Metric                        | Definition                                                                                               | Baseline Threshold | Target Threshold | Measured By     |
| ----------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------ | ---------------- | --------------- |
| **Hit Rate @5**               | Percentage of answerable questions for which `expected_doc_id` appears among the top 5 retrieved chunks. | To be measured     | ≥ 0.80           | `evaluation.py` |
| **Precision @5**              | Percentage of relevant chunks among the top 5 retrieved chunks.                                          | To be measured     | ≥ 0.60           | `evaluation.py` |
| **Faithfulness**              | Percentage of claims in the generated answer that are supported by the retrieved context.                | To be measured     | ≥ 0.90           | AI judge (Groq) |
| **Correctness**               | Percentage of generated answers that are correct compared with the `reference_answer`.                   | To be measured     | ≥ 0.80           | AI judge (Groq) |
| **Refusal Accuracy**          | Percentage of unanswerable questions that are correctly refused by the system.                           | To be measured     | ≥ 0.90           | New in Week 1   |
| **Access-Control Violations** | Number of restricted document chunks leaked to unauthorized users or organizations.                      | To be measured     | 0                | New in Week 2   |

## Week 1 Baseline

The metrics marked as **"To be measured"** will be populated after the first evaluation run using the 20 test cases.

This baseline will serve as the reference point for measuring future improvements to OrgMind, including model changes, hybrid retrieval,
