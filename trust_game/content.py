"""消息选项与强度映射。

本模块不依赖 oTree，可独立单元测试。

两侧量表均为 0-4 序数编码（规格第 6.2 节），编码越高表示信任意向 /
承诺强度越高。
"""

# (编码, 文案)。列表顺序即为界面显示顺序，从最强到最弱。
INVESTOR_MESSAGES = [
    (4, '我打算把全部 10 点都送给你'),
    (3, '我打算送出大部分点数'),
    (2, '我打算送出一部分点数'),
    (1, '我打算只送出很少的点数'),
    (0, '我还没有决定'),
]

TRUSTEE_MESSAGES = [
    (4, '我承诺会把收到的点数全部返还给你'),
    (3, '我承诺会返还一半以上'),
    (2, '我承诺会返还一部分'),
    (1, '我不确定会不会返还'),
    (0, '我还没有决定'),
]

INVESTOR_ROLE = 'Investor'
TRUSTEE_ROLE = 'Trustee'


def message_labels(messages):
    """返回用于 oTree 表单 choices 的 (存储值, 显示文案) 列表。

    存储值使用文案本身（而非编码），以便数据保留被试实际看到的内容。
    """
    return [(label, label) for _, label in messages]


def strength_of(messages, label):
    """把消息文案映射回 0-4 的强度编码。未知文案抛 KeyError。"""
    mapping = {text: code for code, text in messages}
    return mapping[label]
