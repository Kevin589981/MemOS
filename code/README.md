#### 第一次运行，运行一遍这个预处理数据
python -c "from src.MemOS.preprocessor import ConversationPreprocessor; ConversationPreprocessor().preprocess_dataset('dataset/locomo10_test2.json','dataset/locomo10_test2_enhanced_v2.json')"  

#### 后面只需要运行如下命令即可（没改api可以不add）
python run_experiments.py --technique_type memos --method add --dataset dataset/locomo10_test2_enhanced_v2.json --batch_size 16 --overlap 8 --max_workers 5
python run_experiments.py --technique_type memos --method search --dataset dataset/locomo10_test2_enhanced_v2.json --top_k 30 --max_workers 5
python evals.py --input_file results/memos_results_top_30.json --output_file evaluation_metrics_optimized_v2.json --max_workers 1
python generate_scores.py evaluation_metrics_optimized_v2.json
