import argparse
import concurrent.futures
import json
from collections import defaultdict

from metrics.llm_judge import evaluate_llm_judge
from metrics.utils import calculate_metrics
from tqdm import tqdm

from dotenv import load_dotenv
load_dotenv()
import nltk
try:
    nltk.download("punkt_tab")
    nltk.download("wordnet")
except Exception:
    pass

def process_single_qa(qa_data):
    """Process a single QA item."""
    k, item = qa_data
    gt_answer = str(item["answer"])
    pred_answer = str(item["response"])
    category = str(item["category"])
    question = str(item["question"])

    # Skip category 5
    if category == "5":
        return None

    metrics = calculate_metrics(pred_answer, gt_answer, category=category)
    llm_score = evaluate_llm_judge(question, gt_answer, pred_answer)

    return (
        k,
        {
            "question": question,
            "answer": gt_answer,
            "response": pred_answer,
            "category": category,
            "bleu_score": metrics["bleu1"],
            "f1_score": metrics["f1"],
            "llm_score": llm_score,
        },
    )


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG results")
    parser.add_argument(
        "--input_file", type=str, default="results/memos_results_top_10.json", help="Path to the input dataset file"
    )
    parser.add_argument(
        "--output_file", type=str, default="evaluation_metrics.json", help="Path to save the evaluation results"
    )
    parser.add_argument("--max_workers", type=int, default=10, help="Maximum number of worker threads")

    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Flatten all QA items with their keys
    all_qa_items = []
    for k, v in data.items():
        for item in v:
            all_qa_items.append((k, item))

    results = defaultdict(list)

    # Use ThreadPoolExecutor with specified workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(process_single_qa, qa_data) for qa_data in all_qa_items]

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Evaluating QA"):
            result = future.result()
            if result is not None:
                k, item_result = result
                results[k].append(item_result)

    # Save results to JSON file
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"Results saved to {args.output_file}")


if __name__ == "__main__":
    main()
