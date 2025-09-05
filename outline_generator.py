import json
import uuid
from typing import Dict, List, Any
import openai
from config import config, prompts

class OutlineGenerator:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL
        )
    
    def _generate_json_example(self, max_level: int) -> str:
        """根据此类的层级或者样式深度动态生成JSON格式示例"""
        def create_level(current_level: int) -> List[Dict]:
            if current_level >= max_level:
                return []
            
            next_level = current_level + 1
            # 为了引导模型生成更稳定的结构，不同层级给出更明确的示例数量
            if next_level == 1:
                num_children = 3  # 示例包含3个一级章节
            elif next_level == 2:
                num_children = 4  # 每个一级章节下示例4个二级
            elif next_level == 3:
                num_children = 4  # 每个二级章节下示例4个三级
            elif next_level == 4:
                num_children = 3  # 每个三级章节下示例3个四级
            else:
                num_children = 0
            
            nodes = []
            for _ in range(num_children):
                node = {
                    "level": next_level,
                    "title": "xxx",
                }
                if next_level < max_level:
                    node["children"] = create_level(next_level)
                nodes.append(node)
            return nodes

        example = {
            "title": "xxx标题",
            "outline": create_level(0)
        }
        return json.dumps(example, indent=2, ensure_ascii=False)

    async def generate_outline(self, summary_content: str, max_level: int = 4) -> Dict[str, Any]:
        """根据总结内容生成1-4层级的目录结构
        
        Args:
            summary_content: 文档总结内容
            max_level: 最大目录层级，范围为3-4。小于3会自动修正为3，大于4会修正为4。
        """
        try:
            # 验证并调整最大层级参数。
            # 由于1-2级目录不生成内容，为确保文档有实际内容，最小层级强制为3。
            if max_level < 3:
                max_level = 3
            if max_level > 4:
                max_level = 4
            
            # 动态生成JSON格式示例
            json_example = self._generate_json_example(max_level)

            # 根据层级选择更确定性的提示词
            if max_level == 3:
                prompt = prompts.GENERATE_OUTLINE_3.format(
                    json_example=json_example,
                    summary_content=summary_content
                )
            else:
                prompt = prompts.GENERATE_OUTLINE_4.format(
                    json_example=json_example,
                    summary_content=summary_content
                )

            system_prompt = self._build_system_prompt(max_level)
            
            response = await self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=8192,
                temperature=0.1,
                response_format={"type": "json_object"}  # 强制JSON格式
            )
            
            content = response.choices[0].message.content.strip()
            
            # 解析JSON
            try:
                outline_data = json.loads(content)
                
                # 验证和标准化数据结构、
                # print(f"原始目录结构: {outline_data}")
                standardized_outline = self._standardize_bid_outline(outline_data, max_level)
                
                # 验证是否达到要求的层级深度
                actual_max_level = self._get_max_depth(standardized_outline)
                if actual_max_level < max_level:
                    print(f"警告：生成的目录最大深度为{actual_max_level}层，未达到要求的{max_level}层")
                
                # 验证3-4级的丰富性
                richness_check = self._validate_outline_richness(standardized_outline, max_level)
                
                return {
                    "success": True,
                    "outline": standardized_outline,
                    "total_sections": self._count_sections(standardized_outline),
                    "max_level": max_level,
                    "actual_max_level": actual_max_level,
                    "richness_check": richness_check
                }
                
            except json.JSONDecodeError as e:
                # 如果JSON解析失败，返回错误
                return {
                    "success": False,
                    "error": f"目录生成失败：AI未能返回有效的JSON格式。错误：{str(e)}",
                    "outline": None
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"目录生成失败: {str(e)}",
                "outline": None
            }
    
    def _standardize_bid_outline(self, outline_data: Dict, max_level: int) -> Dict:
        """标准化投标方案目录结构，并递归处理子项"""
        if not isinstance(outline_data, dict):
            raise ValueError("目录数据必须是字典格式")

        def _recursive_standardize(items: List[Dict], current_level: int) -> List[Dict]:
            if not isinstance(items, list) or current_level >= max_level:
                return []

            standardized_list = []
            next_level = current_level + 1

            for i, item in enumerate(items):
                if isinstance(item, dict):
                    # 强制使用真实层级，忽略输入中的 level 值，保证层级与深度一致
                    level = next_level
                    if level > max_level:
                        continue
                    
                    standardized_item = {
                        "level": level,
                        "title": item.get("title", f"章节 {i+1}"),
                        "id": str(uuid.uuid4()),
                        "children": _recursive_standardize(item.get("children", []), next_level)
                    }
                    standardized_list.append(standardized_item)
            return standardized_list

        title = outline_data.get("title", "投标文件")
        outline_items = outline_data.get("outline", [])
        if not isinstance(outline_items, list):
            outline_items = []

        return {
            "title": title,
            "outline": _recursive_standardize(outline_items, 0)
        }

    def _count_sections(self, outline_data: Dict) -> int:
        """递归计算目录中的总章节数"""
        def _recursive_count(items: List[Dict]) -> int:
            count = 0
            for item in items:
                count += 1
                count += _recursive_count(item.get("children", []))
            return count
        
        return _recursive_count(outline_data.get("outline", []))

    def _get_max_depth(self, outline_data: Dict) -> int:
        """递归获取目录的最大深度"""
        def get_item_depth(item: Dict) -> int:
            max_depth = item.get("level", 1)
            for child in item.get("children", []):
                max_depth = max(max_depth, get_item_depth(child))
            return max_depth

        max_overall_depth = 0
        for item in outline_data.get("outline", []):
            max_overall_depth = max(max_overall_depth, get_item_depth(item))
        
        return max_overall_depth

    def _build_system_prompt(self, max_level: int) -> str:
        """构建更严格和确定性的System提示，确保目录层级稳定且只返回JSON"""
        if max_level == 3:
            return (
                "你是投标文件编制专家。请严格遵循以下规则生成目录，并且只返回一个有效的JSON对象：\n"
                "- 输出格式：只能是一个JSON对象，包含 'title' 和 'outline' 两个键；不得包含任何其他文本、注释或Markdown。\n"
                "- 层级深度：必须且仅生成3层（level=1/2/3）。严禁出现第4级或更深层级。\n"
                "- 结构约束：\n"
                "  * 每个 level=1 节点下包含 3-5 个 level=2 子节点；\n"
                "  * 每个 level=2 节点下包含 3-5 个 level=3 子节点；\n"
                "  * 所有 level=3 节点的 children 必须为 []。\n"
                "  * 严禁线性结构：任意节点的 children 数量不得为 1。\n"
                "- 字段要求：'outline' 中每个节点必须包含 'level'（数字1/2/3）、'title'（非空字符串）、'children'（数组）。\n"
                "- 标题规范：标题不含编号（如“第一章”“1.1”“1.1.1”），避免'其他'、'相关内容'等模糊表述。\n"
            )
        else:
            return (
                "你是投标文件编制专家。请严格遵循以下规则生成目录，并且只返回一个有效的JSON对象：\n"
                "- 输出格式：只能是一个JSON对象，包含 'title' 和 'outline' 两个键；不得包含任何其他文本、注释或Markdown。\n"
                "- 层级深度：必须且仅生成4层（level=1/2/3/4）。\n"
                "- 结构约束：\n"
                "  * 每个 level=1 节点下包含 3-5 个 level=2 子节点；\n"
                "  * 每个 level=2 节点下包含 3-5 个 level=3 子节点；\n"
                "  * 每个 level=3 节点下包含 2-4 个 level=4 子节点；\n"
                "  * 严禁线性结构：任意节点的 children 数量不得为 1。\n"
                "- 字段要求：'outline' 中每个节点必须包含 'level'（数字1/2/3/4）、'title'（非空字符串）、'children'（数组）。\n"
                "- 标题规范：标题不含编号（如“第一章”“1.1”“1.1.1”），避免'其他'、'相关内容'等模糊表述。\n"
            )
    
    def _validate_outline_richness(self, outline_data: Dict, max_level: int) -> Dict[str, Any]:
        """验证目录结构的丰富性，特别是3-4级"""
        issues = []
        suggestions = []
        
        def check_children_count(items: List[Dict], parent_level: int, parent_title: str = ""):
            for item in items:
                level = item.get("level", 1)
                title = item.get("title", "")
                children = item.get("children", [])
                
                # 检查第2级章节下的第3级数量
                if level == 2 and max_level >= 3:
                    child_count = len(children)
                    if child_count < 3:
                        issues.append(f"第2级章节 '{title}' 下只有 {child_count} 个第3级子章节，建议至少3-5个")
                        suggestions.append(f"为 '{title}' 添加更多具体的实施细节或技术要点")
                
                # 检查第3级章节下的第4级数量
                if level == 3 and max_level >= 4:
                    child_count = len(children)
                    if child_count < 2 and child_count > 0:
                        issues.append(f"第3级章节 '{title}' 下只有 {child_count} 个第4级子章节，建议至少2-4个")
                        suggestions.append(f"为 '{title}' 添加更多操作步骤或具体措施")
                
                # 递归检查子章节
                if children:
                    check_children_count(children, level, title)
        
        outline_items = outline_data.get("outline", [])
        check_children_count(outline_items, 0)
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "suggestions": suggestions,
            "total_issues": len(issues)
        } 