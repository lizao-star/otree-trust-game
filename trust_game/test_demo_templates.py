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

        # autojunk=False：默认的启发式会把大量重复行（本模板里 endblock/endif
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


CONSOLE_HTML = PROJECT_ROOT / '_static' / 'global' / 'step_console.html'
GUARD_HTML = PROJECT_ROOT / '_templates' / 'bot_step_guard.html'


class TestGuardIsUnconditional(unittest.TestCase):
    """守卫必须在 bot 页面上**无条件**生效——不得引入任何 opt-in 开关。

    返工记录（规格 §13）：初版用一个 `sessionStorage` 开关做 opt-in，且只有
    控制台页会设它。后果是：从会话页的 **Grid view**、split-screen 或单个被试
    链接打开时开关不存在，守卫完全不生效，8 个机器人 2 秒全部跑完——用户实际
    就是这么踩到的。更糟的是该开关在同一标签页里是**粘住**的，于是同一个 URL
    的行为取决于此前在这个标签页里访问过什么（实测：先开控制台再开 Grid view
    会「看起来正常」，换个标签页就复现）。

    本用例把「不许再引入任何形式的开关」钉住：守卫与控制台里都不许出现
    `sessionStorage`。加了它就等于把「静默变回自动跑完」这条路重新打开。
    """

    def test_no_opt_in_switch_in_guard_or_console(self):
        # 匹配 `sessionStorage.`（带点），也就是真正的调用写法
        # （setItem / getItem / removeItem）。刻意不匹配光秃秃的关键词：
        # 两份文件里都有**说明为什么不能用它**的注释，那些散文不该让用例变红。
        for path in (GUARD_HTML, CONSOLE_HTML):
            self.assertNotIn(
                'sessionStorage.', path.read_text(encoding='utf-8'),
                f'{path.name} 里出现了 sessionStorage 调用：守卫一旦依赖 opt-in '
                '开关，未经控制台打开的 bot 页面（如 Grid view）会静默变回自动'
                '跑完，详见规格 §13',
            )


if __name__ == '__main__':
    unittest.main()
