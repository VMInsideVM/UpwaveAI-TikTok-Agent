"""
Multi-modal Product Category Classifier Agent - V3
不使用 bind_tools，改用 prompt engineering 让模型返回 JSON
"""
import os
import json
import base64
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tools import CategoryReaderTool, GetCategoryURLSuffixTool

# 商品大类列表
MAIN_CATEGORIES = [
    '二手', '五金工具', '保健', '儿童时尚', '厨房用品', '图书&杂志&音频',
    '女装与女士内衣', '宠物用品', '家具', '家电', '家纺布艺', '家装建材',
    '居家日用', '手机与数码', '收藏品', '时尚配件', '母婴用品', '汽车与摩托车',
    '玩具和爱好', '珠宝与衍生品', '电脑办公', '男装与男士内衣', '穆斯林时尚',
    '箱包', '美妆个护', '虚拟商品', '运动与户外', '鞋靴', '食品饮料'
]


class ProductCategoryClassifierV3:
    """商品分类 Agent - V3 版本（无工具绑定）"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 5,
        verbose: bool = True
    ):
        self.model_name = model_name or os.getenv("OPENAI_MODEL")
        self.temperature = temperature if temperature is not None else float(os.getenv("TEMPERATURE", "0.1"))
        self.max_iterations = max_iterations
        self.verbose = verbose

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")

        llm_params = {
            "model": self.model_name,
            "temperature": self.temperature,
        }
        if api_key:
            llm_params["api_key"] = api_key
        if base_url:
            llm_params["base_url"] = base_url

        if self.verbose:
            print(f"\n🔧 初始化分类器 V3 (无工具绑定):")
            print(f"  📦 模型: {self.model_name}")
            print(f"  🌡️  温度: {self.temperature}")
            print(f"  🌐 Base URL: {base_url or '默认'}\n")

        self.llm = ChatOpenAI(**llm_params)

        # 初始化工具
        self.category_reader = CategoryReaderTool()
        self.url_suffix_tool = GetCategoryURLSuffixTool()

    def classify(
        self,
        text: Optional[str] = None,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """分类商品"""

        if not text and not image_path and not image_url:
            return {
                "status": "error",
                "message": "请至少提供文字描述或图片"
            }

        try:
            # 第一步：识别商品并确定大类
            if self.verbose:
                print("\n📍 第一步：识别商品并确定大类")

            content_parts = []

            if text:
                content_parts.append({
                    "type": "text",
                    "text": f"商品信息：{text}"
                })

            if additional_info:
                content_parts.append({
                    "type": "text",
                    "text": f"\n额外信息：{json.dumps(additional_info, ensure_ascii=False)}"
                })

            if image_path:
                content_parts.append(self._load_local_image(image_path))
            elif image_url:
                # SiliconFlow API 不支持直接使用 URL，需要下载并转为 base64
                content_parts.append(self._load_url_image(image_url))

            # 构建第一步的提示
            step1_system_prompt = f"""你是一个商品分类专家。

可用的商品大类（共{len(MAIN_CATEGORIES)}个）：
{', '.join(MAIN_CATEGORIES)}

请分析用户提供的商品信息（文字、图片等），然后：
1. 识别商品是什么
2. 从上述大类中选择最匹配的一个

**请以 JSON 格式回复：**
```json
{{
  "product_description": "商品描述",
  "main_category": "选择的大类名称",
  "reasoning": "为什么选择这个大类"
}}
```

只需要返回 JSON，不要其他内容。"""

            # 构建用户消息内容
            # 如果只有一个文本元素，提取文本字符串；否则传递完整列表
            if len(content_parts) == 1 and content_parts[0].get("type") == "text":
                user_content = content_parts[0]["text"]
            else:
                user_content = content_parts

            messages = [
                SystemMessage(content=step1_system_prompt),
                HumanMessage(content=user_content)
            ]

            response = self.llm.invoke(messages)

            if self.verbose:
                print(f"   模型响应: {response.content[:300]}...")

            # 解析第一步的结果
            step1_result = self._extract_json(response.content)
            if not step1_result or 'main_category' not in step1_result:
                return {
                    "status": "error",
                    "message": "无法确定商品大类",
                    "raw_response": response.content
                }

            main_category = step1_result['main_category']
            product_description = step1_result.get('product_description', '')

            if self.verbose:
                print(f"\n   ✅ 识别结果:")
                print(f"      商品: {product_description}")
                print(f"      大类: {main_category}")

            # 第二步：读取分类结构
            if self.verbose:
                print(f"\n📍 第二步：读取 '{main_category}' 的分类结构")

            category_data = self.category_reader._run(main_category)

            if self.verbose:
                print(f"   ✅ 获取到分类数据: {len(category_data)} 字符")

            # 第三步：深度分类分析
            if self.verbose:
                print(f"\n📍 第三步：深度分类分析")

            step3_system_prompt = """你是一个专业的商品分类专家。

请分析商品信息和分类结构，选择最合适的分类。

**规则：**
1. 优先选择最具体的三级分类
2. 如果没有合适的三级分类，选择二级分类
3. 如果没有合适的二级分类，选择一级分类

**请以 JSON 格式回复：**
```json
{
  "selected_category": "选择的分类名称（一级/二级/三级）",
  "category_level": "分类级别（L1/L2/L3）",
  "parent_categories": "父分类路径（如果有）",
  "reasoning": "选择理由",
  "confidence": "置信度（0-1）"
}
```

只需要返回 JSON，不要其他内容。"""

            step3_message = f"""商品信息：
{product_description}

大类：{main_category}

完整分类结构：
{category_data}

请分析并选择最合适的分类。"""

            response = self.llm.invoke([
                SystemMessage(content=step3_system_prompt),
                HumanMessage(content=step3_message)
            ])

            if self.verbose:
                print(f"   模型响应: {response.content[:300]}...")

            step3_result = self._extract_json(response.content)
            if not step3_result or 'selected_category' not in step3_result:
                return {
                    "status": "error",
                    "message": "无法确定具体分类",
                    "raw_response": response.content
                }

            selected_category = step3_result['selected_category']

            if self.verbose:
                print(f"\n   ✅ 分类结果:")
                print(f"      分类: {selected_category}")
                print(f"      级别: {step3_result.get('category_level')}")
                print(f"      理由: {step3_result.get('reasoning', '')[:100]}")

            # 第四步：获取 URL 后缀
            if self.verbose:
                print(f"\n📍 第四步：获取分类 URL")

            url_result = self.url_suffix_tool._run(
                category_name=selected_category,
                main_category=main_category
            )

            url_data = json.loads(url_result)

            if self.verbose:
                print(f"   ✅ URL 后缀: {url_data.get('url_suffix', 'N/A')}")

            # 返回完整结果
            return {
                "status": "success",
                "product_description": product_description,
                "main_category": main_category,
                "selected_category": selected_category,
                "category_level": step3_result.get('category_level'),
                "parent_categories": step3_result.get('parent_categories'),
                "url_suffix": url_data.get('url_suffix'),
                "reasoning": step3_result.get('reasoning'),
                "confidence": step3_result.get('confidence')
            }

        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"分类过程中发生错误: {str(e)}",
                "traceback": traceback.format_exc() if self.verbose else None
            }

    def _load_local_image(self, image_path: str) -> Dict[str, Any]:
        """加载本地图片并转换为base64"""
        try:
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }.get(ext, 'image/jpeg')

                return {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}"
                    }
                }
        except Exception as e:
            return {
                "type": "text",
                "text": f"[图片加载失败: {str(e)}]"
            }

    def _load_url_image(self, image_url: str) -> Dict[str, Any]:
        """下载 URL 图片并转换为 base64"""
        try:
            import requests

            if self.verbose:
                print(f"   📥 下载图片: {image_url[:60]}...")

            # 下载图片
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            # 获取内容类型
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            if 'image' not in content_type:
                raise ValueError(f"URL 返回的不是图片类型: {content_type}")

            # 转换为 base64
            image_data = base64.b64encode(response.content).decode('utf-8')

            # 确定 MIME 类型
            if 'jpeg' in content_type or 'jpg' in content_type:
                mime_type = 'image/jpeg'
            elif 'png' in content_type:
                mime_type = 'image/png'
            elif 'gif' in content_type:
                mime_type = 'image/gif'
            elif 'webp' in content_type:
                mime_type = 'image/webp'
            else:
                mime_type = 'image/jpeg'  # 默认

            if self.verbose:
                print(f"   ✅ 图片下载成功: {len(response.content)} bytes, 类型: {mime_type}")

            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}"
                }
            }
        except Exception as e:
            error_msg = f"[URL 图片加载失败: {str(e)}]"
            if self.verbose:
                print(f"   ❌ {error_msg}")
            return {
                "type": "text",
                "text": error_msg
            }

    def _extract_json(self, text: str) -> Optional[Dict]:
        """从文本中提取 JSON"""
        import re

        # 尝试直接解析
        try:
            return json.loads(text)
        except:
            pass

        # 尝试从 markdown 代码块中提取
        patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^{}]*\{[^{}]*\}[^{}]*\})',  # 嵌套 JSON
            r'(\{[^{}]+\})'  # 简单 JSON
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except:
                    continue

        return None

    def _is_image_url(self, text: str) -> bool:
        """判断文本是否为图片URL"""
        import re

        # URL模式匹配
        url_pattern = r'^https?://[^\s]+$'
        if not re.match(url_pattern, text):
            return False

        # 检查常见图片域名和扩展名
        image_indicators = [
            # 常见图片扩展名
            r'\.(jpg|jpeg|png|gif|webp|bmp|svg)(\?.*)?$',
            # 常见图片服务域名
            r'(gstatic\.com|imgur\.com|unsplash\.com|cloudinary\.com)',
            r'(amazonaws\.com.*\.(jpg|jpeg|png|gif|webp))',
            # Google图片URL特征
            r'(tbm=isch|imgurl=|/images\?)',
        ]

        for pattern in image_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def classify_interactive(self):
        """交互式分类模式"""
        print("=" * 60)
        print("欢迎使用商品分类 Agent V3 (无工具绑定版本)")
        print("=" * 60)
        print("\n支持的输入方式：")
        print("1. 直接输入商品描述")
        print("2. 输入 'image:图片路径' 来上传本地图片")
        print("3. 输入 'url:图片URL' 来使用在线图片")
        print("4. 直接粘贴图片URL（自动识别）")
        print("5. 输入 'quit' 退出\n")

        while True:
            user_input = input("\n请输入商品信息: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("再见！")
                break

            if not user_input:
                continue

            # 解析输入
            if user_input.startswith("image:"):
                image_path = user_input[6:].strip()
                result = self.classify(
                    text="请根据图片识别商品并分类",
                    image_path=image_path
                )
            elif user_input.startswith("url:"):
                image_url = user_input[4:].strip()
                result = self.classify(
                    text="请根据图片识别商品并分类",
                    image_url=image_url
                )
            elif self._is_image_url(user_input):
                # 自动识别图片URL
                if self.verbose:
                    print("   🔍 检测到图片URL，自动下载识别...")
                result = self.classify(
                    text="请根据图片识别商品并分类",
                    image_url=user_input
                )
            else:
                result = self.classify(text=user_input)

            # 显示结果
            print("\n" + "=" * 60)
            print("分类结果：")
            print("=" * 60)
            print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    """主函数"""
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("警告: 未设置 OPENAI_API_KEY 环境变量")
        return

    classifier = ProductCategoryClassifierV3(verbose=True)
    classifier.classify_interactive()


if __name__ == "__main__":
    main()
