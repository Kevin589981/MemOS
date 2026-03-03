from openai import OpenAI
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import time

load_dotenv()

# 初始化OpenAI客户端
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
)

CACHE_FILE = "image_descriptions_cache.json"
IMAGES_DIR = Path("downloaded_images")

def load_cache():
    """加载缓存"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """保存缓存"""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def describe_image(image_path, use_thinking=False):
    """使用qwen3-vl-plus识别图片（base64方案，检查文件大小）"""
    try:
        # 检查文件大小（阿里云限制10MB）
        file_size = os.path.getsize(image_path)
        max_size = 10 * 1024 * 1024  # 10MB
        
        if file_size > max_size:
            print(f"  ⚠ 文件过大({file_size/1024/1024:.2f}MB)，跳过")
            return None
        
        # 读取图片并转换为base64
        with open(image_path, 'rb') as f:
            import base64
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        },
                    },
                    {
                        "type": "text", 
                        "text": """Please describe the contents of this image in detail.

Focus on:
1. Text in the image (such as book titles, headings, slogans, etc.)
2. Main objects and scenes
3. People (if any)
4. Colors and atmosphere
5. Any special symbols or logos

Please use complete sentences to describe, including all visible important information."""
                    },
                ],
            },
        ]
        
        if use_thinking:
            completion = client.chat.completions.create(
                model="qwen3-vl-plus",
                messages=messages,
                extra_body={
                    'enable_thinking': True,
                    "thinking_budget": 8192
                }
            )
        else:
            completion = client.chat.completions.create(
                model="qwen3-vl-plus",
                messages=messages
            )
        
        return completion.choices[0].message.content
    
    except Exception as e:
        print(f"识别失败: {e}")
        return None

def main():
    print("="*80)
    print("图片识别脚本")
    print("="*80)
    
    # 加载映射和缓存
    with open('image_mapping.json', 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    cache = load_cache()
    print(f"\n已缓存 {len(cache)} 个图片描述")
    print(f"总共需要识别 {len(mapping)} 个图片")
    
    # 识别图片
    processed = 0
    for dia_id, info in mapping.items():
        filename = info['filename']
        
        if filename in cache:
            print(f"[已缓存] {dia_id}: {filename}")
            continue
        
        image_path = IMAGES_DIR / filename
        if not image_path.exists():
            print(f"[跳过] {dia_id}: 文件不存在 {filename}")
            continue
        
        print(f"\n正在识别 [{processed+1}/{len(mapping)}]: {dia_id}")
        print(f"  文件: {filename}")
        print(f"  原始caption: {info['blip_caption'][:60]}...")
        
        description = describe_image(image_path)
        
        if description:
            cache[filename] = {
                'dia_id': dia_id,
                'filename': filename,
                'url': info['url'],
                'speaker': info['speaker'],
                'original_text': info['text'],
                'blip_caption': info['blip_caption'],
                'query': info['query'],
                'ai_description': description,
                'timestamp': time.time()
            }
            save_cache(cache)
            print(f"  ✓ AI描述: {description[:100]}...")
            processed += 1
        else:
            print(f"  ✗ 识别失败")
        
        # 避免API限流
        time.sleep(1)
    
    print("\n" + "="*80)
    print(f"识别完成！")
    print(f"  总数: {len(mapping)}")
    print(f"  缓存: {len(cache)}")
    print(f"  新识别: {processed}")
    print(f"  缓存文件: {CACHE_FILE}")
    print("="*80)

if __name__ == '__main__':
    main()
