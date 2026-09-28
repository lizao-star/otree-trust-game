# 演示模式：单步控制台 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在浏览器里逐页观察 8 个机器人被试走完 `trust_game` + `survey`——按一次按钮，8 人各填一页。

**Architecture:** 复用 oTree 内置 browser bots（demo config 带 `use_browser_bots=True`）产生 8 个机器人被试；用一个只对机器人页面渲染的守卫脚本（`_templates/otree/Page.html` 副本 + `global_scripts` 块 + `is_browser_bot` 条件）废掉 oTree 的自动提交，使页面停住；一个自建静态控制台页（`_static/global/step_console.html`）提供「全部前进一页」按钮，靠点击各 iframe 的原生提交按钮驱动。**真实被试的 HTML 里不含守卫的任何字节。**

**Tech Stack:** oTree 6.0.15 / Python 3.11.16 / 原生 JS（无框架、无外部依赖）

**规格:** `docs/superpowers/specs/2026-09-28-demo-bots-design.md`（第 2 版）

---

## 环境

本机解释器：`C:/Anaconda/envs/otree/python.exe`（Python 3.11.16，含 oTree 6.0.15 与全部依赖）。
README §2 写的是部署机上的 Linux 路径，本机跑测试/服务器一律用上面这个。

当前测试基线（已实测）：

```
python -m unittest discover -t .   →  Ran 41 tests ... OK
```

## 文件结构

| 文件 | 职责 |
|---|---|
| `settings.py` | 新增两个演示专用 session config；改 `DEMO_PAGE_INTRO_HTML` |
| `_templates/otree/Page.html` | oTree `Page.html` 的副本，末尾多一段按 `is_browser_bot` 门控的 `global_scripts` |
| `_templates/bot_step_guard.html` | 守卫 JS（唯一真值来源） |
| `_static/global/step_console.html` | 单步控制台（自建静态页，不覆盖任何 oTree 模板） |
| `trust_game/test_settings.py` | session config 守卫（5 个用例） |
| `trust_game/test_demo_templates.py` | 模板副本漂移守卫 + 门控条件 + 键名一致性（3 个用例） |
| `README.md` | §3 目录结构 / §4 演示模式 / §5 测试计数 / §9 注意事项 |

测试计数预期：41 → 46（Task 1）→ 48（Task 2）→ 49（Task 3）。

---

## Task 1: 演示 session config

**Files:**
- Create: `trust_game/test_settings.py`
- Modify: `settings.py:3-20`（`SESSION_CONFIGS`）、`settings.py:40`（`DEMO_PAGE_INTRO_HTML`）

- [ ] **Step 1: 写失败的守卫测试**

创建 `trust_game/test_settings.py`：

```python
"""settings.py 的 session config 守卫。

运行（项目根目录）：
    python -m unittest trust_game.test_settings -v

⚠️ 本文件守的是**演示开关不得落到真实 config 上**。

`use_browser_bots=True` 的语义是「本会话的全体被试由 bot 驱动」。它一旦出现在
trust_baseline / trust_communication 上，真实被试拿到的每一页都会在渲染后被 JS
自动提交（otree/views/abstract.py:483-513），被试还没读完题目就翻页；而数据照样
写库、otree test 照样全绿。这是不会自己报出来的错误：它只在收完数据后表现为
一片无意义的常量。故此处逐条钉死，让误改在测试阶段就失败。

为什么按文件路径 importlib 加载 settings.py，而不是 `import settings`：
    被测对象是仓库里这个文件的**实际取值**；用 spec_from_file_location 读它，
    既不依赖当前工作目录（discover 的顶层目录由 -t 决定），也不向 sys.modules
    注册一个顶层的 settings 模块。
"""

import importlib.util
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PY = PROJECT_ROOT / 'settings.py'

# 真实 config → 其对应的演示 config。改这里的映射即改守卫的适用范围。
REAL_TO_DEMO = {
    'trust_baseline': 'trust_baseline_bots',
    'trust_communication': 'trust_communication_bots',
}


def load_settings():
    """按文件路径加载项目根的 settings.py。"""
    spec = importlib.util.spec_from_file_location('project_settings', SETTINGS_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configs_by_name():
    return {c['name']: c for c in load_settings().SESSION_CONFIGS}


class TestDemoConfigs(unittest.TestCase):

    def setUp(self):
        self.configs = configs_by_name()

    def config(self, name):
        self.assertIn(name, self.configs,
                      f'settings.py 中缺少 session config：{name}')
        return self.configs[name]

    def test_real_configs_must_not_use_browser_bots(self):
        """真实 config 绝不可带 use_browser_bots：否则真实被试会被 bot 顶替。"""
        for name in REAL_TO_DEMO:
            value = self.config(name).get('use_browser_bots', False)
            # 缺键与显式 False 都必须通过。用 assertIs 而非真值判断，
            # 使 None / 0 / '' 这些「碰巧为假」的值同样被拦下——
            # 本仓库已有把 0 误当缺失值的先例。
            self.assertIs(
                value, False,
                f'{name} 的 use_browser_bots 必须是 False 或缺键，实际是 {value!r}；'
                '真实 config 带该开关会让真实被试的页面被自动提交',
            )

    def test_demo_configs_use_browser_bots(self):
        """演示 config 必须带 use_browser_bots：单步控制台全靠它。"""
        for demo_name in REAL_TO_DEMO.values():
            value = self.config(demo_name).get('use_browser_bots', False)
            self.assertIs(
                value, True,
                f'{demo_name} 的 use_browser_bots 必须是 True，实际是 {value!r}；'
                '否则该会话不会由 bot 驱动，控制台无对象可驱动',
            )

    def test_demo_configs_mirror_communication_flag(self):
        """演示 config 的 communication 必须与对应真实 config 逐值相同。

        用 assertIs 比较：None 与 False 在真值判断下同形，而它们对
        has_communication() 的后果不同。
        """
        for real_name, demo_name in REAL_TO_DEMO.items():
            real = self.config(real_name)
            self.assertIn('communication', real,
                          f'{real_name} 缺少 communication 键，无法作对齐基准')
            self.assertIs(
                self.config(demo_name).get('communication'),
                real['communication'],
                f'{demo_name} 的 communication 与 {real_name} 不一致',
            )

    def test_demo_configs_mirror_app_sequence(self):
        for real_name, demo_name in REAL_TO_DEMO.items():
            self.assertEqual(
                self.config(demo_name)['app_sequence'],
                self.config(real_name)['app_sequence'],
                f'{demo_name} 的 app_sequence 必须与 {real_name} 相同，'
                '否则演示覆盖不到调查问卷',
            )

    def test_demo_num_participants_within_grid_view_limits(self):
        """人数必须落在网格视图限额内，否则演示页上 Grid view 不可用。

        限额从 otree.views.admin 导入而非写死字面量：写死会随 oTree 升级
        变成一句关于旧版本的陈述，而本断言要保证的是「现在仍然可用」。
        """
        from otree.views.admin import GRID_LOWER_LIMIT, GRID_UPPER_LIMIT

        for demo_name in REAL_TO_DEMO.values():
            num = self.config(demo_name)['num_demo_participants']
            self.assertGreaterEqual(
                num, GRID_LOWER_LIMIT,
                f'{demo_name} 人数 {num} 低于网格视图下限 {GRID_LOWER_LIMIT}')
            self.assertLessEqual(
                num, GRID_UPPER_LIMIT,
                f'{demo_name} 人数 {num} 高于网格视图上限 {GRID_UPPER_LIMIT}')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd "E:/大学课件资料/研一/行为经济学/自设计实验/otree-trust-game-repo"
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_settings -v
```

预期：4 个用例 FAIL（`AssertionError: 'trust_baseline_bots' not found in {...}` 之类），
`test_real_configs_must_not_use_browser_bots` 通过（现有两个 config 本来就没这个键）。

- [ ] **Step 3: 加两个演示 config**

把 `settings.py` 的 `SESSION_CONFIGS` 改成（在 `trust_communication` 之后追加两项）：

```python
SESSION_CONFIGS = [
    dict(
        name='trust_baseline',
        display_name='信任博弈 — 基线组（无沟通）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=False,
        doc='标准信任博弈，全程匿名，无任何沟通',
    ),
    dict(
        name='trust_communication',
        display_name='信任博弈 — 沟通组',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=True,
        doc='信任博弈，双方在决策前同时发送预设消息并互相可见',
    ),
    # 演示专用：-- 以下是两个「演示·单步」config。
    # use_browser_bots=True 让全体被试成为 browser bot（页面自动填写），
    # 单步控制台再据此把自动提交挡下来，改为按按钮驱动。
    # ！！绝不可把该键挪到上面两个真实 config 上！！——
    # 那样真实被试会被当成 bot、页面被自动提交，而数据照样入库、
    # otree test 照样全绿。trust_game/test_settings.py 会拦下这种改动。
    dict(
        name='trust_baseline_bots',
        display_name='信任博弈 — 基线组（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=False,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
    dict(
        name='trust_communication_bots',
        display_name='信任博弈 — 沟通组（演示·单步）',
        app_sequence=['trust_game', 'survey'],
        num_demo_participants=8,
        communication=True,
        use_browser_bots=True,
        doc='演示专用，非真实数据；配套 _static/global/step_console.html',
    ),
]
```

再把 `DEMO_PAGE_INTRO_HTML` 改成：

```python
DEMO_PAGE_INTRO_HTML = """
<p><b>演示模式（单步）</b></p>
<p>1. 点下面任一「演示·单步」配置创建会话；<br>
2. 从地址栏复制会话码（<code>/SessionStartLinks/&lt;码&gt;</code>）；<br>
3. 打开
<a href="/static/global/step_console.html">/static/global/step_console.html</a>
并填入会话码；<br>
4. 按「全部前进一页」——按一次，8 人各填一页。</p>
<p>「连续跑完」按钮会撤掉单步开关，让机器人自动跑完全程。</p>
"""
```

- [ ] **Step 4: 运行，确认通过**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_settings -v
```

预期：`Ran 5 tests ... OK`

- [ ] **Step 5: 跑全仓，确认没有回归**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest discover -t .
```

预期：`Ran 46 tests ... OK`

- [ ] **Step 6: 提交**

```bash
git add settings.py trust_game/test_settings.py
git commit -m "feat: 演示专用 session config（基线/沟通各一）+ 真实 config 不得带 use_browser_bots 的守卫"
```

---

## Task 2: 模板守卫

**Files:**
- Create: `_templates/otree/Page.html`（oTree 副本 + 一段）
- Create: `_templates/bot_step_guard.html`
- Create: `trust_game/test_demo_templates.py`

- [ ] **Step 1: 写失败的守卫测试**

创建 `trust_game/test_demo_templates.py`：

```python
"""演示模式的模板副本守卫。

运行（项目根目录）：
    python -m unittest trust_game.test_demo_templates -v

守两件事：

1. `_templates/otree/Page.html` 是 oTree 自带 `otree/Page.html` 的副本，差异必须
   **恰好是一段连续插入**（那段守卫 include）。oTree 升级会让副本过时——本用例
   让那件事**响**，而不是静默沿用旧行为。第 1 版设计正是栽在「静默」上：
   按实例改 `_template_type` 后，模板缓存只按文件名做键、忽略 template_type
   （otree/templating/loader.py:18-24），谁先渲染谁决定全局，两个方向各错一个
   且都不报错（见规格 §7.1）。

2. 那段守卫的准入条件必须是 `is_browser_bot`：真实被试的 HTML 里不得出现守卫。
   这是规格 §1 硬约束（用户明示）的第一道证据。
"""

import difflib
import unittest
from pathlib import Path

import otree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUR_PAGE_HTML = PROJECT_ROOT / '_templates' / 'otree' / 'Page.html'
OTREE_PAGE_HTML = (
    Path(otree.__file__).parent / 'templates' / 'otree' / 'Page.html'
)


class TestPageOverride(unittest.TestCase):

    def test_override_differs_from_otree_only_by_guard_block(self):
        """副本 = oTree 原文件 + 恰好一段连续插入，且插入的含守卫 include。"""
        ours = OUR_PAGE_HTML.read_text(encoding='utf-8').splitlines(keepends=True)
        theirs = OTREE_PAGE_HTML.read_text(encoding='utf-8').splitlines(keepends=True)

        # autojunk=False：默认的启发式会把大量重复行（本模板里 endfor/endblock
        # 很多）当成 junk，可能把一处插入拆成多段而误报。
        sm = difflib.SequenceMatcher(None, theirs, ours, autojunk=False)
        changes = [op for op in sm.get_opcodes() if op[0] != 'equal']
        self.assertEqual(
            len(changes), 1,
            f'副本与 otree/Page.html 的差异必须恰好是一处，实际 {len(changes)} 处：'
            f'{changes}。若 oTree 已升级，请重新复制该文件并重新加守卫块'
            '（见规格 §4 文件清单第 2 项）。',
        )
        tag, _i1, _i2, j1, j2 = changes[0]
        self.assertEqual(tag, 'insert',
                         f'差异必须是纯插入（副本只许多出内容），实际是 {tag}')
        inserted = ''.join(ours[j1:j2])
        self.assertIn(
            "include 'bot_step_guard.html'", inserted,
            '插入的内容必须是守卫 include；插入别的东西说明副本被改坏了',
        )

    def test_guard_is_gated_on_is_browser_bot(self):
        """守卫必须被 is_browser_bot 条件包住（规格 §1 硬约束）。"""
        text = OUR_PAGE_HTML.read_text(encoding='utf-8')
        # 断言「条件包住 include」这个结构，而不是仅仅文件里出现过该词——
        # 后者在条件被删掉、只剩一句注释时也会通过。
        self.assertRegex(
            text,
            r"\{%\s*if[^%]*is_browser_bot[^%]*%\}\s*"
            r"\{%\s*include 'bot_step_guard\.html'\s*%\}",
            '守卫 include 必须被 is_browser_bot 条件包住',
        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行，确认失败**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates -v
```

预期：2 个用例 ERROR（`FileNotFoundError: ..._templates\otree\Page.html`）

- [ ] **Step 3: 复制 oTree 的 Page.html**

```bash
mkdir -p _templates/otree
cp "C:/Anaconda/envs/otree/Lib/site-packages/otree/templates/otree/Page.html" _templates/otree/Page.html
```

- [ ] **Step 4: 在副本末尾追加守卫块**

在 `_templates/otree/Page.html` **文件末尾**追加（紧接在最后一个 `{% endblock %}` 之后）：

```html
{# ===== 演示模式守卫：仅机器人页面渲染 =====
   本文件是 otree/templates/otree/Page.html 的副本，差异只有下面这一段；
   trust_game/test_demo_templates.py 会逐行核对该差异，oTree 升级导致副本过时
   会让它失败。改动 oTree 原文件后请重新复制并重新追加本段。
   is_browser_bot 为真 ⇒ 本会话由 browser bot 驱动（演示 config 专属）。
   真实被试该字段恒为假，本段内容不会出现在他们的 HTML 里。 #}
{% block global_scripts %}
    {% if is_defined('player') and player.participant.is_browser_bot %}
        {% include 'bot_step_guard.html' %}
    {% endif %}
{% endblock %}
```

> 位置很关键：`global_scripts` 是 `<body>` 的最后一块，渲染结果正好落在 oTree
> 追加的自动提交脚本**之前**（已实测：标记出现在 `</body>` 前最后一行）。

- [ ] **Step 5: 创建守卫 JS**

创建 `_templates/bot_step_guard.html`：

```html
{# 单步演示守卫。只被 _templates/otree/Page.html 在
   player.participant.is_browser_bot 为真时 include —— 真实被试的页面
   不含本文件的任何字节（trust_game/test_demo_templates.py 钉住该条件）。

   按下「全部前进一页」的控制台页会先设好 sessionStorage 开关再创建 iframe；
   同源 iframe 共享同一标签页的 sessionStorage，故此处读得到。
   开关不在的场合（例如直接打开 oTree 演示页的 Grid view）守卫不生效，
   机器人照旧自动跑完——那是「连续跑完」的默认行为。 #}
<script>
(function () {
    if (sessionStorage.getItem('otree_bot_step') !== '1') return;
    // oTree 在每个页面末尾追加一段自动提交脚本（otree/views/abstract.py:501-513），
    // 内容是 form.submit()。把它覆盖成空操作，页面就会停下来等控制台的按钮。
    // 人类点页面上的「下一页」走的是原生表单提交，不经过 HTMLFormElement.prototype.submit，
    // 因此照常工作；而机器人下一次要提交的答案在页面被 GET 时就已在服务端排队
    // （otree/views/abstract.py:494），所以点下去用的就是机器人的答案。
    // 覆盖 .on 是因为 oTree 那段脚本还调用了 form.on(...)（jQuery 方法），
    // 不覆盖的话每次都会往控制台抛一条 TypeError（oTree 自身缺陷，无害但很吵）。
    HTMLFormElement.prototype.submit = function () {};
    HTMLFormElement.prototype.on = function () {};
})();
</script>
```

- [ ] **Step 6: 运行，确认通过**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates -v
```

预期：`Ran 2 tests ... OK`

- [ ] **Step 7: 跑全仓**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest discover -t .
```

预期：`Ran 48 tests ... OK`

- [ ] **Step 8: 提交**

```bash
git add _templates trust_game/test_demo_templates.py
git commit -m "feat: 单步守卫模板（仅机器人页面渲染）+ 副本漂移守卫

_templates/otree/Page.html 是 oTree Page.html 的副本，差异只有末尾那段
按 is_browser_bot 门控的 global_scripts；真实被试的 HTML 不含守卫字节。
oTree 升级导致副本过时会被 test_demo_templates.py 逐行比对抓出来。"
```

---

## Task 3: 单步控制台

**Files:**
- Create: `_static/global/step_console.html`
- Modify: `trust_game/test_demo_templates.py`（追加一个用例类）

- [ ] **Step 1: 追加失败的一致性测试**

在 `trust_game/test_demo_templates.py` 末尾（`if __name__` 之前）插入：

```python
# 与 _templates/bot_step_guard.html 和 _static/global/step_console.html
# 两处出现的 sessionStorage 键名必须逐字相同——这是两处真值源，
# 改一处而漏改另一处，守卫就永远读不到控制台设的开关（静默失效）。
CONSOLE_HTML = PROJECT_ROOT / '_static' / 'global' / 'step_console.html'
STEP_STORAGE_KEY = 'otree_bot_step'
GUARD_HTML = PROJECT_ROOT / '_templates' / 'bot_step_guard.html'


class TestStepStorageKey(unittest.TestCase):

    def test_key_is_identical_in_guard_and_console(self):
        for path in (GUARD_HTML, CONSOLE_HTML):
            self.assertIn(
                f"'{STEP_STORAGE_KEY}'", path.read_text(encoding='utf-8'),
                f'{path.name} 里没有出现键名 {STEP_STORAGE_KEY!r}；'
                '守卫与控制台必须用同一个键，否则开关不生效且不报错',
            )
```

- [ ] **Step 2: 运行，确认失败**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates.TestStepStorageKey -v
```

预期：`FileNotFoundError: ..._static\global\step_console.html`

- [ ] **Step 3: 创建控制台**

创建 `_static/global/step_console.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>单步演示控制台</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font: 13px/1.5 system-ui, "Microsoft YaHei", sans-serif; }
  #bar { position: sticky; top: 0; z-index: 10; background: #fff;
         border-bottom: 1px solid #ccc; padding: 8px 12px;
         display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  #bar h1 { font-size: 14px; margin: 0 8px 0 0; }
  button { padding: 5px 12px; cursor: pointer; }
  #step-all { font-weight: 700; padding: 7px 18px; }
  #code { padding: 5px 8px; width: 140px; }
  #status { color: #666; margin-left: auto; }
  #grid { display: grid; gap: 6px; padding: 6px; }
  .cell { border: 1px solid #ccc; border-radius: 4px; overflow: hidden;
          display: flex; flex-direction: column; height: calc(50vh - 34px); }
  .cell .bar { display: flex; gap: 6px; align-items: center;
               padding: 3px 6px; border-bottom: 1px solid #ccc; font-size: 12px; }
  .cell iframe { flex: 1; width: 100%; border: 0; }
  .page-name { font-family: ui-monospace, Consolas, monospace; color: #0a5; }
  .cell button { padding: 2px 8px; font-size: 12px; }
</style>
</head>
<body>
<div id="bar">
  <h1>单步演示控制台</h1>
  <input id="code" placeholder="会话码">
  <button id="load">加载</button>
  <button id="step-all">全部前进一页</button>
  <button id="run-all">连续跑完</button>
  <span id="status"></span>
</div>
<div id="grid"></div>

<script>
// 与 _templates/bot_step_guard.html 里的键名必须逐字相同；
// trust_game/test_demo_templates.py 会断言两处一致。
const STEP_KEY = 'otree_bot_step';

const grid = document.getElementById('grid');
const statusEl = document.getElementById('status');
let frames = [];     // [{ iframe, nameEl }]
let stepCount = 0;

function setStatus(text) { statusEl.textContent = text; }

async function load(code) {
  if (!code) { setStatus('请填会话码'); return; }
  // 必须在创建 iframe **之前**设置：同源 iframe 共享本标签页的 sessionStorage，
  // 守卫在页面解析时就会读它。
  sessionStorage.setItem(STEP_KEY, '1');
  setStatus('正在读取会话 ' + code + ' …');

  const resp = await fetch('/SessionStartLinks/' + code);
  if (!resp.ok) { setStatus('读不到会话页：HTTP ' + resp.status); return; }
  const doc = new DOMParser().parseFromString(await resp.text(), 'text/html');
  const urls = [...doc.querySelectorAll('a.participant-link')].map(a => a.href);
  if (!urls.length) { setStatus('该会话没有被试链接（会话码对吗？）'); return; }

  grid.textContent = '';
  grid.style.gridTemplateColumns = 'repeat(' + Math.ceil(urls.length / 2) + ', 1fr)';
  frames = urls.map((url, i) => {
    const cell = document.createElement('div');
    cell.className = 'cell';
    const bar = document.createElement('div');
    bar.className = 'bar';
    const label = document.createElement('span');
    label.textContent = 'P' + (i + 1);
    const nameEl = document.createElement('span');
    nameEl.className = 'page-name';
    nameEl.textContent = '…';
    const btn = document.createElement('button');
    btn.textContent = '前进';
    const frame = { iframe: null, nameEl: nameEl };
    btn.addEventListener('click', () => { step(frame); setTimeout(refreshNames, 700); });
    bar.append(label, nameEl, btn);
    const iframe = document.createElement('iframe');
    iframe.src = url;
    frame.iframe = iframe;
    cell.append(bar, iframe);
    grid.append(cell);
    return frame;
  });
  setStatus('已加载 ' + urls.length + ' 个被试');
  setTimeout(refreshNames, 800);
}

// 让一个被试前进一页：点他页面上的原生提交按钮。
// 机器人的答案已在服务端排队（GET 该页时入队），所以点下去用的是机器人的答案。
function step(frame) {
  const doc = frame.iframe.contentDocument;
  if (!doc) return false;
  const form = doc.querySelector('#form');
  // 与 oTree 自己找提交按钮的口径一致：<button> 且 type != 'button'
  // （oTree 的提交按钮无 type 属性，默认即 submit）。
  const btn = [...doc.querySelectorAll('#form button, #form input[type=submit]')]
    .find(el => el.getAttribute('type') !== 'button');
  if (!form || !btn) return false;   // 等待页没有表单，由 oTree 自行跳转

  // 下面两件都必须做，否则点击无声失效（均已实测）：
  // 1) 机器人的答案不预填在表单里，字段是 required 且空的，不关掉约束校验
  //    就会被浏览器挡下，POST 根本发不出去；
  // 2) oTree 每次提交后把 .otree-btn-next 禁用 5000ms 防连点
  //    （otree/static/otree/js/common_user_facing.js:26-38）。
  form.noValidate = true;
  btn.disabled = false;
  btn.click();
  return true;
}

function stepAll() {
  let hit = 0;
  for (const f of frames) if (step(f)) hit++;
  stepCount += 1;
  setStatus('已下发第 ' + stepCount + ' 步（命中 ' + hit + ' 个）');
  setTimeout(refreshNames, 700);
}

function refreshNames() {
  for (const f of frames) {
    try {
      const parts = f.iframe.contentWindow.location.pathname.split('/');
      f.nameEl.textContent = parts[parts.length - 2] || '?';
    } catch (e) {
      f.nameEl.textContent = '?';
    }
  }
}

// 撤掉单步开关并重载，回到机器人自动跑完（约 2 秒跑完全部 12 页）。
function runAll() {
  sessionStorage.removeItem(STEP_KEY);
  stepCount = 0;
  setStatus('已撤掉单步开关，重载中……');
  for (const f of frames) {
    try { f.iframe.contentWindow.location.reload(); } catch (e) {}
  }
  setTimeout(refreshNames, 3000);
}

document.getElementById('load').addEventListener('click', () => {
  load(document.getElementById('code').value.trim());
});
document.getElementById('step-all').addEventListener('click', stepAll);
document.getElementById('run-all').addEventListener('click', runAll);
document.getElementById('code').addEventListener('keydown', e => {
  if (e.key === 'Enter') load(e.target.value.trim());
});

const fromQuery = new URLSearchParams(location.search).get('code');
if (fromQuery) {
  document.getElementById('code').value = fromQuery;
  load(fromQuery);
}
</script>
</body>
</html>
```

- [ ] **Step 4: 运行，确认通过**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates -v
```

预期：`Ran 3 tests ... OK`

- [ ] **Step 5: 跑全仓**

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest discover -t .
```

预期：`Ran 49 tests ... OK`

- [ ] **Step 6: 提交**

```bash
git add _static/global/step_console.html trust_game/test_demo_templates.py
git commit -m "feat: 单步演示控制台（全部前进一页 / 连续跑完）"
```

---

## Task 4: 变异探针（证伪性验证）

**目的**：证明每条守卫都**能被改坏**——永远通过的守卫等于没有守卫。本仓库既有先例
（`实验报告.md` §6.5 记录了逐条做探针）。**每一步都要先看到红，再撤销。**

- [ ] **Step 1: 探针 A —— 把演示开关挪到真实 config**

```bash
"C:/Anaconda/envs/otree/python.exe" - <<'PY'
from pathlib import Path
p = Path('settings.py'); s = p.read_text(encoding='utf-8')
old = "        communication=False,\n        doc='标准信任博弈，全程匿名，无任何沟通',"
new = "        communication=False,\n        use_browser_bots=True,\n        doc='标准信任博弈，全程匿名，无任何沟通',"
assert old in s, '锚点没找到，请手工改'
p.write_text(s.replace(old, new, 1), encoding='utf-8')
PY
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_settings 2>&1 | tail -4
```

预期：`FAILED (failures=1)`，失败的是 `test_real_configs_must_not_use_browser_bots`。
然后把 `settings.py` 改回来：

```bash
git checkout settings.py
```

- [ ] **Step 2: 探针 B —— 让副本与 oTree 出现第二处差异**

```bash
"C:/Anaconda/envs/otree/python.exe" - <<'PY'
from pathlib import Path
p = Path('_templates/otree/Page.html'); s = p.read_text(encoding='utf-8')
assert 'id="form"' in s
p.write_text(s.replace('id="form"', 'id="form_x"', 1), encoding='utf-8')
PY
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates.TestPageOverride 2>&1 | tail -4
```

预期：`FAILED (failures=1)`，失败的是
`test_override_differs_from_otree_only_by_guard_block`（差异变成 2 处、且含 replace）。
撤销：

```bash
git checkout _templates/otree/Page.html
```

- [ ] **Step 3: 探针 C —— 把守卫的准入条件改成恒真**

```bash
"C:/Anaconda/envs/otree/python.exe" - <<'PY'
from pathlib import Path
p = Path('_templates/otree/Page.html'); s = p.read_text(encoding='utf-8')
old = "{% if is_defined('player') and player.participant.is_browser_bot %}"
assert old in s
p.write_text(s.replace(old, "{% if True %}", 1), encoding='utf-8')
PY
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates.TestPageOverride 2>&1 | tail -4
```

预期：`FAILED (failures=1)`，失败的是 `test_guard_is_gated_on_is_browser_bot`。
撤销：

```bash
git checkout _templates/otree/Page.html
```

- [ ] **Step 4: 探针 D —— 只改控制台里的键名**

```bash
"C:/Anaconda/envs/otree/python.exe" - <<'PY'
from pathlib import Path
p = Path('_static/global/step_console.html'); s = p.read_text(encoding='utf-8')
assert "'otree_bot_step'" in s
p.write_text(s.replace("'otree_bot_step'", "'otree_bot_stepX'", 1), encoding='utf-8')
PY
"C:/Anaconda/envs/otree/python.exe" -m unittest trust_game.test_demo_templates.TestStepStorageKey 2>&1 | tail -4
```

预期：`FAILED (failures=1)`。撤销：

```bash
git checkout _static/global/step_console.html
```

- [ ] **Step 5: 确认全部撤销干净并复跑全仓**

```bash
git status --short          # 预期：空
"C:/Anaconda/envs/otree/python.exe" -m unittest discover -t .
```

预期：`Ran 49 tests ... OK`

---

## Task 5: 端到端验证（含硬约束回归）

**本任务是本计划最重要的一步**：Task 4 证明守卫写得对，本任务证明它**跑起来对**。

- [ ] **Step 1: 起服务器**

```bash
cd "E:/大学课件资料/研一/行为经济学/自设计实验/otree-trust-game-repo"
export PATH="/c/Anaconda/envs/otree:/c/Anaconda/envs/otree/Scripts:$PATH"
export OTREE_ADMIN_PASSWORD=local-dev-pw
otree devserver 8140
```

（用 `run_in_background` 起，日志重定向到临时文件。）

- [ ] **Step 2: 硬约束回归 —— 真实被试页不含守卫**

用浏览器（playwright MCP）执行：

```js
async (page) => {
  const base = 'http://localhost:8140';
  const out = {};
  await page.goto(base + '/demo/trust_baseline');
  await page.waitForURL(/SessionStartLinks/, { timeout: 60000 });
  const link = await page.evaluate(() => document.querySelector('a.participant-link').href);
  const html = await page.evaluate(async u => (await fetch(u, {redirect:'follow'})).text(), link);
  out.真实被试页_含守卫JS = html.includes('HTMLFormElement.prototype.submit');
  out.真实被试页_含开关键名 = html.includes('otree_bot_step');
  return out;
}
```

预期：**两个都是 `false`**。任一为 `true` 即硬约束被破坏，必须停下来排查。

- [ ] **Step 3: 单步 —— 按一次，8 人各前进一页**

新建一个「演示·单步」会话，取会话码，然后：

```js
async (page) => {
  const base = 'http://localhost:8140';
  await page.goto(base + '/demo/trust_baseline_bots');
  await page.waitForURL(/SessionStartLinks/, { timeout: 60000 });
  const code = page.url().split('/').pop();

  await page.goto(`${base}/static/global/step_console.html?code=${code}`);
  await page.waitForTimeout(3000);

  const snap = () => page.evaluate(() =>
    [...document.querySelectorAll('iframe')].map(f => {
      try { return f.contentWindow.location.pathname.split('/').slice(-2)[0]; }
      catch (e) { return '?'; }
    }).join(' '));

  const out = { code, 初始: await snap() };
  for (let i = 1; i <= 6; i++) {
    await page.click('#step-all');
    await page.waitForTimeout(1500);
    out['第' + i + '步'] = await snap();
  }
  return out;
}
```

预期（实测过的形态）：

```
初始    Introduction ×8
第1步   ComprehensionCheck ×8
第2步   BeliefElicit ×8                ← 第 1 步故意答错被拒，第 2 步才通过
第3步   InvestorDecision×4 / BeliefElicit×4    ← 角色分叉在这里出现
第4步   ResultsWaitPage×4 / TrusteeDecision×4  ← 等待页
第5步   Results ×8
第6步   RiskPreference ×8
```

要点：**每一步 8 个人都在同一页**（等待页除外）。若出现「有的走了有的没走」，
说明某个 iframe 的点击没生效。

- [ ] **Step 4: 沟通组演示有消息页，基线组没有**

把 Step 3 的 `/demo/trust_baseline_bots` 换成 `/demo/trust_communication_bots`，
重跑；第 2～3 步之间应出现 `MessageSend` 与 `MessageReveal`。基线组全程不应出现这两个页面名。

- [ ] **Step 5: 「连续跑完」恢复自动跑完**

在控制台页执行：

```js
async (page) => {
  await page.click('#run-all');
  await page.waitForTimeout(5000);
  return page.evaluate(() =>
    [...document.querySelectorAll('iframe')].map(f => {
      try { return f.contentWindow.location.pathname.split('/').slice(-2)[0]; }
      catch (e) { return '?'; }
    }).join(' '));
}
```

预期：8 个 iframe 全部到 `OutOfRangeNotification`（全部页面跑完的终态）。

- [ ] **Step 6: 关掉服务器，确认工作区干净**

```bash
git status --short
```

预期：空（`.playwright-mcp/` 与截图属于 playwright MCP 产物，若出现请删除）。

- [ ] **Step 7: `otree test` 不回归**

新增的 `_templates/otree/Page.html` 会被 `otree test` 渲染的页面用到（非 bot 会话走
`is_browser_bot == False` 分支，守卫不输出）。跑一遍确认 bot 端到端测试仍全绿：

```bash
ls -l db.sqlite3        # 先看清目标：README §9.8 说它常为 0 字节、可删
rm -f db.sqlite3        # README §9.8 规定跑 oTree 测试前先删（沿用旧库会报 Please delete your database）
export PATH="/c/Anaconda/envs/otree:/c/Anaconda/envs/otree/Scripts:$PATH"
otree test trust_baseline
otree test trust_communication
```

预期：各输出两行 `Bots completed session`，退出码 0。

> 若 `db.sqlite3` 并非 0 字节（里面有你不想丢的数据），**不要执行 `rm`**，
> 先把文件改名备份再跑，跑完再决定去留。

---

## Task 6: README 同步

**Files:** Modify `README.md`

README 的目录结构、测试计数与注意事项都是**带具体数字**的陈述；不同步即成为失实陈述
（本仓库有先例：提交 `1622017`）。

- [ ] **Step 1: §3 目录结构**

把这一行：

```
├── settings.py                  SESSION_CONFIGS：trust_baseline / trust_communication
```

改为：

```
├── settings.py                  SESSION_CONFIGS：2 个真实 + 2 个演示（*_bots，见 §4）
```

在 `trust_game/` 块里 `test_content.py` 那行之后补两行：

```
│   ├── test_settings.py         session config 守卫（5 个）
│   ├── test_demo_templates.py   演示模板副本漂移守卫（3 个）
```

在 `analysis/` 块之前插入：

```
├── _templates/                  模板覆盖（演示单步守卫）
│   ├── otree/Page.html          oTree Page.html 的副本，差异只有末尾守卫块
│   └── bot_step_guard.html      单步守卫 JS（仅机器人页面渲染）
│
├── _static/global/
│   ├── empty.css                oTree 静态文件占位（原有，未改动）
│   └── step_console.html        单步演示控制台（见 §4.1）
│
```

> 原 `└── _static/global/empty.css     oTree 静态文件占位` 一行随之并入上面的块。
> **不要顺手删掉 `empty.css` 本身**——它不是本次改动引入的，删它是另一件事。
> （旁注，不在本计划范围：该文件从未被任何模板引用，`grep -rn "empty.css" .`
> 只命中 README 与本目录下的历史文档。是否清理由你另行决定。）

- [ ] **Step 2: §4 运行实验**

把「**http://localhost:8000/demo** —— 演示页，列出两个 session config
（`信任博弈 — 基线组（无沟通）` / `信任博弈 — 沟通组`），点击任一 config 即可创建会话并
取得各参与者的进入链接；」改为：

```
- **http://localhost:8000/demo** —— 演示页，列出四个 session config
  （两个真实：`信任博弈 — 基线组（无沟通）` / `信任博弈 — 沟通组`；
  两个演示：`…（演示·单步）`）。点任一 config 即可创建会话并取得各参与者的进入链接；
```

在 §4 末尾（`> **本机重要限制：** ...` 那段引用块**之前**）插入一节：

```markdown
### 4.1 演示模式：单步控制台

用于**在没有真实被试时逐页观察实验流程**。机器人被试由 oTree 内置的 browser bots
提供，驱动脚本就是本仓库已有的 `trust_game/tests.py` 与 `survey/tests.py`
（与 `otree test` 跑的是同一份）。默认情况下机器人会以机器速度跑完（8 人 × 12 页
约 2 秒，肉眼看不到过程），单步控制台把自动提交挡下来，改为按按钮驱动。

1. 打开 `http://localhost:8000/demo/`，点「信任博弈 — 基线组（演示·单步）」；
2. 从地址栏复制会话码（`/SessionStartLinks/<码>` 里的那一段）；
3. 打开 `http://localhost:8000/static/global/step_console.html?code=<码>`；
4. 按「**全部前进一页**」——按一次，8 人各填一页；页面上直接看角色分叉、等待页
   与校验报错（理解检验先答错被拒、再答对通过，属预期）。

「连续跑完」按钮撤掉单步开关并重载，回到 2 秒自动跑完，用于只要数据的时候。

**守卫只出现在机器人页面。** `_templates/otree/Page.html` 里那段守卫被
`is_browser_bot` 条件包住，真实被试（该字段恒为假）拿到的 HTML 里**不含它的任何
字节**；`trust_game/test_demo_templates.py` 会断言这个条件存在。

**已知行为：**

- 控制台里会刷出若干 `TypeError: form.on is not a function`。这是 oTree 自身
  注入的自动提交脚本的缺陷（它在 `form.submit()` 之后调用 jQuery 的 `form.on`），
  无害，已由守卫顺带消除；未启用单步时仍会出现。
- 每次创建演示会话会随机抽一个 bot case（`normal` 或 `zero_send`，同一会话内
  8 人同 case）。两者**页面序列完全相同**，只是数值不同（`zero_send` 时投资者送 0、
  受托人页无表单）。想看另一分支就重新点一次配置。
- **不要用 `otree test` 之外的正式库跑演示会话**：演示会话会写数据库。按
  `participant._is_bot` 过滤可识别（见「注意事项」）。
```

- [ ] **Step 3: §5 测试计数**

`grep -n "41\|29 个" README.md` 找出全部出现处（当前在注释、正文、§8、§9 共 5 处），
按下列规则改：

| 位置 | 原文 | 改为 |
|---|---|---|
| §5.2 代码块注释 | `# 全仓（41 个）` | `# 全仓（49 个）` |
| §5.2 正文 | `Ran 41 tests ... OK (skipped=12)`——**实际执行 29 个** | `Ran 49 tests ... OK (skipped=12)`——**实际执行 37 个** |
| §5.2 正文 | 要跑满 41 个 | 要跑满 49 个 |
| §8 交付物清单 | `纯函数单元测试 29 个 + 分析管线守卫 12 个 = **41 个**` | `纯函数单元测试 29 个 + 分析管线守卫 12 个 + 演示模式守卫 8 个 = **49 个**` |
| §9 注意事项第 10 条 | `只跑 29 个而不是 41 个` | `只跑 37 个而不是 49 个` |

`trust_game/test_payoffs.py` 那行「纯函数单元测试（13 个）」与 `test_content.py` 的
「（16 个）」**不变**（13+16=29，仍成立）。

改完**必须实测核对**：

```bash
"C:/Anaconda/envs/otree/python.exe" -m unittest discover -t .
```

预期：`Ran 49 tests ... OK`。若实际数字不是 49，以实测为准改 README。

- [ ] **Step 4: §9 注意事项追加一条**

在 §9 末尾（第 10 条之后）追加为**第 11 条**（不要插在中间——README 开头引用
「注意事项第 1 条」、演示模式一节引用「第 6 条」，插入会让这些交叉引用全部指错）：

```markdown
11. **演示模式的会话是 bot 会话，不得混进正式数据。** 演示 config（`*_bots`）跑出来的
    被试在导出里可识别、可过滤：`participant._is_bot` 为 1、`session.is_demo` 为 1。
    导出后**按 `participant._is_bot == 0` 过滤**，而不是依赖「记得不要在正式库上跑」。
    另注意 `/api/export_wide` 会**忽略 `code` 参数**、导出库中全部会话——想只看一个
    会话时必须自行按 `session.code` 筛选。
```

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -m "docs: README 同步演示模式（§3 结构 / §4.1 用法 / §5 计数 49 / §9 数据卫生）"
```

---

## 自查记录

**规格覆盖**：§1 目标/硬约束 → Task 2 Step 1（条件断言）、Task 5 Step 2（回归）；§2 事实表
→ 已写入规格，非代码；§3.1 守卫 → Task 2 Step 5；§3.2 门控 → Task 2 Step 4；§3.3 控制台 →
Task 3；§4 文件清单 → Task 1-3；§6.1 config 守卫 → Task 1；§6.2 模板守卫 → Task 2-3；
§6.3 证伪性 → Task 4；§8 README → Task 6；§9 数据卫生 → Task 6 Step 4；§10 验证 → Task 5。

**与规格的一处偏差**（有意）：

- 规格 §3.3 说控制台从 `/SessionStartLinks/<code>` 取被试链接；实现同此，但**会话码需
  手工从地址栏复制**——oTree 没有「从会话页跳到控制台」的钩子。已写进 README §4.1。

**范围外但值得知道的两件事**：

- `_static/global/empty.css` 从未被任何模板引用（`grep -rn "empty.css" .` 只命中文档）。
  本次**不删**——它不是本次改动引入的。是否清理由用户另行决定。
- Task 5 Step 7 要跑 `otree test`，按 README §9.8 需先删 `db.sqlite3`。计划里已写明
  「先 `ls -l` 看清目标，非 0 字节就先备份」。

**实测过的关键假设**（不是推理）：

- 副本末尾追加的 `global_scripts` block **确实渲染**，且位置在 oTree 追加脚本之前
- `is_browser_bot` 条件**确实排除真实被试**（标记出现、守卫不出现）
- 漂移守卫的 diff 判定稳定：纯追加 = 1 个 insert；改动一处 = 出现 replace（必红）
- 项目根 `_static/` **确实**被服务（`/static/global/empty.css` 返回 200，对照 404）
- 单步链路全程跑通过一次（详见规格 §2 的 F9-F13 与 §10-3）
