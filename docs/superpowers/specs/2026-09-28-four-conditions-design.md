# 四处理组改造（2×2 沟通方向）设计

**日期：** 2026-09-28
**范围：** 只做实验代码与测试，做到 `otree test` 与 `unittest discover` 全绿。
**不在本轮：** 实验报告的假说、功效分析、模拟结果（等真实实验后）；分析管线的四组适配（只加一道中止守卫，见 §7）。

---

## 1. 需求

1. **「你的判断」在两个组里的位置不一致** —— 已与你确认**维持现状**。事实是：两侧的逻辑位置本来就相同（都在决策之前、都是第 6 页），不一样的是它前面有什么（沟通组多出消息页）。这是当初为 H4 的中介时序刻意设计的：信念必须测在操纵之后、行为之前。四组下同理，故代码不动。
2. **四个处理组**：① 无沟通 ② 仅 B→A 单向 ③ 仅 A→B 单向 ④ 双向（同时发送）。

其中第 ④ 组就是现有的沟通组，逻辑逐字节不变。

---

## 2. 处理组表示

**唯一真值源 = session.config 的两个布尔键。**

| 键 | 含义 |
|---|---|
| `investor_sends_message` | 投资者 A 能否给受托人 B 发消息 |
| `trustee_sends_message` | 受托人 B 能否给投资者 A 发消息 |

**降范式存储**：`creating_session` 把两个键逐值写入每个 Player 的同名字段，使每份导出自带处理组标识（同现有 `is_communication` 的理由）。**删除 `is_communication` 字段**——它的语义是「任一方向有消息」，可由两列派生；留着就是第三个真值源，而 2×2 的格子该由哪两个键决定并不唯一。

**读取入口**（`trust_game/__init__.py` 内，全部唯一）：

```python
def investor_sends(player):    # A 能否发
    return player.session.config.get('investor_sends_message', False)

def trustee_sends(player):     # B 能否发
    return player.session.config.get('trustee_sends_message', False)

def sends_message(player):     # 本方是不是发送方
def receives_message(player):  # 本方是不是接收方
def any_message(player):       # 本组有没有任何消息页
```

`.get(key, False)` 是**必需**的，不是防御性写法：`trust_game/test_content.py` 的桩 config 只带报酬两个键，缺这两个键时不得报错。

---

## 3. 四个 session config

| name | display_name | `investor_sends_message` | `trustee_sends_message` |
|---|---|---|---|
| `trust_none` | 信任博弈 — 无沟通 | False | False |
| `trust_b_to_a` | 信任博弈 — 仅 B→A（承诺） | False | True |
| `trust_a_to_b` | 信任博弈 — 仅 A→B（意向） | True | False |
| `trust_both` | 信任博弈 — 双向沟通 | True | True |

各配一个 `<name>_bots` 演示 config（`use_browser_bots=True`，其余键逐值相同），共 8 个 config。演示控制台照旧按会话码工作，无需改动。

**命名变更**：`trust_baseline` → `trust_none`，`trust_communication` → `trust_both`。理由：四组下「baseline / communication」这对名字把双向当成了「有沟通」，读起来会以为另外两组没有沟通。影响面仅限 README 与实验报告里的命令与 config 列表。

---

## 4. 页面显示矩阵

| 组 | `MessageSend` | `MessageWaitPage` | `MessageReveal` |
|---|---|---|---|
| 无沟通 | 都跳过 | **跳过** | 都跳过 |
| 仅 B→A | 只有 B | 显示 | 只有 A |
| 仅 A→B | 只有 A | 显示 | 只有 B |
| 双向 | 双方 | 显示 | 双方 |

实现即三个判定：

```python
MessageSend.is_displayed       = sends_message(player)
MessageWaitPage.is_displayed   = any_message(player)
MessageReveal.is_displayed     = receives_message(player)
```

**等待页对所有人显示（不只是接收方）**，这是时序安全的关键：接收方不进 `MessageSend`，直接到等待页等；发送方提交后才放行，故接收方不可能在发送方提交前越过等待页看到消息。单向组里两人同时放行后，接收方进消息页、发送方跳过。

oTree 的 `WaitPage.inner_dispatch_group`（`otree/views/abstract.py:1059-1071`）会调 `_is_displayed()`；跳过该页的被试不参与该页的人数清点，故单向组的两条不同路径不会互相卡死。

**双向组退化为改造前的行为**：两个键都为 True 时，三个判定与原来的 `has_communication` 等价。

---

## 5. 面向被试的文案

### 5.1 `Introduction`（4 变体）

```
双向：  在做出决策之前，你与对方可以各自选择一条消息发送给对方，双方都能看到对方的消息。
发送方：在做出决策之前，你可以选择一条消息发送给对方，对方会看到这条消息；对方无法向你发送消息。
接收方：在做出决策之前，对方可以选择一条消息发送给你，你会看到这条消息；你无法向对方发送任何消息。
无沟通：整个过程中你与对方完全匿名，不会有任何信息交流。
```

**接收方那段不点名角色**（写「对方」而不是「甲方／乙方」）。原方案是点名角色、读起来更明确，但那要在 `vars_for_template` 里再存一份「甲方／乙方」的字面量——而这份字面量在模板里已经有一份，又是两处真值源：模板改了称谓而 Python 没改，被试读到的句子就会指错人。用「对方」两处都回避，且与发送方那段（同样说「对方」）结构对称。

**为什么要向接收方明说「你无法发送」**：不说明的话，单向组的接收方在等待页会以为自己的页面漏了；更重要的是，信息结构若含糊，被试对「对方能不能给我发」的不确定本身就会变成处理内变异，把操纵效应和它对冲掉。四组的信息结构都是公开知识。

模板用 `{% if %}/{% elif %}/{% else %}`。oTree 模板引擎支持 `elif` 与 `and`/`or`（`otree/templating/nodes.py:339-360`，注意**不支持括号**，`and` 优先级高于 `or`）。

### 5.2 `MessageSend`（2 变体）

```
双向：你可以选择一条消息发送给对方。对方也会选择一条消息发送给你，双方都能看到对方的选择。
单向：你可以选择一条消息发送给对方，对方会看到这条消息。对方无法向你发送消息。
```

这两种措辞与角色无关（发送方在两种单向组里的处境相同），故只按「是否双向」分支。消息集不变：A 侧仍是信任意向 0–4，B 侧仍是承诺强度 0–4。

### 5.3 `MessageReveal`

**不变**。「对方选择的消息是：……／请注意：消息不具约束力，对方没有义务遵守」在四种情形下都成立。

---

## 6. 测试

### 6.1 `trust_game/tests.py`

- 分派改为按两个 Player 字段：本方发送则 yield `MessageSend`（含一次 `SubmissionMustFail` 空提交）＋`MessageReveal`（若本方接收）。
- `check_round` 的断言改为矩阵形式：按 `sends_message` / `receives_message` 分别断言消息字段已落库或**恰好为 NULL**。
- **删除**按 config 名归一（`removesuffix('_bots')`）的那条核对。它是为了在运行时验证「config 名 ↔ 键」自洽；新分派只读键、不读名字，该失效模式随之消失，而名字↔键的一致性由 §6.2 在静态层面更早、更强地覆盖。
- **三个 case：`normal` / `miss_belief` / `zero_send`，数值不随处理组变化。**

  改造前是「基线组送 5、沟通组送 10」，于是「奖金该发 / 不该发」这两条分支靠**处理组**
  区分。四组两两组合后照旧写要维护四套期望值，且每组只覆盖一半分支。改成把分支挂到
  case 上：四个组跑同一套数值、同一套断言，**每个组都完整覆盖两条分支**（`normal` 的预测
  偏差恰好落在容差边界上得奖，`miss_belief` 超容差不给奖，`zero_send` 覆盖 x = 0 的退化
  路径）。代价是每组的运行时间从 2 个 case 变成 3 个（单 config 约 9 秒）。

### 6.2 `trust_game/test_settings.py`

单一事实表，替代原来的两 config 映射：

```python
CONDITIONS = {
    'trust_none':   (False, False),   # (investor_sends_message, trustee_sends_message)
    'trust_b_to_a': (False, True),
    'trust_a_to_b': (True, False),
    'trust_both':   (True, True),
}
```

断言：

1. `settings.py` 的 config 名集合**恰好**等于 `CONDITIONS` 的键 ∪ 各自 `+ '_bots'`（集合相等，改名的空洞已被上一轮教训堵过）。
2. 每个 config 的两个键 `assertIs` 到对应布尔值（不是真值判断——`None` 与 `False` 同形）。
3. 演示 config 与真实 config 的两个键逐值相同。

### 6.3 `trust_game/test_content.py`

- 新增：逐个渲染四种情形的 `Introduction`，断言**本情形那段话出现、另外三段不出现**。
- 新增：渲染两种 `MessageSend` 情形，断言单向版含「对方无法向你发送消息」且不含「双方都能看到」。
- 现有奖励与报酬文案断言不变（它们不依赖处理组）。

---

## 7. `analysis/` 中止守卫

`analysis/analyze.py` 的 `load()` 在 `pd.read_csv` 之后立刻检查原列名：

```python
FOUR_CONDITION_COLUMNS = ('investor_sends_message', 'trustee_sends_message')
```

宽表里这两列形如 `trust_game.1.player.investor_sends_message`，故用**子串匹配**；命中即 `SystemExit`，点名越界列，并说明这是四组数据、本管线仍是两组版本、继续跑会把四个格子静默压成两组。

**它挡的是两条路，第二条才是真正的静默失效：**

1. 真实四组导出里**没有** `is_communication` 列（四组改造已把该字段删掉），所以实际先撞上的是 `REQUIRED_FIELDS` 那条「数据缺少本管线必需的字段：is_communication……若这是单 app 导出，请改用宽表」——**两处都指错方向**：这**就是**宽表，缺的也不是导出方式。守卫早于那条检查运行，是为了让报错指向真实原因。两者都中止，差别全在报错内容上，故顺序只有测试能钉住。
2. 只要数据里**有**一列 `is_communication`（手工补的，或将来某个导出又带上它），本管线就照常算出 `treatment`，把四个格子压成两组——表照出、图照画、p 值照报，问题不以任何形式暴露。这条没有守卫时完全无声。

**一处事实更正（写实现时被自己的测试抓到）**：本规格初稿说 `_rename_otree_export` 会「静默丢掉」这两个列，是**错的**。那一步对不在 `FIELD_SOURCE` 里的列执行 `continue`，跳过的是「改名」而不是「这一列」——原列名原样留在帧里（`analysis/test_analyze.py::test_rename_step_leaves_them_untouched_but_unused` 钉住这一事实）。所以守卫放在重命名前后都查得到，放在前面纯粹是为了报错顺序。

**其余逻辑一律不动**：老的两组数据（含 `analysis/output/simulated_data.csv`）照常跑通。

### 7.1 连带修好的夹具问题

宽表夹具（`analysis/test_analyze.py::build_wide_fixture`）是**扫 app 源码**取字段名的（`app_custom_fields` 用正则抓所有 `models.XField` 定义），因此四组改造后它自动多出两个因子列、又自动少了被删掉的 `is_communication`——前者触发新守卫、后者触发缺列检查，两者都是 `SystemExit`，而 `SystemExit` 是 `BaseException`，**unittest 不捕获它**：整个测试进程在 `setUpClass` 处直接死掉，后面的用例一个都不跑，也没有 `Ran N tests` 汇总。

修法是把夹具的契约写明确：它模拟的是**本管线能消费的两组导出格式**（四组改造之前的那一版），于是明确排除两个因子列、补回 `is_communication`。并新增 `TestFourConditionExportIsRefused`（3 个用例）把守卫本身也测起来——此前没有任何测试覆盖它。

---

## 8. 数据库

Player 模型字段变了，`db.sqlite3` 的旧表结构与新模型不兼容。跑之前需 `otree resetdb` 或删除 `db.sqlite3`（当前库里只有演示会话，无真实被试数据）。

---

## 9. 实施阶段实测到的三件事

### 9.1 bot 生成器里**不许在 yield 之后读 player 属性**

`trust_game/tests.py` 的各个 round 函数是生成器：每恢复执行一次就是一次新的请求，而
**player 对象在上一次请求结束后已从 SQLAlchemy 会话脱落**，此时读它的属性会抛
`DetachedInstanceError`，表现为该页 HTTP 500、bot 卡死。

实测复现：`trust_both` 的 8 人同时推进时，`message_round` 里两处后置读取
（`player.role` 与 `receives_message(player)`）各触发过一次。改法是把本函数需要的一切
在**第一次 yield 之前**读进局部变量（角色与处理组在一次会话内不变，缓存是安全的）。

这是本次改造**自己引入**的：改造前每次都用 `bot.player.role` 重新取，恰好绕开了。
新写 round 函数时照此办理。

### 9.2 本机有两份 oTree，devserver 会挑错的那份

`otree devserver` 用 `Popen(['otree', 'devserver_inner', port])` 拉起子进程
（`otree/cli/devserver.py:38`）——**按 PATH 解析 `otree`，而不是用父进程自己**。
本机 PATH 里 `otree` 指向 `C:\Anaconda\envs\claude`，于是：

- 父进程、`otree test`：跑 `envs/otree`（正确）
- devserver 子进程：跑 `envs/claude` 那份 oTree

两份的差别是 site-packages 里那个**未入库的补丁**（见 9.3）。表现为演示会话在
`ComprehensionCheck` 上 8 人全部 HTTP 500。

**怎么起才对**：把正确的环境放到 PATH 最前，例如
`export PATH="/c/Anaconda/envs/otree/Scripts:$PATH"` 后再 `otree devserver <port>`。
验证办法：`netstat -ano | grep :<port>.*LISTENING` 拿 PID，再看
`Get-CimInstance Win32_Process -Filter "ProcessId=<PID>"` 的 CommandLine 用的是哪个 python。

### 9.3 依赖一个只存在于 site-packages 的 oTree 补丁（未入库）

`envs/otree/.../otree/views/abstract.py` 的 `Page.post` 里有一段**中文注释的补丁**：
浏览器 bot 的提交数据合并时，要把列表值（如 `error_fields`）展开成多个 `(k, v)` 对，
否则 `str(['comp_q1'])` 会变成字面量 `"['comp_q1']"`，`getlist` 拿到错误结果，页面上
直接抛 `BotError`。

**触发条件**：浏览器 bot（演示 config）＋ `SubmissionMustFail(..., error_fields=[...])`。
本仓库的 `comprehension_round` 正是这个组合。CLI bot（`otree test`）不走这条路径，所以
**测试全绿也发现不了**。

**风险**：这份补丁不在版本库里，重装 oTree 即丢失，且只打在两个环境中的一个。
三条出路，尚未定：

1. 把补丁做成本仓库的运行时补丁（例如在 `trust_game/__init__.py` 里导入时打），入库、可复现；
2. 去掉对它的依赖：`comprehension_round` 不再传 `error_fields`（`SubmissionMustFail`
   的该参数是可选的）。代价是失去「错误必须落在 `comp_q1` 这个字段上」这条断言；
3. 只写进 README 作为环境前提（最省事，也最脆）。

## 10. 考虑过但否决的方案

1. **保留 `is_communication`，再加一个方向键。** 三个键里任意两个能推出第三个，是两个真值源；且四个格子该由哪两个键决定不唯一。否决。
2. **用一个 `message_flow` 字符串枚举四值。** 把 2×2 的两个因子编码进一个字段，分析时要拆回来，拆错（例如把 `'both'` 当成只有 B 发）不会报错。否决。
3. **把「你的判断」移到消息之前。** 会破坏 H4 的中介时序——信念测在操纵之前就检验不了「承诺 → 信念 → 行为」。已与你确认维持现状。
4. **给单向组加一页「对方没有给你发消息」的提示页。** 多余：指导语已说明谁不能发，且空页会让人以为出了故障。否决。
5. **把分析管线一并改成 2×2。** 主效应与交互该怎么检验属于分析计划的决定（要等设计定稿），现在写等于替你定了。仅加中止守卫（§7）。
