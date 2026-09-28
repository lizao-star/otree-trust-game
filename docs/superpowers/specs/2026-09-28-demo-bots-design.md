# 演示模式：单步控制台（观察流程用）

**规格文档** · 2026-09-28（第 2 版）· oTree 6.0.15

> **本版推翻了同日第 1 版的设计。** 第 1 版假设「用 oTree 内置 browser bots + 网格视图
> 就能看着 8 个被试逐页填写」。实测否证：8 人 × 12 页**总耗时 2 秒**，肉眼看不到过程；
> 且第 1 版用来做单步的方案（按实例改 `_template_type`）经实测是一场**渲染顺序竞态**，
> 会把守卫泄漏给真实被试（§7.1）。第 1 版的其余结论（browser bots 机制成立、数据正确、
> 导出可识别）仍然有效，见 §2。

---

## 1. 目标

在浏览器里**逐页**观察 8 个被试走完 `trust_game` + `survey`，以肉眼确认：

- 页面顺序与分支（基线组无消息页；沟通组有 `MessageSend` → `MessageReveal`）；
- 角色分派（投资者/受托人在哪一页分开、等待页出现在哪里）；
- 校验与拦截确实生效（理解检验答错被拒、空提交被拒）；
- 结算结果与 `payoffs.py` 一致。

**硬约束（用户明示）**：守卫脚本与按钮**只对机器人页面存在**——真实被试拿到的 HTML 里
**根本不含**这段代码，不是「含但停用」。

**非目标**：不改动任何面向真实被试的页面、字段或结算逻辑；不引入新 app；不追求严格
「一键到位」（见 §5）。

## 2. 已验证的事实（本文档的据）

在 `C:\WINDOWS\TEMP` 的项目副本上实测所得，非推理：

| # | 事实 | 证据 |
|---|---|---|
| F1 | demo 路径会读取 config 的 `use_browser_bots`，把全体被试标记为 browser bot | `otree/channels/consumers.py:454-476`；实测 8 人全自动跑完 |
| F2 | **8 人 × 12 页总耗时 2 秒** | `export_page_times` 实测，8 人各 12 页、各耗时 2 秒 |
| F3 | 全程数据正确：`zero_send` 那次送 0 / 收益 10.0、0.0；`normal` 那次送 5 / 返 6 / 13.0、9.0 | 与 `trust_game/tests.py` 的期望值逐位一致 |
| F4 | 逐人逐页序列正确：投资者走 `InvestorDecision`，受托人走 `DecisionWaitPage → TrusteeDecision`；基线组无 `MessageSend`/`MessageReveal` | `export_page_times` 实测 |
| F5 | 导出列 `participant._is_bot` = 1、`session.is_demo` = 1 | `/api/export_wide` 实测 |
| F6 | `/api/export_wide?code=X` **忽略 code 参数**，导出库中**全部**会话 | 实测：返回了 3 个会话的行 |
| F7 | 网格视图 8 人 = 4 列 × 2 行，1600px 视口下每个 iframe 400×450 | 实测 |
| F8 | oTree 注入的自动提交脚本每次报 `TypeError: form.on is not a function`（约 116 条/次） | 控制台实测；是 oTree 自身缺陷（`form.submit()` 已先执行），无害 |
| F9 | 覆盖 `HTMLFormElement.prototype.submit` 与 `.on` 能让自动提交失效，页面停住等按钮 | 实测：8 个 iframe 全停在 `Introduction` |
| F10 | 点击能推进：一次点击 8 人齐步走一页 | 实测：`Introduction → ComprehensionCheck → BeliefElicit/InvestorDecision → ResultsWaitPage/TrusteeDecision → Results → survey` |
| F11 | 点击前必须 `form.noValidate = true`，否则被 HTML5 校验挡下（机器人答案在服务端排队，不预填在表单里，字段是 `required` 且空的） | 实测：不设时点击无效、卡死 |
| F12 | 点击前必须解除按钮禁用，oTree 每次提交后禁用 `.otree-btn-next` 5000ms | `otree/static/otree/js/common_user_facing.js:26-38`；实测 2.5s 间隔点击无效 |
| F13 | 提交按钮是 `<button class="otree-btn-next btn btn-primary">下一页</button>`，**无 `type` 属性**（默认即 submit） | 实测 DOM |
| F14 | **devserver 每次热重载都会把内存库 dump 到 `db.sqlite3`**：`otree/cli/devserver.py:65` 在文件变化时 POST `/SaveDB`，`otree/views/admin.py:633-644` 调 `save_sqlite_db()`，后者在 `IN_MEMORY` 时执行 `sqlite_mem_conn.backup(sqlite_disk_conn)`（`otree/database.py:163-175`），且 `_dumped` 保证每进程只 dump 一次。实测：跑 devserver 期间改文件 → 库变成 168 KB 且含全部演示会话；不改文件 → 恒 0 字节 |
| F15 | 沟通组演示会话在 `trust_game` 结束时 **HTTP 500** | 实测：`tests.py` 的 `check_round` 用 config **名**精确匹配 `'trust_communication'`，`trust_communication_bots` 落进 else 分支、被要求 `is_communication` 为假。已修（见 §11） |

## 3. 机制

### 3.1 让机器人页面停下来

oTree 在每个页面末尾追加一段自动提交脚本（`otree/views/abstract.py:501-513`）：

```js
var form = document.querySelector('#form');
form.submit();                                  // ← 就是这行让机器人一路狂奔
form.on('submit', function (e) { ... });        // ← 必崩（jQuery 方法），但在 submit 之后
```

守卫脚本（F9）把这两个方法覆盖成空操作。**人类点击页面上的「下一页」走的是原生表单提交，
不经过 `HTMLFormElement.prototype.submit`，因此照常工作**；而机器人下一次要提交的答案，
在页面被 GET 时**服务端就已排队**（`otree/views/abstract.py:494`），所以点下去用的就是
机器人的答案。

### 3.2 守卫如何只出现在机器人页面（本版的关键修正）

**不能**按实例改 `_template_type` —— 见 §7.1，那是渲染顺序竞态。
守卫必须放在**模板渲染时**判断，渲染缓存才无关：

```
_templates/otree/Page.html
    {% block global_scripts %}
    {% if is_defined('player') and player.participant.is_browser_bot %}
      {% include 'bot_step_guard.html' %}
    {% endif %}
    {% endblock %}
```

`_templates/` 在模板搜索路径中**先于** oTree 自带模板（`otree/templating/loader.py:63-67`），
故该副本会覆盖内置的 `otree/Page.html`；应用页模板会自动 `extends` 它
（`otree/templating/template.py:16-22`）。真实被试的 `is_browser_bot` 为假 → 守卫
**不出现在 HTML 里**，满足 §1 的硬约束。

### 3.3 控制台

`_static/global/step_console.html?code=<会话码>`，一个自建静态页（我们完全拥有，
不覆盖任何 oTree 模板）：

1. 从 `/SessionStartLinks/<code>` 取 8 个被试链接（演示模式下该页免登录，
   `otree/urls.py` 的 `UNRESTRICTED_IN_DEMO_MODE`）；
2. 每个被试一个 iframe + 当前页名 + 单独的「前进」按钮；
3. 一个「**全部前进一页**」按钮（主操作）：对每个 iframe 依次
   `form.noValidate = true` → 解除按钮禁用（F12）→ 点击提交；
4. 一个「**连续跑完**」按钮：由控制台以 `setInterval` 反复点击驱动，直到 8 人都到
   `OutOfRangeNotification`（每帧最小点击间隔 600ms、上限 150 次，再按一次可停止）。

> **控制台不是守卫的前提。** 守卫在 bot 页面上**无条件生效**（§13），所以从会话页的
> Grid view、split-screen 或单个被试链接打开同样会停下来等人点——控制台只是把
> 「一次点 8 个」和「连着点」包成了按钮。第 2 版曾用 `sessionStorage` 做 opt-in，
> 已被否证，见 §13。

## 4. 文件清单

| # | 文件 | 类型 | 内容 |
|---|---|---|---|
| 1 | `settings.py` | 改 | 新增 `trust_baseline_bots` / `trust_communication_bots` 两个演示 config（`use_browser_bots=True`、`num_demo_participants=8`、`display_name` 标「演示·单步」）；`DEMO_PAGE_INTRO_HTML` 改成操作指引 |
| 2 | `_templates/otree/Page.html` | 新增 | oTree `Page.html` 的副本 + §3.2 那段 `global_scripts` |
| 3 | `_templates/bot_step_guard.html` | 新增 | 守卫 JS，唯一真值来源 |
| 4 | `_static/global/step_console.html` | 新增 | 控制台页 |
| 5 | `trust_game/test_settings.py` | 新增 | session config 守卫（§6.1） |
| 6 | `trust_game/test_demo_templates.py` | 新增 | 模板副本漂移守卫 + 门控条件 + 无条件生效（§6.2） |
| 7 | `README.md` | 改 | 见 §8 |

### 4.1 演示 config 的字段

| 字段 | 值 | 理由 |
|---|---|---|
| `name` | `trust_baseline_bots` / `trust_communication_bots` | `_bots` 后缀，在 config 列表与导出里一眼可辨 |
| `display_name` | `信任博弈 — 基线组（演示·单步）` / `…沟通组（演示·单步）` | 演示页上必须与真实 config 视觉可分 |
| `app_sequence` | `['trust_game', 'survey']` | 与真实 config 一致 |
| `num_demo_participants` | `8` | 网格视图限额 3–12（`otree/views/admin.py:207-208`）；8 人 = 4 组 |
| `communication` | `False` / `True` | 与对应真实 config 逐值一致 |
| `use_browser_bots` | `True` | 全部机制来源 |
| `doc` | 「演示专用，非真实数据」 | 显示在管理后台会话详情 |

### 4.2 为什么单开 config

`use_browser_bots=True` 一旦落到真实 config 上，**真实被试会被当成 bot**：页面渲染后
被 JS 自动提交，被试还没看见题目就翻页，而数据照样写库、`otree test` 照样全绿。
由 §6.1 的守卫钉死。

## 5. 操作步骤

```bash
cd <项目根目录>
otree devserver 8000
```

1. 打开 `http://localhost:8000/demo/`，点「信任博弈 — 基线组（演示·单步）」；
2. 从会话页地址栏复制会话码（`/SessionStartLinks/<code>` 里那一段）；
3. 打开 `http://localhost:8000/static/global/step_console.html?code=<code>`；
4. 按「全部前进一页」——**按一次，8 人各填一页**；页面上直接看角色分叉、等待页、
   校验报错。

## 6. 守卫

### 6.1 `trust_game/test_settings.py`（session config）

按文件路径 `importlib` 加载 `settings.py`（不依赖 CWD、不往 `sys.modules` 塞同名模块），
断言：

1. `trust_baseline`、`trust_communication` 的 `use_browser_bots` **必须为假**（缺键视为假，
   用 `assertIs(..., False)` 而非真值判断）；
2. 两个演示 config 的 `use_browser_bots` **必须为真**；
3. 每个演示 config 的 `communication` 与对应真实 config **逐值相等**（`is` 比较）；
4. 演示 config 的 `app_sequence` 与对应真实 config 一致；
5. 两个演示 config 的 `num_demo_participants` 落在 `[3, 12]`（从
   `otree.views.admin` 导入 `GRID_LOWER_LIMIT`/`GRID_UPPER_LIMIT`，不写死字面量）。

### 6.2 `trust_game/test_demo_templates.py`

1. **漂移守卫**：逐字节比对 `_templates/otree/Page.html` 与
   `otree/templates/otree/Page.html`，断言二者差异**只有** §3.2 新增的那段
   `global_scripts` 块。差异超出预期即失败——这样 oTree 升级导致副本过时会**响**，
   而不是静默沿用旧行为。
2. **守卫的准入条件是 `is_browser_bot`**：断言 `_templates/otree/Page.html` 里那段
   `{% if %}` 的条件文本包含 `is_browser_bot`。这是 §1 硬约束的第一道证据——
   条件一旦被改成恒真或改成别的字段，本用例失败。
3. **守卫是无条件的**：断言 `_templates/bot_step_guard.html` 与
   `_static/global/step_console.html` 里都**没有 `sessionStorage.` 调用**。
   重新引入 opt-in 开关等于把「Grid view 静默变回 2 秒跑完」这条路打开，见 §13。

> 第 2 版这里是「断言两处 `sessionStorage` 键名逐字相同」。该用例随开关一起删除——
> 它守的东西已不存在，而它守不住的正是真正的故障（见 §13）。

### 6.3 证伪性

每条守卫都必须**能被改坏**：把 `use_browser_bots=True` 加到 `trust_baseline`、把
`_templates/otree/Page.html` 与 oTree 版的差异改成别的、把守卫的准入条件改成恒真、
把演示 config 改成不符合命名约定、给守卫或控制台重新引入 `sessionStorage.` 调用——
都必须让对应用例失败。实现时会逐条做变异探针并记录。

## 7. 已否证的做法（留档，避免重走）

### 7.1 按实例改 `_template_type`（第 1 版方案）——已否证

思路是让页面在 `player.participant.is_browser_bot` 时解析到 `otree/StepPage.html`。
**不可行**：`FileLoader.load()` 的缓存**只以文件名为键、忽略 `template_type`**
（`otree/templating/loader.py:18-24`），因此**一个页面文件在进程内第一次被渲染时用什么
模板，之后所有会话都跟着用**。实测两个方向：

| 先渲染 | 真实被试页 | bot 页 |
|---|---|---|
| 真实会话 | 无守卫 ✓ | **无守卫** ✗ 单步失效 |
| bot 会话 | **有守卫** ✗ 泄漏给真人 | 有守卫 ✓ |

两种结果必然错一个，且**不报错**。故舍弃。

### 7.2 网络节流放慢（曾考虑）——不可靠

CDP `Network.emulateNetworkConditions` 只能把 2 秒拉到 4.2 秒（温和参数）或 14.1 秒
（20KB/s + 1s 延迟）。要靠它把 12 页拉长到可观察需要极端参数，且需额外安装 playwright
（本机 `C:\Anaconda\envs\otree` 未安装）。**单步控制台完全取代了这个需求。**

### 7.3 运行时 monkey-patch `browser_bot_stuff`（曾考虑）——未采用

可做到零模板改动、且按代码路径天然只为 bot 生效，但需要在运行时改 oTree 内部逻辑，
并依赖其内部标记字符串。爆炸半径大于 §4 的模板副本方案，故不采用。

## 8. README 需同步的小节

README 的目录结构、测试计数与注意事项都是**带具体数字**的陈述，改动后不同步即成为
失实陈述（本仓库有先例：提交 `1622017`）。

| 小节 | 改动 |
|---|---|
| §3 目录结构 | `settings.py` 行补两个演示 config；新增 `_templates/`、`_static/global/step_console.html`；`trust_game/` 增列两个新测试文件（含用例数） |
| §4 运行实验 | 新增「演示模式：单步控制台」子节 = 本规格 §5 |
| §5 运行测试 | 全仓测试计数改为**实现后的实测值**（当前为 41；同步「实际执行 29 个」一句） |
| §9 注意事项 | 新增 1 条（bot 会话的数据卫生，见本文档 §9）。**追加为最后一条**，现有 10 条编号不变——README 开头引用「注意事项第 1 条」、本文档 §9 引用「第 6 条」，插入会让这些交叉引用全部指错 |

## 9. 数据卫生与已知行为

| 项 | 说明 |
|---|---|
| 导出可过滤 | `session.is_demo`、`participant._is_bot`（F5） |
| `/api/export_wide` 忽略 code（F6） | 只想看一个演示会话时，返回的是**全库**；必须按列自行筛选。README 写明 |
| 控制台报错（F8） | oTree 自身缺陷，约 116 条/次，无害；README 写明以免被误当故障 |
| case 随机 | 每次创建演示会话随机抽 `normal` 或 `zero_send`（`otree/bots/browser.py:55`，同一会话内 8 人同 case）。两者**页面序列相同**，仅数值不同（`zero_send` 时送 0、受托人页无表单）。想看另一分支重新点一次配置。要固定 case 需走 REST（`otree/views/rest.py:266` 接受 `case_number`）另写脚本，**本规格不做** |
| 改用 devserver 前不要改代码 | devserver 自动重载会清空进程内的 `browser_bot_worker`，页面报 `Bot for Participant ... not loaded`（`otree/bots/browser.py:28`） |
| 演示会话会写库 | devserver 运行期间用的是内存库，但**每次热重载都会把它 dump 到 `db.sqlite3`**——实测触发路径见 §2 的 F14。故不得依赖「devserver 不落盘」，一律靠 §9 的列过滤 |
| `/SessionStartLinks` 需可访问 | 控制台靠它取被试链接。演示模式下该页免登录（`otree/urls.py` 的 `UNRESTRICTED_IN_DEMO_MODE`）；`OTREE_PRODUCTION=1` 后需管理员登录，属预期 |
| 覆盖范围有限 | 演示只覆盖 bot 会走的路径；**演示通过 ≠ 实验无缺陷** |

## 10. 验证方式

1. `python -m unittest discover -t .` 全绿，含 §6 新增用例。
2. **变异探针**（每条守卫都要看到它变红，再撤销）：见 §6.3。
3. 端到端：走完 §5 的四步，确认
   - 「全部前进一页」每按一次，8 个 iframe 各前进一页；
   - 第 3 步左右能看到角色分叉（4 个到 `InvestorDecision`、4 个到 `BeliefElicit`）；
   - 理解检验页出现「答案不正确」后，下一次点击才通过（那是 `tests.py` 刻意的
     must-fail，属预期）；
   - 基线组演示中**没有**消息页，沟通组演示中**有**；
   - 「连续跑完」能在 2 秒内跑完全部 12 页。
4. **硬约束回归（最重要）**：新建一个**真实** config 的会话，取其任一被试页面 HTML，
   断言其中**不含** `HTMLFormElement.prototype.submit`、不含 `otree_bot_step`。
   此项是对 §1 硬约束的直接证据。

### 10.1 实施结果（2026-09-28 全部执行完毕）

| 验证项 | 结果 |
|---|---|
| §10.1 `unittest discover` | 50 个全绿（41 → 50：config 守卫 6 + 模板守卫 3） |
| §10.2 变异探针 | 6 条全部命中正确用例，撤销后全绿（见 §6.3 与 §11） |
| §10.3 基线组单步 6 步 | `Introduction → ComprehensionCheck（先拒后过）→ BeliefElicit → 角色分叉 → 等待页 → Results` |
| §10.3 沟通组单步 | 出现 `MessageSend`（含空提交被拒）与 `MessageReveal` |
| §10.3「连续跑完」 | 两组均 8 人全部到 `OutOfRangeNotification`，无 500 |
| §10.4 硬约束回归 | 真实被试页不含守卫 JS、不含键名、不含守卫注释 |
| `otree test` 不回归 | 两个真实 config 各 2 个 case 全部 `Bots completed session` |

**实施期发现的计划外缺陷**：见 §11（沟通组演示会话 500）。

## 11. 实施期新增：沟通组演示会话的 500（F15）

**这是计划外发现的既有缺陷，由本功能暴露。**

`trust_game/tests.py` 的 `check_round` 用 config **名**做一次「名字 ↔
`communication` 键」的交叉核对：

```python
if player.session.config['name'] == 'trust_communication':   # 精确匹配
    expect(is_comm, True)
else:
    expect(is_comm, False)
```

新加的 `trust_communication_bots` 不等于 `'trust_communication'`，于是落进 `else`
分支、被要求 `is_communication` 为假——而它正确地为真，于是 bot 断言炸出 500，
**沟通组的演示会话在 `trust_game` 结束时卡死**。基线组侥幸躲过（`else` 分支的期望
恰好与基线相符），所以问题只在沟通组显现。

**修法**：先归一再比对，保住这条独立核对：

```python
if player.session.config['name'].removesuffix('_bots') == 'trust_communication':
```

配套守卫 `test_settings.py::test_demo_config_names_follow_the_bots_suffix_convention`
把「演示 config 名 = 对应真实 config 名 + `_bots`」变成受测断言。

**守卫写法的返工**（留档）：初版写成「逐个检查以 `_bots` 结尾的名字，断言其去后缀后
是一个已存在的 config」。变异探针实测发现它有空洞——把 config 改名成
`trust_communication_bots_v2` 之后，它不再以 `_bots` 结尾，**根本不会进入被检查的
集合**，测试照样全绿。改为断言**集合相等**（`{以 _bots 结尾的名字} ==
set(REAL_TO_DEMO.values())`）后，改名与少登记都会失败。

**教训**：变异探针的价值正在于此——初版守卫「看起来在守」，实测证明它什么都没守。
只写守卫、不做探针，等于把一个空洞当成保险。

## 12. 实施期新增：`analysis/test_analyze.py` 漏了一个 skip 守卫

**同样是计划外发现的既有缺陷。**

同步 README 测试计数时实测发现：`analysis/output/simulated_data.csv` 不存在时
（全新检出的常态），`python -m unittest discover -t .` 的实际输出是

```
Ran 44 tests ... FAILED (errors=1, skipped=6)     退出码 1
```

而 README 与 `analysis/test_analyze.py` 自己的 docstring 都说「这 12 个用例会**跳过**
并打印原因（不是静默跳过）」。

根因：该文件只有第一个类带 `@unittest.skipUnless(os.path.exists(DATA_PATH), ...)`
（`analysis/test_analyze.py:155`）；第二个类 `TestSourceLabelBackstop`（原 `:263`）
**没有**，其 `setUpClass` 无条件 `pd.read_csv(DATA_PATH)` → `FileNotFoundError` → ERROR。
查该文件全部历史（两个提交）：`skipUnless` **始终只出现 1 次**，故这是文档与代码
从一开始就对不上，不是本次改动引入的。

**修法**：给 `TestSourceLabelBackstop` 补上同样的 `@unittest.skipUnless`（正是该文件
声明的意图）。修复后实测：

| 情形 | 输出 | 退出码 |
|---|---|---|
| 有 csv | `Ran 50 tests ... OK` | 0 |
| 无 csv | `Ran 50 tests ... OK (skipped=12)` | 0 |

即 README 原本的描述结构重新成立，只是数字要同步为 50 / 38。
`实验报告.md` 的三处计数（§6.1 目录清单、§6.5 测试、附录运行命令）同步更新。

## 13. 实施后返工：守卫改为无条件生效（用户实测踩到）

**这是用户实际使用后报告的缺陷，不是推断出来的。**

### 13.1 现象与根因

用户点开演示配置、在会话页按了 **Grid view** 的 Launch，结果 8 个机器人**2 秒跑完**，
完全没有停下来等点击；而按 §4 的步骤走控制台则一切正常。

根因：守卫的生效被做成 **opt-in** —— 它读一个 `sessionStorage` 标志，而**只有控制台页
会去设它**。于是：

| 打开方式 | 标志存在？ | 结果 |
|---|---|---|
| 单步控制台（`step_console.html?code=`） | 有 | 停下等点击 ✓ |
| 会话页的 **Grid view** / split-screen | **无** | **2 秒跑完** ✗ |
| 单个被试链接 / session-wide 链接 | **无** | **2 秒跑完** ✗ |

更糟的是该标志在同一标签页里**粘住**：同一个 URL 的行为取决于此前在这个标签页里访问过
什么。首次复现失败正是被这个特性骗过——先开过控制台，于是 Grid view「看起来正常」。

**设计错误在于**：把「停下来」做成 opt-in，等于让最自然的操作路径（会话页上最显眼的
那两个按钮）恰好绕过它，而且绕过时**不报错、不提示**，只表现为「跑得很快」。

### 13.2 修法：删掉开关

守卫改为**在 bot 页面上无条件生效**（`_templates/bot_step_guard.html` 不再读任何存储）。
于是**任何入口**打开 bot 页面都会停下来等人点「下一页」。这消灭的是整类故障：
不再有「开关没设 → 静默变成自动跑完」这种失败模式，因为不再有开关。

「连续跑完」相应改为**由控制台反复点击驱动**（`setInterval` + 每帧 600ms 的最小点击
间隔 + 150 次上限），不再依赖「撤掉开关」这一副作用——那个副作用本身还是个缺陷：
它删掉标志且不恢复，按过之后同标签页里「全部前进一页」就永久失效了。

**代价一条**（写入 README §4.1）：`otree browser_bots` 命令行启动器会挂住——它等被试
跑完的完成信号，而现在被试永远等你去点。本项目不使用该启动器（它需要额外的 `ws4py`
与 Chrome 拉起的独立工作流）。

### 13.3 守卫与验证的同步调整

- 新增回归用例 `test_demo_templates.py::TestGuardIsUnconditional`：守卫与控制台里
  **不得出现 `sessionStorage.` 调用**。加了它就等于把这条故障重新打开。
  （断言匹配带点的调用写法 `sessionStorage.`，不匹配光秃秃的关键词——两份文件里都有
  「为什么不能用它」的注释，散文不该让用例变红。）
- 原 `TestStepStorageKey`（断言两处键名一致）随开关一起删除——它守的东西已不存在。
- **验证方式的教训**：§10.3 只按文档路径测了控制台，漏掉了会话页上更显眼的 Grid view。
  返工后改为**逐个入口验证**：控制台、Grid view、单个被试链接，一个不落；「所有入口
  都会停下」现在是硬性验收项，而不是「控制台能用就行」。
