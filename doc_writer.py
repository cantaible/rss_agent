"""
飞书文档写入辅助类
用于将机器人生内容写入飞书云文档（支持Wiki）
"""
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

class FeishuDocWriter:
    """飞书文档写入器"""
    
    BASE_URL = "https://open.larkoffice.com/open-apis"
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: Optional[datetime] = None
        self._wiki_doc_cache: Dict[str, str] = {}  # wiki_token -> document_id

    def get_tenant_access_token(self) -> str:
        """获取应用访问凭证"""
        if (self._tenant_access_token and self._token_expire_time and 
            datetime.now() < self._token_expire_time):
            return self._tenant_access_token
        
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            if result.get("code") != 0:
                print(f"❌ 获取access_token失败: {result.get('msg')}")
                return ""
            
            self._tenant_access_token = result["tenant_access_token"]
            expire_seconds = result.get("expire", 7200) - 300
            self._token_expire_time = datetime.now() + timedelta(seconds=expire_seconds)
            return self._tenant_access_token
        except Exception as e:
            print(f"❌ 获取access_token异常: {e}")
            return ""

    def _get_headers(self) -> Dict[str, str]:
        token = self.get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def get_document_id_from_wiki(self, wiki_token: str) -> str:
        """从Wiki token获取实际的文档ID"""
        if wiki_token in self._wiki_doc_cache:
            return self._wiki_doc_cache[wiki_token]
        
        url = f"{self.BASE_URL}/wiki/v2/spaces/get_node"
        params = {"token": wiki_token}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            result = response.json()
            
            if result.get("code") != 0:
                print(f"❌ 获取Wiki节点信息失败: {result.get('msg')}")
                return ""
            
            node = result.get("data", {}).get("node", {})
            obj_token = node.get("obj_token")
            
            if obj_token:
                self._wiki_doc_cache[wiki_token] = obj_token
                return obj_token
            return ""
        except Exception as e:
            print(f"❌ 获取Wiki ID异常: {e}")
            return ""

    def find_first_callout_index(self, document_id: str) -> int:
        """查找第一个高亮块（Callout, block_type=19）的位置"""
        url = f"{self.BASE_URL}/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        try:
            # 获取前50个块，假设高亮块在开头
            response = requests.get(url, headers=self._get_headers(), params={"page_size": 50})
            if response.status_code != 200:
                return -1
                
            items = response.json().get("data", {}).get("items", [])
            for i, block in enumerate(items):
                # block_type: 19=Callout, 18=Quote, 17=Equation? 
                # 文档通常用 Callout (19) 做提示
                if block.get("block_type") in [17, 18, 19]:
                    print(f"📍 找到高亮块 (Type {block.get('block_type')}) at index {i}")
                    return i + 1
            return -1
        except Exception as e:
            print(f"⚠️ find_first_callout_index exception: {e}")
            return -1

    def append_blocks(self, document_id: str, children: List[Dict], index: int = -1) -> bool:
        """批量写入Block (默认追加到末尾，指定 index 则插入)"""
        block_id = document_id
        url = f"{self.BASE_URL}/docx/v1/documents/{document_id}/blocks/{block_id}/children"
        
        payload = {
            "children": children,
            "index": index
        }
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
            result = response.json()
            if result.get("code") != 0:
                print(f"❌ 写入Block失败: {result.get('msg')}")
                return False
            return True
        except Exception as e:
            print(f"❌ 写入Block异常: {e}")
            return False

    def create_heading_block(self, text: str, level: int = 1) -> Dict:
        """构建标题Block"""
        block_type = 2 + level # 3=H1, 4=H2...
        return {
            "block_type": block_type,
            f"heading{level}": {
                "elements": [{"text_run": {"content": text}}],
                "style": {}
            }
        }

    def create_text_block(self, text: str) -> Dict:
        """构建普通文本Block"""
        return {
            "block_type": 2,
            "text": {
                "elements": [{"text_run": {"content": text}}],
                "style": {}
            }
        }

    def create_divider_block(self) -> Dict:
        """构建分割线Block"""
        return {
            "block_type": 22,
            "divider": {}
        }

    def write_daily_news_to_wiki(self, wiki_token: str, all_categories_news: Dict[str, Dict]) -> bool:
        """
        写入每日新闻到Wiki (插入到第一个高亮块之后)
        all_categories_news: {"AI": briefing_dict, "MUSIC": ...}
        briefing_dict 结构: {"global_summary": str, "clusters": [{"name": str, "items": [...]}]}
        """
        # 1. 获取文档ID
        document_id = self.get_document_id_from_wiki(wiki_token)
        if not document_id:
            return False

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        blocks_to_write = []

        # 2. 构建内容
        # 分割线（区分上一次写入）
        blocks_to_write.append(self.create_divider_block())
        
        # 写入时间头
        blocks_to_write.append(self.create_heading_block(f"🕒 自动归档 - {current_time}", level=2))

        # 遍历类别
        for category, briefing in all_categories_news.items():
            # 类别标题
            icon = "🤖" if category == "AI" else ("🎵" if category == "MUSIC" else "🎮")
            blocks_to_write.append(self.create_heading_block(f"{icon} {category} 新闻", level=2))

            if not briefing or not isinstance(briefing, dict):
                blocks_to_write.append(self.create_text_block("（暂无数据）"))
                continue
            
            # 2.1 全局摘要
            global_summary = briefing.get("global_summary")
            if global_summary:
                blocks_to_write.append(self.create_text_block(f"📝 综述：{global_summary}"))

            # 2.2 遍历板块 (Clusters)
            clusters = briefing.get("clusters", [])
            if not clusters:
                 blocks_to_write.append(self.create_text_block("（无板块数据）"))
                 continue

            for cluster in clusters:
                cluster_name = cluster.get("name", "未命名板块")
                # H3 板块标题
                blocks_to_write.append(self.create_heading_block(f"📌 {cluster_name}", level=3))
                
                items = cluster.get("items", [])
                for i, news in enumerate(items, 1):
                    # news 应该是 dict
                    if not isinstance(news, dict):
                         continue
                         
                    title = news.get("title", "无标题")
                    link = news.get("url", "") # 注意 agent_graph 里是 url
                    summary = news.get("summary", "")

                    # 格式：1. 标题
                    #      🔗 链接
                    #      摘要
                    content = f"{i}. {title}"
                    if link:
                        content += f"\n   🔗 {link}"
                    if summary:
                        content += f"\n   {summary}"
                    
                    blocks_to_write.append(self.create_text_block(content))

        # 3. 确定插入位置
        insert_index = self.find_first_callout_index(document_id)
        if insert_index == -1:
            print("⚠️ 未找到高亮块，将追加到文档末尾")
        else:
            print(f"📝 将插入到索引 {insert_index} (高亮块之后)")
            
        # 4. 写入
        return self.append_blocks(document_id, blocks_to_write, index=insert_index)
