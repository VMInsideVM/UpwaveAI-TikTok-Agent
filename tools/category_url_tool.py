"""
GetCategoryURLSuffix Tool - wrapper for get_product_category_level function
"""
import json
from typing import Optional
from langchain.tools import BaseTool
from pydantic import Field
import sys
import os

# 添加父目录到路径以导入category模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from category import get_product_category_level


class GetCategoryURLSuffixTool(BaseTool):
    """Tool for getting category URL suffix"""

    name: str = "get_category_url_suffix"
    description: str = """
    根据商品分类名称和商品大类获取URL后缀。
    这是最终步骤，在确定了具体的分类名称后调用此工具。

    输入参数：
    - category_name: 分类名称（可以是一级、二级或三级分类名称）
    - main_category: 商品大类名称

    输出：包含URL后缀和完整分类信息的JSON字符串

    示例输出：
    {
      "level": "l3",
      "category_name": "口红与唇彩",
      "category_id": "601534",
      "parent_categories": ["美妆个护", "美妆"],
      "url_suffix": "&sale_category_l3=601534"
    }
    """

    def _run(self, category_name: str = "", main_category: str = "", **kwargs) -> str:
        """
        获取分类的URL后缀

        Args:
            category_name: 分类名称
            main_category: 商品大类名称
            **kwargs: 其他参数（兼容不同调用方式）

        Returns:
            JSON格式的结果字符串
        """
        try:
            # 如果没有直接传递参数，尝试从 kwargs 解析
            if not category_name and not main_category:
                # 检查是否有 query 参数
                if 'query' in kwargs:
                    params = json.loads(kwargs['query'])
                    category_name = params.get("category_name", "")
                    main_category = params.get("main_category", "")
                else:
                    return json.dumps({
                        "status": "error",
                        "message": "缺少必要参数：category_name 和 main_category"
                    }, ensure_ascii=False)

            if not category_name or not main_category:
                return json.dumps({
                    "status": "error",
                    "message": f"缺少必要参数：category_name={category_name}, main_category={main_category}"
                }, ensure_ascii=False)

            # 调用原有函数
            result = get_product_category_level(
                product_name=category_name,
                main_category=main_category,
                return_url_suffix=True
            )

            # 添加状态标识
            if result.get('level') is None:
                result['status'] = 'not_found'
            else:
                result['status'] = 'success'

            return json.dumps(result, ensure_ascii=False, indent=2)

        except json.JSONDecodeError:
            return json.dumps({
                "status": "error",
                "message": "输入格式错误，请提供有效的JSON字符串"
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"处理请求时发生错误: {str(e)}"
            }, ensure_ascii=False)

    async def _arun(self, query: str) -> str:
        """异步运行（暂不支持）"""
        return self._run(query)
