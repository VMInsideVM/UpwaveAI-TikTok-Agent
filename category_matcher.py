"""
商品分类智能匹配模块
使用 LLM 进行语义推理,匹配商品到分类层级
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from category import get_product_category_level

# 加载环境变量
load_dotenv()

# 29 个一级分类列表
MAIN_CATEGORIES = [
    "美妆个护", "女装与女士内衣", "保健", "时尚配件", "运动与户外",
    "手机与数码", "食品饮料", "居家日用", "男装与男士内衣", "汽车与摩托车",
    "收藏品", "玩具和爱好", "电脑办公", "家装建材", "厨房用品",
    "鞋靴", "箱包", "家纺布艺", "五金工具", "宠物用品",
    "家电", "珠宝与衍生品", "图书&杂志&音频", "家具", "母婴用品",
    "穆斯林时尚", "儿童时尚", "虚拟商品", "二手"
]


class CategoryMatcher:
    """商品分类智能匹配器"""

    def __init__(self):
        """初始化 LLM"""
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0.1  # 降低温度以获得更确定的结果
        )
        self.categories_dir = "categories"

    def infer_main_category(self, product_name: str) -> Optional[str]:
        """
        步骤1: 使用 LLM 推断商品属于哪个一级分类

        Args:
            product_name: 商品名称

        Returns:
            一级分类名称,如果无法推断则返回 None
        """
        prompt = f"""你是一个电商商品分类专家。请根据商品名称,从以下 29 个一级分类中选择最合适的一个:

{', '.join(MAIN_CATEGORIES)}

商品名称: {product_name}

请直接回答分类名称,不要有任何额外解释。如果商品明显不属于任何分类,请回答"无法分类"。

示例:
商品: 口红 → 美妆个护
商品: 运动鞋 → 鞋靴
商品: 瑜伽垫 → 运动与户外
商品: 护肤水 → 美妆个护

现在请回答:"""

        try:
            response = self.llm.invoke(prompt)
            category = response.content.strip()

            # 验证返回的分类是否在列表中
            if category in MAIN_CATEGORIES:
                return category

            # 如果 LLM 返回了类似的但不完全匹配的名称,尝试模糊匹配
            for cat in MAIN_CATEGORIES:
                if cat in category or category in cat:
                    return cat

            return None

        except Exception as e:
            print(f"❌ 推断一级分类时出错: {e}")
            return None

    def load_category_json(self, main_category: str) -> Optional[Dict]:
        """
        步骤2: 加载对应一级分类的 JSON 文件

        Args:
            main_category: 一级分类名称

        Returns:
            分类数据字典,如果文件不存在返回 None
        """
        json_path = os.path.join(self.categories_dir, f"{main_category}.json")

        if not os.path.exists(json_path):
            print(f"⚠️ 分类文件不存在: {json_path}")
            return None

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 读取分类文件出错: {e}")
            return None

    def extract_all_categories(self, category_data: Dict) -> Dict[str, List[str]]:
        """
        步骤3: 提取所有层级的分类名称

        Args:
            category_data: 分类 JSON 数据

        Returns:
            格式: {
                'l1': [(名称, ID)],
                'l2': [(名称, ID, 父级)],
                'l3': [(名称, ID, 父级)]
            }
        """
        result = {'l1': [], 'l2': [], 'l3': []}

        # 遍历一级分类
        for l1_name, l1_data in category_data.items():
            l1_id = l1_data.get('id')
            result['l1'].append((l1_name, l1_id))

            # 遍历二级分类
            if 'children' in l1_data:
                for l2_name, l2_data in l1_data['children'].items():
                    l2_id = l2_data.get('id')
                    result['l2'].append((l2_name, l2_id, l1_name))

                    # 遍历三级分类
                    if 'children' in l2_data:
                        for l3_name, l3_id in l2_data['children'].items():
                            result['l3'].append((l3_name, l3_id, l2_name))

        return result

    def find_best_match(self, product_name: str, category_data: Dict) -> Tuple[str, str]:
        """
        步骤4: 使用 LLM 深度推理找到最佳匹配的分类层级

        Args:
            product_name: 商品名称
            category_data: 分类 JSON 数据

        Returns:
            (层级, 分类名称) 如 ('l3', '口红') 或 ('l2', '彩妆') 或 ('l1', '美妆个护')
        """
        categories = self.extract_all_categories(category_data)

        # 构建候选分类列表
        l3_candidates = [name for name, _, _ in categories['l3']]
        l2_candidates = [name for name, _, _ in categories['l2']]
        l1_candidates = [name for name, _ in categories['l1']]

        # 首先尝试匹配三级分类
        if l3_candidates:
            l3_match = self._match_to_candidates(
                product_name,
                l3_candidates,
                "三级分类(最精确)",
                categories
            )
            if l3_match:
                return ('l3', l3_match)

        # 如果三级分类没有合适的,尝试二级分类
        if l2_candidates:
            l2_match = self._match_to_candidates(
                product_name,
                l2_candidates,
                "二级分类(较精确)",
                categories
            )
            if l2_match:
                return ('l2', l2_match)

        # 最后返回一级分类
        if l1_candidates:
            return ('l1', l1_candidates[0])

        return ('l1', list(category_data.keys())[0])

    def _match_to_candidates(
        self,
        product_name: str,
        candidates: List[str],
        level_name: str,
        all_categories: Dict
    ) -> Optional[str]:
        """
        使用 LLM 从候选分类中选择最佳匹配

        Args:
            product_name: 商品名称
            candidates: 候选分类列表
            level_name: 层级名称(用于提示词)
            all_categories: 所有分类数据(用于获取父级关系)

        Returns:
            最佳匹配的分类名称,如果没有合适的返回 None
        """
        # 如果候选太多,分批处理
        if len(candidates) > 50:
            candidates = candidates[:50]  # 限制候选数量

        candidates_str = '\n'.join([f"- {cat}" for cat in candidates])

        prompt = f"""你是电商商品分类专家。请判断商品"{product_name}"最适合以下哪个{level_name}:

{candidates_str}

请仔细思考商品的特性,选择最精确匹配的分类。如果以上分类都不太合适,请回答"无合适分类"。

只需回答分类名称,不要解释。

商品: {product_name}
最佳{level_name}:"""

        try:
            response = self.llm.invoke(prompt)
            match = response.content.strip()

            # 检查是否是有效的候选分类
            if match in candidates:
                return match

            # 尝试模糊匹配
            for candidate in candidates:
                if candidate in match or match in candidate:
                    return candidate

            # 检查是否明确表示无合适分类
            if "无" in match or "不" in match or "没有" in match:
                return None

            return None

        except Exception as e:
            print(f"❌ 匹配分类时出错: {e}")
            return None

    def match_product_category(self, product_name: str) -> Optional[Dict]:
        """
        完整流程: 匹配商品分类并返回 URL 后缀

        Args:
            product_name: 商品名称

        Returns:
            包含分类信息和 URL 后缀的字典,失败返回 None
            格式: {
                'level': 'l3',
                'category_name': '口红',
                'category_id': '123456',
                'url_suffix': '&sale_category_l3=123456',
                'main_category': '美妆个护'
            }
        """
        print(f"🔍 开始分析商品: {product_name}")

        # 步骤1: 推断一级分类
        main_category = self.infer_main_category(product_name)
        if not main_category:
            print(f"❌ 无法推断商品 '{product_name}' 的一级分类")
            return None

        print(f"✅ 推断一级分类: {main_category}")

        # 步骤2: 加载分类 JSON
        category_data = self.load_category_json(main_category)
        if not category_data:
            print(f"❌ 无法加载分类文件: {main_category}")
            return None

        # 步骤3: 深度推理找到最佳匹配
        level, category_name = self.find_best_match(product_name, category_data)
        print(f"✅ 匹配到{level}分类: {category_name}")

        # 步骤4: 调用现有函数获取 URL 后缀
        try:
            result = get_product_category_level(
                product_name=category_name,
                main_category=main_category,
                return_url_suffix=True
            )

            if result:
                result['main_category'] = main_category
                print(f"✅ URL 后缀: {result.get('url_suffix', '')}")
                return result
            else:
                print(f"⚠️ 无法获取 URL 后缀")
                return None

        except Exception as e:
            print(f"❌ 获取 URL 后缀时出错: {e}")
            return None


# 便捷函数
def match_product_category(product_name: str) -> Optional[Dict]:
    """
    便捷函数: 直接匹配商品分类

    Args:
        product_name: 商品名称

    Returns:
        分类信息字典或 None
    """
    matcher = CategoryMatcher()
    return matcher.match_product_category(product_name)


if __name__ == "__main__":
    # 测试代码
    test_products = ["口红", "运动鞋", "瑜伽垫", "iPhone手机壳", "狗粮"]

    for product in test_products:
        print(f"\n{'='*50}")
        result = match_product_category(product)
        if result:
            print(f"✅ 商品 '{product}' 匹配成功!")
            print(f"   层级: {result['level']}")
            print(f"   分类: {result['category_name']}")
            print(f"   URL: {result['url_suffix']}")
        else:
            print(f"❌ 商品 '{product}' 匹配失败")
