"""
测试图像分析功能
"""

import os
from dotenv import load_dotenv
from image_analyzer import get_image_analyzer

# 加载环境变量
load_dotenv()


def test_image_analyzer():
    """测试图像分析器的各种功能"""
    print("=" * 80)
    print("测试图像分析器")
    print("=" * 80)
    print()

    analyzer = get_image_analyzer()

    # 测试 1: 分析网络图像（通用描述）
    print("📸 测试 1: 分析网络商品图像（手表）")
    print("-" * 80)
    test_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800"
    result = analyzer.analyze_image_from_url(
        test_url,
        prompt="这是什么商品？请详细描述它的类型、颜色、风格、材质等特征。"
    )
    print(f"分析结果:\n{result}")
    print()

    # 测试 2: 分析网络图像（商品信息提取）
    print("📸 测试 2: 提取商品信息")
    print("-" * 80)
    # 注意：analyze_product_image 只支持本地文件
    # 这里我们使用通用的 analyze_image_from_url 并自定义提示词
    product_prompt = """请分析这张商品图片，提取以下信息：

1. **商品名称**：商品的具体名称或描述
2. **商品类别**：商品所属的类别（如：美妆个护、服饰配饰、食品饮料等）
3. **商品特征**：商品的主要特征（颜色、材质、风格等）
4. **目标人群**：商品的目标用户群体（性别、年龄段等）
5. **适合场景**：商品的使用场景或推广场景

请直接给出分析结果。"""

    result = analyzer.analyze_image_from_url(test_url, product_prompt)
    print(f"商品信息:\n{result}")
    print()

    # 测试 3: 分析不同商品（化妆品）
    print("📸 测试 3: 分析化妆品图像")
    print("-" * 80)
    cosmetics_url = "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=800"
    result = analyzer.analyze_image_from_url(
        cosmetics_url,
        prompt="这是什么化妆品？请识别品牌、产品类型、颜色、包装风格等。"
    )
    print(f"分析结果:\n{result}")
    print()

    # 测试 4: 分析服装
    print("📸 测试 4: 分析服装图像")
    print("-" * 80)
    clothing_url = "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=800"
    result = analyzer.analyze_image_from_url(
        clothing_url,
        prompt="这是什么服装？请描述款式、颜色、适合场合、目标人群等。"
    )
    print(f"分析结果:\n{result}")
    print()

    print("=" * 80)
    print("✅ 所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_image_analyzer()
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
