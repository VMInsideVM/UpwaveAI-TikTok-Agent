"""
CategoryReader Tool for reading category JSON files
"""
import json
import os
from typing import Optional, Dict, Any
from langchain.tools import BaseTool
from pydantic import Field


class CategoryReaderTool(BaseTool):
    """Tool for reading category structure from JSON files"""

    name: str = "category_reader"
    description: str = """
    读取指定商品大类的完整分类结构。
    输入：商品大类名称（如：'美妆个护'、'食品饮料'等）
    输出：该大类的完整分类树结构，包含一级、二级、三级分类及其ID

    可用的商品大类：
    '二手', '五金工具', '保健', '儿童时尚', '厨房用品', '图书&杂志&音频',
    '女装与女士内衣', '宠物用品', '家具', '家电', '家纺布艺', '家装建材',
    '居家日用', '手机与数码', '收藏品', '时尚配件', '母婴用品', '汽车与摩托车',
    '玩具和爱好', '珠宝与衍生品', '电脑办公', '男装与男士内衣', '穆斯林时尚',
    '箱包', '美妆个护', '虚拟商品', '运动与户外', '鞋靴', '食品饮料'
    """

    categories_dir: str = Field(default="categories")

    def _run(self, main_category: str) -> str:
        """
        读取指定商品大类的分类结构

        Args:
            main_category: 商品大类名称

        Returns:
            JSON格式的分类结构字符串
        """
        json_file = os.path.join(self.categories_dir, f'{main_category}.json')

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                category_data = json.load(f)

            # 提取分类信息用于分析
            analysis = self._analyze_structure(category_data)

            result = {
                "status": "success",
                "main_category": main_category,
                "structure": category_data,
                "analysis": analysis
            }

            return json.dumps(result, ensure_ascii=False, indent=2)

        except FileNotFoundError:
            return json.dumps({
                "status": "error",
                "message": f"未找到商品大类 '{main_category}' 的分类文件"
            }, ensure_ascii=False)
        except json.JSONDecodeError:
            return json.dumps({
                "status": "error",
                "message": f"分类文件 '{json_file}' 格式错误"
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"读取分类文件时发生错误: {str(e)}"
            }, ensure_ascii=False)

    def _analyze_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析分类结构，提取有用信息

        Args:
            data: 分类数据

        Returns:
            分析结果
        """
        analysis = {
            "level1_categories": [],
            "level2_categories": [],
            "level3_categories": [],
            "total_level3_count": 0
        }

        for l1_name, l1_info in data.items():
            analysis["level1_categories"].append({
                "name": l1_name,
                "id": l1_info.get("id", "")
            })

            if "children" in l1_info and isinstance(l1_info["children"], dict):
                for l2_name, l2_info in l1_info["children"].items():
                    analysis["level2_categories"].append({
                        "name": l2_name,
                        "id": l2_info.get("id", ""),
                        "parent": l1_name
                    })

                    if "children" in l2_info and isinstance(l2_info["children"], dict):
                        for l3_name, l3_id in l2_info["children"].items():
                            analysis["level3_categories"].append({
                                "name": l3_name,
                                "id": str(l3_id),
                                "parent_l2": l2_name,
                                "parent_l1": l1_name
                            })
                            analysis["total_level3_count"] += 1

        return analysis

    async def _arun(self, main_category: str) -> str:
        """异步运行（暂不支持）"""
        return self._run(main_category)
