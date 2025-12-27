"""
BaseTask - 所有應用層任務的抽象基類

用於組合多個 vghsdk 爬蟲模組完成業務邏輯的 Task。
單純的資料抓取請使用 vghsdk.core.CrawlerTask。
"""
from abc import ABC, abstractmethod
from typing import Type, Optional, Callable, Awaitable, Any, Union, Dict, List
from pydantic import BaseModel
from vghsdk.core import VghClient


class BaseTask(ABC):
    """
    應用層任務的抽象基類
    
    用於組合多個 vghsdk 爬蟲完成業務目標，如：
    - 待床追蹤 (抓取資料 + 更新 Google Sheets)
    - 手術統計 (抓取資料 + 計算統計 + 更新 Google Sheets)
    - 手術紀錄 (抓取資料 + 建構 Payload + 提交 Web9)
    
    Attributes:
        id: 任務唯一識別符，用於 API 路由 (e.g., "dashboard_bed")
        name: 任務顯示名稱
        description: 任務描述
        params_model: 參數的 Pydantic Model 類別 (可選)
        search_keywords: 搜尋關鍵字 (可選)
    """
    id: str
    name: str
    description: str
    params_model: Optional[Type[BaseModel]] = None
    search_keywords: List[str] = []
    
    @property
    def params_schema(self) -> Dict[str, Any]:
        """返回參數的 JSON Schema (用於 API 文檔)"""
        if self.params_model:
            return self.params_model.model_json_schema()
        return {}
    
    @abstractmethod
    async def run(
        self,
        params: Union[BaseModel, Dict[str, Any]],
        client: VghClient,
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]] = None
    ) -> Any:
        """
        執行任務
        
        Args:
            params: 已驗證的 Pydantic model (推薦) 或 dict
            client: 已登入的 VghClient
            progress_callback: 進度回報函數 async def(progress: int, message: str)
            
        Returns:
            任務執行結果 (通常是 Pydantic model 或 dict)
        """
        pass

