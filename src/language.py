"""Localize Kirby's original thoughts without changing gameplay identifiers."""
import re
from preferences import values

TEXT = {
    'Whoa!': '哇喵！', 'Dizzy...': '有点晕喵……', 'Again!!': '再来一次！',
    'Caught you! Nom nom~': '抓到啦！抱住啃啃～', 'That was fun!': '还想再玩一会儿～',
    'Delicious~': '好好吃～', 'More food!': '还想吃！', 'Poyo~!': '啵哟～！',
    'Poyo~': '啵哟～', 'Hehe~': '嘿嘿～', 'That tickles!': '好痒呀！',
    'More pets!': '再摸摸我！', "I'm starving...": '肚子好饿……',
    'Oops...': '哎呀……', 'Uh oh~': '糟糕～', 'Excuse me!': '不好意思！',
    'Thanks!': '谢谢你！', 'Clean~!': '干净啦～！', 'Sparkle!': '亮晶晶！',
    '*trips* Poyo!': '绊了一下！啵哟！', 'Dance time!': '跳个舞吧！',
    'Achoo!': '阿嚏！', 'Hic!': '嗝！', 'Hiccup!': '打嗝啦！',
    'Wheee!': '飞起来啦！', 'Poyooo~!': '啵哟哟～！', 'Waaaah!': '哇啊！',
    'A baby kitten!': '猫咪宝宝！', 'New friend!': '新朋友！',
    'Poyo poyo~!': '啵哟啵哟～！', 'Family grows!': '家里又热闹啦！',
    "Good morning! Let's code!": '早上好！一起工作吧！',
    'Time to be productive!': '元气满满的一天！', 'Lunch time? Feed me!': '午饭时间，喂喂我！',
    'Afternoon coding session!': '下午也要加油哦！', 'Evening already? Keep going!': '晚上好，辛苦啦！',
    'So late... still coding?': '这么晚了，还在忙吗？',
    '*hic* ...hic!': '嗝……嗝！', 'So hot...': '好热呀……',
    'Awoo awoo~ Lao Wu Lao Wu!': '嗷呜嗷呜～老吴老吴！', 'Hisss!!': '哈——！！',
    'Mrrrowww...': '呜嗷嗷嗷……', 'Who are you?!': '你是谁？！', 'Phew...': '呼……吓死猫了',
    'CPU burning!': '处理器好忙呀！', 'Need rest...': '想休息一下……', 'Working hard!': '努力工作中！',
}
FOODS_ZH = dict(Fish='小鱼', Chicken='鸡肉', Kibble='猫粮', Tuna='金枪鱼', Salmon='三文鱼', **{'Cat Treat': '猫零食', 'Star Treat': '星星冻干'})
ACH = {
 'first_bite': ('第一口', '吃到第一份食物'), 'hungry_boy': ('小馋猫', '吃掉 10 份食物'),
 'level5': ('长大啦', '达到 5 级'), 'level10': ('大猫咪', '达到 10 级'),
 'level25': ('猫咪大王', '达到 25 级'), 'glutton': ('美食家', '吃掉 50 份食物'),
 'legend': ('传说吃货', '吃掉 200 份食物'), 'pet_lover': ('摸摸头', '被抚摸 20 次'),
 'star_hunter': ('星星猎人', '吃掉 10 颗星星冻干'),
}

def thought(text):
    text = text.replace('Kirby', 'kitten')
    if 'Poyo' in text or 'poyo' in text:
        return '喵呜～' if values['language'] == 'zh' else 'Mrrp~!'
    if values['language'] != 'zh':
        return text
    if text in TEXT:
        return TEXT[text]
    if text.startswith('Yum! '):
        return '好吃！' + FOODS_ZH.get(text[5:].rstrip('!'), text[5:].rstrip('!')) + '！'
    match = re.fullmatch(r'Level (\d+)!', text)
    if match:
        return f'升到 {match[1]} 级啦！'
    if text.startswith('Found a star!'):
        return text.replace('Found a star!', '找到一颗星星！')
    for en, zh in [('CPU is hot!', '电脑有点烫！'), ('So much work!', '任务好多呀！'), ('Take a break?', '休息一下吧？')]:
        text = text.replace(en, zh)
    for key, (name, _) in ACH.items():
        from utils.utils import ACHIEVEMENTS
        original = next(a['name'] for a in ACHIEVEMENTS if a['id'] == key)
        text = text.replace(original, name)
    return text
