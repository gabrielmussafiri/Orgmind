import json
import re
import time
from datetime import datetime
from pathlib import Path

from langchain_anthropic import ChatAnthropic

from app.services.rag_service import retrieve_documents, query_documents
from app.config import settings


evaluator = ChatAnthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    model="claude-haiku-4-5-20251001",
    temperature= 0,
    max_tokens = 1024,
)

# Helper Function

def parse_json_response(text:str)-> dict:
    """ Strip Markdown code fences before JSON parsing, """
    text = text.strip()
    # Retire ```json ... ``` ou ```...```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


# Evaluate Faithfulness (check the retrieved chunks content and what the LLM responded)
def evaluate_faithfulness(context, generated_answer):
    prompt = f"""
    You are a faithfulness evaluator.

    Evaluate the generated answer using ONLY the provided context.
    Identify every factual claim in the answer.
    Count how many claims are supported by the context.
    Do not use external knowledge.

    Context:
    {context}

    Generated Answer:
    {generated_answer}

    Return ONLY a valid JSON in this exact format:
    {{
        "total_claims": 2,
        "supported_claims": 1,
        "unsupported_claims": 1
    }}
    The numbers above are examples, not the evaluation result.
    Do not include explanations or Markdown code fences.
    """
    result = evaluator.invoke(prompt)
    
    try:
        return parse_json_response(result.content)
    except Exception as e:
        print(f"Faithfulness evaluation failed: {type(e).__name__}: {e}")
        print(f'Raw content was:{result.content!r}')
        raise


# Evaluate Correctness (check the LLM answer against the trusted reference answer)
def evaluate_answer_correctness(generated_answer, reference_answer):
    prompt = f"""
    You are an answer correctness evaluator.

    Compare the generated answer with the trusted reference answer.

    Evaluate factual meaning, not exact wording.
    Accept paraphrases that communicate the same facts.
    Do not use external knowledge.

    Generated Answer:
    {generated_answer}

    Reference Answer:
    {reference_answer}

    Return ONLY valid JSON with these keys:
    {{
        "Correct": true or false,
        "Reason": "brief explanation"
    }}
    """
    result = evaluator.invoke(prompt)
    return parse_json_response(result.content)


# Run evaluation against eval/eval_set.json
def run_eval():
    cases = json.load(open("eval/eval_set.json"))
    results = []

    for i, case in enumerate(cases, 1):
        qid = case["id"]
        question = case["question"]
        case_type = case["type"]

        print(f"\n[{i}/{len(cases)}] {qid} — {case_type}")

        result = {
            "id": qid,
            "type": case_type,
            "question": question,
            "generated_answer": None,
            "retrieved_doc_ids": [],
            "metrics": {},
        }

        # ---------- ANSWERABLE ----------
        if case_type == "answerable":
            retrieved = retrieve_documents(
                question, org_id=case["user_org_id"], k=5
            )
            response = query_documents(question, org_id=case["user_org_id"])

            result["generated_answer"] = response["answer"]
            result["retrieved_doc_ids"] = [
                d.metadata.get("doc_id") for d in retrieved
            ]

            # Hit rate
            expected = case["expected_doc_ids"]
            hit = any(
                doc_id in expected for doc_id in result["retrieved_doc_ids"]
            )
            result["metrics"]["hit@5"] = 1.0 if hit else 0.0

            # Precision
            if result["retrieved_doc_ids"]:
                relevant = sum(
                    1
                    for d in result["retrieved_doc_ids"]
                    if d in expected
                )
                result["metrics"]["precision@5"] = relevant / len(
                    result["retrieved_doc_ids"]
                )
            else:
                result["metrics"]["precision@5"] = 0.0

            # Faithfulness
            try:
                faith = evaluate_faithfulness(
                    response["context"], response["answer"]
                )
                total = faith["total_claims"]
                supported = faith["supported_claims"]
                result["metrics"]["faithfulness"] = (
                    supported / total if total > 0 else None
                )
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    print("Rate limit hit, waiting 30s...")
                    time.sleep(30)
                result["metrics"]["faithfulness"] = None
                result["metrics"]["faithfulness_error"] = str(e)

            # Correctness
            try:
                correctness = evaluate_answer_correctness(
                    response["answer"], case["reference_answer"]
                )
                result["metrics"]["correctness"] = (
                    1.0 if correctness["Correct"] else 0.0
                )
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    print("Rate limit hit, waiting 30s...")
                    time.sleep(30)
                result["metrics"]["correctness"] = None
                result["metrics"]["correctness_error"] = str(e)

        # ---------- UNANSWERABLE ----------
        elif case_type == "unanswerable":
            response = query_documents(question, org_id=case["user_org_id"])
            result["generated_answer"] = response["answer"]

            answer_lower = response["answer"].lower()
            refused = (
                "don't have enough evidence" in answer_lower
                or "do not have enough evidence" in answer_lower
                or "no relevant documents" in answer_lower
                or "does not contain information" in answer_lower
                or "not contain" in answer_lower
                or "does not contain" in answer_lower
            )
            result["metrics"]["refused"] = 1.0 if refused else 0.0

        # ---------- ACCESS CONTROL ----------
        elif case_type == "access_control":
            response = query_documents(question, org_id=case["user_org_id"])
            result["generated_answer"] = response["answer"]
            # To be fully implemented in Week 2 (real access control)
            result["metrics"]["access_control_pending"] = True

        results.append(result)

    # ---------- AGGREGATE  ----------
    answerable = [r for r in results if r["type"] == "answerable"]
    unanswerable = [r for r in results if r["type"] == "unanswerable"]

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": "claude-haiku-4-5-20251001",
        "total_cases": len(cases),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "hit_rate@5": (
            sum(r["metrics"].get("hit@5", 0) for r in answerable)
            / len(answerable)
            if answerable
            else None
        ),
        "precision@5": (
            sum(r["metrics"].get("precision@5", 0) for r in answerable)
            / len(answerable)
            if answerable
            else None
        ),
        "faithfulness": (
            sum(r["metrics"].get("faithfulness") or 0 for r in answerable)
            / len(answerable)
            if answerable
            else None
        ),
        "correctness": (
            sum(r["metrics"].get("correctness") or 0 for r in answerable)
            / len(answerable)
            if answerable
            else None
        ),
        "refusal_accuracy": (
            sum(r["metrics"].get("refused", 0) for r in unanswerable)
            / len(unanswerable)
            if unanswerable
            else None
        ),
    }

    # ---------- SAVE ----------
    Path("eval/results").mkdir(parents=True, exist_ok=True)
    timestamps = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = f"eval/results/{timestamps}.json"
    with open(out_path, "w") as f:
        json.dump(
            {"summary": summary, "results": results},
            f,
            indent=2,
            ensure_ascii=False,
        )

    # ---------- PRINT ----------
    print("\n=== BASELINE EVAL ===")
    for k, v in summary.items():
        if v is None:
            print(f"{k}: N/A")
        elif isinstance(v, float):
            print(f"{k}: {v:.2%}")
        else:
            print(f"{k}: {v}")
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    run_eval()