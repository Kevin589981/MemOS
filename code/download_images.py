import json
import os
import requests
from pathlib import Path
from urllib.parse import urlparse
import hashlib

# 创建图片存储目录
IMAGES_DIR = Path("downloaded_images")
IMAGES_DIR.mkdir(exist_ok=True)

def get_image_filename(url):
    """根据URL生成唯一的文件名"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    ext = Path(urlparse(url).path).suffix or '.jpg'
    return f"{url_hash}{ext}"

def download_image(url, save_path):
    """下载图片"""
    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"下载失败 {url}: {e}")
        return False

def extract_image_urls(dataset_path):
    """从数据集中提取所有图片URL"""
    with open(dataset_path, encoding='utf-8') as f:
        data = json.load(f)
    
    image_info = []
    for conv_data in data:
        for key, value in conv_data['conversation'].items():
            if isinstance(value, list):
                for msg in value:
                    if 'img_url' in msg and msg['img_url']:
                        for url in msg['img_url']:
                            image_info.append({
                                'url': url,
                                'dia_id': msg['dia_id'],
                                'speaker': msg.get('speaker'),
                                'text': msg.get('text', ''),
                                'blip_caption': msg.get('blip_caption', ''),
                                'query': msg.get('query', '')
                            })
    
    return image_info

def main():
    print("="*80)
    print("图片下载脚本")
    print("="*80)
    
    # 读取数据集
    dataset_path = 'dataset/locomo10_test2.json'
    print(f"\n正在分析数据集: {dataset_path}")
    
    image_info = extract_image_urls(dataset_path)
    print(f"找到 {len(image_info)} 个图片URL")
    
    # 下载图片
    print("\n开始下载图片...")
    downloaded = 0
    failed = []
    
    for i, info in enumerate(image_info, 1):
        url = info['url']
        filename = get_image_filename(url)
        save_path = IMAGES_DIR / filename
        
        if save_path.exists():
            print(f"[{i}/{len(image_info)}] 已存在: {filename}")
            downloaded += 1
        else:
            print(f"[{i}/{len(image_info)}] 下载中: {url[:60]}...")
            if download_image(url, save_path):
                downloaded += 1
                print(f"  ✓ 保存为: {filename}")
            else:
                failed.append(url)
                print(f"  ✗ 失败")
    
    # 保存图片映射信息
    mapping = {}
    for info in image_info:
        filename = get_image_filename(info['url'])
        mapping[info['dia_id']] = {
            'filename': filename,
            'path': str(IMAGES_DIR / filename),
            'url': info['url'],
            'speaker': info['speaker'],
            'text': info['text'][:100],
            'blip_caption': info['blip_caption'],
            'query': info['query']
        }
    
    with open('image_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print(f"下载完成！")
    print(f"  成功: {downloaded}/{len(image_info)}")
    print(f"  失败: {len(failed)}")
    print(f"  映射文件: image_mapping.json")
    print("="*80)
    
    if failed:
        print("\n失败的URL:")
        for url in failed[:10]:
            print(f"  - {url}")

if __name__ == '__main__':
    main()
