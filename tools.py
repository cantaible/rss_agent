import requests
import json
from datetime import datetime, timedelta

def fetch_news(category: str):
    """
    调用外部 API 获取新闻数据
    """
    url = "http://150.158.113.98:9090/api/newsarticles/search"
    headers = {"Content-Type": "application/json"}
    
    # 构造最近 24 小时的时间范围 (或者根据需求调整)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=2) # 抓最近2天，确保有数据
    
    payload = {
        "keyword": category,
        "category": category,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "sortOrder": "latest",
        "includeContent": False  # 只拿标题摘要，省 token
    }
    
    try:
        print(f"🌍 Fetching news for {category}...")
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # 假设返回的是列表，或者 data 字段里是列表
            # 这里先原样返回，后续观察数据结构微调
            return data
        else:
            return f"Error: API status {resp.status_code}"
    except Exception as e:
        return f"Fetch exception: {str(e)}"

if __name__ == "__main__":
    # 本地测试
    print(fetch_news("AI"))
