# 沟通对信任与可信度的影响：一项信任博弈实验

**规格文档** · 2026-09-13 · oTree 6.0.15

---

## 1. 研究问题

事前沟通（cheap talk）能否提升信任水平与可信度？若有效，其作用机制是否通过改变**信念**实现？

本实验采用 Berg, Dickhaut & McCabe (1995) 投资博弈范式，设置沟通与基线两个被试间处理组，检验沟通对信任行为、可信度行为的影响，并通过信念引出检验 Charness & Dufwenberg (2006) 提出的"沟通—信念—行为"机制。

## 2. 理论基础

**信任博弈的结构性背离。** 该博弈的社会最优（A 送出全部禀赋，B 均分收益）与子博弈完美均衡（B 返还零，A 逆推后送出零）之间存在巨大差距。实际观测通常落在两者之间，这一"过度信任"与"过度互惠"现象是行为经济学的核心谜题之一。

**沟通的作用机制。** Charness & Dufwenberg (2006) 提出，沟通并非简单地传递信息，而是通过改变**二阶信念**起作用：当 B 作出承诺后，A 对 B 返还行为的预期上升；同时 B 因承诺产生内疚厌恶（guilt aversion），违约的心理成本使其更倾向履约。该机制预测沟通效应部分由信念中介——这是本实验 H4 的直接来源。

## 3. 假说

| 编号 | 内容 | 预期方向 | 检验方式 |
|---|---|---|---|
| **H1** | 沟通组投资者送出金额更高（信任↑） | x_T > x_C | 独立样本 t 检验 |
| **H2** | 沟通组受托人返还比例更高（可信度↑） | ratio_T > ratio_C | 独立样本 t 检验 |
| **H3** | 控制 x 后，沟通对 y 仍有直接效应 | β_treat > 0 | OLS: y ~ treat + x |
| **H4** | 沟通效应部分由信念中介 | 间接效应显著 | 中介分析（bootstrap） |
| **H5** | 承诺强度与返还比例正相关 | ρ > 0 | 相关分析 / 回归 |

**多重比较控制：** 主结果变量预注册为 **x**（H1），其余为次要结果。次要结果的 p 值需报告并说明未做校正，或采用 Benjamini-Hochberg 校正。

## 4. 实验设计

**设计类型：** 2（沟通：有 / 无）× 被试间，个体随机分配

| 条件 | 名称 | 操纵 |
|---|---|---|
| 基线组 (C) | `trust_baseline` | 标准信任博弈，全程匿名，无任何沟通 |
| 沟通组 (T) | `trust_communication` | 双方在决策前同时发送预设消息，互相可见 |

**随机化：** 通过建立多个 session 实现，每个 session 只运行一种条件。**不采用 session 内随机化**——同一实验室内两组被试可能产生交流污染。

## 5. 博弈结构与收益函数

### 5.1 参数

| 参数 | 取值 |
|---|---|
| 禀赋 E | 10 点 |
| 乘子 m | 3 |
| 投资者决策 x | 整数，0 ≤ x ≤ 10 |
| 受托人决策 y | 整数，0 ≤ y ≤ 3x |

### 5.2 时序与收益

```
A 获得禀赋 10 点
      ↓
A 选择送出 x 点（0 ≤ x ≤ 10）
      ↓
实验者执行乘子：B 收到 3x 点
      ↓
B 选择返还 y 点（0 ≤ y ≤ 3x）
      ↓
收益结算：  A = 10 − x + y
            B = 3x − y
```

**总额守恒验证：** 总额 = (10 − x + y) + (3x − y) = 10 + 2x。x=10 时总额 30，均分各 15（对应 y=15）。

**关键性质：**
- 社会最优：x=10，总额 30，双方各 15
- 子博弈完美均衡：B 返还 y=0 → A 逆推后选择 x=0
- **B 无独立禀赋**——若 A 送出 0，B 收益为 0。这是 Berg et al. 原始设计的组成部分，构成 B 的履约压力来源

### 5.3 派生变量

```
return_ratio = y / (3x)    若 x > 0
return_ratio = 0           若 x = 0（约定：此时 B 无可返还，实际返还必为 0）
```

该约定使 x=0 时的信念奖金判定保持自洽：A 若报告预期返还 0%，即为正确。

## 6. 沟通操纵

### 6.1 时序

双方**同时**发送消息 → 等待双方完成 → **互相可见** → 各自决策。

此设计确保：B 的承诺在 A 决定 x 之前已被 A 看到（H1 的操纵有效性前提），A 的意向在 B 决定 y 之前已被 B 看到（H2 的操纵有效性前提）。

### 6.2 消息选项（预设）

**投资者 A 发送给 B——信任意向（编码 0–4）：**

| 编码 | 文案 |
|---|---|
| 4 | 我打算把全部 10 点都送给你 |
| 3 | 我打算送出大部分点数 |
| 2 | 我打算送出一部分点数 |
| 1 | 我打算只送出很少的点数 |
| 0 | 我还没有决定 |

**受托人 B 发送给 A——承诺强度（编码 0–4）：**

| 编码 | 文案 |
|---|---|
| 4 | 我承诺会把收到的点数全部返还给你 |
| 3 | 我承诺会返还一半以上 |
| 2 | 我承诺会返还一部分 |
| 1 | 我不确定会不会返还 |
| 0 | 我还没有决定 |

**两侧量表对称：** `investor_message_strength` 与 `promise_strength` 均为 **0–4** 序数编码，便于直接比较与合并建模。

**实现说明：** 两个角色使用**不同字段**（`message_investor` / `message_trustee`），通过 `Page.get_form_fields(player)` 按角色返回对应字段。两个强度变量由各自的消息字段在 `before_next_page` 中映射得到。

## 7. 信念引出

| 角色 | 引出内容 | 字段 | 取值范围 |
|---|---|---|---|
| A | 预期 B 会返还的比例 | `belief_return_pct` | 0–100 整数 |
| B | 预期 A 会送出的金额 | `belief_investor_send` | 0–10 整数 |

**引出时点：** 处理组在消息展示之后、决策之前；基线组在理解检验之后、决策之前。保证信念测量在操纵之后、行为之前，满足中介分析时序要求。

**激励方式（A 侧）：** 区间计分。若 `|belief_return_pct − return_ratio×100| ≤ 10`，奖励 2 点，否则 0 点。

**奖金归属：** `belief_bonus` **仅计入投资者 A 的收益**，在 `ResultsWaitPage.after_all_players_arrive` 中与博弈收益一并结算。受托人 B 的 `belief_bonus` 恒为 0。

**B 侧信念不设激励**，作为次要测量使用。

## 8. 页面流程规格

### 8.1 完整流程

| # | 页面类 | 投资者 A | 受托人 B | 基线组 | 关键逻辑 |
|---|---|---|---|---|---|
| 1 | `Introduction` | 阅读角色说明 | 阅读角色说明 | 相同 | 显示角色专属指导语 |
| 2 | `ComprehensionCheck` | 3 题理解检验 | 3 题理解检验 | 相同 | 须全对；否则 `error_message` 拦截并累计尝试次数 |
| 3 | `MessageSend` | 选择消息 | 选择消息 | **跳过** | `is_displayed` 读 config |
| 4 | `MessageWaitPage` | 等待 | 等待 | **跳过** | 等待双方完成 |
| 5 | `MessageReveal` | 查看 B 的承诺 | 查看 A 的意向 | **跳过** | 只读展示 |
| 6 | `BeliefElicit` | 报告返还比例 | 报告预期送出额 | 相同 | 表单输入 |
| 7 | `InvestorDecision` | **选择 x** | 跳过 | 相同 | `is_displayed` 限 A |
| 8 | `DecisionWaitPage` | 等待 | 等待 | 相同 | 等待 A 完成 |
| 9 | `TrusteeDecision` | 跳过 | **选择 y** | 相同 | `is_displayed` 限 B |
| 10 | `ResultsWaitPage` | 结算收益 | 结算收益 | 相同 | `after_all_players_arrive` |
| 11 | `Results` | 查看结果 | 查看结果 | 相同 | 显示本人收益 |

### 8.2 页面跳过机制

页面 3–5 由统一的条件函数控制：

```python
def has_communication(player):
    return player.session.config.get('communication', False)
```

**注意：** 页面 7、9 的角色跳过与处理组跳过是**两个独立维度**，不可合并判断。

### 8.3 x = 0 的边界处理

当 A 选择 x=0 时，3x=0，B 的可返还集合为 `{0}`，形成退化表单。处理方式：`TrusteeDecision` 页面检测 `3x == 0`，显示说明文字"对方没有送出点数，您没有可返还的金额"，并将 y 自动设为 0，不渲染表单控件。

**注意：** 此时 B 的收益为 0（B 无独立禀赋），页面须明确告知，避免被试误以为获得正收益。

### 8.4 可空字段的判空要求（实现阶段实测补充）

oTree 的 `blank=True` 会使表单字段**非必填**，且 wtforms_sqlalchemy 对可空列追加的 `Optional()` 会擦除空输入的处理错误——空值以 `None` 正常落库、表单不报错，直到下游读取时才抛 `NullFieldError`（HTTP 500，被试卡死且该组收益无法结算）。

实现阶段已两次触发该失效（`MessageSend` 的消息字段、`TrusteeDecision.return_amount`），后者在**清空数字输入框**这一普通操作下即可复现。

**要求：每个可空字段必须满足其一——**

1. 由本页 `error_message` 拦截空值并给出中文提示；或
2. 在每一个下游读取点用 `field_maybe_none()` 判空。

**并在 Bot 测试中以 `SubmissionMustFail(Page, {}, check_html=False)` 覆盖空提交路径。** 注意：边界值用例（如 x=0）**不能**替代空提交用例——二者路径不同，前者无法发现此类缺陷。

## 9. 数据模型

### 9.1 `trust_game` app — Player 字段

| 字段名 | 类型 | 说明 |
|---|---|---|
| `is_communication` | BooleanField | **处理组标识**，1=沟通组，0=基线组 |
| `message_investor` | StringField(choices) | A 的信任意向消息 |
| `message_trustee` | StringField(choices) | B 的承诺消息 |
| `investor_message_strength` | IntegerField(0–4) | A 消息编码（派生） |
| `promise_strength` | IntegerField(0–4) | B 承诺编码（派生） |
| `belief_return_pct` | IntegerField(0–100) | A 的返还比例预期 |
| `belief_investor_send` | IntegerField(0–10) | B 对 A 送出额的预期 |
| `send_amount` | IntegerField(0–10) | x |
| `return_amount` | IntegerField(0–30) | y |
| `return_ratio` | FloatField | y/(3x)，x=0 时为 0 |
| `comprehension_attempts` | IntegerField | 理解检验尝试次数 |
| `belief_bonus` | IntegerField | 信念奖金 0 或 2（仅 A） |

### 9.2 `survey` app — Player 字段

| 字段名 | 类型 | 说明 |
|---|---|---|
| `risk_choice` | IntegerField(1–6) | 辉奖券选项，序数 |
| `dictator_give` | IntegerField(0–10) | 独裁者博弈送出额 |
| `general_trust` | IntegerField(0–10) | 一般信任量表 |
| `gender` / `age` / `grade` / `major` | — | 人口学 |
| `econ_courses` | IntegerField | 已修经济学课程数 |
| `prior_experience` | BooleanField | 是否参加过类似实验 |

### 9.3 处理组标识（降范式存储）

`session.config['communication']` 是处理组的**权威来源**，但**同时写入** `Player.is_communication` 字段。

**赋值方式（⚠️ oTree 6 实测约束，写错会导致字段恒为 NULL）：** 必须写成**模块级函数** `def creating_session(subsession):`，**不能**写成 `Subsession` 的实例方法。

oTree 6 的调用链为：`common.is_noself(app)` 判定 `__init__.py` 含 `"import"` 时为真 → `Subsession.get_user_defined_target()` 返回**模块**而非类（`database.py:706-707`）→ `run_creating_session_functions` 执行 `getattr(模块, 'creating_session')`（`session.py:453`）。若定义在类上，`getattr` 返回 `None`，函数被静默跳过。oTree 6 自带模板即采用模块级写法（`assets/app_template_trials/__init__.py:33`）。

**验证要求：** 该字段必须在测试中被断言为非 NULL，否则"字段恒为 NULL"这一失效模式无法被发现——而它会让依据该字段分派的 Bot 测试**静默地走错分支**。

**理由：** 若处理组仅存在于 session 配置中，导出的 CSV 不自包含，分析脚本必须按 `session.code` 做脆弱的跨表关联，且 oTree 导出中 session 配置的序列化格式随版本变动。降范式存储使每份数据自带处理组标识，分析脚本与 Bot 测试都更稳健。

**约束：** 两者必须在同一 session 内保持一致；`creating_session` 是唯一赋值点，禁止在别处修改。

## 10. `survey` app 规格

| # | 页面 | 内容 | 影响报酬 |
|---|---|---|---|
| 1 | `RiskPreference` | 简化辉奖券选择题，6 档递进（确定金额 vs 50/50 彩票） | 否 |
| 2 | `DictatorGame` | 独裁者博弈：10 点中送对方 s 点 | **是**，收益 = 10 − s |
| 3 | `GeneralTrust` | 一般信任量表 0–10 | 否 |
| 4 | `Demographics` | 性别/年龄/年级/专业/经济学课程/实验经历 | 否 |

**独裁者博弈说明：** 所有被试均作为分配者参与，收益 = 10 − s 计入总报酬。由于该博弈在此处承担**个体差异测量**职能而非策略互动职能，不设置配对接受方。此简化须在报告局限部分声明。

## 11. 报酬设计

| 项目 | 设定 |
|---|---|
| 出场费 | 20 元（`participation_fee`） |
| 兑换率 | 1 点 = 1 元（`real_world_currency_per_point`） |
| 信任博弈收益 | A: **0–30 点**；B: 0–30 点 |
| 独裁者博弈收益 | 0–10 点 |
| 信念奖金 | 0 或 2 点（仅 A） |
| **预期总报酬** | 约 35–40 元 |
| **上限** | A 62 元 / B 60 元 |

**收益范围推导：** `A = 10 − x + y`，在 x=10、y=30 时取得最大值 30（A 送出全部、B 全额返还），在 x=10、y=0 时取得最小值 0。故 A 的范围为 0–30，**不是** 0–20。`B = 3x − y`，范围同为 0–30。

## 12. oTree 6 实现约束

**版本特性：** oTree 6.0.15 基于 starlette + uvicorn + SQLAlchemy，**非** Django。以下为经实地验证的版本差异点，实现时不可套用 oTree 5 写法。

| 项目 | oTree 6 正确写法 | 错误写法（会失败） |
|---|---|---|
| 角色定义 | `Constants` 中 `INVESTOR_ROLE = 'Investor'`（键名含 `_ROLE` 或 `ROLE_` 前缀，值必须为字符串） | 定义 `role()` 方法 |
| 角色读取 | `player.role`（**属性**） | `player.role()` |
| 角色分配 | 由 `Group.set_players()` 按 `id_in_group` 顺序自动分配 | 手动赋值 |
| 开发服务器 | `otree devserver` | `otree runserver` |
| 数据回读 | `read_csv(path, PlayerModel)` | — |

**角色分配顺序保证：** `get_roles()` 遍历 `Constants.__dict__`，依赖 Python 3.7+ 的字典插入序。因此 `INVESTOR_ROLE` 必须在 `TRUSTEE_ROLE` **之前**定义，以保证 `id_in_group=1` 为投资者。

**字段定义：** `models.IntegerField(min=, max=, label=, choices=, widget=)`；`widgets.RadioSelect` / `widgets.RadioSelectHorizontal`。

**收益写入：** `AUTO_TABULATE_PAYOFFS` 默认为 `True`，可直接 `player.payoff = cu(...)`，赋值会累加至 `participant.payoff`，跨 app 自动求和。

**Session 配置：** `SessionConfig` 是 `dict` 子类，`clean()` 仅校验必需键，**不拒绝自定义键**——自定义键 `communication` 可安全使用，通过 `session.config['communication']` 访问。

**Bot 测试：** `Bot` / `Submission` / `SubmissionMustFail` / `expect` 均可用，通过 `otree test` 运行。

## 13. 项目结构

```
behavioral_experiment/
├── settings.py              # SESSION_CONFIGS: trust_baseline / trust_communication
├── requirements.txt
├── README.md                # 安装、运行、测试、导出说明
├── 实验报告.md               # 交付物 1
├── trust_game/              # 核心实验 app
│   ├── __init__.py          # Constants / Subsession / Group / Player / Pages
│   ├── Introduction.html
│   ├── ComprehensionCheck.html
│   ├── MessageSend.html
│   ├── MessageReveal.html
│   ├── BeliefElicit.html
│   ├── InvestorDecision.html
│   ├── TrusteeDecision.html
│   ├── Results.html
│   └── tests.py             # Bot 测试 + 收益函数单元测试
├── survey/                  # 个体测量 app
│   ├── __init__.py
│   ├── RiskPreference.html
│   ├── DictatorGame.html
│   ├── GeneralTrust.html
│   ├── Demographics.html
│   └── tests.py
├── analysis/                # 分析管线
│   ├── simulate_data.py     # 生成模拟数据
│   ├── analyze.py           # 描述统计 / 检验 / 回归 / 图表
│   └── output/              # 输出表格与图
└── docs/superpowers/specs/2026-09-13-trust-game-design.md   # 本文档
```

**架构决策：单 app + session config 控制处理组。**

不采用"每处理组一个 app"的方案——表面上更隔离，但两份代码会随时间产生细微差异（如某处措辞或参数只改了一边），直接破坏实验内部效度。单 app 保证两组除消息页外逻辑完全同源。

## 14. 测试策略

### 14.1 Bot 测试（`otree test`）

| 测试项 | 断言 |
|---|---|
| 基线组完整流程 | 11 页减 3 页消息页 = 8 页，全部跑通 |
| 沟通组完整流程 | 11 页全部跑通，消息字段正确写入 |
| 消息页在基线组跳过 | `MessageSend` 的 `is_displayed` 返回 `False` |
| 收益计算（中间值） | x=5, y=6 → A=11, B=9 |
| 收益计算（边界 x=0） | x=0, y=0 → A=10, B=0 |
| 收益计算（边界 x=10） | x=10, y=30 → A=30, B=0；x=10, y=15 → A=15, B=15 |
| 总额守恒 | 任意 (x,y) 下 A+B = 10 + 2x |
| 表单越界拦截 | x=11 被拒；y=3x+1 被拒 |
| 理解检验拦截 | 答错时 `SubmissionMustFail`，答对后 `comprehension_attempts` 正确累计 |
| 角色分配 | A 为 `Investor`，B 为 `Trustee` |
| `return_ratio` 派生 | x=0 时为 0；x=5,y=6 时为 0.4 |
| 处理组标识一致 | `is_communication` 与 `session.config['communication']` 在两种 config 下均一致 |
| 信念奖金计算 | 偏差 ≤10% 得 2 点；偏差 >10% 得 0 点；B 恒为 0 |
| 消息强度映射 | 各选项正确映射到 `investor_message_strength` / `promise_strength` 的 0–4 |

### 14.2 单元测试

收益函数独立于 oTree 框架验证，避免测试与实现共享同一 bug。

### 14.3 分析脚本自测

在模拟数据上验证已知效应能被检出（回归系数符号与显著性正确）。

## 15. 分析计划（预注册）

### 15.1 样本量

- **目标样本：** N = 120（每组 60）
- **依据：** 独立样本 t 检验，α = .05 双侧，power = .80，可检测 **d ≈ 0.51**
- **文献参照：** 沟通对信任的效应量通常 d ≈ 0.5–0.9，功效充足
- **剔除规则：** 剔除未完成全部页面、或存在超时/断线的被试；括号内报告剔除前后结果
- **理解检验：** 采用"全对才能继续"的拦截机制（见 8.1），因此完成实验的被试均已理解规则，**无需按理解度剔除**。`comprehension_attempts` 的均值与分布作为理解程度的检验指标报告

### 15.2 主要分析

| 假说 | 方法 | 变量 |
|---|---|---|
| H1 | 独立样本 t 检验 | `send_amount` ~ `treatment` |
| H2 | 独立样本 t 检验 | `return_ratio` ~ `treatment` |
| H3 | OLS 回归 | `return_amount` ~ `treatment` + `send_amount` + 控制变量 |
| H4 | 中介分析（bootstrap，5000 次） | `treatment` → `belief_return_pct` → `send_amount` |
| H5 | 相关分析 + 回归 | `return_ratio` ~ `promise_strength` |

**H3 的稳健性处理：** 当 x=0 时 y 必然为 0，这类观测会对 `treatment` 系数产生机械性影响。因此 H3 同时报告三个模型：(a) 全样本；(b) **剔除 x=0 的子样本**（主要规格，仅考察真正发生转移的配对）；(c) 以 `return_ratio` 为因变量。三者结论一致方可支持 H3。

**控制变量：** 风险偏好、利他倾向、一般信任、性别、年龄、经济学课程数。

### 15.3 输出物

- 描述统计表（分处理组的均值、标准差、中位数、N）
- t 检验结果表（含效应量 Cohen's d 与 95% 置信区间）
- 回归结果表（含稳健标准误）
- 中介分析结果（间接效应、直接效应、总效应、bootstrap CI）
- 分布图：x 的分布、return_ratio 的分布、按处理组分色
- 承诺强度与返还比例的散点图 + 拟合线
- 信念与 x 的关系图

### 15.4 模拟数据生成原则

`simulate_data.py` 按**文献报告的效应量**生成数据，而非随机噪声：

- 基线组 x 服从均值约 5、右偏的分布
- 沟通组 x 均值提升约 0.5 个标准差
- `return_ratio` 随 x 递减（经典发现：送出越多，返还比例越低）
- 承诺强度与返还比例正相关
- 信念与 x 正相关，且沟通提升信念

**⚠️ 报告中的结果部分必须显著标注为模拟数据，不得与真实结果混淆。**

## 16. 报告结构

`实验报告.md` 章节：

1. 摘要
2. 引言与研究问题
3. 文献综述与理论框架
4. 研究假说（H1–H5）
5. 实验设计（处理组、参数、随机化、样本量功效分析）
6. 实验实施（oTree 实现、页面流程、操纵有效性保障）
7. 分析计划（预注册）
8. **模拟数据演示结果**（含明确标注）
9. 讨论与局限
10. 参考文献
11. 附录（实验指导语全文、消息选项、问卷全文、oTree 项目说明）

## 17. 局限与风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 单一实验室 | 结果外部效度受限 | 报告须声明 |
| 独裁者博弈无配对接受方 | 弱化了策略环境 | 报告局限部分声明 |
| 信念引出仅 A 侧受激励 | B 侧信念数据质量较低 | 仅作次要分析 |
| 沟通操纵强度 | 预设消息弱于自由文本 | 在局限中说明；预设选项保证了可编码性 |
| 样本量 | d < 0.5 的效应无法检出 | 预注册主结果变量，避免事后挑拣 |
| 模拟数据误读 | 读者可能误认为真实结果 | 报告与图表标题统一标注"模拟数据" |

## 18. 交付物清单

| # | 交付物 | 路径 |
|---|---|---|
| 1 | 实验报告 | `实验报告.md` |
| 2 | oTree 项目代码 | `trust_game/`、`survey/`、`settings.py` |
| 3 | 分析管线 | `analysis/simulate_data.py`、`analysis/analyze.py` |
| 4 | 测试 | `trust_game/tests.py`、`survey/tests.py` |
| 5 | 项目说明 | `README.md` |
| 6 | 本规格文档 | `docs/superpowers/specs/2026-09-13-trust-game-design.md` |

## 19. 参考文献

- Berg, J., Dickhaut, J., & McCabe, K. (1995). Trust, reciprocity, and social history. *Games and Economic Behavior*, 10(1), 122–142.
- Charness, G., & Dufwenberg, M. (2006). Promises and partnership. *Econometrica*, 74(6), 1579–1601.
- Fehr, E., & Gächter, S. (2002). Altruistic punishment in humans. *Nature*, 415(6868), 137–140.
- Holt, C. A., & Laury, S. K. (2002). Risk aversion and incentive effects. *American Economic Review*, 92(5), 1644–1655.
