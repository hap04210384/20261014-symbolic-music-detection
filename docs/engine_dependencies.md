# 引擎依赖登记（Engine Dependencies）

B 论文复用 A 论文的两台引擎。仓库链接来自两篇在投论文的 CODE AND DATA AVAILABILITY 节。

## 来源论文

| 引擎 | 论文 | 本地 PDF |
|---|---|---|
| AnyFIM | *Anytime Frequent Itemset Mining: A Threshold-Free Progressive Item-Activation Framework with CPU–GPU Heterogeneous Collaboration* | `E:\20261010-paper-Musician meets AI character-02\607dc03d-88fe-4965-ac5f-194fef6c85ee.pdf` |
| TensorFIM | *TensorFIM: Exact Maximal Frequent Itemset Mining on Tensor Cores*（TKDE 在投） | `E:\20261010-paper-Musician meets AI character-02\a52451c4-952a-47e0-ba11-1891bc48246b.pdf` |
| A 论文（已投 EAAI） | *Certified-Exact Anytime Mining of Maximal Frequent Patterns on Million-Transaction Symbolic Music…* | `E:\20261010-paper-Musician meets AI character-02\EAAI-26-31892.pdf`（代码 acceptance 后公开，现为匿名 artifact） |

## 仓库

| 引擎 | URL | 本地位置 | 状态 |
|---|---|---|---|
| AnyFIM | https://github.com/hap04210384/Anytime-Frequent-Itemset-Mining | `kimi_work/src/engine_anyfim/` | ✅ 已就位（本地副本，commit f2fbd69，MIT） |
| TensorFIM | https://github.com/hap04210384/TensorFIM | `kimi_work/src/engine_tensorfim/` | ✅ 已就位（本地副本，commit 7067017，含预编译引擎与 gold 集） |

**已核实（2026-10-11）**：本地副本 commit 与 GitHub main HEAD 逐字符一致；
溯源登记见 `src/SOURCES.txt`。引擎源码按规则不入 B 的 git 库（.gitignore 已排除）。

## 许可证注意

- AnyFIM 代码：MIT（仓库 LICENSE），B 可放心复用，需保留版权头。
- TensorFIM：复现包性质，复用前确认其 LICENSE 文件条款。
- 两篇论文均在审：B 中引用为 "under review"，代码注释注明来源，B 仓库不把引擎源码重新公开发布（避免在审稿期造成双投稿混淆），仅保留接口层。
