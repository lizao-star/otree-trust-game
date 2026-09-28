# 演示模式：一键自动填写（观察流程用）

**规格文档** · 2026-09-28 · oTree 6.0.15

---

## 1. 目标

在没有真实被试的情况下，用最少的操作让**全部 8 个参与者自动完成一整轮**（`trust_game` +
`survey` 的全部页面），操作者在浏览器里并排观察页面序列，以肉眼确认：

- 页面顺序与分支是否正确（基线组没有消息页；沟通组有 `MessageSend` → `MessageReveal`）；
- 条件逻辑是否生效（`x = 0` 时受托人页无表单、`TrusteeDecision.error_message` 的动态上限等）；
- 校验与拦截是否真的在工作（理解检验答错被拒、空提交被拒）；
- 结算结果是否与 `payoffs.py` 一致。

**非目标（本规格明确不做）：**

- 不改动任何面向真实被试的页面、字段或结算逻辑；
- 不引入新的 app、不写自定义视图；
- 不追求「严格一步到位」——见 §5。

## 2. 机制：不写新逻辑，只开一个开关

oTree 6 内置的 **browser bots** 已经提供了所需的一切：

| 环节 | 位置 |
|---|---|
| 演示页创建会话时读取 config 的 `use_browser_bots` | `otree/channels/consumers.py:454-476`（`WSCreateDemoSession`，`:470` 取值） |
| 给全体 participant 打上 `is_browser_bot=True` 并装载 bot | `otree/bots/runner.py:66` `make_bots(..., use_browser_bots=True)` |
| 页面 GET 时把 bot 的下一次提交注入 HTML 并自动 submit | `otree/views/abstract.py:483` `browser_bot_stuff()`，`:501` `auto_submit_js` |
| 网格视图（一页 N 个 iframe） | `otree/views/admin.py:147` `SessionDemoGridView`；人数限额 `:207-208`，3–12 人 |

**关键点：自动填写用的 bot 就是本仓库已有的 `trust_game/tests.py` 与 `survey/tests.py`
里的 `PlayerBot`** —— 和 `otree test` 跑的是同一份脚本（`trust_game/tests.py:33`
`cases = ['normal', 'zero_send']`；`survey/tests.py:65` `cases = list(CASES)`）。

因此演示不仅会走完页面，还会**在页面上真实演出**测试脚本里刻意的失败提交
（`SubmissionMustFail`）：理解检验先提一次错答案、消息页/返款页先提一次空表单。
这恰好是「校验是否真的在拦」的现场证据。

## 3. 改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `settings.py` | 新增两个演示专用 session config：`trust_baseline_bots`、`trust_communication_bots` |
| 2 | `settings.py` | `DEMO_PAGE_INTRO_HTML` 从「信任博弈实验 — 演示」改为两步操作指引 |
| 3 | `trust_game/test_settings.py`（新增） | 守卫用例，见 §6 |
| 4 | `README.md` | 见 §3.3 —— 涉及 4 个小节，其中测试计数必须改成实测值 |

### 3.3 README 需同步的小节（逐项）

README 的目录结构、测试计数与注意事项都是**带具体数字**的陈述，改动后不同步即成为
失实陈述——本仓库对此有先例（见提交 `1622017`）。需改：

| 小节 | 改动 |
|---|---|
| §3 目录结构 | `settings.py` 行的 config 列表补两个演示 config；`trust_game/` 增列 `test_settings.py`（含用例数） |
| §4 运行实验 | 新增「演示模式：一键自动填写」子节，内容 = 本规格 §5 |
| §5 运行测试 | 全仓测试计数由 `41` 改为**实现后的实测值**，并同步「实际执行 29 个」一句 |
| §9 注意事项 | 新增 1 条（bot 会话的数据卫生，见 §7）。**追加为最后一条，不插入中间**——现有文档已有按编号的交叉引用（README 开头引用第 1 条、本规格 §4 引用第 6 条），插入会让它们全部指错 |

现有 10 条注意事项的编号**保持不变**是本项的验收条件之一。

### 3.1 新增 config 的字段（逐项）

| 字段 | 值 | 理由 |
|---|---|---|
| `name` | `trust_baseline_bots` / `trust_communication_bots` | 加 `_bots` 后缀，在 config 列表与导出里一眼可辨 |
| `display_name` | `信任博弈 — 基线组（演示·自动填写）` / `…沟通组（演示·自动填写）` | 演示页上必须与真实 config 视觉可分 |
| `app_sequence` | `['trust_game', 'survey']` | 与真实 config 一致，演示才能覆盖问卷 |
| `num_demo_participants` | `8` | 必须落在网格视图的 3–12 区间（`otree/views/admin.py:207-208`）；8 人 = 4 组 |
| `communication` | `False` / `True` | 与对应的真实 config 逐值一致 |
| `use_browser_bots` | `True` | 本规格的全部机制来源 |
| `doc` | 说明「演示专用，非真实数据」 | `doc` 会显示在管理后台的会话详情里 |

### 3.2 为什么单开 config，而不是给现有 config 加开关

`use_browser_bots=True` 一旦落到 `trust_baseline` / `trust_communication` 上，
**真实被试会被当成 bot**：页面会在渲染后被 JS 自动提交，被试还没看见题目就已经进入下一页，
而数据照样写库、`otree test` 照样全绿。这是典型的「静默失败」——错误不会报出来，
只会在收完数据后表现为一片无意义的常量。故真实 config 必须保持该键**不存在或为 False**，
并由 §6 的守卫钉死。

## 4. 已知行为与取舍

1. **case 随机。** 每次创建演示会话，oTree 从 `range(num_cases)` 中随机抽一个
   （`otree/bots/browser.py:55`，`num_cases` 由 `otree/session.py:70` 取各 app
   `PlayerBot.cases` 长度的最大值 = 2），**同一会话内 8 人同 case**。`normal` 与
   `zero_send` 两个 case 的**页面序列完全相同**，只是数值不同：`zero_send` 时投资者送 0、
   受托人页无表单。想看另一分支就重新点一次配置。
   若要固定 case，只能走 REST 接口（`otree/views/rest.py:266` `CreateBrowserBotsSession`
   接受 `case_number`）另写脚本，代价约 30 行且需要 `OTREE_REST_KEY` 与管理员登录。
   **本规格不做。**
2. **演示会话是真会话，会写数据库。** 只能在 devserver（内存库）或专门的演示库上跑，
   **不得在正式收集数据的 prodserver 上创建演示会话**。在 NFS 部署机上（README
   「注意事项」第 6 条）devserver 被 oTree 强制为内存库，演示数据不落盘、服务器一停即失，
   需要保留证据应在关闭前从 `/ExportIndex` 导出（README 第 4 节）；若在可写磁盘上跑
   devserver 或 prodserver，演示会话会**真实落库**，此时必须依赖 §7 的过滤列。
3. **建完会话后不要改代码。** devserver 会自动重载，重载会清空进程内保存 bot 的
   `browser_bot_worker`，页面随即报 `Bot for Participant ... not loaded`
   （`otree/bots/browser.py:28`）。此时重新创建会话即可。
4. **理解检验页会闪现一次「答案不正确」。** 那是 `trust_game/tests.py` 的
   `comprehension_round()` 刻意的 must-fail，属预期行为，不是缺陷。
5. **演示只覆盖已有 bot 会走的路径。** bot 覆盖不到的分支（例如真实被试的异常输入）
   不会被演示到；演示通过不等于实验无缺陷。

## 5. 操作步骤（两步，不是一步）

```bash
cd <项目根目录>
otree devserver 8000     # 解释器与绝对路径同 README 第 4 节
```

1. 打开 `http://localhost:8000/demo/`，点「信任博弈 — 基线组（演示·自动填写）」
   或「…沟通组（演示·自动填写）」；
2. 会话页 `Combined views` 一栏点 **Grid view** 的 `Launch`。

8 个 iframe 随即各自逐页自动填写，跑完 `trust_game` 后继续 `survey` 直到结束页。

**关于「一个按钮」的诚实说明：** oTree 没有暴露「创建会话后直接跳转网格视图」的钩子，
做成严格一步需要自定义视图并接管会话创建流程，与本规格 §1 的非目标冲突。两步是本方案
在零自定义逻辑前提下能达到的最短路径，故 §3 的第 2 项把这两步写进演示页右栏，
让操作者不必回来翻文档。

## 6. 守卫：`trust_game/test_settings.py`

新增一个 `unittest` 用例模块（与 `trust_game/test_payoffs.py`、`analysis/test_analyze.py`
同构，`python -m unittest discover -t .` 可发现），断言：

1. `trust_baseline`、`trust_communication` 两个真实 config 的
   `use_browser_bots` **必须为假**（缺键视为假）；
2. `trust_baseline_bots`、`trust_communication_bots` 两个演示 config 的
   `use_browser_bots` **必须为真**；
3. 每个演示 config 的 `communication` 与它对应的真实 config **逐值相等**
   （用 `is` 比较，不用真值判断——本仓库已因 `None` vs `False` 吃过一次亏）；
4. 演示 config 的 `app_sequence` 与对应真实 config 一致；
5. 两个演示 config 的 `num_demo_participants` 落在 `[3, 12]`（网格视图限额）。

守卫的**证伪性**：把任意一条改动（例如给 `trust_baseline` 加上
`use_browser_bots=True`）都必须让该模块失败。测试文件中会写明这一点。

## 7. 数据卫生

bot 会话在导出产物里**可识别、可过滤**：

| 模型 | 导出列名 | 来源 |
|---|---|---|
| Session | `session.is_demo` | `otree/export.py:73` |
| Participant | `participant._is_bot` | `otree/export.py:82` |

列名带模型前缀且 `_is_bot` **保留前导下划线**：表头由
`f'{m}.{col}'` 直接拼接（`otree/export.py:431`），不做去下划线处理
（`:134` 的 `not f.startswith('_')` 只作用于 monitor 视图的字段枚举，不影响导出）。
本仓库 `analysis/analyze.py:91-92` 已确认同类前缀命名（`participant.code`
而非 `code`）。

因此正确做法是：**导出后按 `participant._is_bot == 0` 过滤**，而不是依赖
「记得不要在正式库上跑」。README 的「注意事项」新增条目会写明这一点，并交叉引用本节。

本仓库当前的分析管线（`analysis/analyze.py`）读取的是 `analysis/output/simulated_data.csv`，
不读真实导出，故本次改动**不影响**现有分析产物，无需改动分析代码。

## 8. 验证方式

1. `python -m unittest discover -t .` —— 全仓测试通过，含 §6 新增用例；
   另**故意**给 `trust_baseline` 加上 `use_browser_bots=True`，确认新增用例失败，
   再撤销（证明守卫有效，而不是永远为真）。
2. 手动走一遍 §5 的两步，确认：
   - 8 个 iframe 都跑到 `Results` 并继续进入 `survey` 直至结束；
   - 基线组演示中**没有**消息页，沟通组演示中**有** `MessageSend` / `MessageReveal`；
   - 理解检验页确实闪现过一次「答案不正确」后通过。
3. 记录一次演示会话的导出，确认 `participant._is_bot` 对 8 人全为 1、
   `session.is_demo` 为 1（对照组：真实 config 的会话该列为 0）。

## 9. 风险

| 风险 | 处置 |
|---|---|
| 演示 config 被误用于正式收数（在正式库里点了演示配置） | `display_name` 明确标注 + §7 靠 `participant._is_bot` 过滤 + README 注意事项 |
| `use_browser_bots` 被误加到真实 config | §6 守卫 1 |
| oTree 升级后 `use_browser_bots` 的语义变化 | 本文档所有引用均带 `otree` 包内行号；升级时按 §2 表格逐条复核 |
| 演示通过被当成「实验无缺陷」的证据 | §1 非目标与 §4 第 5 条已写明；README 同步 |
