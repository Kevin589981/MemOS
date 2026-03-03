import argparse
import os

from src.utils import METHODS, TECHNIQUES
from src.MemOS.add import MemOSAdd
from src.MemOS.search import MemOSSearch


class Experiment:
    def __init__(self, technique_type, chunk_size):
        self.technique_type = technique_type
        self.chunk_size = chunk_size

    def run(self):
        print(f"Running experiment with technique: {self.technique_type}, chunk size: {self.chunk_size}")


def main():
    parser = argparse.ArgumentParser(description="Run memory experiments")
    parser.add_argument("--technique_type", choices=TECHNIQUES, default="memos", help="Memory technique to use")
    parser.add_argument("--method", choices=METHODS, default="add", help="Method to use")
    parser.add_argument("--dataset", type=str, default="dataset/locomo10.json", help="Path to dataset")
    parser.add_argument("--chunk_size", type=int, default=1000, help="Chunk size for processing")
    parser.add_argument("--output_folder", type=str, default="results/", help="Output path for results")
    parser.add_argument("--top_k", type=int, default=30, help="Number of top memories to retrieve")
    parser.add_argument("--filter_memories", action="store_true", default=False, help="Whether to filter memories")
    parser.add_argument("--is_graph", action="store_true", default=False, help="Whether to use graph-based search")
    parser.add_argument("--num_chunks", type=int, default=1, help="Number of chunks to process")
    parser.add_argument("--max_workers", type=int, default=10, help="Max workers for parallel processing")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size for adding messages")
    parser.add_argument("--overlap", type=int, default=1, help="Overlap size for sliding window batching")
    parser.add_argument(
        "--enable_preprocessing",
        action="store_true",
        default=False,
        help="Whether to enable runtime preprocessing during add",
    )

    args = parser.parse_args()

    # Add your experiment logic here
    print(f"Running experiments with technique: {args.technique_type}, chunk size: {args.chunk_size}")

    if args.technique_type == "memos":
        if args.method == "add":
            memory_manager = MemOSAdd(
                data_path=args.dataset,
                batch_size=args.batch_size,
                overlap=args.overlap,
                enable_preprocessing=args.enable_preprocessing,
            )
            memory_manager.process_all_conversations(max_workers=args.max_workers)
        elif args.method == "search":
            output_file_path = os.path.join(
                args.output_folder,
                f"memos_results_top_{args.top_k}.json",
            )
            memory_searcher = MemOSSearch(output_file_path, args.top_k)
            memory_searcher.process_data_file(args.dataset, max_workers=args.max_workers)
        else:
            raise ValueError(f"Invalid method: {args.method}")
    else:
        raise ValueError(f"Invalid technique type: {args.technique_type}")


if __name__ == "__main__":
    main()
