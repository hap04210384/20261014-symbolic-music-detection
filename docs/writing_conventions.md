# 论文写作规范（Writing Conventions）

本规范适用于本目录产出的所有论文稿件，长期有效。

## 1. 文件名与格式

- 论文稿件文件名统一为 **`Manuscript.docx`**，**位置固定在 `kimi_work/` 根目录**（与 README、docs/ 同级，不放子目录）。
- 最终交付形态为 Word（.docx）。LaTeX 源文件（如期刊要求）另存于 `docs/latex/`，但以 Word 版为准。

## 2. Word 文档属性（元数据）

- **作者（author）字段 = 通讯作者姓名（Yalong Zhang）**，严禁出现 "Python"、"python-docx" 或任何工具名。
- 用 python-docx 生成时必须显式覆盖以下核心属性：

```python
from docx import Document
doc = Document()
cp = doc.core_properties
cp.author = "Yalong Zhang"            # 通讯作者（见第 5 节署名表）
cp.last_modified_by = "Yalong Zhang"
cp.title = "Paper Title"
cp.subject = ""
cp.comments = ""
```

- 投稿前检查 文件 → 信息 → 属性，确认作者栏为 Yalong Zhang。

## 2.1 稿件署名（2026-10-11 登记，论文 B 专用）

**Authors:** Xuemei Li¹, Jianping Deng¹, Meng Huang², Bao Wang², Yalong Zhang²*

**Affiliations:**
1. Faculty of Teacher Education, Quzhou University, Quzhou 324000, China
2. College of Electrical and Information Engineering, Quzhou University, Quzhou 324000, China

\* 通讯作者。一作 Xuemei Li；共同作者单位 1 为教师教育学院，单位 2 为电气与信息工程学院（均衢州学院）。

**Acknowledgements:**

> This work was supported by the Key Science and Technology Tackling Program of the Quzhou Municipal Bureau of Science and Technology under Grant 2025K192, and by the "Pioneer and Leading Goose+X" R&D Program of the Department of Science and Technology of Zhejiang Province under Grant 2024C01227.

## 3. 图表嵌入：EMF 格式

- 所有图（matplotlib 生成）一律以 **EMF** 嵌入 Word，禁止贴 PNG/JPEG 位图。
- 转换管线（已验证本机可用）：

```bash
# 1. matplotlib 存矢量图
python experiments/xx/plot.py --out results/fig3.svg
# 2. Inkscape 转 EMF（本机路径见下）
"C:\Program Files\Inkscape\bin\inkscape.exe" results/fig3.svg --export-type=emf --export-filename=results/fig3.emf
# 3. python-docx 以 EMF 嵌入（需指定宽高）
doc.add_picture("results/fig3.emf", width=Cm(8.5))
```

- 备选转换器（Inkscape 失败时）：LibreOffice headless
  `"C:\Program Files\LibreOffice\program\soffice.exe" --headless --convert-to emf results/fig3.svg --outdir results/`
- 图表分辨率：EMF 为矢量，无 DPI 问题；导出 SVG 时字体一律转曲或嵌入，防止 Word 中缺字体变形。
- 推荐字体嵌入：matplotlib 存 SVG 时设置 `svg.fonttype = 'path'`（文字转路径，跨机器零风险）。

## 4. 表格

- Word 内表格一律用 python-docx 原生表格（三线表样式），不用截图。

## 5. 作者登记（2026-10-11 已确认）

| 条目 | 值 |
|---|---|
| 稿件署名 | Xuemei Li¹, Jianping Deng¹, Meng Huang², Bao Wang², Yalong Zhang²* |
| 一作 | Xuemei Li |
| 通讯作者（= Word 元数据 author） | Yalong Zhang |
| 单位 1 | Faculty of Teacher Education, Quzhou University, Quzhou 324000, China |
| 单位 2 | College of Electrical and Information Engineering, Quzhou University, Quzhou 324000, China |
| ORCID | 待补（论文 PDF 中曾见 0009-0000-7650-6006，待确认归属） |

## 6. 生成脚本位置

统一的稿件生成脚本将放在 `src/publish/build_manuscript.py`：
读取 `results/` 下的 EMF 图表与指标表 → 生成 `kimi_work/Manuscript.docx` →
自动校验元数据作者字段。建好前，手工生成也必须遵守本规范。
