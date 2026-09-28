# 信任博弈实验（沟通 vs 基线）

> ⚠️ **本仓库的分析部分全部基于模拟数据。** `analysis/output/` 下的模拟数据、表格与图
> 仅供演示分析管线可跑通，**不是真实被试的行为数据**。详见「注意事项」第 1 条与
> `实验报告.md` 第 8 节。

oTree 6 实现的信任博弈（Berg, Dickhaut & McCabe, 1995）实验，含问卷模块、模拟数据集、
统计分析管线与实验报告。

---

## 1. 项目简介

本实验研究**事前沟通（cheap talk）能否提升信任水平与可信度，以及其作用是否通过改变信念实现**。

采用 Berg, Dickhaut & McCabe (1995) 的信任博弈范式：投资者获得 10 点禀赋，选择送出
x 点（0 ≤ x ≤ 10），实验者乘以 3 后交给受托人，受托人选择返还 y 点（0 ≤ y ≤ 3x）；
收益为 A = 10 − x + y、B = 3x − y，均以真实货币支付，另有 20 元出场费。

**处理组设计：2 组被试间（between-subjects），由 session config 单点控制。**

| 条件 | session config | 操纵 |
|---|---|---|
| 基线组（C） | `trust_baseline` | 标准信任博弈，全程匿名，无任何沟通 |
| 沟通组（T） | `trust_communication` | 双方在决策前同时发送预设消息、互相可见 |

两组除消息页外使用**完全相同的代码、模板、参数与指导语结构**，处理组由
`session.config['communication']` 单点决定（读取入口统一为 `has_communication(player)`）。

博弈结束后，全部被试完成问卷（风险偏好、独裁者博弈、一般信任、人口学）。

---

## 2. 环境要求

**解释器与 oTree 版本是固定的，不要换用系统 `python3`。**

| 项 | 值 |
|---|---|
| conda 环境 | `otree` |
| Python | 3.11.16 |
| oTree | 6.0.15 |
| 解释器绝对路径 | `/share/zrs2022150501010/miniconda3/envs/otree/bin/python` |
| oTree CLI 绝对路径 | `/share/zrs2022150501010/miniconda3/envs/otree/bin/otree` |

本机实测的依赖版本：requests 2.34.2、numpy 2.4.6、pandas 3.0.5、scipy 1.17.1、
statsmodels 0.15.0、matplotlib 3.11.2。

**依赖已安装。** 如需重建环境或核对依赖：

```bash
# 依赖清单：/share/zrs2022150501010/project/behavioral_experiment/requirements.txt
/share/zrs2022150501010/miniconda3/envs/otree/bin/pip install -r /share/zrs2022150501010/project/behavioral_experiment/requirements.txt
```

从零重建 conda 环境（仅在环境损坏时需要）：

```bash
conda create -n otree python=3.11.16 -y
/share/zrs2022150501010/miniconda3/envs/otree/bin/pip install -r /share/zrs2022150501010/project/behavioral_experiment/requirements.txt
```

> `requests` 是 `otree test` 的**隐式依赖**：未安装时 `otree test` 在第一个
> session（`test case 0`）处即中止，把
> "You need to install requests to run bots" 打到 **stderr** 并以**退出码 1** 结束
> （`otree/bots/bot.py:224` 的 `sys.exit(str)`；本机实测确认），因此它**不会**
> 输出任何 `Bots completed session`——只数 `Bots completed session` 行数而不看退出码
> 的话，会把它误读成"检查项没跑"。`requirements.txt` 已显式包含 `requests`。

---

## 3. 目录结构

```
/share/zrs2022150501010/project/behavioral_experiment/
├── README.md                    本文件（交付物 5）
├── 实验报告.md                  实验报告（交付物 1）
├── settings.py                  SESSION_CONFIGS：2 个真实 + 2 个演示（*_bots，见 §4.1）
├── requirements.txt             依赖清单
├── db.sqlite3                   oTree 默认库文件（0 字节，已被 .gitignore 排除）
│
├── trust_game/                  核心实验 app（博弈流程）
│   ├── __init__.py              Pages / Models / creating_session
│   ├── payoffs.py               收益与派生量计算（不依赖 oTree，可独立单测）
│   ├── content.py               消息文案与强度编码（唯一真值来源）
│   ├── tests.py                 oTree bot 端到端测试（2 个 case）
│   ├── test_payoffs.py          纯函数单元测试（13 个）
│   ├── test_content.py          文案与常量同源测试（16 个）
│   ├── test_settings.py         session config 守卫（6 个）
│   ├── test_demo_templates.py   演示模板守卫：副本漂移 + 门控条件 + 键名（3 个）
│   └── *.html                   8 个页面模板
│
├── survey/                      问卷 app（个体测量）
│   ├── __init__.py              4 页：风险偏好 / 独裁者 / 一般信任 / 人口学
│   ├── tests.py                 oTree bot 测试（2 个 case）
│   └── *.html                   4 个页面模板
│
├── _templates/                  模板覆盖（演示模式单步守卫，见 §4.1）
│   ├── otree/Page.html          oTree Page.html 的副本，差异只有末尾守卫块
│   └── bot_step_guard.html      单步守卫 JS（**仅机器人页面**渲染）
│
├── analysis/                    模拟数据与分析管线
│   ├── __init__.py              空文件，使 analysis 可被 unittest discover 发现
│   ├── simulate_data.py         模拟数据生成（固定种子 20260913）
│   ├── analyze.py               统计分析管线（5 表 + 4 图）
│   ├── test_analyze.py          分析管线值级守卫（12 个用例）
│   └── output/                  产物目录；除 .gitkeep 外全部 gitignore
│
├── docs/superpowers/
│   ├── specs/2026-09-13-trust-game-design.md        设计规格（交付物 6）
│   └── plans/2026-09-13-trust-game-implementation.md 实施计划
│
└── _static/global/
    ├── empty.css                oTree 静态文件占位
    └── step_console.html        单步演示控制台（见 §4.1）
```

`analysis/output/` 中的文件**全部是生成物**，不随仓库分发：模拟数据、5 张表、4 张图。
在全新检出上该目录只有 `.gitkeep`，必须先运行生成脚本（见第 7 节）。

---

## 4. 运行实验

`otree devserver` 会通过 `PATH` 重新 exec 一个**裸 `otree` 命令**，因此必须先把环境的
`bin/` 加入 `PATH`，否则会以 "command not found" 失败。

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
export PATH=/share/zrs2022150501010/miniconda3/envs/otree/bin:$PATH
otree devserver 8000
```

启动后在浏览器打开：

- **http://localhost:8000/demo** —— 演示页，列出四个 session config：
  两个真实（`信任博弈 — 基线组（无沟通）` / `信任博弈 — 沟通组`）、
  两个演示（`信任博弈 — 基线组（演示·单步）` / `…沟通组（演示·单步）`，见 §4.1）。
  点任一 config 即可创建会话并取得各参与者的进入链接；
- **http://localhost:8000/sessions** —— 已有会话列表；
- **http://localhost:8000/ExportIndex** —— 数据导出入口（见第 6 节）；
- **http://localhost:8000/rooms** —— 实验室房间（本项目 `ROOMS = []`，未使用）；
- **http://localhost:8000/server_check** —— 服务器自检。

**两个 config 的说明：**

- `trust_baseline`：标准信任博弈，全程匿名、无任何沟通；被试经历 8 页（跳过消息相关 3 页）。
- `trust_communication`：双方在决策前各自从 5 个预设选项中选一条消息、同时发送、互相可见；
  被试经历全部 11 页。

`num_demo_participants = 8`（每个 config），即一桌 8 人 = 4 对。真实实验时用
`otree create_session <config> <人数>`（本机实测于可写磁盘：`Created session with code
ctuhabar`）或管理界面按实际人数创建。**注意 `create_session` 需要可写的 sqlite**：
在 `/share` 这个 NFS 挂载上会**卡住不返回**（不是报错），故只能在本地磁盘上执行。

### 4.1 演示模式：单步控制台

用于**在没有真实被试时逐页观察实验流程**。机器人被试由 oTree 内置的 browser bots
提供，驱动脚本就是本仓库已有的 `trust_game/tests.py` 与 `survey/tests.py`——与
`otree test` 跑的是同一份。

**机器人页面会停下来等人点。** 守卫在 bot 页面上无条件生效，所以**不论从哪个入口
打开**——单步控制台、会话页的 Grid view、split-screen、单个被试链接——页面都停在
当前页，按「下一页」才前进一页（点下去用的是机器人在服务端排好队的答案）。

最省事的用法是控制台：

1. 打开 `http://localhost:8000/demo/`，点「信任博弈 — 基线组（演示·单步）」；
2. 从地址栏复制会话码（`/SessionStartLinks/<码>` 里的那一段）；
3. 打开 `http://localhost:8000/static/global/step_console.html?code=<码>`；
4. 按「**全部前进一页**」——按一次，8 人各填一页。

页面上可直接看到角色分叉（投资者进 `InvestorDecision`、受托人进 `BeliefElicit`）、
等待页、以及校验拦截（理解检验先答错被拒、再答对通过，属预期）。

只要不想一个个点，就用控制台的「**连续跑完**」：它反复点击直到 8 人跑完全部 12 页
（几秒），再按一次可中途停止。**想只看数据不看过程时用它；它不影响守卫是否生效。**

**守卫只对机器人页面存在。** `_templates/otree/Page.html` 里那段守卫被
`is_browser_bot` 条件包住，真实被试（该字段恒为假）拿到的 HTML 里**不含它的任何
字节**——不是「存在但停用」。`trust_game/test_demo_templates.py` 断言该条件存在、
断言守卫里没有 opt-in 开关、并逐行看守副本与 oTree 原文件的差异。

**已知行为：**

- 控制台会刷出若干 `TypeError: form.on is not a function`。这是 oTree 自身注入的
  自动提交脚本的缺陷（它在 `form.submit()` 之后调用 jQuery 的 `form.on`），无害。
- 每次创建演示会话会随机抽一个 bot case（`normal` 或 `zero_send`，同一会话内 8 人
  同 case）。两者**页面序列完全相同**，只是数值不同（`zero_send` 时投资者送 0、
  受托人页无表单）。想看另一分支就重新点一次配置。
- **`otree browser_bots` 那个命令行启动器会挂住**：它等被试跑完的完成信号，而演示
  会话里的被试会停下来等人点。本项目不使用该启动器。
- 演示会话是 bot 会话，**不得混进正式数据**——见「注意事项」第 11 条。

---

> **本机重要限制：** `/share` 是 NFS 挂载，sqlite 写入失败。`otree devserver` 与
> `otree test` 内部强制使用**内存数据库**（`otree/main.py` 对 `devserver_inner` 与 `bots`
> 设置 `OTREE_IN_MEMORY=1`），所以两者都能正常跑；但代价是**会话数据只在内存里，
> 服务器一停就全部丢失**（实测：跑完 devserver 后 `db.sqlite3` 仍是 0 字节）。
> 因此在本机上跑 devserver 时，**务必在关闭服务器之前从 `/ExportIndex` 导出数据**。
> 正式收集数据请换到本地磁盘运行并配合 `OTREE_PRODUCTION=1`（见「注意事项」）。
>
> ⚠️ **补充（实测）**：上面的「不落盘」只在**不改文件**时成立。devserver 每次
> **热重载**都会把内存库 dump 到磁盘：`otree/cli/devserver.py:65` 在监视到 `.py`
> 文件变化时 POST `/SaveDB`，`otree/views/admin.py:633-644` 调
> `save_sqlite_db()`，后者在内存库模式下执行
> `sqlite_mem_conn.backup(sqlite_disk_conn)`（`otree/database.py:163-175`），
> 且 `_dumped` 标志保证每进程只 dump 一次。实测：跑着 devserver 改一次文件，
> `db.sqlite3` 立刻变成 168 KB 并含该进程的全部会话；不改文件则恒为 0 字节。
> 演示模式的会话据此会出现在 `db.sqlite3` 里——见 §4.1 与「注意事项」第 11 条。

---

## 5. 运行测试

测试命令都从项目根目录执行，且**跑 oTree 测试前先删除 `db.sqlite3`**（沿用旧库时 oTree 会
提示 "Please delete your database"）：

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
rm -f db.sqlite3
```

### 5.1 oTree bot 端到端测试

**参数是 session config 名，不是 app 名。** 本项目没有名为 `survey` 的 session config，
`otree test survey` 会报 "No session config with name 'survey'"。

```bash
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline
/share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_communication
```

每个 config 会跑**两个 case**（`trust_game/tests.py` 的 `cases = ['normal', 'zero_send']`
与 `survey/tests.py` 的两个 case 取最大值），因此每个命令会完整跑通**两次 session**
（每个 case 一次），覆盖 `trust_game` + `survey` 两个 app 的全部页面；成功时输出两行
`Bots completed session` 并以退出码 0 结束。`zero_send` case 专门覆盖 x = 0 的退化路径。

任一会话未被跑通（如第 0 个 case 失败）都会**中止并给出非零退出码**，不会静默跳过。

### 5.2 纯函数单元测试与全仓测试

```bash
# 纯函数单元测试：收益函数、返还比例、信念奖金、消息强度映射、文案同源（29 个）
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest trust_game.test_payoffs trust_game.test_content

# 分析管线的值级守卫（12 个）
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest analysis.test_analyze

# 全仓（50 个）；-t . 指定项目根为顶层目录
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest discover -t .
```

**⚠️ 顺序要求：`analysis/test_analyze.py` 依赖 `analysis/output/simulated_data.csv`。**
在全新检出上该文件不存在，这 12 个用例会**跳过并打印原因**（不是静默跳过）：

```
skipped '需要 analysis/output/simulated_data.csv；请先在项目根运行 python analysis/simulate_data.py'
```

此时 `discover` 的输出是 `Ran 50 tests ... OK (skipped=12)`——**实际执行 38 个**。
要跑满 50 个，请先执行第 7 节的 `simulate_data.py`。

---

## 6. 导出数据

三种方式，按用途选：

1. **管理界面（推荐，真实数据用）**：运行 devserver 时打开
   **http://localhost:8000/ExportIndex**，选择会话后导出；也可从 `/sessions` 页进入。
   导出的是宽表 `all_apps_wide.csv`（每被试一行）。
2. **bot 数据导出（测试用）**：`otree test` 加 `--export` 参数，把 bot 跑出的数据存盘。
   ```bash
   /share/zrs2022150501010/miniconda3/envs/otree/bin/otree test trust_baseline 60 --export /tmp/exp_baseline
   ```
   产物目录含 `all_apps_wide.csv`、`trust_game.csv`、`survey.csv`。
3. **分析用宽表**：`analysis/analyze.py --data <上述 all_apps_wide.csv>`（见第 7 节）。

> `otree zip` **不是数据导出命令**。在 oTree 6 中它把项目打包成 `.otreezip` 用于部署，
> 且需要交互式回答依赖文件问题，与本项目的数据导出无关。

**处理组标识：** 宽表 CSV 中的字段 **`trust_game.1.player.is_communication`** 即处理组标识
（1 = 沟通组，0 = 基线组）。该字段由 `creating_session` 从
`session.config['communication']` 降范式写入每个 Player，使每份导出数据**自包含**——不需要
按 `session.code` 做跨表关联就能分辨处理组。宽表中同时保留原始配置列
`session.config.communication`，两者在同一 session 内必然一致。

> 只跑了单个 config 的导出（单臂）做不了任何组间比较。`analysis/analyze.py` 会在**落盘之前**
> 检测到这种情况并以明确信息中止（退出码 1，产物目录一个字节都不写）。需要两个 config 的
> `all_apps_wide` 合并后才能分析。

---

## 7. 运行分析

**顺序是强制的：生成数据 → 分析 → 测试。** 后一步依赖前一步的产物。

```bash
cd /share/zrs2022150501010/project/behavioral_experiment
```

**第 1 步：生成模拟数据**（产出 `analysis/output/simulated_data.csv`，随机种子 20260913 固定）

```bash
/share/zrs2022150501010/miniconda3/envs/otree/bin/python /share/zrs2022150501010/project/behavioral_experiment/analysis/simulate_data.py
```

**第 2 步：运行分析**（产出 5 张表 + 4 张图，全部写入 `analysis/output/`）

```bash
# 默认读模拟数据
/share/zrs2022150501010/miniconda3/envs/otree/bin/python /share/zrs2022150501010/project/behavioral_experiment/analysis/analyze.py

# 真实数据：--data 指向 oTree 导出的宽表 all_apps_wide.csv
/share/zrs2022150501010/miniconda3/envs/otree/bin/python /share/zrs2022150501010/project/behavioral_experiment/analysis/analyze.py --data /path/to/all_apps_wide.csv
```

产物：

| 文件 | 内容 |
|---|---|
| `simulated_data.csv` | 模拟数据（第 1 步产出；真实数据运行时不需要它） |
| `table_descriptives.csv` | 分处理组描述统计 + `risk_choice` 分布 |
| `table_ttests.csv` | H1 / H2 的 Welch t 检验（含 Cohen's d 与 95% CI） |
| `table_regressions.csv` | H3 的四个 OLS 规格（HC1 稳健标准误） |
| `table_mediation.csv` | H4 中介分析（bootstrap 5000 次） |
| `table_correlation.csv` | H5 与相关分析 |
| `fig_send_amount.png` | 送出金额分布（按处理组分色） |
| `fig_return_ratio.png` | 返还比例分布（仅 x > 0） |
| `fig_promise_ratio.png` | 承诺强度 ~ 返还比例（含 OLS 拟合线） |
| `fig_belief_send.png` | 信念 ~ 送出金额（分组拟合） |

数据来源标注**由脚本自动生成、不可手工关闭**：表格首列 `数据来源` 与图的标题/页脚统一写作
`【模拟数据，非真实被试结果】`；`--data` 只要不是默认的模拟数据路径，就自动改标 `【真实数据】`。

**标注按路径判定，另有内容核对兜底。** 路径本身并不能证明数据是什么，故脚本在读取前会用
**文件内容**核对一次（`analyze.py` 的 `check_source_label`）：模拟数据的被试编号一律以
`sim_` 开头（`simulate_data.py` 生成），核对不一致就以退出码 1 中止、不写出任何产物。
被拦下的两种情形正是标注会与来源相反、而产物看不出异常的两种误用：

- **真实导出被放到默认路径** `analysis/output/simulated_data.csv` → 会被整份标成
  `【模拟数据，非真实被试结果】`（真实结果被当成演示数据）；
- **把 `simulated_data.csv` 拷到别处再用 `--data` 传入** → 会被整份标成 `【真实数据】`
  （演示数据被当成真实结果）。**因此不要复制模拟数据 CSV 再传给 `--data`**：要重跑演示，
  直接用默认路径即可；模拟数据 CSV 本身**不带**内嵌的标注列（只有五张产物表有 `数据来源` 列），
  内容侧的唯一判据就是被试编号前缀。

**已知边界：** 若数据里没有被试编号列（`participant.code` / `participant_code` 都没有），
内容无从核对，脚本会打印"无法据内容核对来源、仅由路径推断"后继续运行——此时标注是否正确
完全取决于路径。

`--data` 指向真实导出时，脚本会自动利用宽表结构完成**配对合并**（x 只在投资者行、y 只在
受托人行，故凡同时使用 x 与 y 的模型都先合并成"每对一行"再估计）。

**第 3 步：跑分析测试**（依赖第 1 步的产物；12 个用例）

```bash
/share/zrs2022150501010/miniconda3/envs/otree/bin/python -m unittest analysis.test_analyze
```

> 输出目录固定为 `analysis/output/`，脚本**没有**单独的输出目录参数。跑真实数据会覆盖
> 已有的表格与图；若要保留模拟数据的演示产物，请先备份该目录，或事后重新执行第 1、2 步
> 恢复（模拟数据脚本固定种子，产物逐字节可复现）。

---

## 8. 交付物清单

| # | 交付物 | 路径 |
|---|---|---|
| 1 | 实验报告 | `/share/zrs2022150501010/project/behavioral_experiment/实验报告.md` |
| 2 | oTree 项目代码 | `/share/zrs2022150501010/project/behavioral_experiment/trust_game/`、`survey/`、`settings.py` |
| 3 | 分析管线 | `/share/zrs2022150501010/project/behavioral_experiment/analysis/simulate_data.py`、`analysis/analyze.py` |
| 4 | 测试 | `/share/zrs2022150501010/project/behavioral_experiment/trust_game/tests.py`、`survey/tests.py`、`analysis/test_analyze.py` |
| 5 | 项目说明 | `/share/zrs2022150501010/project/behavioral_experiment/README.md`（本文件） |
| 6 | 设计规格 | `/share/zrs2022150501010/project/behavioral_experiment/docs/superpowers/specs/2026-09-13-trust-game-design.md` |
| 7 | 实施计划 | `/share/zrs2022150501010/project/behavioral_experiment/docs/superpowers/plans/2026-09-13-trust-game-implementation.md` |

测试合计：纯函数单元测试 29 个 + 分析管线守卫 12 个 + 演示模式守卫 9 个 = **50 个**（`unittest discover` 全仓）；
另有两个 config 的 oTree bot 端到端测试。页面模板 12 个（`trust_game/` 8 个 + `survey/` 4 个）。

---

## 9. 注意事项

1. **模拟数据不得当作实证结果。** 本实验**尚未招募真实被试**。`analysis/` 生成的一切数据、
   `analysis/output/` 的一切产物、`实验报告.md` 第 8 节的一切数值，都是按文献报告的效应量
   生成的**模拟数据**，用途是验证分析管线可跑通并展示产物的形状，**不构成任何关于真实
   沟通效应的证据**。报告中的模拟显著性（如 H1 的 p = 0.114）也不得被解读为设计缺陷或
   真实效应的证据；模拟数据的显著性**不是**分析管线正确性的指标。

2. **真实实验前必须设置 `OTREE_ADMIN_PASSWORD`。** `settings.py` 中
   `ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')`——未设置该环境变量时管理后台
   没有可用密码。不要把它硬编码进 `settings.py`（该文件会进版本库）：
   ```bash
   export OTREE_ADMIN_PASSWORD='<自行设置一个强口令>'
   ```
   口令只放在运行时环境里，不要写进任何代码、注释或日志。

   **同一条纪律适用于 `SECRET_KEY`。** `settings.py` 中
   `SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'dev-only-not-for-production')`：
   仓库里的那个默认值只是一个**开发占位符**，作用是让 `otree test` 与 devserver
   免配置即可跑通；它已经出现在版本库里、任何人都读得到，**不得用于正式收集数据**。
   正式部署前必须替换：
   ```bash
   export OTREE_SECRET_KEY='<自行生成一个长随机串>'
   ```
   该值参与 oTree 的 `make_hash`（`otree/common.py:125`：与 `ADMIN_PASSWORD`
   拼接后散列），而 `make_hash` 用于 room 的安全链接校验
   （`otree/room.py:109`、`otree/views/participant.py:269`）与数据导出相关的哈希
   （`otree/common.py:139`）。默认值既已公开，这层混淆在正式运行中等于不存在。

3. **正式收集数据时应设置 `OTREE_PRODUCTION=1`**，并配合 `prodserver` 而非 `devserver`：
   ```bash
   export OTREE_PRODUCTION=1
   export OTREE_ADMIN_PASSWORD='<强口令>'
   /share/zrs2022150501010/miniconda3/envs/otree/bin/otree prodserver 8000
   ```
   `OTREE_PRODUCTION=1` 会关闭调试信息与自动重载，避免泄露内部状态。
   **`prodserver` 必须跑在可写磁盘上**：它不像 `devserver` 那样强制内存库，需要真实写入
   `db.sqlite3`；在 `/share` 这个 NFS 挂载上会因 sqlite 写失败而不可用。因此正式收集数据
   请把项目复制到本地磁盘运行，或另行设置可写的 `DATABASE_URL`。

4. **远端 `origin` 是一个私有库，必须保持私有。**
   `git remote -v` 显示 `origin → https://github.com/lizao-star/otree-trust-game.git`；
   匿名访问该地址返回 404、`git ls-remote` 要求身份认证，即它是**私有**仓库。
   推送到它没有问题，但**不要把它改成公开、也不要发布到任何公开位置**——仓库内含
   实验设计、指导语全文与预注册的分析计划，**正式收集数据前公开会污染被试**。
   若将来确实需要公开，先确认数据已收集完毕。

5. **`analysis/output/` 除 `.gitkeep` 外全部被 `.gitignore` 排除。** 模拟数据、表格与图都是
   可再生产物，不随仓库分发。全新检出后该目录是空的，必须先跑第 7 节的第 1 步，否则
   `实验报告.md` 第 8.8 节的 4 张图无法显示、12 个分析测试会被跳过。

6. **本机在 NFS 挂载上，sqlite 写入失败。** 因此：
   - `otree devserver` 与 `otree test` 可以正常用（oTree 内部强制内存库）；
   - **`otree resetdb` 必须加前缀**，否则报 `sqlite3.OperationalError: disk I/O error`；
     非交互环境下还要加 `--noinput`，否则会卡在确认提示：
     ```bash
     OTREE_IN_MEMORY=1 /share/zrs2022150501010/miniconda3/envs/otree/bin/otree resetdb --noinput
     ```
   - 附带一提：`otree resetdb --help` 在本机也会崩——该子命令在解析参数前就要初始化 ORM；
   - **不要用软链接把 `db.sqlite3` 指到别处**（例如 `/tmp`）。这会让 `otree test` 的数据库
     版本检查读到不符合预期的文件从而失败。
   - 在内存库模式下，devserver 的会话数据**不落盘**，服务器一停就丢；跑数据前请先导出
     （见第 4 节）。

7. **解释器固定**：一律使用 `/share/zrs2022150501010/miniconda3/envs/otree/bin/python`，
   不要用 `python3`（系统解释器没有 oTree 及其依赖）。运行 oTree 命令前把
   `/share/zrs2022150501010/miniconda3/envs/otree/bin` 加进 `PATH`，因为 `otree devserver`
   会通过 `PATH` 重新 exec 裸 `otree`。

8. **跑 oTree 测试前先 `rm -f db.sqlite3`。** 修改 app 代码后沿用旧库，oTree 会提示
   "Please delete your database"。本机 `db.sqlite3` 常常以 0 字节形式重新出现，属正常现象
   且已被 gitignore，不需要处理。

9. **`otree test` 的参数是 session config 名，不是 app 名。** 本项目只有
   `trust_baseline` 与 `trust_communication` 两个 config，**没有** `survey` config。

10. **`analysis/__init__.py` 是有意保留的空文件。** 删掉它会让
    `python -m unittest discover -t .` **静默跳过**整个 `analysis/`（只跑 38 个而不是 50 个，
    且不给任何提示）。这是本项目最忌讳的"静默不发生"，故不要删除。

11. **演示模式（§4.1）的会话是 bot 会话，不得混进正式数据。** 演示 config（`*_bots`）
    跑出来的被试在导出里可识别、可过滤：`participant._is_bot` 为 1、`session.is_demo`
    为 1。**导出后按 `participant._is_bot == 0` 过滤**，而不是依赖「记得不要在正式库上
    跑」——devserver 会在热重载时把内存库 dump 到 `db.sqlite3`（见第 4 节末尾的补充），
    所以演示会话确实可能落到盘上。
    另注意：`/api/export_wide` 会**忽略 `code` 参数**、导出库中**全部**会话——想只看
    一个会话时必须自行按 `session.code` 筛选（本机实测：请求一个演示会话的导出，
    返回了库里全部 3 个会话的行）。
