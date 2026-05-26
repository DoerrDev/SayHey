from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QwenVoice:
    voice_id: str
    display_name: str
    gender: str
    language: str
    preview_url: str = ""
    description: str = ""


QWEN_VOICES: list[QwenVoice] = [
    QwenVoice("Tina", "甜甜 Tina", "female", "多语种", description="温暖甜美，解决问题不含糊"),
    QwenVoice("Cindy", "林欣宜 Cindy", "female", "中文(台湾口音)/多语种", description="台湾说话嗲嗲的小姐姐"),
    QwenVoice("Liora Mira", "清欢 Liora Mira", "female", "多语种", description="用声音织就烟火人间的温柔"),
    QwenVoice("Sunnybobi", "知芝 Sunnybobi", "female", "多语种", description="大大咧咧的社恐邻家姑娘"),
    QwenVoice("Raymond", "林川野 Raymond", "male", "多语种", description="声音清亮，爱吃外卖的宅男"),
    QwenVoice("Ethan", "晨煦 Ethan", "male", "多语种", description="阳光温暖活力，带部分北方口音"),
    QwenVoice("Theo Calm", "予安 Theo Calm", "male", "多语种", description="在静默处传递理解，在言语间疗愈人心"),
    QwenVoice("Serena", "苏瑶 Serena", "female", "多语种", description="温柔小姐姐"),
    QwenVoice("Harvey", "厚 Harvey", "male", "多语种", description="低沉温和，带咖啡与旧书的气息"),
    QwenVoice("Maia", "四月 Maia", "female", "多语种", description="知性与温柔的碰撞"),
    QwenVoice("Evan", "江晨 Evan", "male", "多语种", description="男大学生，年下奶狗"),
    QwenVoice("Qiao", "小乔妹 Qiao", "female", "中文(台湾口音)/多语种", description="表面甜妹，个性十足"),
    QwenVoice("Momo", "茉兔 Momo", "female", "多语种", description="撒娇搞怪，逗你开心"),
    QwenVoice("Wil", "伟伦 Wil", "male", "多语种", description="在深圳长大的港台腔小哥哥"),
    QwenVoice("Angel", "台普-安琪 Angel", "female", "多语种", description="略带台式口音，超甜"),
    QwenVoice("Li Cassian", "东厂-李公公 Li Cassian", "male", "多语种", description="话中三分留白、七分察言观色"),
    QwenVoice("Mia", "舒然 Mia", "female", "多语种", description="温柔生活博主，慢生活美学"),
    QwenVoice("Joyner", "阿逗 Joyner", "male", "多语种", description="搞笑、夸张、接地气"),
    QwenVoice("Gold", "金爷 Gold", "male", "多语种", description="西海岸黑人 Rapper"),
    QwenVoice("Katerina", "卡捷琳娜 Katerina", "female", "多语种", description="御姐音色，韵律回味十足"),
    QwenVoice("Ryan", "甜茶 Ryan", "male", "多语种", description="节奏拉满，戏感炸裂"),
    QwenVoice("Jennifer", "詹妮弗 Jennifer", "female", "多语种", description="品牌级、电影质感美语女声"),
    QwenVoice("Aiden", "艾登 Aiden", "male", "多语种", description="精通厨艺的美语大男孩"),
    QwenVoice("Mione", "敏儿 Mione", "female", "多语种", description="成熟知性英国邻家妹妹"),
    QwenVoice("Sohee", "素熙 Sohee", "female", "多语种", description="温柔开朗，情绪丰富的韩国欧尼"),
    QwenVoice("Lenn", "莱恩 Lenn", "male", "多语种", description="理性叛逆的德国青年"),
    QwenVoice("Ono Anna", "小野杏 Ono Anna", "female", "多语种", description="鬼灵精怪的青梅竹马"),
    QwenVoice("Sonrisa", "索尼莎 Sonrisa", "female", "多语种", description="热情开朗的拉美大姐"),
    QwenVoice("Bodega", "博德加 Bodega", "male", "多语种", description="热情的西班牙大叔"),
    QwenVoice("Emilien", "埃米尔安 Emilien", "male", "多语种", description="浪漫的法国大哥哥"),
    QwenVoice("Andre", "安德雷 Andre", "male", "多语种", description="声音磁性，自然舒服、沉稳"),
    QwenVoice("Radio Gol", "拉迪奥·戈尔 Radio Gol", "male", "多语种", description="足球诗人，激情解说"),
    QwenVoice("Alek", "阿列克 Alek", "male", "多语种", description="战斗民族的冷与暖"),
    QwenVoice("Rizky", "阿力 Rizky", "male", "多语种", description="印尼青年小伙，声线个性"),
    QwenVoice("Roya", "萝雅 Roya", "female", "多语种", description="热爱运动，自由的心"),
    QwenVoice("Arda", "阿尔达 Arda", "male", "多语种", description="干净利落中带着温润气质"),
    QwenVoice("Hana", "阿幸 Hana", "female", "多语种", description="爱狗狗的越南成熟姐姐"),
    QwenVoice("Dolce", "多尔切 Dolce", "male", "多语种", description="慵懒的意大利大叔"),
    QwenVoice("Jakub", "雅克 Jakub", "male", "多语种", description="波兰小镇文艺青年，声线磁性"),
    QwenVoice("Griet", "海娜 Griet", "female", "多语种", description="荷兰成熟又文艺的女性"),
    QwenVoice("Eliška", "艾莉卡 Eliška", "female", "多语种", description="中欧的匠心与温度"),
    QwenVoice("Marina", "玛丽娜 Marina", "female", "多语种", description="多元文化城市长大的女孩"),
    QwenVoice("Siiri", "西芮 Siiri", "female", "多语种", description="内敛温柔，语速舒缓"),
    QwenVoice("Ingrid", "林恩 Ingrid", "female", "多语种", description="挪威乡村姑娘"),
    QwenVoice("Sigga", "海娜 Sigga", "female", "多语种", description="冰岛小镇的知性女青年"),
    QwenVoice("Bea", "雅娜 Bea", "female", "多语种", description="爱喝咖啡的菲律宾甜甜小姐姐"),
    QwenVoice("Chloe", "思怡 Chloe", "female", "多语种", description="马来西亚白领女生"),
]

QWEN_VOICE_BY_ID: dict[str, QwenVoice] = {v.voice_id: v for v in QWEN_VOICES}
QWEN_DEFAULT_VOICE_ID = "Tina"


QWEN_LANGUAGES_S2S: list[tuple[str, str]] = [
    ("auto", "自动识别"),
    ("zh", "中文"),
    ("en", "英语"),
    ("ja", "日语"),
    ("ko", "韩语"),
    ("fr", "法语"),
    ("de", "德语"),
    ("es", "西班牙语"),
    ("ru", "俄语"),
    ("it", "意大利语"),
    ("pt", "葡萄牙语"),
    ("ar", "阿拉伯语"),
    ("th", "泰语"),
    ("vi", "越南语"),
    ("id", "印尼语"),
]

QWEN_LANGUAGES_TARGET: list[tuple[str, str]] = [
    (code, name) for code, name in QWEN_LANGUAGES_S2S if code != "auto"
]
