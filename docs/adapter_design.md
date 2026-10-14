# 适配层设计（Adapter Design）v1.0

**日期：2026-10-11　状态：引擎接口已实测确认，适配层实现以此为准**
约束：AnyFIM / TensorFIM 两上游仓库支撑在投论文，**审稿期间一律只读**；
一切适配、优化（含 G3.5 稠密重映射）只发生在本文档定义的适配层。

---

## 1. 引擎清单与调用协议（2026-10-11 逐字读码确认）

| 引擎 | exe 路径（相对 `src/`） | argv 协议 | 输出文件（相对 CWD） | 稠密 ID |
|---|---|---|---|---|
| TensorFIM bitmap（baseline 内核） | `engine_tensorfim/code/engine/run/CoParaCG_baseline.exe` | `<dataset> <support>` | `<dataset>-<support>=Results.txt` | **内核内置**（`buildBitmap()` 内 origToDense 重映射，输出经 `denseToOrig` 反映射） |
| TensorFIM BMMA（wave 引擎） | `engine_tensorfim/code/engine/run/CoParaCG_bmma.exe` | 同上（`RUN_MODE=1` 且 `BMMA_ENGINE=1` → `runWaveEngine()` 批量波） | 同上 | 内置，同上 |
| AnyFIM GivenThreshold | `engine_anyfim/code/AnyFIM-GivenThreshold/x64/Release/CoParaCG.exe` | `<RUN_MODE> <CPU_CORES> <dataset> <support>`（`main(argc,argv)` 支持运行时覆盖，**exe 冒烟待验**） | 同 TensorFIM 命名 | **无** → G3.5 由适配层补 |
| AnyFIM Anytime | `engine_anyfim/code/AnyFIM-Anytime/x64/Release/AnytimeMining.exe` | **无 argv**（编译期硬编码 `..\TransactionSets\accidents.txt`、`UptoStage=20`） | `<transSetFile>-20-stages=Results.txt` | **无** → G3.5 由适配层补 |

### 已确认的引擎行为（读码事实，非推测）

- 输入格式：FIMI 事务集，每行一串非负整数项 ID。
- AnyFIM anytime 主循环（`kernel.cu` main）：第 `Step` 阶段阈值 = `freqPerItem_inSort[Step-1]`
  （即第 Step 高频项的频度），逐阶段把 MFIs 写入 `MFIsPool[Step]`；
  **结果文件含每个阶段的全部 MFI 及其频度、每阶段运行时间**——E3 的 anytime 曲线
  由单次运行的事后重构获得，无需引擎支持中途停止。
- AnyFIM anytime 的 `reduceTransSet` 用 `freqPerItem_inSort[UptoStage]`（第 UptoStage+1 名
  的频度）作为幸存下界；`buildBitmap()` 按 `(itemIDmax+1) × bitmapWords` 开行（**稀疏 ID 空间，
  这正是 G3.5 的优化点**）。
- TensorFIM 两内核 `buildBitmap()` 均已在引擎内做稠密化（行数 = 幸存项数），其 gold 校验纪律
  （`scripts/run_all_configs.py`：输出 MFI 集合与 `data/gold_results/` 逐集合比对）沿用为
  G3.5 等价性验收的模板。

### 运行环境

- GPU：NVIDIA GeForce RTX 3060 Ti（Ampere，sm_86，含 Tensor Core）。
  `nvidia-smi` 报 NVML 初始化失败（驱动/虚拟化层问题，不影响 CUDA runtime）；
  以实际跑通为准，`engine_tensorfim/portable/prebuilt/smcheck.exe` 可作算力自检。

### 引擎地雷（2026-10-11 实测，`runs/G3.4/debug_item0`）

**项 ID 0 被两台引擎各自"特殊对待"，且行为不一致**：
AnyFIM 静默丢弃项 0（{0,1,2} 只输出 {1,2}）；TensorFIM 会把含 0 的非极大对
当 MFI 输出（{0,1},{0,2} 而非 {0,1,2}）。
**适配层规则：项 ID 0 保留不用**，`write_fimi` 拒绝 0 及负数，
`dense_remap` 的稠密 ID 从 1 开始编。MIDI 编码层同样不得产生项 0。

### 引擎语义发现（2026-10-11，门禁 4 深挖，`runs/G3.4/gate4`）

**输出 MFI 集合依赖于项 ID 的数值顺序**（little-endian 扩展只加比当前根更小 ID 的项 +
根 = 频度**严格大于**阈值 `transNum×support` 的项）。后果：
- 同一数据、两种 ID 编排，输出可以不同——边界情形 = 某个频繁集的"id 最大元"频度恰好
  == 阈值时，该集只在"最大元是严格频繁项"的编排下被输出。
- **适配层任何重映射必须保持原始 ID 的相对顺序**（见 §3），否则行为等价性不成立。
- 对论文理论部分的意义：引擎"可证明召回"的完备性陈述必须以引擎的操作语义为准
  （固定编码 + 顺序保持），不能套用教科书 MFI 定义；已在
  `docs/paper_number_lineage.md` 登记为理论部分待写条目。

### Anytime exe 的调用技巧（不改动上游）

exe 硬编码相对路径 `..\TransactionSets\accidents.txt`，约定：

```
runs/<exp>/<cfg>/bin/AnytimeMining.exe        ← 从上游复制 exe（复制≠改动）
runs/<exp>/<cfg>/TransactionSets/accidents.txt ← 我们生成的 FIMI 数据用此文件名
CWD = runs/<exp>/<cfg>/bin
```

结果文件落在 `runs/<exp>/<cfg>/TransactionSets/accidents.txt-20-stages=Results.txt`。

---

## 2. 检测范式：查询即事务，命中即 MFI

**状态：v2.0（2026-10-12 作者拍板选 A 方案）——§2.1 协议实测不可行，替换为 §2.2。**

### 2.1 （废弃，留档）σ=2/(N+1) 全库挖掘协议

1. **编码**：MIDI → 事件集（onset, pitch, duration, channel），网格量化
   （粒度由 E5.7 扫描决定，默认初值见 §5）→ 每个量化事件编码为一个项 ID
   （复合编码 `id = (((onset_g × P) + pitch) × D + dur_g) × C + channel` 的分桶版本，
   具体分桶函数在适配层实现并登记）。
2. **事务集**：查询片段 Q → 1 个事务；语料每首曲子 → 1 个事务；共 N+1 行 FIMI 文件。
3. **挖掘**：支持度阈值 σ = 2/(N+1)（命中 = 项集至少同时出现在 Q 与一首库曲中）。
   anytime 模式不设 σ，按阶段频度阈值跑满 UptoStage=20 档，事后按时间轴取各阶段并集。
4. **命中判定与定位**：MFI 项集 S 若 ⊆ Q 且 ⊆ 某库曲事务，则记一次命中；
   项的 onset 分量反映射回区间 → 查询端/库端片段定位（span）。
5. **容噪**（E5.5 的 k-容噪）在编码层实现：查询端事件带容噪键（如音高 ±k 桶并集），
   引擎本身无感。

**废弃原因（2026-10-12 实测，`docs/feasibility_cutoff2.md`）**：cutoff=2 时
真实音乐语料的频繁项集组合爆炸（N=300 即 1130 万频繁对），枚举式挖掘在
N≥50 即无法在分钟级完成；anytime 阶段截断剪掉 freq=2 的复制项，保证失效。

### 2.2 （现行）查询侧稀有优先包含验证协议

1. **编码**：同 §2.1（不变，G1.3 已实现）。
2. **语料侧索引**：每首曲子一个事务（项集）→ 倒排索引（项 → 曲目 ID 升序数组），
   一次建库、全部查询复用。位图/GPU 批量验证（BMMA 思想）为 E5 优化项，
   正确性不依赖其实现。
3. **查询处理**：Q 的项按语料频率升序（稀有优先）逐个累加曲目计数器。
   - 召回保证：verbatim 片段 ≥ L 项 ⟹ 每个片段项都与供体共享 ⟹ 供体计数器
     必达 L，与处理顺序无关（可证明）。
   - anytime：任一停止时刻，仍可能命中的曲目集合 = { i : cnt[i] + U ≥ L }，
     U = 未处理查询项数，作为可证明的不完备界输出。
   - 免阈值：系统唯一语义参数 L = 最少证据项数（如 8 个事件），不是调出来的
     超参；容噪 k 是另一语义参数（噪声上界）。
4. **命中判定与定位**：cnt[i] ≥ L 的曲目为候选；精确共享片段 = Q ∩ C_i；
   项反映射回（音高, 时值, 音距, 力度）→ 查询端/库端定位。命中是确定性的。
5. **容噪**（E5.5 的 k-容噪）：查询端为每个事件生成有界变体键（音高 ±k 桶
   等），候选计数按"≥L 个位置匹配"判定；召回下界对噪声 ≤k 仍然成立（定理进
   论文理论部分，操作语义以固定编码+顺序为准）。
6. **引擎的角色变更**：AnyFIM/TensorFIM 不再承担检测主循环，作为
   **基线家族**参加 E4/E5（GivenThreshold 在可行阈值区间运行，画出枚举式
   挖掘的不可行边界——该边界本身是实验发现）；其位图内核思想仍是
   Method 4.2 的方法组件（适配层自研位图验证波次）。

---

## 3. G3.5 稠密 ID 重映射（适配层实现方案）

**插入点**：FIMI 文件写入之前。

**步骤**：
1. 适配层扫一遍事务集统计项频（与引擎 `getItemsFrequ()` 相同的口径：行内去重后计数）。
2. 按引擎同款规则推导幸存项：
   - GivenThreshold / TensorFIM：`freq(x) ≥ ⌈σ·N⌉`（引擎 `frequencyThreshold = transNum × supportThreshold`）；
   - Anytime：幸存下界 = 频度第 UptoStage+1 名的频度（引擎 `reduceTransSet` 用 `freqPerItem_inSort[UptoStage]`）。
3. 幸存项按**原始 ID 升序**编稠密 ID 1…m（**顺序保持**，不打频率序）。
   写 `orig→dense`、`dense→orig` 两张表（JSON 入库）。
4. 事务集按映射重写为 FIMI 文件喂引擎；引擎输出项集经 `dense→orig` 反映射后进入命中判定。

**为什么必须顺序保持**（2026-10-11 引擎语义发现，见 §1）：引擎只把 ID 小于当前根的项
作为扩展候选，且根要求频度严格大于阈值；MFI 输出由此依赖 ID 顺序。顺序保持的重编号
使引擎的逻辑探索路径与原始输入**逐位等价**（tie-break 也因"频度降序 + ID 升序 = 原始
相对序"而一致）；任何重排（包括按频率排序）都会改变边界 MFI 的可见性。

**行为等价性论证**（要点，全文见论文附录）：
- 引擎内部依赖的只是项的频度序、集合成员关系与阈值比较；ID 数值仅用作位图行号
  与数组下标。位图行数从 `itemIDmax+1` 降为幸存项数 m，内存与 GPU 传输量同比下降，
  挖掘语义不变。
- **空事务必须保留**：引擎对 FIMI 文件的每一行（含空行）都计入 `transNum`，而
  `transNum` 是阈值 `frequencyThreshold = transNum × support` 的基准；适配层丢弃
  空行会静默改变支持度基准（2026-10-11 门禁 4 实测抓获的 bug，已修）。
- 引擎读入时静默丢弃负数项 ID——适配层规则：项 ID ≥ 1（0 保留，见 §1 引擎地雷）。
- little-endian 扩展的循环顺序随 ID 编排变化，而引擎输出确实依赖该顺序（见 §1
  引擎语义发现）——所以等价性不靠"集合不变量"假设，靠**顺序保持重编号**保证。

**硬验收协议**（沿用 TensorFIM gold 纪律）：
- 同一事务集、同一阈值，分别以 (a) 原生稠密 ID 直喂、
  (b) 人为打散到稀疏大 ID + 适配层重映射，两种方式运行；
  输出 MFI 集合（反映射后，无序比较）与频度必须逐集合一致。
- 随机合成事务集 ≥20 组（不同密度/维度/种子）全部通过才算 G3.5 完成。
- E4/E5 默认配置 = 开重映射；off 对照组数据另存，用于消融表。

---

## 4. 运行目录与溯源约定

```
runs/<实验号>/<配置名>/
    bin/                  # 仅 anytime 需要：复制的 exe
    TransactionSets/      # 仅 anytime 需要：accidents.txt（我们的 FIMI 数据）
    input.fimi            # 直调类引擎的输入（登记 sha256，大文件不入 git）
    <dataset>-<thr>=Results.txt
    manifest.json         # 输入/exe 的 sha256、阈值、seed、超时、墙钟时间、
                          # 适配层版本(git commit)、引擎版本(SOURCES.txt 登记号)
    stdout.log
```

- 引擎 exe 一律只读引用上游路径直接调用（anytime exe 例外，见 §1）。
- 每篇论文数字登记到 `docs/paper_number_lineage.md`（脚本 + commit + manifest 指针）。

---

## 5. 适配层 API（Python，`src/adapter/`）

```python
adapter = FIMEngineAdapter(
    engine="tensorfim_bmma" | "tensorfim_bitmap" | "anyfim_gt" | "anyfim_anytime",
    dense=True,                 # G3.5 开关（消融 off 对照）
    quantization={"tpb": 8, "pitch_bins": 1, "dur_bins": ...},  # E5.7 扫描参数
)
adapter.build_corpus(corpus_midi_paths)          # 编码 + 事务集缓存（data/processed/）
hits = adapter.detect(query_midi, support=2/(N+1), timeout=None) -> list[Hit]
```

- `Hit`：`{corpus_id, query_span, corpus_span, itemset, frequency, stage?, engine_meta}`。
- anytime 模式：`detect(..., budget_secs=t)` 以 per-stage 输出重构 t 时刻的命中并集
  （阶段墙钟时间取 `runtimePerStage` 前缀和）。
- 所有公开入口接受 `--seed`；随机性只出现在 planted-copy 数据生成侧，引擎调用本身确定。

## 6. G3.4 sanity check 协议（进入 G1 前的门禁）

1. **冒烟**：TensorFIM 两 exe 在自带 FIMI 数据（mushrooms/chess）上与
   `data/gold_results/` 集合比对通过（复用 `run_all_configs.py` 的比对器）。
2. **AnyFIM 互证**：AnyFIM-GivenThreshold 与 AnytimeMining 在相同小数据上运行，
   与 TensorFIM 输出互证（AnyFIM 无 gold 文件）。
3. **planted**：合成 50 曲、10 对 verbatim 复制 → 召回 = 100%。
4. **G3.5 等价性**：§3 协议 ≥20 组随机合成集全部通过。

四门全过 → G3 完成，进入 G1/G2。
