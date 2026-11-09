# 信任博弈实验（2×2 沟通方向）

oTree 6 实现的信任博弈实验（Berg, Dickhaut & McCabe, 1995），把事前沟通拆成
「投资者 A 能否发送送出意向」×「受托人 B 能否发送返还承诺」的 2×2 析因设计。
项目只交付**行为实验代码**，不含数据分析管线；实验设计与实现说明见
`实验设计与实现报告.tex`（编译产物 `实验设计与实现报告.pdf`）。

---

## 1. 项目简介

投资者获得 10 点禀赋，选择送出 x 点（0 ≤ x ≤ 10）；实验者乘以 3 后交给受托人，
受托人选择返还 y 点（0 ≤ y ≤ 3x）；收益为 A = 10 − x + y、B = 3x − y，以真实货币
支付（1 点 = 1 元），另付出场费 20 元。

设计要点：

- **单轮、被试间**：每名被试只经历一个条件、只做一次决策。
- **条件与角色在配对层随机**（真实采集配置 `trust_random`）：四格在同一场次内并存，
  避免条件与场次、时段、到场人群混淆。四个固定条件配置保留，只用于演示与教学。
- **消息前后各测一次信念**，共有三个信念对象：A 的返还比例、B 的送出点数、B 的二阶信念
  （B 认为 A 相信他会返还多少）。三类都有物质激励；沟通组随机抽取其中一次计奖。
- **无沟通组也有一次决策前判断**，但那是「假如可以交换消息」的假设性基线，不参与奖金；
  字段 `belief_before_hypothetical` 区分真实报告与假设性基线。
- 诚信承诺页、四道理解检验、事后情绪与操纵检查均为不参与报酬的辅助测量。

处理组由两个布尔键决定，不是一个四值字符串；两个键同时写入每个 `Player`，导出数据
自包含。读取入口统一为 `trust_game/__init__.py` 的 `investor_sends` / `trustee_sends` /
`sends_message` / `receives_message` / `any_message`。

---

## 2. 环境要求

| 项 | 值 |
| --- | --- |
| conda 环境 | `otree` |
| Python | 3.11.16 |
| oTree | 6.0.15 |
| Python 解释器 | `C:\Anaconda\envs\otree\python.exe` |
| oTree CLI | `C:\Anaconda\envs\otree\Scripts\otree.exe` |

依赖清单见 `requirements.txt`。`requests` 是 `otree test` 的隐式依赖：未安装时
`otree test` 会在第一个 case 处中止并以退出码 1 结束，**不会**输出
`Bots completed session`。

---

## 3. 目录结构

```
otree-trust-game-repo/
├── README.md                     本文件
├── settings.py                   SESSION_CONFIGS（4 个固定 + trust_random + 5 个演示）
├── requirements.txt              依赖清单
├── db.sqlite3                    oTree 默认库文件（已 gitignore）
├── proposal.tex                  课程研究计划（早期文档）
├── 实验设计与实现报告.tex          实验设计与实现报告（LaTeX 源码）
├── 实验设计与实现报告.pdf          报告编译产物
│
├── trust_game/                   核心实验 app
│   ├── __init__.py               模型、页面、creating_session、条件读取函数
│   ├── payoffs.py                收益、比例、信念奖金（不依赖 oTree）
│   ├── content.py                消息文案、强度编码、承诺二元编码
│   ├── tests.py                  oTree bot 端到端测试（3 个 case）
│   ├── test_payoffs.py           纯函数单测（19 个）
│   ├── test_content.py           文案同源、四组指导语互斥、承诺编码（28 个）
│   ├── test_settings.py          session config 守卫（10 个）
│   ├── test_demo_templates.py    演示模板副本守卫（3 个）
│   └── *.html                    11 个页面模板
│
├── survey/                       问卷 app（4 页：人口学、一般信任、风险偏好、独裁者博弈）
├── _templates/                   模板覆盖（演示单步守卫，仅机器人页面渲染）
├── _static/global/               单步演示控制台
└── docs/                         历史规格、计划与本项目 API 文档
```

`analysis/` 已删除：本项目不做数据分析，导出数据后按报告第 3、4 节的口径另行分析。

---

## 4. 运行实验

```powershell
conda activate otree
& "C:\Anaconda\envs\otree\Scripts\otree.exe" devserver 8000
```

管理员页面：`http://localhost:8000/demo`；数据导出：`http://localhost:8000/ExportIndex`。

### 4.1 会话配置

| config | 用途 | A 可发 | B 可发 | 说明 |
| --- | --- | --- | --- | --- |
| `trust_none` | 演示/教学 | 否 | 否 | 无沟通 |
| `trust_b_to_a` | 演示/教学 | 否 | 是 | 仅 B→A（承诺） |
| `trust_a_to_b` | 演示/教学 | 是 | 否 | 仅 A→B（意向） |
| `trust_both` | 演示/教学 | 是 | 是 | 双向 |
| `trust_random` | **真实采集** | 配对随机 | 配对随机 | 四格同场并存，角色也随机 |
| `*_bots` | 演示·单步 | 与对应真实 config 相同 | — | 带 `use_browser_bots=True` |

`*_bots` 与对应真实 config 的两个处理组键逐值相同，由
`trust_game/test_settings.py` 核对。**真实 config 绝不可带 `use_browser_bots=True`**：
它会让真实被试的页面被自动提交，而数据照样入库、测试照样全绿。

### 4.2 页面与分派

`page_sequence` 共 14 项：

```
Introduction → ComprehensionCheck → Pledge → BeliefBefore → MessageSend →
MessageWaitPage → MessageReveal → BeliefElicit → InvestorDecision →
DecisionWaitPage → TrusteeDecision → ResultsWaitPage → Results → PostRound
```

页面归属由 `is_displayed` 决定：`MessageSend` 只对发送方显示，`MessageReveal` 只对
接收方显示，`MessageWaitPage` 对全组显示（含不发送的一方，保证时序安全）。
`BeliefBefore` 对所有玩家显示：沟通组是真实事前判断，无沟通组是「假如可以交换消息」
的假设性基线。`PostRound` 对所有玩家显示：投资者答对返还额的不满，受托人答对送出额的不满
（信任缺失的供给侧），收到消息的一方另答消息可信度。
$x=0$ 时受托人决策页不渲染表单，`y` 自动记为 0。

### 4.3 演示模式：单步控制台

用于无真实被试时逐页观察流程。机器人页面会停下来等人点，「连续跑完」会反复点击
直到跑完。

1. 打开 `http://localhost:8000/demo/`，点一个「演示·单步」配置；
2. 从地址栏复制会话码（`/SessionStartLinks/<码>` 中的一段）；
3. 打开 `http://localhost:8000/static/global/step_console.html?code=<码>`；
4. 按「全部前进一页」。

守卫在 bot 页面上无条件生效，从 Grid view、split-screen、单个被试链接打开时同样会
停住。守卫被 `is_browser_bot` 条件包住，真实被试拿到的 HTML 不含它。

---

## 5. 运行测试

从项目根目录执行。跑 `otree test` 前先删除 `db.sqlite3`（否则 oTree 会提示
"Please delete your database"）。

### 5.1 单元测试（66 项）

```powershell
& "C:\Anaconda\envs\otree\python.exe" -m unittest `
  trust_game.test_payoffs trust_game.test_content `
  trust_game.test_settings trust_game.test_demo_templates -v
```

### 5.2 机器人测试（五个 config）

**参数是 session config 名，不是 app 名。** 每个 config 会跑三个 case（`tests.py` 的
`CASES`），成功时输出三行 `Bots completed session`、退出码 0。

```powershell
& "C:\Anaconda\envs\otree\Scripts\otree.exe" test trust_none 6
& "C:\Anaconda\envs\otree\Scripts\otree.exe" test trust_b_to_a 6
& "C:\Anaconda\envs\otree\Scripts\otree.exe" test trust_a_to_b 6
& "C:\Anaconda\envs\otree\Scripts\otree.exe" test trust_both 6
& "C:\Anaconda\envs\otree\Scripts\otree.exe" test trust_random 10
```

四个固定 config 各只覆盖一种页面归属，不能互相替代；`trust_random` 覆盖配对层随机
与四格同场。`trust_random` 的人数取偶数，测试用 10 人（5 对）是为了让四格更可能都出现。

---

## 6. 导出数据

管理界面 `http://localhost:8000/ExportIndex` 导出宽表 `all_apps_wide.csv`（每被试一行）。

关键列：

| 列 | 含义 |
| --- | --- |
| `trust_game.<round>.player.pair_cell` | 四格标签：`none` / `b_to_a` / `a_to_b` / `both` |
| `trust_game.<round>.player.role_randomized` | 是否经配对层随机 |
| `trust_game.<round>.player.investor_sends_message` | A 能否发意向（1/0） |
| `trust_game.<round>.player.trustee_sends_message` | B 能否发承诺（1/0） |
| `trust_game.<round>.player.promise` | 承诺派生编码（1 = 强度 ≥ 2） |
| `trust_game.<round>.player.belief_before_hypothetical` | 1 = 决策前判断为假设性基线 |
| `trust_game.<round>.player.belief_paid_timing` | 本次计奖时点 `before` / `after` |
| `trust_game.<round>.player.second_order_belief_return_pct` | B 的二阶信念（决策前）；计奖基准为甲方实际报告的信念 |
| `trust_game.<round>.player.trustee_anger_intensity` | 受托人对甲方送出额的不满（1–5） |

注意：

- `promise` 是**预设量表上的派生编码**，不是 Dufwenberg et al. (2026) 对自由文本的
  人工双编码，不可混用。
- `belief_*_before` 现在对所有玩家都有值，但无沟通组的那次是假设性基线
  （`belief_before_hypothetical = 1`），不能与沟通组的真实事前判断直接合并。
- `second_order_belief_*` 只有受托人有值，投资者行为 NULL，属角色造成的结构性缺失。
- `belief_bonus` 是本人的奖金合计：投资者 0/2，受托人 0/2/4（一阶与二阶各 2 点）。
  两者判定规则不同（点数 vs 百分点），不宜当作同一规则的结果。
- bot 导出（`otree test --export`）每个 case 各建一个 session，导出行数 = 人数 × case 数
  （本项目 3 倍），只适合验证数据形状，不能当作样本量。
- 演示会话可按 `participant._is_bot == 1` / `session.is_demo == 1` 过滤，导出后务必过滤。

---

## 7. 报告与文档

- [实验设计与实现报告.tex](实验设计与实现报告.tex)：10 章 + 3 个附录，含 6 条参考文献。
- [实验设计与实现报告.pdf](实验设计与实现报告.pdf)：编译产物。
- [docs/API.md](docs/API.md)：模型字段、页面、配置与条件函数的实现接口说明。

编译报告（xelatex 两遍，确保目录与引用编号）：

```powershell
& "C:\texlive\2025\bin\windows\xelatex.exe" -interaction=nonstopmode "实验设计与实现报告.tex"
& "C:\texlive\2025\bin\windows\xelatex.exe" -interaction=nonstopmode "实验设计与实现报告.tex"
```

---

## 8. 注意事项

1. **真实采集用 `trust_random`。** 四个固定条件 config 只用于演示与教学；用它们收真实
   数据会让条件与场次、时段、到场人群完全混淆。
2. **正式运行前设置 `OTREE_ADMIN_PASSWORD` 与 `OTREE_SECRET_KEY`**，不要把真值写进
   `settings.py`。仓库中的 `dev-only-not-for-production` 只是开发占位符。
3. **正式收集数据设置 `OTREE_PRODUCTION=1`**，用 `prodserver` 而非 `devserver`，并确保
   运行目录可写（`prodserver` 需要真实写入 sqlite）。
4. **演示会话不得混进正式数据。** devserver 热重载时会把内存库 dump 到 `db.sqlite3`，
   因此演示会话确实可能落盘；导出后按 `participant._is_bot == 0` 过滤。
5. **跑 oTree 测试前删除 `db.sqlite3`**，修改 app 代码后沿用旧库会报
   "Please delete your database"。
6. **`otree test` 的参数是 config 名，不是 app 名。** 本项目没有名为 `survey` 的 config。
7. **`creating_session` 必须是模块级函数。** oTree 6 对含 import 的 app 以模块为解析
   目标，写成 `Subsession` 类方法会被静默跳过，条件字段恒为 NULL。
8. **读取可空字段一律经 `field_maybe_none()`。** oTree 6 读取仍为 NULL 的字段会抛
   `TypeError`，与 `blank=True` 无关。
9. **仓库与报告含实验设计与指导语，正式收集数据前不要公开。** 公开会污染被试。
10. **无沟通组的决策前判断是假设性基线**，分析时先按 `belief_before_hypothetical` 分开，
    不要把它当作与沟通组同质的事前测量。
