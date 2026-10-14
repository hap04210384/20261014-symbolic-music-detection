# 论文数字溯源表（paper number lineage）

规则：终稿每个图表数字必须能指到 {脚本, 结果文件, commit, 语料状态}。
本表对应语料状态：**Lakh `roszcz/lakh-lmd-full` 55/55 分片全部下载并编码，
共 174,300 曲**（2026-10-12 晚完成）；困难负例/确认/级联/记忆化/判例实验
用分片 0 前 3000 曲（与 E1/E5 同源，固定 seed）。日期均为 2026-10-12。

| 论文位置 | 数字 | 脚本 → 结果 | commit |
|---|---|---|---|
| 图2 规模曲线 | **174,300 曲（全语料）建索引 24.75s、内存 1053MB；查询 p50 41.9ms / p95 123.5ms；planted 召回 47/47**；100,000 曲：16.71s / 615MB / 23.1ms / 44/44；Jaccard 基线在 10,000 曲 p50 238ms（≈20× 慢于本系统 12ms），之上不可行 | `tools/e4_scaling.py` → `runs/e4/scaling.jsonl` | `cd1cd5c`（新增行在 `dac551b` 模板轮之后写入） |
| 主表 E1 | 337 格召回 99.1%（334/337；失败格全在保证边界外） | `tools/e1_matrix.py` → `runs/e1/matrix.jsonl` | `ea05d04` |
| 图4 E2 | 理论下界 337 格 0 违例；保证内命中 100% | `tools/e2_bounds.py` → `runs/e2/bounds.jsonl` | `ea05d04` |
| 图3 E3 | 50% 预算时候选数 rare/random/hot = 7.9/16.4/128.6（16× 洁净）；60/60 供体 100% 预算找回；界恒有效 | `tools/e3_anytime.py` → `runs/e3/anytime.jsonl` | `5edce32` |
| 消融 E5 | L×1.5：FP 21.5k→12.1k、召回恒定 100%；k 扫描 (0,0,0)→(2,1,1) 召回 23/29→29/29、FP 338→18.9k；网格 250/125/62ms 召回全 100% | `tools/e5_ablation.py` → `runs/e5/ablation.jsonl` | `d8345ca` |
| E1.3 发现 | tolerant 层：frag-FP 93.3%、供体 top-20 37%；verbatim 层：top-20 93.7%、margin p50 45、frag-FP 22%（236 片段，风格最相似 20 曲为负例池） | `tools/e13_hard_negatives.py` → `runs/e13/v2_screening.jsonl` | `382570d` |
| 主表 E1.4 | 严容差 (1,0,0)：ρ=0.5 → FP 2.1%、召回 83.9%；ρ=0.4 → FP 7.2%、召回 98.3%（验收 <5% 达标） | `tools/e14_structural_confirm.py` → `runs/e14/confirm.jsonl` | `f762811` |
| 图5 E7 | 单层筛查 FP 92.7%（@0.5\|q\|）；单层排序 τ=30：R 82.0/FP 1.3；级联 C=50：ρ=0.4 → R 95.7/FP 8.2，ρ=0.5 → R 80.7/FP 2.6；候选保留率 C=5/10/20/50 = 84.1/87.1/93.1/96.6% | `tools/e17_cascade.py` → `runs/e17/cascade.jsonl` | `eb084af` |
| 图6 E6.2 | 记忆化光谱检出率：λ=0 → 26–34%（多为风格级共享、非源曲，源曲归属 2–4%）；λ=0.5 → 44–56%（源曲 18–38%）；λ=0.75 → 96–100%（源曲 90–96%）；λ=1 → 100%（源曲 96–100%）；延迟 240ms/首 | `tools/e62_memorization.py` → `runs/e62/memorization.jsonl` | `34fd9a6` |
| Case E6.3 | 全库发现 1,658,993 候选重复对（精确+音程草图双索引）；判例：identical 3200/3200 对齐；+3st 转调全恢复且偏移估计正确（−3）；30s 拼接段定位（段长 1593）；风格相似负例正确拒绝（段长 1） | `tools/e63_cases.py` → `runs/e63/cases.jsonl` | `8e4b346` |

## 复现

```bash
bash scripts/run_all.sh        # 全部（增量，可反复跑）
bash scripts/run_all.sh e14    # 单实验
```

注意：G1 下载受 hf-mirror 线路影响，`download_all_shards.py` 退出码 2 =
仍有分片待取，需反复运行直至 55/55；之后 `build_corpus.py` 自动编码新分片。
困难负例类实验（E1.3/E1.4/E7）语料为分片 0 前 3000 曲（`e13.CORPUS_PIECES`）。

## 已知边界（写进 Discussion）

- E4 的 50,000 点首次测量 20s 为 tracemalloc 噪声，复测 4.1–6.8s，论文取复测均值。
- E6.2 λ=0 的残余检出是流行音乐共享长有序结构所致（与 E1.3 发现一致），
  系统输出的是候选+证据，最终裁决在人。
- 碎片化部分记忆（λ=0.25 逐音符随机复制）低于连续性阈值时逃逸——
  保序链确认层的诚实边界。
- E6.3 的转调/拼接判例由真实在库重复对合成（`synthesized_from_real_pair`
  标记），因分片 0 的自然重复几乎全是同调同编曲转录。
