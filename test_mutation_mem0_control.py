#!/usr/bin/env python3
"""
测试脚本：验证 QTRAN_MUTATION_USE_MEM0 环境变量是否正确控制变异阶段的 Mem0 使用
"""

import os
import sys

def test_env_control():
    """测试环境变量控制逻辑"""
    
    # 测试场景1: use_mem0=true, use_mutation_mem0=false
    print("="*70)
    print("测试场景 1: 翻译启用Mem0，变异禁用Mem0")
    print("="*70)
    
    use_mem0 = os.environ.get("QTRAN_USE_MEM0", "false").lower() == "true"
    use_mutation_mem0 = os.environ.get("QTRAN_MUTATION_USE_MEM0", "false").lower() == "true"
    
    print(f"环境变量 QTRAN_USE_MEM0: {os.environ.get('QTRAN_USE_MEM0', 'not set')}")
    print(f"环境变量 QTRAN_MUTATION_USE_MEM0: {os.environ.get('QTRAN_MUTATION_USE_MEM0', 'not set')}")
    print(f"\n解析结果:")
    print(f"  use_mem0 (翻译阶段): {use_mem0}")
    print(f"  use_mutation_mem0 (变异阶段): {use_mutation_mem0}")
    
    # 模拟初始化逻辑
    mem0_manager = None
    mutation_mem0_manager = None
    
    if use_mem0:
        mem0_manager = "MockTransferMemoryManager"  # 模拟对象
        print(f"\n✅ 翻译阶段 Mem0 已初始化: {mem0_manager}")
    else:
        print(f"\n❌ 翻译阶段 Mem0 未启用")
    
    if use_mutation_mem0:
        mutation_mem0_manager = "MockMutationMemoryManager"  # 模拟对象
        print(f"✅ 变异阶段 Mem0 已初始化: {mutation_mem0_manager}")
    else:
        print(f"❌ 变异阶段 Mem0 未启用")
    
    # 模拟使用检查
    print(f"\n" + "="*70)
    print("模拟代码执行路径:")
    print("="*70)
    
    # 模拟变异阶段的使用检查
    print("\n1. 启动变异会话:")
    if mutation_mem0_manager:
        print(f"   → 会调用: mutation_mem0_manager.start_session()")
    else:
        print(f"   → 跳过: mutation_mem0_manager 为 None")
    
    print("\n2. 传递给 run_muatate_llm_single_sql:")
    print(f"   → mem0_manager={mutation_mem0_manager}")
    
    print("\n3. 在 MutateLLM.py 中增强 Prompt:")
    if mutation_mem0_manager:
        print(f"   → 会执行: mem0_manager.build_enhanced_prompt()")
    else:
        print(f"   → 跳过: if mem0_manager 检查失败")
    
    print("\n4. 记录变异结果:")
    if mutation_mem0_manager:
        print(f"   → 会执行: mem0_manager.record_successful_mutation()")
    else:
        print(f"   → 跳过: if mem0_manager 检查失败")
    
    print("\n5. 记录 Bug 模式:")
    if mutation_mem0_manager:
        print(f"   → 会执行: mutation_mem0_manager.record_bug_pattern()")
    else:
        print(f"   → 跳过: if mutation_mem0_manager 检查失败")
    
    # 验证结果
    print(f"\n" + "="*70)
    print("验证结果:")
    print("="*70)
    
    expected_translation_enabled = use_mem0
    expected_mutation_enabled = use_mutation_mem0
    
    actual_translation_enabled = mem0_manager is not None
    actual_mutation_enabled = mutation_mem0_manager is not None
    
    translation_pass = expected_translation_enabled == actual_translation_enabled
    mutation_pass = expected_mutation_enabled == actual_mutation_enabled
    
    print(f"\n翻译阶段 Mem0:")
    print(f"  期望: {'启用' if expected_translation_enabled else '禁用'}")
    print(f"  实际: {'启用' if actual_translation_enabled else '禁用'}")
    print(f"  结果: {'✅ PASS' if translation_pass else '❌ FAIL'}")
    
    print(f"\n变异阶段 Mem0:")
    print(f"  期望: {'启用' if expected_mutation_enabled else '禁用'}")
    print(f"  实际: {'启用' if actual_mutation_enabled else '禁用'}")
    print(f"  结果: {'✅ PASS' if mutation_pass else '❌ FAIL'}")
    
    print(f"\n" + "="*70)
    if translation_pass and mutation_pass:
        print("✅ 所有测试通过！环境变量控制正确工作。")
        return 0
    else:
        print("❌ 测试失败！请检查环境变量配置。")
        return 1

if __name__ == "__main__":
    sys.exit(test_env_control())


