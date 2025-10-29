#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度跟踪器 - 实时更新测试进度
用于后台运行时的进度监控
"""

import json
import os
from datetime import datetime
from pathlib import Path


class ProgressTracker:
    """进度跟踪器类"""
    
    def __init__(self, input_filename: str, total_cases: int):
        """
        初始化进度跟踪器
        
        Args:
            input_filename: 输入文件名（用于生成进度文件名）
            total_cases: 总测试用例数
        """
        self.total_cases = total_cases
        self.completed = 0
        self.current_index = 0
        self.current_stage = "初始化"
        self.start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.status = "running"
        
        # 获取最新的进度文件
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 查找最新的进度文件
        progress_files = sorted(log_dir.glob("progress_*.txt"), reverse=True)
        if progress_files:
            self.progress_file = progress_files[0]
        else:
            # 如果没有，创建一个新的
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.progress_file = log_dir / f"progress_{timestamp}.txt"
        
        self.update()
    
    def update(self, **kwargs):
        """
        更新进度信息
        
        Args:
            **kwargs: 要更新的字段（completed, current_index, current_stage, status等）
        """
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # 写入进度文件
        progress_data = {
            "total": self.total_cases,
            "completed": self.completed,
            "current_index": self.current_index,
            "current_stage": self.current_stage,
            "start_time": self.start_time,
            "status": self.status
        }
        
        # 如果已完成，添加结束时间
        if self.status == "completed":
            progress_data["end_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 写入文件
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 更新进度文件失败: {e}")
    
    def update_case(self, index: int, stage: str):
        """
        更新当前处理的测试用例
        
        Args:
            index: 测试用例索引
            stage: 当前阶段（如 "翻译中", "变异中", "完成"）
        """
        self.current_index = index
        self.current_stage = stage
        if stage == "完成":
            self.completed += 1
        self.update()
    
    def complete(self):
        """标记测试完成"""
        self.status = "completed"
        self.completed = self.total_cases
        self.current_stage = "全部完成"
        self.update()
    
    def error(self, error_msg: str):
        """标记测试出错"""
        self.status = "error"
        self.current_stage = f"错误: {error_msg}"
        self.update()


# 全局进度跟踪器实例
_global_tracker = None


def init_progress_tracker(input_filename: str, total_cases: int):
    """初始化全局进度跟踪器"""
    global _global_tracker
    _global_tracker = ProgressTracker(input_filename, total_cases)
    return _global_tracker


def get_progress_tracker():
    """获取全局进度跟踪器"""
    return _global_tracker


def update_progress(**kwargs):
    """更新进度（快捷方法）"""
    if _global_tracker:
        _global_tracker.update(**kwargs)


def update_case(index: int, stage: str):
    """更新当前处理的测试用例（快捷方法）"""
    if _global_tracker:
        _global_tracker.update_case(index, stage)


def complete_progress():
    """标记测试完成（快捷方法）"""
    if _global_tracker:
        _global_tracker.complete()


def error_progress(error_msg: str):
    """标记测试出错（快捷方法）"""
    if _global_tracker:
        _global_tracker.error(error_msg)

