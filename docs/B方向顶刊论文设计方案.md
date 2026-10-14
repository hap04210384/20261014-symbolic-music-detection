# 方向 B 顶刊论文设计方案

**方向 B：位图加速的 AI 音乐原创性 / 训练数据复制检测**
**目标期刊：IEEE TETCI（中科院 2 区，已定稿，2026-10-11）**
**日期：2026-10-11（定稿版）**

---

## 1. 一句话定位

> 首个**可证明完备**（免阈值 anytime + 单边扩展）、**百万文件级**（GigaMIDI 规模）的符号音乐**精确复制检测引擎**，为 AI 生成音乐提供可解释、可呈证、有召回保证的"训练数据记忆化筛查层"，并与神经嵌入方法形成互补混合系统。

注意措辞：不说"判定抄袭"（那是法律判断），说 **replication / memorization detection**（复制/记忆化检测）。这对应 CV/NLP 领域已确立的 Somepalli（diffusion replication）、Carlini（extraction attack）问题范式，审稿人认得这个 framing。

## 2. 目标期刊（按优先级）

| 优先级 | 期刊 | 分区（2025升级版） | 适配逻辑 |
|---|---|---|---|
| **一志愿（已定）** | **IEEE Transactions on Emerging Topics in Computational Intelligence (TETCI)** | 计算机科学 **2区**（小类 AI 3区, IF≈5.3–6, SCIE, IEEE, 单盲） | 2025 由 3区 升 2区，新升区窗口期竞争温和；范围天然契合：anytime 自适应调度、免阈值搜索、精确+神经混合系统均为 CIS 口味；AI 音乐版权检测是如假包换的 emerging hot topic |
| 平移备选 | Neural Networks | 计算机科学 **2区 Top**（Elsevier, 单盲） | 2025 由 1区-TOP 降为 2区-TOP；若走"可学习容错 + 精确保证混合"叙事适配；作者无在投冲突 |
| 保底备选 | IEEE Transactions on Big Data (TBD) | 计算机科学 **2区** | scalability + wave batching 故事契合（注：作者当前有一篇在投，须等其结果落定后再投 B） |
| 有保留备选 | J. King Saud Univ. CS (JSCI) | 计算机科学 **2区**（IF 6.4, OA） | 分区达标、不在预警名单，但审稿约 45 周偏慢、OA 占比 99.7%——时间宽裕时再考虑 |
| 暂不推荐 | TASLP（已更名 TASLPRO） | 分区数据暂未公布 | 新更名刊在中科院分区表中暂无条目，不满足"明确 1/2 区"要求，等分区稳定后再考虑 |
| 已排除 | TMM / TKDE（1区 Top 冲档） | 机会成本过高 | B 潜力在 1区有竞争力，但作者当前策略是稳拿 2区；若日后需要第二篇 1区可重启此选项 |
| 已排除 | Cognitive Computation / Complex & Intelligent Systems / Applied Intelligence / Soft Computing / IJMLC | 2025 均已降为 **3区/4区** | 2025升级版人工智能期刊大面积降档，勿按旧印象投稿 |
| 已排除 | Multimedia Tools and Applications (MTAP) | **4区 + 中科院预警名单（论文工厂）+ IF 被压制为 0** | 选题虽匹配，但分区不达标且在预警名单，职称/结题场景为负收益 |

审稿方式说明：以上 IEEE 与 Elsevier 期刊均为**单盲**（作者身份可见，审稿人匿名），符合"不要双盲"的要求。

**A 引擎论文已投 EAAI**（2025 升级版为 1区 Top）——B 的候选池与 A 无期刊冲突，无香肠论文风险；B 写作中涉及引擎的部分需控制篇幅、改写表述，并引用 A 为"under review"，明确 B 的增量贡献是有界容错扩展（C2 下半）、检测协议/基准与混合系统（C3）。

投稿策略（2026-10-11 定稿）：B 一志愿 **TETCI**（2区，新升区窗口期，CIS 口味：anytime 自适应系统叙事）；被拒后平移 Neural Networks（2区 Top）→ TBD（2区，需等其当前在投稿出结果）。方法与实验设计不变，平移时只需重写引言与 related work 的重心。

## 3. 核心创新点（4 个，TETCI/CIS 口味排序）

> TETCI 审稿人来自计算智能社区（而非纯 MIR 或数据库社区）：接受 theory + application，但要求主菜是"智能系统/方法"。因此排序从 TMM 版的"C1 理论先行"调整为"C2+C3 方法系统先行、C1 理论作为支撑保证"。

### C1（系统主贡献，第一位）：免阈值 anytime 自适应检测系统
- 将 AnyFIM 的免阈值 anytime 调度 + 单边扩展移植为复制检测系统：任意时刻停止即得当前完备结果，无需调阈值——对 CIS 审稿人讲成"adaptive anytime search with zero hyperparameter tuning"。
- 支撑理论保留：停止时刻的完备性与召回率下界（定理 + 证明草图，Method 一节内完成，不进独立理论章节）。

### C2（方法主贡献，第二位）：BMMA 位图加速核 + 有界容错单边扩展
- BMMA 张量核位图加速：查询片段 × 百万文件语料的精确匹配转化为位图/张量核运算，数量级加速（GigaMIDI 全库秒级～分钟级）。
- 有界容错扩展（bounded-error single-side extension）：每匹配位置容忍 ≤k 个事件偏差（转录噪声、移调、音符分裂合并），给出噪声 ≤k 时的召回下界——把系统从"只抓 verbatim"升级为"抓 near-verbatim 且有保证"。
- 卖点数字目标：吞吐率比 SIATEC 家族基线高 2–3 个数量级，实证"方法停在百首时代、数据已进入百万时代"的交叉空白。

### C3（基准+应用，实验贡献）：检测协议、基准与混合系统
- 提出**音乐训练数据复制检测协议**（评测任务定义 + planted-copy 基准构建方法），填补该任务无标准评测的空白；
- 证明精确层与神经嵌入层（MERT/MelodySim 式）的**互补性**：精确层抓 verbatim/near-verbatim（法律上最易举证），嵌入层抓语义相似；混合系统在两族正样本上同时优于任一单方法；
- 输出音乐人/法律场景可用的**可解释证据**：命中片段对齐定位图（类似 MelodySim 的 decision matrix 但基于确定性命中）+ MD5 验证协议保证结果可复现可呈证。

## 4. 实验设计（7 组实验，支撑创新点）

### 4.1 任务与数据

**任务 T1——已知语料库的复制检测（controlled）**
- 基准库：GigaMIDI（143 万文件，fair dealing，主语料）；Lakh MIDI（版权灰色，仅作对照，规避合规风险）。
- 查询集（planted copies，ground truth 已知）：从 GigaMIDI 抽样片段，施加受控变换生成正样本：①verbatim；②移调 ±1~3 半音；③变速 0.9–1.1×；④音符分裂/合并（MelodySim 式增强）；⑤换乐器/删声部；⑥转录往返（MIDI→音频→MT3/Basic Pitch 转录，模拟真实 AI 音频输出）。每种变换 3–5 个强度级别 × 片段长度梯度（2/4/8/16 小节）。
- 负样本：同风格未复制片段 + 已知风格相似但无复制的配对（覆盖"实质性相似但非复制"的困难负例）。

**任务 T2——真实 AI 生成音乐的训练数据筛查（in the wild）**
- 生成源：当前开源符号生成模型 + MusicGen 类音频模型输出转录；以及"受控自训模型"：自己训练 1–2 个小型音乐生成模型，在已知语料（GigaMIDI 子集）上训练并故意调节记忆化程度（epochs/数据重复率），产出已知记忆化水平的生成样本——这是 ground truth 完全可控的记忆化基准，论文中最有说服力的一组实验。

**任务 T3——真实判例定性评估**
- MCIC 数据集（116 起真实法庭判例，含判赔/驳回标注）：不求精确匹配方法"判对法律结果"，而是展示命中证据与法官认定的相关性 + 3–5 个著名 sound-alike 案例的深度案例研究。

### 4.2 基线（必须覆盖三类）

| 类别 | 基线 | 作用 |
|---|---|---|
| 精确结构挖掘家族 | SIATEC、COSIATEC、（可选 SIARCT-CFP 处理近似） | 证明"同家族方法跑不到语料级规模"（E4）+ 检测质量对比（E1） |
| 字符串/哈希类 | n-gram 钢琴卷帘哈希、旋律轮廓编辑距离 | 轻量基线，审稿人必问 |
| 神经嵌入类 | MERT embedding 相似度（MelodySim 式实现）、余弦检索 | 证明互补性而非互斥（E7） |

### 4.3 实验矩阵

- **E1 检测性能**：T1 全变换 × 长度矩阵上的 recall / precision / F1 / ROC-AUC；与全部基线对比。指标强调**召回率**（筛查场景漏检代价高），给出 95% 置信区间（多种子重复）。
- **E2 容错保证验证**（C2 下半）：planted-copy 召回率 vs 噪声强度 k 曲线，验证实测召回 ≥ 理论下界——这是容错贡献的实证锚点，必须做。
- **E3 anytime 行为**（C1）：命中数/召回率 vs 运行时间曲线，对比阈值化基线（早停 vs 漏检）；展示任意时刻停止的"已发现命中数"单调性与完备性界。
- **E4 可扩展性**（C2 上半）：语料规模 10³→10⁶ 文件的运行时间/内存曲线（对数坐标）；全 GigaMIDI 吞吐率；与 SIATEC 家族的规模-可行边界对比（基线在哪个规模超时/超内存）。
- **E5 消融**：位图核 on/off、wave batching on/off、单边扩展 vs 双边、免阈值 vs 阈值化、MD5 验证协议开销——逐组件证明设计必要性。
- **E6 真实世界**（T2/T3）：受控记忆化模型的检出率 vs 训练重复率曲线；MCIC 案例研究 3–5 个（命中片段乐谱对照图 + 法律结果对照表）。
- **E7 混合系统**（C3）：精确层、嵌入层、级联混合（精确层先筛、嵌入层复核语义相似阴性附近的候选）在合成 + 真实数据上的联合 P-R 曲线，证明 1+1>2。

### 4.4 关键图表清单（论文 12–14 页双栏的容量）

1. 系统架构图（anytime 引擎 + 容错扩展 + 混合级联 + 证据输出模块）
2. E4 规模-时间对数曲线（含基线不可行边界）——**最重要的图**
3. E3 anytime 质量-时间曲线族
4. E2 召回率-噪声强度曲线（理论下界 vs 实测）
5. E7 混合系统 P-R 曲线
6. T2 记忆化水平-检出率曲线
7. 案例研究：3 组乐谱对照 + 对齐定位热图
8. 大表：E1 全矩阵结果（主结果表，放附录或 online）

## 5. 论文骨架（IEEE TETCI 双栏格式，建议正文 12–14 页）

1. **Introduction**：生成式 AI 音乐诉讼与授权时代背景（RIAA/Koda/GEMA、和解潮）→ 检测工具刚需 → 现有方法三类（精确家族跑不动百万级 / 字符串类无保证 / 神经嵌入近似不可呈证）→ 本文 anytime 自适应系统（贡献按 CIS 口味排序：免阈值自适应系统 → 位图加速 + 有界容错 → 完备性保证 → 协议/基准/混合系统）。
2. **Related Work**：(a) 符号音乐模式挖掘（SIATEC 家族谱系）；(b) 音乐相似度与抄袭检测（MelodySim、Oxford 图像法、MCIC/SMP）；(c) anytime 算法与自适应搜索；(d) 生成模型记忆化与复制检测（Carlini、Somepalli 的跨域迁移）。
3. **Problem Formulation & Preliminaries**：复制检测形式化、事件集表示、TEQ（平移等价）记号、威胁模型与噪声模型。
4. **Method**：4.1 anytime 免阈值检测系统（含完备性定理 + 证明草图）；4.2 BMMA 位图加速核（wave batching）；4.3 有界容错单边扩展（定理 + 召回下界）；4.4 混合级联与证据输出。
5. **Experimental Setup**：数据、planted-copy 协议、基线实现细节、指标、实现环境（硬件规格写清楚，便于复现）。
6. **Results & Analysis**：E1–E7 依序，每实验一段 + 一节综合讨论（何时用精确层、何时用嵌入层）。
7. **Case Studies**：MCIC + sound-alike 深案例。
8. **Discussion & Ethics**：能力边界（抓不到实质性相似）、转录误差传播、滥用风险（检测器也可用于规避）、数据合规声明。
9. **Conclusion**。

## 6. 时间线（按 TETCI 投稿倒排，约 8–10 个月）

| 月份 | 里程碑 |
|---|---|
| M1–M2 | 有界容错单边扩展理论完成（C2 下半）+ 引擎移植；planted-copy 基准构建 |
| M3–M4 | 基线复现（SIATEC 家族、MERT 嵌入）；E1/E2/E4 首轮跑通 |
| M5–M6 | T2 受控记忆化实验 + E3/E5/E7；MCIC 案例收集 |
| M7 | 图表定稿 + 全文撰写 |
| M8 | 内审一轮（找 MIR + 计算智能双背景同事各一人）→ 投稿 TETCI |
| M8+3~6月 | 一审意见 → 修回 |

若 M8 时容错理论打磨不及预期：降级策略是把容错部分拆成后续工作，先投 Neural Networks 或 TBD（2区，TBD 需等其当前在投稿出结果）保成果，容错补全后再冲 TETCI/TMM 第二篇。

## 7. 主要风险与应对

1. **审稿人质疑"符号域不实用"**（AI 输出是音频）→ T1 的转录往返通道 + T2 真实转录实验必须做实；把方法定位为"筛查层"，与音频域嵌入级联。
2. **MCIC 上精确匹配命中率可能不高**（真实抄袭多为实质性相似而非 verbatim）→ 预先框定为 case study 而非定量主结果，避免被一票否决。
3. **合规**→ 主语料只用 GigaMIDI（fair dealing），Lakh 仅对照，论文中明确许可声明。
4. **竞争窗口**→ SMP（ICASSP 2026）、MelodySim 说明社区在加速；2026 年内投稿保住"首个可证明完备的大规模符号复制检测"的首发权。
5. **TETCI 小类 3 区**→ 投稿前确认单位按大类还是小类认定（多数按大类，无碍）。

## 8. 备选标题（TETCI/CIS 口味，3 选 1）

1. *An Anytime Adaptive System for Provable Training-Data Replication Detection in AI-Generated Music*
2. *Threshold-Free Meets Guaranteed-Recall: A Bitmap-Accelerated Hybrid System for Music Memorization Detection*
3. *Who Did the Model Listen To? Anytime Detection of Symbolic Music Replication at Million-File Scale*
