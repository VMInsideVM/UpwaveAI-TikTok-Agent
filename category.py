import json
import re
import pandas as pd
from datetime import datetime
import os
import glob

category = ['二手', '五金工具', '保健', '儿童时尚', '厨房用品', '图书&杂志&音频', '女装与女士内衣', '宠物用品', '家具', '家电', '家纺布艺', '家装建材', '居家日用', '手机与数码', '收藏品', '时尚配件', '母婴用品', '汽车与摩托车', '玩具和爱好', '珠宝与衍生品', '电脑办公', '男装与男士内衣', '穆斯林时尚', '箱包', '美妆个护', '虚拟商品', '运动与户外', '鞋靴', '食品饮料']

def get_product_category_level(product_name, main_category, return_url_suffix=True):
    """
    根据用户输入的商品类型和商品大类，从categories目录对应的JSON文件中返回该商品的层级信息

    Args:
        product_name (str): 用户输入的商品类型名称
        main_category (str): 商品大类名称（如"美妆个护"、"食品饮料"等），用于指定从categories目录下的哪个JSON文件中查找
        return_url_suffix (bool): 是否返回URL后缀格式，默认为True

    Returns:
        dict: 包含层级信息的字典
            - level (str): 层级标识 ('l1', 'l2', 'l3')
            - category_name (str): 分类名称
            - category_id (str): 分类ID
            - parent_categories (list): 父级分类路径
            - url_suffix (str): URL后缀格式，如 "&sale_category_l3=603704" (仅当return_url_suffix=True时)
            - error (str): 错误信息（当未找到分类时）

    Examples:
        >>> get_product_category_level("手足膜", "美妆个护", return_url_suffix=True)
        {'level': 'l3', 'category_name': '手足膜', 'category_id': '601454', 'parent_categories': ['美妆个护', '手足及指甲护理'], 'url_suffix': '&sale_category_l3=601454'}
        >>> get_product_category_level("洗发护发", "美妆个护", return_url_suffix=True)
        {'level': 'l3', 'category_name': '洗发护发', 'category_id': '601469', 'parent_categories': ['美妆个护', '头部护理与造型'], 'url_suffix': '&sale_category_l3=601469'}
        >>> # 替代原来的get_category_url_suffix功能：
        >>> result = get_product_category_level("手足膜", "美妆个护", return_url_suffix=True)
        >>> url_suffix = result.get('url_suffix', '') if result.get('level') else ''
        >>> print(url_suffix)  # "&sale_category_l3=601454"
    """
    # 根据main_category参数从categories目录下加载对应的JSON文件
    json_file = f'categories/{main_category}.json'

    # 从文件加载分类数据
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            category_data = json.load(f)
    except FileNotFoundError:
        return {'level': None, 'category_name': None, 'category_id': None, 'parent_categories': [], 'error': f'{json_file}文件未找到，请检查商品大类名称是否正确'}
    except json.JSONDecodeError:
        return {'level': None, 'category_name': None, 'category_id': None, 'parent_categories': [], 'error': f'{json_file}文件格式错误'}
    
    # 递归搜索分类
    def search_category(data, target_name, parent_path=None):
        if parent_path is None:
            parent_path = []
            
        for category_name, category_info in data.items():
            current_path = parent_path + [category_name]
            
            # 检查是否匹配当前分类名称
            if category_name == target_name:
                # 判断层级
                if 'children' in category_info and isinstance(category_info['children'], dict):
                    # 有children且children是字典，说明是l1或l2层级
                    if parent_path == []:
                        level = 'l1'
                    else:
                        level = 'l2'
                    return {
                        'level': level,
                        'category_name': category_name,
                        'category_id': category_info.get('id', ''),
                        'parent_categories': parent_path
                    }
                else:
                    # 没有children或children不是字典，说明是l3层级
                    return {
                        'level': 'l3',
                        'category_name': category_name,
                        'category_id': str(category_info) if isinstance(category_info, (str, int)) else '',
                        'parent_categories': parent_path
                    }
            
            # 如果有children，递归搜索
            if 'children' in category_info and isinstance(category_info['children'], dict):
                result = search_category(category_info['children'], target_name, current_path)
                if result['level'] is not None:
                    return result
        
        return {'level': None, 'category_name': None, 'category_id': None, 'parent_categories': []}
    
    # 执行搜索
    result = search_category(category_data, product_name)
    
    # 如果没找到，返回未找到的信息
    if result['level'] is None:
        result['error'] = f'未找到商品类型: {product_name}'
        return result
    
    # 如果需要返回URL后缀格式
    if return_url_suffix and result['level'] is not None:
        level = result['level']
        category_id = result['category_id']
        result['url_suffix'] = f"&sale_category_{level}={category_id}"
    
    return result
