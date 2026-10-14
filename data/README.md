# 数据登记册（data registry）

大数据集不入 git 库。每个数据集在此登记来源、版本、校验和与许可。

## 基准库（reference corpus）

| 数据集 | 规模 | 用途 | 许可/合规 | 来源 | 校验和 | 登记日期 |
|---|---|---|---|---|---|---|
| GigaMIDI v2.0.0（extended，2.1M+ MIDI；TISMIR 论文版 1,437,304） | 143 万–210 万 MIDI | 主基准库（T1/T2） | CC BY-NC 4.0（研究用途，署名；含 fair dealing 声明） | https://huggingface.co/datasets/Metacreation/GigaMIDI ，修订 `dc99f77fe125f303ef85f166646a074bc751ef64`（2026-04-21）；**gated 仓库，需授权 HF 账号**；本机 huggingface.co 直连被墙，经 `HF_ENDPOINT=https://hf-mirror.com` 访问 | LFS 文件待下载后登记 | 2026-10-11 |
| Lakh MIDI | ~176,000 MIDI | 仅作对照 | 版权灰色，仅对照使用 | 待补 | 待补 | 待补 |

## 查询/生成侧（query side）

| 数据集 | 用途 | 来源 | 校验和 | 登记日期 |
|---|---|---|---|---|
| Planted-copy 基准（自建） | T1 ground truth | 本库 `experiments/E1_planted_copies/` 生成 | — | 待生成后登记 |
| 受控记忆化生成集（自建） | T2 ground truth | 本库 `experiments/E6_memorization/` 生成 | — | 待生成后登记 |
| MCIC（真实判例 116 对） | T3 case study | 待补 URL | 待补 | 待补 |

## 预处理产物

所有预处理脚本放 `data/scripts/`，产物输出到 `data/processed/`（git-ignored），
产物文件名须含源数据集版本号与参数哈希。
