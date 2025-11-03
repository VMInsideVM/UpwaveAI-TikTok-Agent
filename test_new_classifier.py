"""
测试新分类器是否能正常工作
"""
from agent_tools import match_product_category

def test_classification():
    """测试分类功能"""
    print("="*60)
    print("测试新分类器功能")
    print("="*60)

    test_products = ["口红", "运动鞋", "手机壳"]

    for product in test_products:
        print(f"\n📦 测试商品: {product}")
        print("-" * 40)

        try:
            result = match_product_category(product)

            if result:
                print(f"✅ 分类成功!")
                print(f"  一级分类: {result.get('main_category')}")
                print(f"  分类层级: {result.get('level')}")
                print(f"  分类名称: {result.get('category_name')}")
                print(f"  URL后缀: {result.get('url_suffix')}")
                print(f"  推理过程: {result.get('reasoning', '无')[:100]}...")
            else:
                print(f"❌ 分类失败")

        except Exception as e:
            print(f"❌ 出错: {str(e)}")

    print("\n" + "="*60)
    print("✅ 测试完成!")

if __name__ == "__main__":
    test_classification()
