"""
评测集历史运行用时统计脚本

功能：
1. 遍历两个评测结果目录下的所有批次
2. 从每个 case 的 result.json 中提取 case_id、duration_ms、verdict
3. 按评测集和 case_id 分组，列出每个 case 在不同批次中的用时
4. 输出结构化 JSON 统计报告，包含平均值、最大值、最小值、整体统计

输出文件：d:/AI/rere-agent/_tmp_duration_stats.json
"""

import json
import os
from collections import defaultdict


def collect_batch_results(suite_dir: str) -> list[dict]:
    """
    收集一个评测集目录下所有批次中所有 case 的结果。

    Args:
        suite_dir: 评测集结果目录路径，例如 evals/results/Rollup_Core_20260630/

    Returns:
        包含每个 case 结果的列表，每项格式为：
        {
            "batch": "20260702-013028-rollup_core_20260630",
            "case_id": "alipay_settlement_202605",
            "duration_ms": 187497,
            "verdict": "pass"
        }
    """
    results = []
    if not os.path.isdir(suite_dir):
        return results

    # 遍历评测集目录下的每个批次目录
    for batch_name in sorted(os.listdir(suite_dir)):
        batch_dir = os.path.join(suite_dir, batch_name)
        if not os.path.isdir(batch_dir):
            continue

        cases_dir = os.path.join(batch_dir, "cases")
        if not os.path.isdir(cases_dir):
            continue

        # 遍历批次目录下的每个 case
        for case_id in sorted(os.listdir(cases_dir)):
            case_dir = os.path.join(cases_dir, case_id)
            result_path = os.path.join(case_dir, "result.json")
            if not os.path.isfile(result_path):
                continue

            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                # 跳过无法读取的文件
                print(f"[WARN] 跳过无法读取的文件: {result_path} ({e})")
                continue

            duration_ms = data.get("metrics", {}).get("duration_ms")
            if duration_ms is None:
                continue

            results.append({
                "batch": batch_name,
                "case_id": case_id,
                "duration_ms": duration_ms,
                "verdict": data.get("verdict"),
            })

    return results


def build_stats(all_records: list[dict]) -> dict:
    """
    基于收集到的所有 case 记录，构建按评测集和 case_id 分组的统计报告。

    Args:
        all_records: collect_batch_results 返回的所有记录列表

    Returns:
        结构化的统计报告字典，包含：
        - suites: 按评测集分组的数据
          - batch_count: 批次数
          - cases: 按 case_id 分组的数据
            - runs: 每次运行的批次和用时
            - avg_ms: 平均用时
            - min_ms: 最小用时
            - max_ms: 最大用时
            - duration_change: 首次到最后一次的变化趋势（ms 和 百分比）
          - overall: 评测集整体统计
        - summary: 两个评测集的对比摘要
    """
    # 按 suite 名分组
    suite_map = defaultdict(list)
    for rec in all_records:
        suite_map[rec["suite_name"]].append({
            "batch": rec["batch"],
            "case_id": rec["case_id"],
            "duration_ms": rec["duration_ms"],
            "verdict": rec["verdict"],
        })

    report = {"suites": {}}

    for suite_name, records in suite_map.items():
        # 收集该评测集下所有批次名（去重，保持顺序）
        batches = sorted(set(r["batch"] for r in records))

        # 按 case_id 分组
        case_map = defaultdict(list)
        for r in records:
            case_map[r["case_id"]].append(r)

        cases_stats = {}
        all_durations = []

        for case_id in sorted(case_map.keys()):
            runs = sorted(case_map[case_id], key=lambda x: x["batch"])
            durations = [r["duration_ms"] for r in runs]
            all_durations.extend(durations)

            first_d = durations[0]
            last_d = durations[-1]

            # 计算首次到最后一次的变化
            change_ms = last_d - first_d
            change_pct = round((change_ms / first_d) * 100, 1) if first_d != 0 else None

            cases_stats[case_id] = {
                "runs": [
                    {
                        "batch": r["batch"],
                        "duration_ms": r["duration_ms"],
                        "verdict": r["verdict"],
                    }
                    for r in runs
                ],
                "avg_ms": round(sum(durations) / len(durations), 1),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "min_batch": runs[durations.index(min(durations))]["batch"],
                "max_batch": runs[durations.index(max(durations))]["batch"],
                "duration_change_ms": change_ms,
                "duration_change_pct": change_pct,
            }

        # 评测集整体统计
        overall = {}
        if all_durations:
            overall = {
                "batch_count": len(batches),
                "case_count": len(case_map),
                "total_runs": len(all_durations),
                "avg_ms": round(sum(all_durations) / len(all_durations), 1),
                "min_ms": min(all_durations),
                "max_ms": max(all_durations),
                "median_ms": sorted(all_durations)[len(all_durations) // 2],
                "batches": batches,
            }

        report["suites"][suite_name] = {
            "batches": batches,
            "batch_count": len(batches),
            "cases": cases_stats,
            "overall": overall,
        }

    # 对比摘要
    summaries = []
    for suite_name, suite_data in report["suites"].items():
        o = suite_data["overall"]
        if o:
            summaries.append({
                "suite": suite_name,
                "batch_count": o["batch_count"],
                "case_count": o["case_count"],
                "total_runs": o["total_runs"],
                "avg_ms": o["avg_ms"],
                "min_ms": o["min_ms"],
                "max_ms": o["max_ms"],
                "median_ms": o["median_ms"],
            })

    report["summary"] = summaries

    return report


def main():
    """主入口：收集数据并输出统计报告到 JSON 文件。"""
    base_dir = r"d:\AI\rere-agent\evals\results"

    # 定义要统计的两个评测集目录
    suites = [
        ("Rollup_Core_20260630", os.path.join(base_dir, "Rollup_Core_20260630")),
        ("Rollup_Core_Large_20260704", os.path.join(base_dir, "Rollup_Core_Large_20260704")),
    ]

    all_records = []

    for suite_name, suite_dir in suites:
        print(f"[INFO] 正在扫描评测集: {suite_name}")
        if not os.path.isdir(suite_dir):
            print(f"[WARN] 目录不存在，跳过: {suite_dir}")
            continue

        batch_results = collect_batch_results(suite_dir)
        print(f"  找到 {len(batch_results)} 条 case 记录")

        for rec in batch_results:
            rec["suite_name"] = suite_name
            all_records.append(rec)

    print(f"\n[INFO] 共收集 {len(all_records)} 条记录")

    report = build_stats(all_records)

    output_path = r"d:\AI\rere-agent\_tmp_duration_stats.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[INFO] 报告已写入: {output_path}")


if __name__ == "__main__":
    main()
