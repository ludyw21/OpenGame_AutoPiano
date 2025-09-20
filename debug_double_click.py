#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试双击加载功能
"""
import tkinter as tk
from tkinter import ttk
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

try:
    from app import MeowFieldAutoPiano
    print("✅ MeowFieldAutoPiano 导入成功")
except Exception as e:
    print(f"❌ MeowFieldAutoPiano 导入失败: {e}")
    sys.exit(1)

def test_double_click():
    """测试双击加载功能"""
    print("\n🔍 开始调试双击加载功能...")
    
    # 创建应用程序实例
    app = MeowFieldAutoPiano()
    
    # 检查关键组件
    print(f"✅ playlist_tree 存在: {hasattr(app, 'playlist_tree')}")
    print(f"✅ _file_paths 存在: {hasattr(app, '_file_paths')}")
    print(f"✅ _on_playlist_double_click 存在: {hasattr(app, '_on_playlist_double_click')}")
    print(f"✅ _load_selected_playlist_item_to_main 存在: {hasattr(app, '_load_selected_playlist_item_to_main')}")
    
    if hasattr(app, 'playlist_tree'):
        tree = app.playlist_tree
        print(f"✅ 演奏列表树控件类型: {type(tree)}")
        
        # 检查双击事件绑定
        bindings = tree.bind('<Double-1>')
        print(f"✅ 双击事件绑定: {bindings}")
        
        # 检查演奏列表内容
        children = tree.get_children()
        print(f"✅ 演奏列表项数量: {len(children)}")
        
        if children:
            for i, child in enumerate(children[:3]):  # 只显示前3项
                item = tree.item(child)
                print(f"  [{i+1}] ID: {child}, Values: {item['values']}")
                
                # 检查文件路径字典
                if hasattr(app, '_file_paths'):
                    file_path = app._file_paths.get(child)
                    print(f"      文件路径: {file_path}")
        
        # 检查当前页面
        print(f"✅ current_page 存在: {hasattr(app, 'current_page')}")
        if hasattr(app, 'current_page'):
            current_page = app.current_page
            print(f"✅ current_page 类型: {type(current_page)}")
            if current_page:
                print(f"✅ _load_midi_from_playlist 方法存在: {hasattr(current_page, '_load_midi_from_playlist')}")
    
    # 测试双击加载方法
    print(f"\n🔍 测试双击加载方法...")
    try:
        # 模拟选择第一个项目
        if hasattr(app, 'playlist_tree') and app.playlist_tree.get_children():
            first_item = app.playlist_tree.get_children()[0]
            app.playlist_tree.selection_set(first_item)
            print(f"✅ 已选择项目: {first_item}")
            
            # 调用双击加载方法
            app._load_selected_playlist_item_to_main()
            print("✅ 双击加载方法调用成功")
        else:
            print("❌ 没有演奏列表项可供测试")
            
    except Exception as e:
        print(f"❌ 双击加载方法调用失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 关闭应用程序
    app.root.destroy()

if __name__ == "__main__":
    test_double_click()
