#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比分析 Mutation 阶段使用 Mem0 前后的效果
"""
import json
import os
from pathlib import Path

def load_jsonl(file_path):
    """加载 JSONL 文件"""
    records = []
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    return records

def analyze_directory(dir_path, label):
    """分析一个输出目录"""
    print(f"\n{'='*80}")
    print(f"📁 分析目录: {label}")
    print(f"   路径: {dir_path}")
    print(f"{'='*80}")
    
    transfer_dir = os.path.join(dir_path, "TransferLLM")
    mutation_dir = os.path.join(dir_path, "MutationLLM")
    
    # 统计数据
    stats = {
        'total_files': 0,
        'total_transfer_records': 0,
        'total_mutation_records': 0,
        'transfer_success': 0,
        'transfer_failed': 0,
        'mutation_with_data': 0,
        'oracle_passed': 0,
        'oracle_failed': 0,
        'bugs_found': 0,
        'total_transfer_cost': 0.0,
        'total_mutation_cost': 0.0,
        'total_transfer_time': 0.0,
        'total_mutation_time': 0.0,
        'total_transfer_tokens': 0,
        'total_mutation_tokens': 0,
        'mutation_counts': [],
        'prompt_token_growth': []
    }
    
    # 读取所有文件
    if os.path.exists(transfer_dir):
        files = sorted([f for f in os.listdir(transfer_dir) if f.endswith('.jsonl')])
        stats['total_files'] = len(files)
        
        for file in files:
            transfer_records = load_jsonl(os.path.join(transfer_dir, file))
            stats['total_transfer_records'] += len(transfer_records)
            
            for record in transfer_records:
                # Transfer 统计
                if record.get('TransferSqlExecError', [''])[0] == 'None':
                    stats['transfer_success'] += 1
                else:
                    stats['transfer_failed'] += 1
                
                if record.get('TransferCost'):
                    cost_data = record['TransferCost'][0]
                    stats['total_transfer_cost'] += cost_data.get('Total Cost (USD)', 0)
                    stats['total_transfer_tokens'] += cost_data.get('Total Tokens', 0)
                    stats['prompt_token_growth'].append(cost_data.get('Prompt Tokens', 0))
                
                stats['total_transfer_time'] += record.get('TransferTimeCost', 0)
    
    if os.path.exists(mutation_dir):
        files = sorted([f for f in os.listdir(mutation_dir) if f.endswith('.jsonl')])
        
        for file in files:
            mutation_records = load_jsonl(os.path.join(mutation_dir, file))
            stats['total_mutation_records'] += len(mutation_records)
            
            for record in mutation_records:
                # Mutation 统计
                if record.get('MutateResult'):
                    stats['mutation_with_data'] += 1
                    try:
                        mutate_data = json.loads(record['MutateResult'])
                        mutations = mutate_data.get('mutations', [])
                        stats['mutation_counts'].append(len(mutations))
                    except:
                        pass
                
                if record.get('MutateCost'):
                    cost_data = record['MutateCost']
                    stats['total_mutation_cost'] += cost_data.get('Total Cost (USD)', 0)
                    stats['total_mutation_tokens'] += cost_data.get('Total Tokens', 0)
                
                stats['total_mutation_time'] += record.get('MutateTimeCost', 0)
                
                # Oracle 统计
                oracle = record.get('OracleCheck')
                if oracle:
                    if oracle.get('end') and not oracle.get('error'):
                        stats['oracle_passed'] += 1
                    elif oracle.get('error'):
                        stats['oracle_failed'] += 1
                    if oracle.get('bug_type'):
                        stats['bugs_found'] += 1
    
    return stats

def print_stats(stats, label):
    """打印统计结果"""
    print(f"\n📊 {label} - 统计结果:")
    print(f"  文件数量: {stats['total_files']}")
    print(f"  翻译记录数: {stats['total_transfer_records']}")
    print(f"  变异记录数: {stats['total_mutation_records']}")
    
    print(f"\n✅ 翻译成功率:")
    total = stats['total_transfer_records']
    if total > 0:
        success_rate = stats['transfer_success'] / total * 100
        print(f"  成功: {stats['transfer_success']}/{total} ({success_rate:.1f}%)")
        print(f"  失败: {stats['transfer_failed']}/{total} ({(100-success_rate):.1f}%)")
    
    print(f"\n🧬 变异覆盖率:")
    if stats['total_mutation_records'] > 0:
        mutation_rate = stats['mutation_with_data'] / stats['total_mutation_records'] * 100
        print(f"  含变异数据: {stats['mutation_with_data']}/{stats['total_mutation_records']} ({mutation_rate:.1f}%)")
        
        if stats['mutation_counts']:
            avg_mutations = sum(stats['mutation_counts']) / len(stats['mutation_counts'])
            print(f"  平均变异数量: {avg_mutations:.1f}")
    
    print(f"\n🔍 Oracle 检查:")
    print(f"  通过: {stats['oracle_passed']}")
    print(f"  失败: {stats['oracle_failed']}")
    print(f"  发现 Bug: {stats['bugs_found']}")
    
    print(f"\n💰 成本统计:")
    print(f"  翻译总成本: ${stats['total_transfer_cost']:.6f}")
    print(f"  变异总成本: ${stats['total_mutation_cost']:.6f}")
    print(f"  总成本: ${stats['total_transfer_cost'] + stats['total_mutation_cost']:.6f}")
    if stats['total_transfer_records'] > 0:
        avg_cost = (stats['total_transfer_cost'] + stats['total_mutation_cost']) / stats['total_transfer_records']
        print(f"  平均成本/条: ${avg_cost:.6f}")
    
    print(f"\n⏱️  时间统计:")
    print(f"  翻译总耗时: {stats['total_transfer_time']:.2f}秒")
    print(f"  变异总耗时: {stats['total_mutation_time']:.2f}秒")
    print(f"  总耗时: {stats['total_transfer_time'] + stats['total_mutation_time']:.2f}秒")
    if stats['total_transfer_records'] > 0:
        avg_time = (stats['total_transfer_time'] + stats['total_mutation_time']) / stats['total_transfer_records']
        print(f"  平均耗时/条: {avg_time:.2f}秒")
    
    print(f"\n🪙 Token 统计:")
    print(f"  翻译总 Tokens: {stats['total_transfer_tokens']}")
    print(f"  变异总 Tokens: {stats['total_mutation_tokens']}")
    print(f"  总 Tokens: {stats['total_transfer_tokens'] + stats['total_mutation_tokens']}")
    
    if stats['prompt_token_growth']:
        print(f"\n📈 Mem0 知识积累 (Prompt Tokens 趋势):")
        print(f"  起始: {stats['prompt_token_growth'][0]}")
        print(f"  结束: {stats['prompt_token_growth'][-1]}")
        growth = stats['prompt_token_growth'][-1] - stats['prompt_token_growth'][0]
        if stats['prompt_token_growth'][0] > 0:
            growth_pct = growth / stats['prompt_token_growth'][0] * 100
            print(f"  增长: {growth:+d} tokens ({growth_pct:+.1f}%)")

def compare_stats(stats1, stats2, label1, label2):
    """对比两个统计结果"""
    print(f"\n{'='*80}")
    print(f"🔄 对比分析: {label1} vs {label2}")
    print(f"{'='*80}")
    
    # 翻译成功率对比
    rate1 = stats1['transfer_success'] / max(1, stats1['total_transfer_records']) * 100
    rate2 = stats2['transfer_success'] / max(1, stats2['total_transfer_records']) * 100
    diff = rate2 - rate1
    print(f"\n✅ 翻译成功率:")
    print(f"  {label1}: {rate1:.1f}%")
    print(f"  {label2}: {rate2:.1f}%")
    print(f"  差异: {diff:+.1f}% {'📈' if diff > 0 else '📉' if diff < 0 else '➡️'}")
    
    # 变异覆盖率对比
    mut1 = stats1['mutation_with_data'] / max(1, stats1['total_mutation_records']) * 100
    mut2 = stats2['mutation_with_data'] / max(1, stats2['total_mutation_records']) * 100
    diff_mut = mut2 - mut1
    print(f"\n🧬 变异覆盖率:")
    print(f"  {label1}: {mut1:.1f}%")
    print(f"  {label2}: {mut2:.1f}%")
    print(f"  差异: {diff_mut:+.1f}% {'📈' if diff_mut > 0 else '📉' if diff_mut < 0 else '➡️'}")
    
    # Oracle 通过率对比
    oracle1 = stats1['oracle_passed'] / max(1, stats1['oracle_passed'] + stats1['oracle_failed']) * 100
    oracle2 = stats2['oracle_passed'] / max(1, stats2['oracle_passed'] + stats2['oracle_failed']) * 100
    diff_oracle = oracle2 - oracle1
    print(f"\n🔍 Oracle 通过率:")
    print(f"  {label1}: {oracle1:.1f}% ({stats1['oracle_passed']}/{stats1['oracle_passed']+stats1['oracle_failed']})")
    print(f"  {label2}: {oracle2:.1f}% ({stats2['oracle_passed']}/{stats2['oracle_passed']+stats2['oracle_failed']})")
    print(f"  差异: {diff_oracle:+.1f}% {'📈' if diff_oracle > 0 else '📉' if diff_oracle < 0 else '➡️'}")
    
    # 成本对比
    total_cost1 = stats1['total_transfer_cost'] + stats1['total_mutation_cost']
    total_cost2 = stats2['total_transfer_cost'] + stats2['total_mutation_cost']
    avg_cost1 = total_cost1 / max(1, stats1['total_transfer_records'])
    avg_cost2 = total_cost2 / max(1, stats2['total_transfer_records'])
    diff_cost = avg_cost2 - avg_cost1
    print(f"\n💰 平均成本/条:")
    print(f"  {label1}: ${avg_cost1:.6f}")
    print(f"  {label2}: ${avg_cost2:.6f}")
    print(f"  差异: ${diff_cost:+.6f} {'📈' if diff_cost > 0 else '📉' if diff_cost < 0 else '➡️'}")
    
    # 时间对比
    total_time1 = stats1['total_transfer_time'] + stats1['total_mutation_time']
    total_time2 = stats2['total_transfer_time'] + stats2['total_mutation_time']
    avg_time1 = total_time1 / max(1, stats1['total_transfer_records'])
    avg_time2 = total_time2 / max(1, stats2['total_transfer_records'])
    diff_time = avg_time2 - avg_time1
    print(f"\n⏱️  平均耗时/条:")
    print(f"  {label1}: {avg_time1:.2f}秒")
    print(f"  {label2}: {avg_time2:.2f}秒")
    print(f"  差异: {diff_time:+.2f}秒 {'📈' if diff_time > 0 else '📉' if diff_time < 0 else '➡️'}")
    
    # Mem0 知识积累对比
    if stats1['prompt_token_growth'] and stats2['prompt_token_growth']:
        growth1 = stats1['prompt_token_growth'][-1] - stats1['prompt_token_growth'][0]
        growth2 = stats2['prompt_token_growth'][-1] - stats2['prompt_token_growth'][0]
        print(f"\n📈 Mem0 知识积累 (Prompt Tokens 增长):")
        print(f"  {label1}: {growth1:+d} tokens")
        print(f"  {label2}: {growth2:+d} tokens")
        print(f"  差异: {growth2-growth1:+d} tokens")
    
    # Bug 发现数对比
    print(f"\n🐛 Bug 发现数:")
    print(f"  {label1}: {stats1['bugs_found']}")
    print(f"  {label2}: {stats2['bugs_found']}")
    print(f"  差异: {stats2['bugs_found'] - stats1['bugs_found']:+d}")

def main():
    print("="*80)
    print("🔬 Mem0 在 Mutation 阶段的效果对比分析")
    print("="*80)
    
    # 分析两个目录
    dir1 = "Output/queue_test_mem0_transfer"
    dir2 = "Output/queue_test_mem0_transfer_mutate"
    
    label1 = "仅 Transfer 使用 Mem0"
    label2 = "Transfer + Mutation 都使用 Mem0"
    
    stats1 = analyze_directory(dir1, label1)
    print_stats(stats1, label1)
    
    stats2 = analyze_directory(dir2, label2)
    print_stats(stats2, label2)
    
    # 对比分析
    compare_stats(stats1, stats2, label1, label2)
    
    # 总结
    print(f"\n{'='*80}")
    print("📝 总结与建议")
    print(f"{'='*80}")
    
    # 计算改进指标
    improvements = []
    regressions = []
    
    # 翻译成功率
    rate1 = stats1['transfer_success'] / max(1, stats1['total_transfer_records']) * 100
    rate2 = stats2['transfer_success'] / max(1, stats2['total_transfer_records']) * 100
    if rate2 > rate1:
        improvements.append(f"翻译成功率提升 {rate2-rate1:.1f}%")
    elif rate2 < rate1:
        regressions.append(f"翻译成功率下降 {rate1-rate2:.1f}%")
    
    # 变异覆盖率
    mut1 = stats1['mutation_with_data'] / max(1, stats1['total_mutation_records']) * 100
    mut2 = stats2['mutation_with_data'] / max(1, stats2['total_mutation_records']) * 100
    if mut2 > mut1:
        improvements.append(f"变异覆盖率提升 {mut2-mut1:.1f}%")
    elif mut2 < mut1:
        regressions.append(f"变异覆盖率下降 {mut1-mut2:.1f}%")
    
    # Oracle 通过率
    oracle1 = stats1['oracle_passed'] / max(1, stats1['oracle_passed'] + stats1['oracle_failed']) * 100
    oracle2 = stats2['oracle_passed'] / max(1, stats2['oracle_passed'] + stats2['oracle_failed']) * 100
    if oracle2 > oracle1:
        improvements.append(f"Oracle 通过率提升 {oracle2-oracle1:.1f}%")
    elif oracle2 < oracle1:
        regressions.append(f"Oracle 通过率下降 {oracle1-oracle2:.1f}%")
    
    # Bug 发现数
    if stats2['bugs_found'] > stats1['bugs_found']:
        improvements.append(f"发现了 {stats2['bugs_found'] - stats1['bugs_found']} 个额外的 Bug")
    
    print(f"\n✅ 改进项:")
    if improvements:
        for item in improvements:
            print(f"  • {item}")
    else:
        print(f"  • 无明显改进")
    
    print(f"\n⚠️  退化项:")
    if regressions:
        for item in regressions:
            print(f"  • {item}")
    else:
        print(f"  • 无明显退化")
    
    # 最终评价
    print(f"\n🏆 最终评价:")
    if len(improvements) > len(regressions):
        print(f"  ✅ 在 Mutation 阶段使用 Mem0 带来了显著改进！")
        print(f"  💡 建议: 继续在生产环境中使用 Mem0 集成方案。")
    elif len(improvements) < len(regressions):
        print(f"  ⚠️  在 Mutation 阶段使用 Mem0 效果不佳。")
        print(f"  💡 建议: 检查 Mutation Mem0 配置和 Prompt 设计。")
    else:
        print(f"  ➡️  在 Mutation 阶段使用 Mem0 效果持平。")
        print(f"  💡 建议: 评估成本效益，决定是否启用。")
    
    print("="*80)

if __name__ == "__main__":
    main()

