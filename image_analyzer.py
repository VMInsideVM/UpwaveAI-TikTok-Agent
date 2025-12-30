"""
图像分析工具
使用专门的视觉模型（IMAGE_MODEL）理解图像，将结果传递给主 Agent
"""

import os
import base64
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

load_dotenv()


class ImageAnalyzer:
    """图像分析器 - 使用视觉模型理解图像"""

    def __init__(self):
        """初始化图像分析器"""
        self.image_model = ChatOpenAI(
            model=os.getenv("IMAGE_MODEL", "Qwen/Qwen3-VL-235B-A22B-Thinking"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0.3
        )
        print(f"[OK] 图像分析器已初始化，使用模型: {os.getenv('IMAGE_MODEL')}")

    def encode_image_to_base64(self, image_path: str) -> str:
        """
        将图像编码为 base64 字符串

        Args:
            image_path: 图像文件路径

        Returns:
            base64 编码的图像字符串
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def analyze_image_from_path(
        self,
        image_path: str,
        prompt: str = "请详细描述这张图片的内容，包括主要元素、场景、颜色、风格等。"
    ) -> str:
        """
        从文件路径分析图像

        Args:
            image_path: 图像文件路径
            prompt: 分析提示词

        Returns:
            图像分析结果（文本描述）
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                return f"[ERROR] 图像文件不存在: {image_path}"

            # 获取图像文件扩展名，确定 MIME 类型
            ext = os.path.splitext(image_path)[1].lower()
            mime_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            mime_type = mime_type_map.get(ext, 'image/jpeg')

            # 编码图像
            base64_image = self.encode_image_to_base64(image_path)

            # 构建消息（包含图像和文本提示）
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    }
                ]
            )

            # 调用视觉模型
            print(f"[INFO] 正在使用视觉模型分析图像: {image_path}")
            response = self.image_model.invoke([message])

            # 提取文本响应
            result = response.content
            print(f"[OK] 图像分析完成，返回文本长度: {len(result)} 字符")

            return result

        except Exception as e:
            error_msg = f"[ERROR] 图像分析失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg

    def analyze_image_from_url(
        self,
        image_url: str,
        prompt: str = "请详细描述这张图片的内容，包括主要元素、场景、颜色、风格等。"
    ) -> str:
        """
        从 URL 分析图像

        Args:
            image_url: 图像 URL
            prompt: 分析提示词

        Returns:
            图像分析结果（文本描述）
        """
        try:
            # 构建消息（包含图像 URL 和文本提示）
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            )

            # 调用视觉模型
            print(f"[INFO] 正在使用视觉模型分析图像 URL: {image_url}")
            response = self.image_model.invoke([message])

            # 提取文本响应
            result = response.content
            print(f"[OK] 图像分析完成，返回文本长度: {len(result)} 字符")

            return result

        except Exception as e:
            error_msg = f"[ERROR] 图像分析失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg

    def analyze_product_image(self, image_path: str) -> Dict[str, Any]:
        """
        分析商品图像，提取商品信息

        Args:
            image_path: 商品图像路径

        Returns:
            包含商品信息的字典
        """
        prompt = """请分析这张商品图片，提取以下信息：

1. **商品名称**：商品的具体名称或描述
2. **商品类别**：商品所属的类别（如：美妆个护、服饰配饰、食品饮料等）
3. **商品特征**：商品的主要特征（颜色、材质、风格等）
4. **目标人群**：商品的目标用户群体（性别、年龄段等）
5. **适合场景**：商品的使用场景或推广场景

请以 JSON 格式返回结果，例如：
{
    "product_name": "YSL圣罗兰口红",
    "category": "美妆个护",
    "features": "正红色、哑光质地、高端奢侈品牌",
    "target_audience": "25-40岁女性，追求品质和时尚",
    "suitable_scenarios": "日常妆容、约会、职场、节日礼物"
}
"""

        result_text = self.analyze_image_from_path(image_path, prompt)

        # 尝试解析 JSON 结果
        try:
            import json
            # 提取 JSON 部分（如果模型返回了额外的文字）
            if '```json' in result_text:
                json_str = result_text.split('```json')[1].split('```')[0].strip()
            elif '{' in result_text and '}' in result_text:
                json_str = result_text[result_text.find('{'):result_text.rfind('}')+1]
            else:
                json_str = result_text

            product_info = json.loads(json_str)
            return product_info

        except Exception as e:
            print(f"[WARNING] 无法解析 JSON 结果，返回原始文本")
            return {
                "raw_analysis": result_text,
                "error": str(e)
            }


# 全局单例
_analyzer_instance = None


def get_image_analyzer() -> ImageAnalyzer:
    """
    获取全局图像分析器实例（单例模式）

    Returns:
        ImageAnalyzer 实例
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ImageAnalyzer()
    return _analyzer_instance


if __name__ == "__main__":
    # 测试图像分析器
    print("=" * 80)
    print("测试图像分析器")
    print("=" * 80)
    print()

    analyzer = get_image_analyzer()

    # 测试 1: 分析网络图像
    print("[TEST] 测试 1: 分析网络图像")
    test_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800"
    result = analyzer.analyze_image_from_url(
        test_url,
        prompt="这是什么商品？请描述它的类型、颜色、风格。"
    )
    print(f"分析结果:\n{result}")
    print()

    # 测试 2: 分析本地图像（如果存在）
    # test_image_path = "test_product.jpg"
    # if os.path.exists(test_image_path):
    #     print("[TEST] 测试 2: 分析本地商品图像")
    #     product_info = analyzer.analyze_product_image(test_image_path)
    #     print(f"商品信息:\n{json.dumps(product_info, indent=2, ensure_ascii=False)}")
    # else:
    #     print("[WARNING] 跳过测试 2（本地图像不存在）")
