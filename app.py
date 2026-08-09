import os
import uuid
import json
import random
import requests
import base64
import gzip
import io
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageEnhance
from flask import Flask, request, render_template_string, send_from_directory

app = Flask(__name__)

# ==================== 生产环境配置 ====================
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 上传限制

# 内存配置存储（Render 免费版重启会清空；永久链接 /p/ 不依赖此处）
USER_CONFIGS = {}

# ==================== Kindle 分辨率规格 ====================
# chrome = 浏览器顶部工具栏占用高度（px，估算值），用于计算可视区域居中
MODELS = {
    "basic":   {"name": "Kindle 基础版 第10代及以前", "w": 600,  "h": 800,  "chrome": 55},
    "basic11": {"name": "Kindle 基础版 第11代",       "w": 758,  "h": 1024, "chrome": 90},
    "pw3":     {"name": "Paperwhite 第7代及以前",     "w": 758,  "h": 1024, "chrome": 90},
    "pw4":     {"name": "Paperwhite 第10代",          "w": 758,  "h": 1024, "chrome": 90},
    "pw5":     {"name": "Paperwhite 第11代",          "w": 1236, "h": 1648, "chrome": 90},
    "oasis":   {"name": "Oasis 第9/10代",             "w": 1264, "h": 1680, "chrome": 90},
    "scribe":  {"name": "Scribe",                     "w": 1860, "h": 2480, "chrome": 90},
}

# ==================== 词库（11 语种，例句附中文翻译） ====================
WORD_BANK = {
    "english": {
        "name": "英语", "flag": "🇺🇸",
        "books": {
            "cet4": {"name": "四级英语词汇", "words": [
                {"word": "abandon", "phonetic": "/əˈbændən/", "meaning": "v. 放弃，抛弃", "example": "He abandoned his car in the snow.", "example_cn": "他把车丢在了雪地里。"},
                {"word": "ability", "phonetic": "/əˈbɪləti/", "meaning": "n. 能力，才能", "example": "She has the ability to speak four languages.", "example_cn": "她会说四种语言。"},
                {"word": "absolute", "phonetic": "/ˈæbsəluːt/", "meaning": "adj. 绝对的；完全的", "example": "I have absolute confidence in her.", "example_cn": "我对她有绝对的信心。"},
                {"word": "academic", "phonetic": "/ˌækəˈdemɪk/", "meaning": "adj. 学术的；学院的", "example": "She had a brilliant academic career.", "example_cn": "她的学术生涯非常辉煌。"},
                {"word": "access", "phonetic": "/ˈækses/", "meaning": "n. 通道；使用权", "example": "Students need access to books.", "example_cn": "学生需要能接触到书籍。"},
                {"word": "accompany", "phonetic": "/əˈkʌmpəni/", "meaning": "v. 陪伴，伴随", "example": "She accompanied me to the hospital.", "example_cn": "她陪我去了医院。"},
                {"word": "accomplish", "phonetic": "/əˈkɑːmplɪʃ/", "meaning": "v. 完成，实现", "example": "He accomplished his goal.", "example_cn": "他完成了自己的目标。"},
                {"word": "account", "phonetic": "/əˈkaʊnt/", "meaning": "n. 账户；说明", "example": "I opened a bank account.", "example_cn": "我开了一个银行账户。"},
                {"word": "accurate", "phonetic": "/ˈækjərət/", "meaning": "adj. 准确的，精确的", "example": "The report is accurate.", "example_cn": "这份报告是准确的。"},
                {"word": "achieve", "phonetic": "/əˈtʃiːv/", "meaning": "v. 达到，取得", "example": "She achieved great success.", "example_cn": "她取得了巨大的成功。"},
                {"word": "acknowledge", "phonetic": "/əkˈnɑːlɪdʒ/", "meaning": "v. 承认；致谢", "example": "He acknowledged his mistake.", "example_cn": "他承认了自己的错误。"},
                {"word": "acquire", "phonetic": "/əˈkwaɪər/", "meaning": "v. 获得，习得", "example": "She acquired new skills.", "example_cn": "她学到了新技能。"},
                {"word": "adapt", "phonetic": "/əˈdæpt/", "meaning": "v. 适应；改编", "example": "Children adapt quickly.", "example_cn": "孩子们适应得很快。"},
                {"word": "adequate", "phonetic": "/ˈædɪkwət/", "meaning": "adj. 足够的，适当的", "example": "We have adequate food.", "example_cn": "我们有足够的食物。"},
                {"word": "adjust", "phonetic": "/əˈdʒʌst/", "meaning": "v. 调整，适应", "example": "Adjust the volume please.", "example_cn": "请调一下音量。"},
                {"word": "admire", "phonetic": "/ədˈmaɪər/", "meaning": "v. 钦佩，羡慕", "example": "I admire his courage.", "example_cn": "我钦佩他的勇气。"},
                {"word": "admit", "phonetic": "/ədˈmɪt/", "meaning": "v. 承认；允许进入", "example": "He admitted his fault.", "example_cn": "他承认了自己的过错。"},
                {"word": "adopt", "phonetic": "/əˈdɑːpt/", "meaning": "v. 采用；收养", "example": "They adopted a child.", "example_cn": "他们收养了一个孩子。"},
                {"word": "advance", "phonetic": "/ədˈvæns/", "meaning": "v./n. 前进；进步", "example": "Technology advances rapidly.", "example_cn": "科技进步迅速。"},
                {"word": "advantage", "phonetic": "/ədˈvæntɪdʒ/", "meaning": "n. 优势，好处", "example": "Take advantage of the chance.", "example_cn": "抓住这个机会。"},
                {"word": "adventure", "phonetic": "/ədˈventʃər/", "meaning": "n. 冒险，奇遇", "example": "Life is an adventure.", "example_cn": "生活就是一场冒险。"},
                {"word": "advertise", "phonetic": "/ˈædvərtaɪz/", "meaning": "v. 做广告，宣传", "example": "They advertise on TV.", "example_cn": "他们在电视上做广告。"},
                {"word": "advise", "phonetic": "/ədˈvaɪz/", "meaning": "v. 建议，劝告", "example": "I advise you to rest.", "example_cn": "我建议你休息。"},
                {"word": "affair", "phonetic": "/əˈfer/", "meaning": "n. 事情，事务", "example": "It's a private affair.", "example_cn": "这是私事。"},
                {"word": "affect", "phonetic": "/əˈfekt/", "meaning": "v. 影响；感动", "example": "The weather affects my mood.", "example_cn": "天气影响我的心情。"},
                {"word": "afford", "phonetic": "/əˈfɔːrd/", "meaning": "v. 买得起；承担得起", "example": "I can't afford a car.", "example_cn": "我买不起车。"},
                {"word": "afraid", "phonetic": "/əˈfreɪd/", "meaning": "adj. 害怕的；担心的", "example": "Don't be afraid.", "example_cn": "别害怕。"},
                {"word": "agency", "phonetic": "/ˈeɪdʒənsi/", "meaning": "n. 代理机构；力量", "example": "A travel agency booked it.", "example_cn": "旅行社订的。"},
                {"word": "agenda", "phonetic": "/əˈdʒendə/", "meaning": "n. 议程，日程", "example": "What's on the agenda?", "example_cn": "日程是什么？"},
                {"word": "aggressive", "phonetic": "/əˈɡresɪv/", "meaning": "adj. 侵略的；积极进取的", "example": "He is very aggressive.", "example_cn": "他非常好胜。"},
            ]},
            "cet6": {"name": "六级英语词汇", "words": [
                {"word": "ambiguous", "phonetic": "/æmˈbɪɡjuəs/", "meaning": "adj. 模棱两可的", "example": "The instructions were ambiguous.", "example_cn": "这些指示含糊不清。"},
                {"word": "analogy", "phonetic": "/əˈnælədʒi/", "meaning": "n. 类比，类推", "example": "He drew an analogy between the brain and a computer.", "example_cn": "他把大脑比作电脑。"},
                {"word": "abundant", "phonetic": "/əˈbʌndənt/", "meaning": "adj. 丰富的，充裕的", "example": "The region has abundant resources.", "example_cn": "这个地区资源丰富。"},
                {"word": "accommodate", "phonetic": "/əˈkɑːmədeɪt/", "meaning": "v. 容纳；适应", "example": "The hotel can accommodate 200 guests.", "example_cn": "这家酒店能容纳200位客人。"},
                {"word": "accumulate", "phonetic": "/əˈkjuːmjəleɪt/", "meaning": "v. 积累，积聚", "example": "Dust had accumulated over years.", "example_cn": "灰尘积累了多年。"},
                {"word": "acquaint", "phonetic": "/əˈkweɪnt/", "meaning": "v. 使熟悉，使了解", "example": "Let me acquaint you with the facts.", "example_cn": "让我告诉你事实。"},
                {"word": "acute", "phonetic": "/əˈkjuːt/", "meaning": "adj. 敏锐的；急性的", "example": "She has acute hearing.", "example_cn": "她听觉敏锐。"},
                {"word": "adhere", "phonetic": "/ədˈhɪr/", "meaning": "v. 粘附；坚持", "example": "Adhere to the rules.", "example_cn": "遵守规则。"},
                {"word": "adjacent", "phonetic": "/əˈdʒeɪsnt/", "meaning": "adj. 邻近的，毗邻的", "example": "The adjacent room is empty.", "example_cn": "隔壁房间是空的。"},
                {"word": "administer", "phonetic": "/ədˈmɪnɪstər/", "meaning": "v. 管理；执行", "example": "He administers a large company.", "example_cn": "他管理一家大公司。"},
                {"word": "adolescent", "phonetic": "/ˌædəˈlesnt/", "meaning": "n./adj. 青少年（的）", "example": "Adolescents need guidance.", "example_cn": "青少年需要引导。"},
                {"word": "advent", "phonetic": "/ˈædvent/", "meaning": "n. 到来，出现", "example": "The advent of the internet changed everything.", "example_cn": "互联网的出现改变了一切。"},
                {"word": "adverse", "phonetic": "/ˈædvɜːrs/", "meaning": "adj. 不利的，相反的", "example": "Adverse weather delayed us.", "example_cn": "恶劣天气耽误了我们。"},
                {"word": "aesthetic", "phonetic": "/esˈθetɪk/", "meaning": "adj. 美学的，审美的", "example": "The design has great aesthetic appeal.", "example_cn": "这个设计具有很高的美学吸引力。"},
                {"word": "affiliate", "phonetic": "/əˈfɪlieɪt/", "meaning": "v. 使隶属，加入", "example": "Our club is affiliated with the university.", "example_cn": "我们的俱乐部隶属于这所大学。"},
                {"word": "aggravate", "phonetic": "/ˈæɡrəveɪt/", "meaning": "v. 加重；激怒", "example": "Don't aggravate the situation.", "example_cn": "不要让局势恶化。"},
                {"word": "alleviate", "phonetic": "/əˈliːvieɪt/", "meaning": "v. 减轻，缓和", "example": "The medicine alleviated the pain.", "example_cn": "这种药减轻了疼痛。"},
                {"word": "allocate", "phonetic": "/ˈæləkeɪt/", "meaning": "v. 分配，拨出", "example": "They allocated funds for research.", "example_cn": "他们为研究拨了款。"},
                {"word": "alter", "phonetic": "/ˈɔːltər/", "meaning": "v. 改变，修改", "example": "The plan was slightly altered.", "example_cn": "计划做了一点修改。"},
                {"word": "amateur", "phonetic": "/ˈæmətər/", "meaning": "n./adj. 业余爱好者（的）", "example": "He is an amateur pianist.", "example_cn": "他是业余钢琴家。"},
            ]},
            "kaoyan": {"name": "考研英语词汇", "words": [
                {"word": "advocate", "phonetic": "/ˈædvəkeɪt/", "meaning": "v. 提倡，拥护 n. 拥护者", "example": "She advocates taking a long-term view.", "example_cn": "她主张从长计议。"},
                {"word": "alleviate", "phonetic": "/əˈliːvieɪt/", "meaning": "v. 减轻，缓和", "example": "The medicine alleviated the pain.", "example_cn": "这种药减轻了疼痛。"},
                {"word": "acknowledge", "phonetic": "/əkˈnɑːlɪdʒ/", "meaning": "v. 承认；确认", "example": "We must acknowledge the problem.", "example_cn": "我们必须承认这个问题。"},
                {"word": "acquire", "phonetic": "/əˈkwaɪər/", "meaning": "v. 获得，取得", "example": "He acquired a taste for classical music.", "example_cn": "他培养出了对古典音乐的爱好。"},
                {"word": "address", "phonetic": "/əˈdres/", "meaning": "v. 处理；发表演说 n. 地址", "example": "We need to address this issue.", "example_cn": "我们需要处理这个问题。"},
                {"word": "adequate", "phonetic": "/ˈædɪkwət/", "meaning": "adj. 充分的，足够的", "example": "The evidence is adequate.", "example_cn": "证据充分。"},
                {"word": "adjacent", "phonetic": "/əˈdʒeɪsnt/", "meaning": "adj. 邻近的，毗连的", "example": "The school is adjacent to the park.", "example_cn": "学校紧邻公园。"},
                {"word": "administration", "phonetic": "/ədˌmɪnɪˈstreɪʃn/", "meaning": "n. 管理；行政；政府", "example": "The new administration took office.", "example_cn": "新政府上任了。"},
                {"word": "adopt", "phonetic": "/əˈdɑːpt/", "meaning": "v. 采用；采取；收养", "example": "The committee adopted the proposal.", "example_cn": "委员会采纳了这项提议。"},
                {"word": "advance", "phonetic": "/ədˈvæns/", "meaning": "v. 促进；提出 n. 进步", "example": "He advanced a new theory.", "example_cn": "他提出了一个新理论。"},
                {"word": "affect", "phonetic": "/əˈfekt/", "meaning": "v. 影响；感染", "example": "The policy affects everyone.", "example_cn": "这项政策影响所有人。"},
                {"word": "aggregate", "phonetic": "/ˈæɡrɪɡət/", "meaning": "n./adj. 总数（的） v. 合计", "example": "The aggregate cost is high.", "example_cn": "总成本很高。"},
                {"word": "allegation", "phonetic": "/ˌæləˈɡeɪʃn/", "meaning": "n. 指控，主张", "example": "He denied the allegations.", "example_cn": "他否认了这些指控。"},
                {"word": "allocate", "phonetic": "/ˈæləkeɪt/", "meaning": "v. 分配，分派", "example": "Resources must be allocated efficiently.", "example_cn": "资源必须高效分配。"},
                {"word": "alternative", "phonetic": "/ɔːlˈtɜːrnətɪv/", "meaning": "n./adj. 供替代的（选择）", "example": "We have no alternative.", "example_cn": "我们别无选择。"},
                {"word": "ambiguity", "phonetic": "/ˌæmbɪˈɡjuːəti/", "meaning": "n. 含糊，不明确", "example": "There is some ambiguity in the law.", "example_cn": "法律中存在一些模糊之处。"},
                {"word": "ambitious", "phonetic": "/æmˈbɪʃəs/", "meaning": "adj. 有抱负的，雄心勃勃的", "example": "She is ambitious for success.", "example_cn": "她渴望成功。"},
                {"word": "analyze", "phonetic": "/ˈænəlaɪz/", "meaning": "v. 分析，研究", "example": "Let's analyze the data.", "example_cn": "我们来分析这些数据。"},
                {"word": "approach", "phonetic": "/əˈproʊtʃ/", "meaning": "n./v. 方法；接近", "example": "A new approach is needed.", "example_cn": "需要一种新方法。"},
                {"word": "appropriate", "phonetic": "/əˈproʊpriət/", "meaning": "adj. 适当的 v. 挪用", "example": "Is this dress appropriate?", "example_cn": "这件裙子合适吗？"},
            ]},
            "ielts": {"name": "雅思核心词汇", "words": [
                {"word": "contemporary", "phonetic": "/kənˈtempəreri/", "meaning": "adj. 当代的；同时代的", "example": "Contemporary art is often controversial.", "example_cn": "当代艺术常常引发争议。"},
                {"word": "accommodation", "phonetic": "/əˌkɑːməˈdeɪʃn/", "meaning": "n. 住宿，膳宿", "example": "We booked accommodation online.", "example_cn": "我们在网上订了住宿。"},
                {"word": "achievement", "phonetic": "/əˈtʃiːvmənt/", "meaning": "n. 成就，成绩", "example": "It is a remarkable achievement.", "example_cn": "这是一项了不起的成就。"},
                {"word": "acknowledge", "phonetic": "/əkˈnɑːlɪdʒ/", "meaning": "v. 承认；公认", "example": "He is acknowledged as an expert.", "example_cn": "他被公认为专家。"},
                {"word": "acquire", "phonetic": "/əˈkwaɪər/", "meaning": "v. 获得，习得（语言技能）", "example": "Children acquire language quickly.", "example_cn": "儿童习得语言很快。"},
                {"word": "adequate", "phonetic": "/ˈædɪkwət/", "meaning": "adj. 足够的，合格的", "example": "Adequate preparation is key.", "example_cn": "充分的准备是关键。"},
                {"word": "adjustment", "phonetic": "/əˈdʒʌstmənt/", "meaning": "n. 调整，适应", "example": "Freshmen need time for adjustment.", "example_cn": "新生需要时间适应。"},
                {"word": "administrative", "phonetic": "/ədˈmɪnɪstreɪtɪv/", "meaning": "adj. 行政的，管理的", "example": "Administrative work takes time.", "example_cn": "行政工作需要时间。"},
                {"word": "advocate", "phonetic": "/ˈædvəkeɪt/", "meaning": "v. 提倡 n. 倡导者", "example": "She advocates green living.", "example_cn": "她倡导绿色生活。"},
                {"word": "aesthetic", "phonetic": "/esˈθetɪk/", "meaning": "adj. 美学的，审美的", "example": "The building has aesthetic value.", "example_cn": "这座建筑具有美学价值。"},
                {"word": "affect", "phonetic": "/əˈfekt/", "meaning": "v. 影响（尤指负面）", "example": "Pollution affects health.", "example_cn": "污染影响健康。"},
                {"word": "affordable", "phonetic": "/əˈfɔːrdəbl/", "meaning": "adj. 负担得起的", "example": "Affordable housing is needed.", "example_cn": "需要经济适用房。"},
                {"word": "aggregate", "phonetic": "/ˈæɡrɪɡət/", "meaning": "n. 总数 adj. 合计的", "example": "The aggregate score was 85%.", "example_cn": "总分为85%。"},
                {"word": "allocate", "phonetic": "/ˈæləkeɪt/", "meaning": "v. 分配（资源/时间）", "example": "Time must be allocated wisely.", "example_cn": "必须明智分配时间。"},
                {"word": "alternative", "phonetic": "/ɔːlˈtɜːrnətɪv/", "meaning": "adj. 替代的 n. 选择", "example": "Is there an alternative route?", "example_cn": "有替代路线吗？"},
                {"word": "ambient", "phonetic": "/ˈæmbiənt/", "meaning": "adj. 周围的，环境的", "example": "Ambient lighting is important.", "example_cn": "环境照明很重要。"},
                {"word": "ambiguous", "phonetic": "/æmˈbɪɡjuəs/", "meaning": "adj. 模糊的，有歧义的", "example": "His answer was ambiguous.", "example_cn": "他的回答含糊不清。"},
                {"word": "amend", "phonetic": "/əˈmend/", "meaning": "v. 修正，改正", "example": "The law was amended.", "example_cn": "法律得到了修正。"},
                {"word": "analyze", "phonetic": "/ˈænəlaɪz/", "meaning": "v. 分析，剖析", "example": "Analyze the results carefully.", "example_cn": "仔细分析结果。"},
                {"word": "anticipate", "phonetic": "/ænˈtɪsɪpeɪt/", "meaning": "v. 预期，预料", "example": "We anticipate a rise in demand.", "example_cn": "我们预计需求会增加。"},
            ]},
            "toefl": {"name": "托福核心词汇", "words": [
                {"word": "substantial", "phonetic": "/səbˈstænʃl/", "meaning": "adj. 大量的；实质的", "example": "The project requires substantial funding.", "example_cn": "这个项目需要大量资金。"},
                {"word": "abundant", "phonetic": "/əˈbʌndənt/", "meaning": "adj. 丰富的，充足的", "example": "The forest has abundant wildlife.", "example_cn": "这片森林有丰富的野生动物。"},
                {"word": "accelerate", "phonetic": "/əkˈseləreɪt/", "meaning": "v. 加速，促进", "example": "The car accelerated quickly.", "example_cn": "汽车加速很快。"},
                {"word": "accessible", "phonetic": "/əkˈsesəbl/", "meaning": "adj. 可进入的；易懂的", "example": "The museum is accessible.", "example_cn": "这家博物馆方便前往。"},
                {"word": "accomplish", "phonetic": "/əˈkɑːmplɪʃ/", "meaning": "v. 完成，达到", "example": "She accomplished the task.", "example_cn": "她完成了任务。"},
                {"word": "accumulate", "phonetic": "/əˈkjuːmjəleɪt/", "meaning": "v. 积累，堆积", "example": "Data accumulates over time.", "example_cn": "数据随时间积累。"},
                {"word": "accurate", "phonetic": "/ˈækjərət/", "meaning": "adj. 准确的，精确的", "example": "Accurate data is essential.", "example_cn": "准确数据至关重要。"},
                {"word": "acknowledge", "phonetic": "/əkˈnɑːlɪdʒ/", "meaning": "v. 承认；感谢", "example": "The author acknowledges his sources.", "example_cn": "作者感谢了他的资料来源。"},
                {"word": "acquire", "phonetic": "/əˈkwaɪər/", "meaning": "v. 获得；学到", "example": "He acquired a new skill.", "example_cn": "他学会了一项新技能。"},
                {"word": "adapt", "phonetic": "/əˈdæpt/", "meaning": "v. 适应；改编", "example": "Animals adapt to environment.", "example_cn": "动物适应环境。"},
                {"word": "adjacent", "phonetic": "/əˈdʒeɪsnt/", "meaning": "adj. 相邻的，毗邻的", "example": "The two towns are adjacent.", "example_cn": "这两个城镇相邻。"},
                {"word": "administer", "phonetic": "/ədˈmɪnɪstər/", "meaning": "v. 管理；执行", "example": "She administers the fund.", "example_cn": "她管理这笔基金。"},
                {"word": "advocate", "phonetic": "/ˈædvəkeɪt/", "meaning": "v. 提倡，主张", "example": "Experts advocate exercise.", "example_cn": "专家提倡锻炼身体。"},
                {"word": "aesthetic", "phonetic": "/esˈθetɪk/", "meaning": "adj. 美学的 n. 美感", "example": "The design is aesthetic.", "example_cn": "这个设计很美。"},
                {"word": "aggregate", "phonetic": "/ˈæɡrɪɡət/", "meaning": "n./v. 合计；聚集", "example": "The aggregate demand rose.", "example_cn": "总需求增加了。"},
                {"word": "alleviate", "phonetic": "/əˈliːvieɪt/", "meaning": "v. 缓解，减轻", "example": "Ice alleviates swelling.", "example_cn": "冰敷可消肿。"},
                {"word": "allocate", "phonetic": "/ˈæləkeɪt/", "meaning": "v. 分配，划拨", "example": "Funds were allocated wisely.", "example_cn": "资金分配合理。"},
                {"word": "ambiguous", "phonetic": "/æmˈbɪɡjuəs/", "meaning": "adj. 含糊的，歧义的", "example": "Avoid ambiguous statements.", "example_cn": "避免含糊的表述。"},
                {"word": "analogous", "phonetic": "/əˈnæləɡəs/", "meaning": "adj. 类似的，类比的", "example": "It is analogous to the brain.", "example_cn": "它与大脑类似。"},
                {"word": "anticipate", "phonetic": "/ænˈtɪsɪpeɪt/", "meaning": "v. 预测，期望", "example": "We anticipate problems.", "example_cn": "我们预料到会有问题。"},
            ]},
            "gre": {"name": "GRE词汇", "words": [
                {"word": "abate", "phonetic": "/əˈbeɪt/", "meaning": "v. 减弱，减轻", "example": "The storm began to abate.", "example_cn": "暴风雨开始减弱。"},
                {"word": "aberrant", "phonetic": "/æˈberənt/", "meaning": "adj. 异常的，偏离的", "example": "His aberrant behavior surprised us.", "example_cn": "他反常的行为让我们惊讶。"},
                {"word": "abjure", "phonetic": "/æbˈdʒʊr/", "meaning": "v. 发誓放弃，弃绝", "example": "He abjured his old beliefs.", "example_cn": "他发誓放弃旧信仰。"},
                {"word": "abrasive", "phonetic": "/əˈbreɪsɪv/", "meaning": "adj. 磨损的；生硬的", "example": "He has an abrasive manner.", "example_cn": "他态度生硬。"},
                {"word": "abrogate", "phonetic": "/ˈæbrəɡeɪt/", "meaning": "v. 废除，取消（法律）", "example": "The treaty was abrogated.", "example_cn": "条约被废除了。"},
                {"word": "abscond", "phonetic": "/æbˈskɑːnd/", "meaning": "v. 潜逃，逃跑", "example": "He absconded with the money.", "example_cn": "他携款潜逃了。"},
                {"word": "abstemious", "phonetic": "/əbˈstiːmiəs/", "meaning": "adj. 有节制的，节俭的", "example": "She is abstemious in eating.", "example_cn": "她饮食节制。"},
                {"word": "abstract", "phonetic": "/ˈæbstrækt/", "meaning": "adj. 抽象的 n. 摘要", "example": "Abstract concepts are hard.", "example_cn": "抽象概念很难。"},
                {"word": "abstruse", "phonetic": "/æbˈstruːs/", "meaning": "adj. 深奥的，难懂的", "example": "The theory is abstruse.", "example_cn": "这个理论很深奥。"},
                {"word": "acclaim", "phonetic": "/əˈkleɪm/", "meaning": "v./n. 欢呼；称赞", "example": "The film received wide acclaim.", "example_cn": "这部电影广受赞誉。"},
                {"word": "accolade", "phonetic": "/ˈækəleɪd/", "meaning": "n. 荣誉，赞扬", "example": "He received many accolades.", "example_cn": "他获得了很多荣誉。"},
                {"word": "accretion", "phonetic": "/əˈkriːʃn/", "meaning": "n. 堆积，增长", "example": "Rocks form by accretion.", "example_cn": "岩石靠堆积形成。"},
                {"word": "acerbic", "phonetic": "/əˈsɜːrbɪk/", "meaning": "adj. 尖酸的，刻薄的", "example": "Her acerbic comments stung.", "example_cn": "她尖刻的评论很伤人。"},
                {"word": "acquiesce", "phonetic": "/ˌækwiˈes/", "meaning": "v. 默许，勉强同意", "example": "She acquiesced to the plan.", "example_cn": "她默许了这个计划。"},
                {"word": "acrid", "phonetic": "/ˈækrɪd/", "meaning": "adj. 辛辣的；尖刻的", "example": "Acrid smoke filled the room.", "example_cn": "刺鼻的烟雾充满了房间。"},
                {"word": "acrimonious", "phonetic": "/ˌækrɪˈmoʊniəs/", "meaning": "adj. 激烈的，尖刻的", "example": "The debate was acrimonious.", "example_cn": "辩论异常激烈。"},
                {"word": "adhere", "phonetic": "/ədˈhɪr/", "meaning": "v. 粘附；坚持", "example": "Adhere to the principle.", "example_cn": "坚持原则。"},
                {"word": "adjure", "phonetic": "/əˈdʒʊr/", "meaning": "v. 恳求，郑重要求", "example": "I adjure you to tell the truth.", "example_cn": "我恳请你说实话。"},
                {"word": "admonish", "phonetic": "/ədˈmɑːnɪʃ/", "meaning": "v. 告诫，警告", "example": "He admonished the children.", "example_cn": "他告诫了孩子们。"},
                {"word": "adroit", "phonetic": "/əˈdrɔɪt/", "meaning": "adj. 灵巧的，机敏的", "example": "She is adroit at handling people.", "example_cn": "她善于处理人际关系。"},
            ]},
            "business": {"name": "商务英语", "words": [
                {"word": "deadline", "phonetic": "/ˈdedlaɪn/", "meaning": "n. 截止日期，最后期限", "example": "We must meet the deadline.", "example_cn": "我们必须赶上截止日期。"},
                {"word": "account", "phonetic": "/əˈkaʊnt/", "meaning": "n. 账户；账目 v. 说明", "example": "Please settle the account.", "example_cn": "请结清账目。"},
                {"word": "acquire", "phonetic": "/əˈkwaɪər/", "meaning": "v. 收购；获得", "example": "They acquired a competitor.", "example_cn": "他们收购了一家竞争对手。"},
                {"word": "address", "phonetic": "/əˈdres/", "meaning": "v. 处理；致辞 n. 地址", "example": "Address customer complaints quickly.", "example_cn": "快速处理客户投诉。"},
                {"word": "adjust", "phonetic": "/əˈdʒʌst/", "meaning": "v. 调整，调节", "example": "We need to adjust prices.", "example_cn": "我们需要调整价格。"},
                {"word": "advance", "phonetic": "/ədˈvæns/", "meaning": "n./v. 预付款；进展", "example": "We received an advance payment.", "example_cn": "我们收到了预付款。"},
                {"word": "advertise", "phonetic": "/ˈædvərtaɪz/", "meaning": "v. 做广告，登广告", "example": "We advertise on social media.", "example_cn": "我们在社交媒体上做广告。"},
                {"word": "advise", "phonetic": "/ədˈvaɪz/", "meaning": "v. 建议，咨询", "example": "Please advise us on this.", "example_cn": "请就此给我们建议。"},
                {"word": "affect", "phonetic": "/əˈfekt/", "meaning": "v. 影响（运营/利润）", "example": "Costs affect profitability.", "example_cn": "成本影响盈利。"},
                {"word": "agreement", "phonetic": "/əˈɡriːmənt/", "meaning": "n. 协议，合同", "example": "We signed a new agreement.", "example_cn": "我们签署了新协议。"},
                {"word": "allocate", "phonetic": "/ˈæləkeɪt/", "meaning": "v. 分配（预算/资源）", "example": "Allocate the budget wisely.", "example_cn": "明智分配预算。"},
                {"word": "amend", "phonetic": "/əˈmend/", "meaning": "v. 修改（合同）", "example": "The contract was amended.", "example_cn": "合同已修改。"},
                {"word": "annual", "phonetic": "/ˈænjuəl/", "meaning": "adj. 年度的，每年的", "example": "The annual report is ready.", "example_cn": "年度报告准备好了。"},
                {"word": "anticipate", "phonetic": "/ænˈtɪsɪpeɪt/", "meaning": "v. 预期（需求/增长）", "example": "We anticipate strong demand.", "example_cn": "我们预计需求强劲。"},
                {"word": "application", "phonetic": "/ˌæplɪˈkeɪʃn/", "meaning": "n. 申请；应用程序", "example": "Submit your application online.", "example_cn": "在线提交您的申请。"},
                {"word": "appoint", "phonetic": "/əˈpɔɪnt/", "meaning": "v. 任命，委派", "example": "He was appointed director.", "example_cn": "他被任命为董事。"},
                {"word": "approve", "phonetic": "/əˈpruːv/", "meaning": "v. 批准，通过", "example": "The board approved the plan.", "example_cn": "董事会批准了该计划。"},
                {"word": "arrange", "phonetic": "/əˈreɪndʒ/", "meaning": "v. 安排；整理", "example": "Arrange a meeting please.", "example_cn": "请安排一次会议。"},
                {"word": "assess", "phonetic": "/əˈses/", "meaning": "v. 评估，估价", "example": "We need to assess the risks.", "example_cn": "我们需要评估风险。"},
                {"word": "audit", "phonetic": "/ˈɔːdɪt/", "meaning": "n./v. 审计，审核", "example": "The annual audit is next week.", "example_cn": "下周进行年度审计。"},
            ]},
        }
    },
    "japanese": {
        "name": "日语", "flag": "🇯🇵",
        "books": {
            "n1": {"name": "JLPT N1", "words": [{"word": "意向", "phonetic": "いこう", "meaning": "意向，打算", "example": "彼の意向を確認した。", "example_cn": "确认了他的意向。"}]},
            "n2": {"name": "JLPT N2", "words": [{"word": "曖昧", "phonetic": "あいまい", "meaning": "暧昧，含糊", "example": "曖昧な返事をするな。", "example_cn": "别给含糊的答复。"}]},
            "n3": {"name": "JLPT N3", "words": [{"word": "余計", "phonetic": "よけい", "meaning": "多余", "example": "余計な心配をした。", "example_cn": "白担心了一场。"}]},
            "n4": {"name": "JLPT N4", "words": [{"word": "約束", "phonetic": "やくそく", "meaning": "约定", "example": "約束を守ってください。", "example_cn": "请遵守约定。"}]},
            "n5": {"name": "JLPT N5", "words": [{"word": "学生", "phonetic": "がくせい", "meaning": "学生", "example": "私は大学生です。", "example_cn": "我是大学生。"}]},
        }
    },
    "french": {
        "name": "法语", "flag": "🇫🇷",
        "books": {
            "tef": {"name": "TEF/TCF核心词", "words": [
                {"word": "bonjour", "phonetic": "/bɔ̃ʒuʁ/", "meaning": "interj. 你好，您好；早安", "example": "Bonjour, comment allez-vous?", "example_cn": "您好，您身体好吗？"},
                {"word": "le livre", "phonetic": "/lə livʁ/", "meaning": "n.m. 书，书籍", "example": "Je lis un livre intéressant.", "example_cn": "我在读一本有趣的书。"},
                {"word": "la maison", "phonetic": "/la mɛzɔ̃/", "meaning": "n.f. 房屋，家", "example": "Ma maison est près du parc.", "example_cn": "我家在公园附近。"},
                {"word": "le chat", "phonetic": "/lə ʃa/", "meaning": "n.m. 猫", "example": "Le chat dort sur le canapé.", "example_cn": "猫在沙发上睡觉。"},
                {"word": "la voiture", "phonetic": "/la vwatyʁ/", "meaning": "n.f. 汽车，轿车", "example": "Il achète une nouvelle voiture.", "example_cn": "他买了一辆新车。"},
                {"word": "le temps", "phonetic": "/lə tɑ̃/", "meaning": "n.m. 时间；天气", "example": "Le temps passe vite.", "example_cn": "时间过得很快。"},
                {"word": "la vie", "phonetic": "/la vi/", "meaning": "n.f. 生活，生命", "example": "La vie est belle.", "example_cn": "生活是美好的。"},
                {"word": "le travail", "phonetic": "/lə tʁavaj/", "meaning": "n.m. 工作，劳动", "example": "Je vais au travail à 8h.", "example_cn": "我八点去上班。"},
                {"word": "la famille", "phonetic": "/la famij/", "meaning": "n.f. 家庭，家人", "example": "Ma famille est grande.", "example_cn": "我的家庭很大。"},
                {"word": "l'argent (m)", "phonetic": "/laʁʒɑ̃/", "meaning": "n.m. 钱，金钱；银", "example": "Je n'ai pas d'argent.", "example_cn": "我没有钱。"},
                {"word": "l'école (f)", "phonetic": "/lekɔl/", "meaning": "n.f. 学校", "example": "Les enfants vont à l'école.", "example_cn": "孩子们去上学。"},
                {"word": "le jour", "phonetic": "/lə ʒuʁ/", "meaning": "n.m. 天，日子；白天", "example": "Quel jour sommes-nous?", "example_cn": "今天星期几？"},
                {"word": "la nuit", "phonetic": "/la nɥi/", "meaning": "n.f. 夜晚，夜里", "example": "Bonne nuit!", "example_cn": "晚安！"},
                {"word": "le restaurant", "phonetic": "/lə ʁɛstoʁɑ̃/", "meaning": "n.m. 餐厅，饭馆", "example": "On mange au restaurant ce soir.", "example_cn": "今晚我们去餐馆吃饭。"},
                {"word": "la ville", "phonetic": "/la vil/", "meaning": "n.f. 城市，市区", "example": "Paris est une belle ville.", "example_cn": "巴黎是一座美丽的城市。"},
                {"word": "le problème", "phonetic": "/lə pʁɔblɛm/", "meaning": "n.m. 问题，难题", "example": "Ce n'est pas un problème.", "example_cn": "这不是问题。"},
                {"word": "la question", "phonetic": "/la kɛstjɔ̃/", "meaning": "n.f. 问题，提问", "example": "J'ai une question à vous poser.", "example_cn": "我有个问题要问您。"},
                {"word": "l'ami (m)", "phonetic": "/lami/", "meaning": "n.m. 朋友", "example": "C'est mon meilleur ami.", "example_cn": "这是我最好的朋友。"},
                {"word": "l'amie (f)", "phonetic": "/lami/", "meaning": "n.f. 女朋友，女性朋友", "example": "Elle est mon amie d'enfance.", "example_cn": "她是我童年的朋友。"},
                {"word": "le bureau", "phonetic": "/lə byʁo/", "meaning": "n.m. 办公室；书桌", "example": "Je travaille au bureau.", "example_cn": "我在办公室工作。"},
                {"word": "la porte", "phonetic": "/la pɔʁt/", "meaning": "n.f. 门", "example": "Fermez la porte, s'il vous plaît.", "example_cn": "请关门。"},
                {"word": "le café", "phonetic": "/lə kafe/", "meaning": "n.m. 咖啡；咖啡馆", "example": "Je bois un café le matin.", "example_cn": "我早上喝一杯咖啡。"},
                {"word": "l'eau (f)", "phonetic": "/lo/", "meaning": "n.f. 水", "example": "Je bois de l'eau.", "example_cn": "我喝水。"},
                {"word": "le pain", "phonetic": "/lə pɛ̃/", "meaning": "n.m. 面包", "example": "Je mange du pain au petit-déjeuner.", "example_cn": "我早餐吃面包。"},
                {"word": "la table", "phonetic": "/la tabl/", "meaning": "n.f. 桌子，餐桌", "example": "Mettez le livre sur la table.", "example_cn": "把书放在桌上。"},
                {"word": "le monde", "phonetic": "/lə mɔ̃d/", "meaning": "n.m. 世界；人们", "example": "Le monde est grand.", "example_cn": "世界很大。"},
                {"word": "la chose", "phonetic": "/la ʃoz/", "meaning": "n.f. 事物，东西", "example": "C'est une bonne chose.", "example_cn": "这是件好事。"},
                {"word": "l'heure (f)", "phonetic": "/lœʁ/", "meaning": "n.f. 小时；点钟", "example": "Quelle heure est-il?", "example_cn": "几点了？"},
                {"word": "le cours", "phonetic": "/lə kuʁ/", "meaning": "n.m. 课程；课", "example": "Le cours commence à 9h.", "example_cn": "课程九点开始。"},
                {"word": "la langue", "phonetic": "/la lɑ̃ɡ/", "meaning": "n.f. 语言；舌头", "example": "J'apprends deux langues.", "example_cn": "我学两种语言。"},
            ]},
            "basic_fr": {"name": "法语入门", "words": [
                {"word": "l'amour (m)", "phonetic": "/lamuʁ/", "meaning": "n.m. 爱，爱情", "example": "L'amour est aveugle.", "example_cn": "爱情是盲目的。"},
                {"word": "le père", "phonetic": "/lə pɛʁ/", "meaning": "n.m. 父亲", "example": "Mon père est médecin.", "example_cn": "我父亲是医生。"},
                {"word": "la mère", "phonetic": "/la mɛʁ/", "meaning": "n.f. 母亲", "example": "Ma mère aime cuisiner.", "example_cn": "我母亲喜欢做饭。"},
                {"word": "le frère", "phonetic": "/lə fʁɛʁ/", "meaning": "n.m. 兄弟，哥哥/弟弟", "example": "J'ai un frère et une sœur.", "example_cn": "我有一个兄弟和一个姐妹。"},
                {"word": "la sœur", "phonetic": "/la sœʁ/", "meaning": "n.f. 姐妹，姐姐/妹妹", "example": "Ma sœur est plus âgée.", "example_cn": "我姐姐年龄更大。"},
                {"word": "l'enfant (m/f)", "phonetic": "/lɑ̃fɑ̃/", "meaning": "n. 孩子，儿童", "example": "L'enfant joue dans le jardin.", "example_cn": "孩子在花园里玩耍。"},
                {"word": "l'homme (m)", "phonetic": "/lɔm/", "meaning": "n.m. 男人；人", "example": "C'est un homme gentil.", "example_cn": "这是一个和蔼的男人。"},
                {"word": "la femme", "phonetic": "/la fam/", "meaning": "n.f. 女人；妻子", "example": "Sa femme est française.", "example_cn": "他的妻子是法国人。"},
                {"word": "le garçon", "phonetic": "/lə ɡaʁsɔ̃/", "meaning": "n.m. 男孩；服务员", "example": "Le garçon lit un livre.", "example_cn": "那个男孩在看书。"},
                {"word": "la fille", "phonetic": "/la fij/", "meaning": "n.f. 女孩；女儿", "example": "La fille danse bien.", "example_cn": "这个女孩跳舞跳得很好。"},
                {"word": "le chien", "phonetic": "/lə ʃjɛ̃/", "meaning": "n.m. 狗", "example": "Le chien aboie beaucoup.", "example_cn": "这条狗经常叫。"},
                {"word": "la fleur", "phonetic": "/la flœʁ/", "meaning": "n.f. 花，花朵", "example": "J'aime les fleurs rouges.", "example_cn": "我喜欢红色的花。"},
                {"word": "l'arbre (m)", "phonetic": "/laʁbʁ/", "meaning": "n.m. 树，树木", "example": "Il y a un arbre dans le jardin.", "example_cn": "花园里有一棵树。"},
                {"word": "le jardin", "phonetic": "/lə ʒaʁdɛ̃/", "meaning": "n.m. 花园，园子", "example": "Nous travaillons dans le jardin.", "example_cn": "我们在花园里干活。"},
                {"word": "la mer", "phonetic": "/la mɛʁ/", "meaning": "n.f. 海，大海", "example": "La mer est calme aujourd'hui.", "example_cn": "今天大海风平浪静。"},
                {"word": "le ciel", "phonetic": "/lə sjɛl/", "meaning": "n.m. 天空；天堂", "example": "Le ciel est bleu.", "example_cn": "天空是蓝色的。"},
                {"word": "la chambre", "phonetic": "/la ʃɑ̃bʁ/", "meaning": "n.f. 房间，卧室", "example": "Ma chambre est propre.", "example_cn": "我的房间很干净。"},
                {"word": "la fenêtre", "phonetic": "/la fənɛtʁ/", "meaning": "n.f. 窗户", "example": "Ouvrez la fenêtre, il fait chaud.", "example_cn": "打开窗户吧，太热了。"},
                {"word": "le lit", "phonetic": "/lə li/", "meaning": "n.m. 床", "example": "Je vais au lit à 23h.", "example_cn": "我11点上床睡觉。"},
                {"word": "la chaise", "phonetic": "/la ʃɛz/", "meaning": "n.f. 椅子", "example": "Asseyez-vous sur cette chaise.", "example_cn": "请坐在这张椅子上。"},
                {"word": "le livre scolaire", "phonetic": "/lə livʁ skɔlɛʁ/", "meaning": "n.m. 课本，教科书", "example": "J'ai besoin de mon livre scolaire.", "example_cn": "我需要我的课本。"},
                {"word": "la musique", "phonetic": "/la myzik/", "meaning": "n.f. 音乐", "example": "J'écoute de la musique tous les soirs.", "example_cn": "我每天晚上都听音乐。"},
                {"word": "le sport", "phonetic": "/lə spɔʁ/", "meaning": "n.m. 运动，体育", "example": "Je fais du sport tous les jours.", "example_cn": "我每天都做运动。"},
                {"word": "le cinéma", "phonetic": "/lə sinema/", "meaning": "n.m. 电影院；电影", "example": "Allons au cinéma ce week-end.", "example_cn": "这周末我们去看电影吧。"},
                {"word": "la télé", "phonetic": "/la tele/", "meaning": "n.f. 电视（télevision 缩写）", "example": "Je regarde la télé le soir.", "example_cn": "我晚上看电视。"},
                {"word": "le téléphone", "phonetic": "/lə telefɔn/", "meaning": "n.m. 电话", "example": "Mon téléphone est cassé.", "example_cn": "我的手机坏了。"},
                {"word": "l'ordinateur (m)", "phonetic": "/lɔʁdinatœʁ/", "meaning": "n.m. 电脑，计算机", "example": "J'utilise l'ordinateur pour travailler.", "example_cn": "我用电脑工作。"},
                {"word": "la santé", "phonetic": "/la sɑ̃te/", "meaning": "n.f. 健康", "example": "La santé est plus importante que l'argent.", "example_cn": "健康比金钱更重要。"},
                {"word": "le bonheur", "phonetic": "/lə bɔnœʁ/", "meaning": "n.m. 幸福，快乐", "example": "Le bonheur est simple.", "example_cn": "幸福其实很简单。"},
                {"word": "la paix", "phonetic": "/la pɛ/", "meaning": "n.f. 和平；安静", "example": "Nous voulons la paix dans le monde.", "example_cn": "我们希望世界和平。"},
            ]},
        }
    },
    "german": {
        "name": "德语", "flag": "🇩🇪",
        "books": {
            "testdaf": {"name": "德福核心词", "words": [
                {"word": "Danke", "phonetic": "/ˈdaŋkə/", "meaning": "interj. 谢谢", "example": "Danke schön!", "example_cn": "非常感谢！"},
                {"word": "das Buch", "phonetic": "/das buːx/", "meaning": "n. 书，书籍（中性）", "example": "Das Buch ist sehr interessant.", "example_cn": "这本书非常有趣。"},
                {"word": "der Mann", "phonetic": "/deːɐ̯ man/", "meaning": "n. 男人；丈夫（阳性）", "example": "Der Mann spricht drei Sprachen.", "example_cn": "这个男人会说三种语言。"},
                {"word": "die Frau", "phonetic": "/diː fʁaʊ/", "meaning": "n. 女人；妻子；女士（阴性）", "example": "Die Frau ist meine Lehrerin.", "example_cn": "这位女士是我的老师。"},
                {"word": "das Haus", "phonetic": "/das haʊ̯s/", "meaning": "n. 房屋，房子（中性）", "example": "Das Haus ist groß und modern.", "example_cn": "这房子又大又现代。"},
                {"word": "die Zeit", "phonetic": "/diː tsaɪ̯t/", "meaning": "n. 时间；时代（阴性）", "example": "Die Zeit vergeht schnell.", "example_cn": "时间过得很快。"},
                {"word": "der Tag", "phonetic": "/deːɐ̯ taːk/", "meaning": "n. 天，白天；日子（阳性）", "example": "Guten Tag!", "example_cn": "您好/日安！"},
                {"word": "die Nacht", "phonetic": "/diː naxt/", "meaning": "n. 夜晚，夜里（阴性）", "example": "Gute Nacht!", "example_cn": "晚安！"},
                {"word": "das Wasser", "phonetic": "/das ˈvasɐ/", "meaning": "n. 水（中性）", "example": "Ich trinke viel Wasser.", "example_cn": "我喝很多水。"},
                {"word": "das Kind", "phonetic": "/das kɪnt/", "meaning": "n. 孩子，儿童（中性）", "example": "Das Kind spielt im Garten.", "example_cn": "孩子在花园里玩耍。"},
                {"word": "der Freund", "phonetic": "/deːɐ̯ fʁɔʏ̯nt/", "meaning": "n. 朋友（阳性）", "example": "Er ist mein bester Freund.", "example_cn": "他是我最好的朋友。"},
                {"word": "die Freundin", "phonetic": "/diː ˈfʁɔʏ̯ntɪn/", "meaning": "n. 女朋友（阴性）", "example": "Meine Freundin ist sehr nett.", "example_cn": "我的女朋友很和蔼。"},
                {"word": "die Schule", "phonetic": "/diː ˈʃuːlə/", "meaning": "n. 学校（阴性）", "example": "Die Kinder gehen in die Schule.", "example_cn": "孩子们去上学。"},
                {"word": "der Lehrer", "phonetic": "/deːɐ̯ ˈleːʁɐ/", "meaning": "n. 男教师（阳性）", "example": "Der Lehrer erklärt die Aufgabe.", "example_cn": "老师在讲解题目。"},
                {"word": "die Stadt", "phonetic": "/diː ʃtat/", "meaning": "n. 城市（阴性）", "example": "Berlin ist eine große Stadt.", "example_cn": "柏林是一座大城市。"},
                {"word": "das Land", "phonetic": "/das lant/", "meaning": "n. 国家；农村（中性）", "example": "Deutschland ist mein Heimatland.", "example_cn": "德国是我的祖国。"},
                {"word": "die Sprache", "phonetic": "/diː ˈʃpʁaχə/", "meaning": "n. 语言（阴性）", "example": "Ich lerne zwei Sprachen.", "example_cn": "我学两种语言。"},
                {"word": "das Problem", "phonetic": "/das pʁoˈbleːm/", "meaning": "n. 问题，难题（中性）", "example": "Das ist kein Problem.", "example_cn": "这不是问题。"},
                {"word": "die Frage", "phonetic": "/diː ˈfʁaːɡə/", "meaning": "n. 问题，提问（阴性）", "example": "Ich habe eine Frage.", "example_cn": "我有一个问题。"},
                {"word": "der Weg", "phonetic": "/deːɐ̯ veːk/", "meaning": "n. 道路；方法（阳性）", "example": "Können Sie mir den Weg zeigen?", "example_cn": "您能给我指路吗？"},
                {"word": "das Geld", "phonetic": "/das ɡɛlt/", "meaning": "n. 钱，金钱（中性）", "example": "Ich habe kein Geld.", "example_cn": "我没有钱。"},
                {"word": "die Arbeit", "phonetic": "/diː ˈaʁbaɪ̯t/", "meaning": "n. 工作，劳动（阴性）", "example": "Ich gehe zur Arbeit.", "example_cn": "我去上班。"},
                {"word": "der Platz", "phonetic": "/deːɐ̯ plats/", "meaning": "n. 地方；座位；广场（阳性）", "example": "Ist dieser Platz noch frei?", "example_cn": "这个座位空着吗？"},
                {"word": "das Zimmer", "phonetic": "/das ˈtsɪmɐ/", "meaning": "n. 房间（中性）", "example": "Mein Zimmer ist sehr klein.", "example_cn": "我的房间很小。"},
                {"word": "die Tür", "phonetic": "/diː tyːɐ̯/", "meaning": "n. 门（阴性）", "example": "Machen Sie bitte die Tür zu.", "example_cn": "请把门关上。"},
                {"word": "das Fenster", "phonetic": "/das ˈfɛnstɐ/", "meaning": "n. 窗户（中性）", "example": "Öffnen Sie bitte das Fenster.", "example_cn": "请打开窗户。"},
                {"word": "der Tisch", "phonetic": "/deːɐ̯ tɪʃ/", "meaning": "n. 桌子（阳性）", "example": "Das Buch liegt auf dem Tisch.", "example_cn": "书在桌子上。"},
                {"word": "die Familie", "phonetic": "/diː faˈmiːli̯ə/", "meaning": "n. 家庭（阴性）", "example": "Meine Familie wohnt in München.", "example_cn": "我家住在慕尼黑。"},
                {"word": "das Leben", "phonetic": "/das ˈleːbm̩/", "meaning": "n. 生活，生命（中性）", "example": "Das Leben ist wunderschön.", "example_cn": "生活是美好的。"},
                {"word": "der Kaffee", "phonetic": "/deːɐ̯ ˈkafe/", "meaning": "n. 咖啡（阳性）", "example": "Ich trinke einen Kaffee.", "example_cn": "我喝一杯咖啡。"},
                {"word": "das Wetter", "phonetic": "/das ˈvɛtɐ/", "meaning": "n. 天气（中性）", "example": "Das Wetter ist heute sehr schön.", "example_cn": "今天天气很好。"},
                {"word": "der Welt", "phonetic": "/deːɐ̯ vɛlt/", "meaning": "n. 世界（阴性）", "example": "Die Welt ist sehr groß.", "example_cn": "世界很大。"},
                {"word": "das Essen", "phonetic": "/das ˈɛsn̩/", "meaning": "n. 食物，吃饭（中性）", "example": "Das Essen schmeckt gut.", "example_cn": "饭菜很好吃。"},
                {"word": "der Student", "phonetic": "/deːɐ̯ ʃtuˈdɛnt/", "meaning": "n. 大学生（阳性）", "example": "Mein Bruder ist Student.", "example_cn": "我哥哥是大学生。"},
                {"word": "die Universität", "phonetic": "/diː univɛʁziˈtɛːt/", "meaning": "n. 大学（阴性）", "example": "Sie studiert an der Universität.", "example_cn": "她在上大学。"},
                {"word": "das Auto", "phonetic": "/das ˈaʊ̯toː/", "meaning": "n. 汽车（中性）", "example": "Mein Auto ist sehr alt.", "example_cn": "我的车很旧。"},
                {"word": "der Zug", "phonetic": "/deːɐ̯ tsuːk/", "meaning": "n. 火车；列车（阳性）", "example": "Der Zug kommt pünktlich.", "example_cn": "火车准时到达。"},
                {"word": "der Flug", "phonetic": "/deːɐ̯ fluːk/", "meaning": "n. 航班；飞行（阳性）", "example": "Unser Flug hat Verspätung.", "example_cn": "我们的航班晚点了。"},
                {"word": "das Hotel", "phonetic": "/das hoˈtɛl/", "meaning": "n. 酒店，旅馆（中性）", "example": "Wir übernachten in einem Hotel.", "example_cn": "我们在酒店过夜。"},
                {"word": "der Arzt", "phonetic": "/deːɐ̯ aʁtst/", "meaning": "n. 医生（阳性）", "example": "Ich muss zum Arzt gehen.", "example_cn": "我得去看医生。"},
            ]},
            "basic_de": {"name": "德语入门", "words": [
                {"word": "Hallo", "phonetic": "/ˈhalo/", "meaning": "interj. 你好，喂", "example": "Hallo, wie geht's?", "example_cn": "你好，最近怎么样？"},
                {"word": "Tschüss", "phonetic": "/tʃʏs/", "meaning": "interj. 再见", "example": "Tschüss, bis morgen!", "example_cn": "再见，明天见！"},
                {"word": "Bitte", "phonetic": "/ˈbɪtə/", "meaning": "interj. 请；不客气", "example": "Bitte nehmen Sie Platz.", "example_cn": "请坐。"},
                {"word": "Entschuldigung", "phonetic": "/ɛntˈʃʊldɪɡʊŋ/", "meaning": "n.f. 对不起；抱歉", "example": "Entschuldigung, ich habe mich verspätet.", "example_cn": "对不起，我迟到了。"},
                {"word": "Ja", "phonetic": "/jaː/", "meaning": "adv. 是，对", "example": "Ja, das ist richtig.", "example_cn": "是的，没错。"},
                {"word": "Nein", "phonetic": "/naɪ̯n/", "meaning": "adv. 不，不是", "example": "Nein, danke.", "example_cn": "不，谢谢。"},
                {"word": "der Vater", "phonetic": "/deːɐ̯ ˈfaːtɐ/", "meaning": "n. 父亲（阳性）", "example": "Mein Vater ist Ingenieur.", "example_cn": "我父亲是工程师。"},
                {"word": "die Mutter", "phonetic": "/diː ˈmʊtɐ/", "meaning": "n. 母亲（阴性）", "example": "Meine Mutter kocht gern.", "example_cn": "我母亲喜欢做饭。"},
                {"word": "der Bruder", "phonetic": "/deːɐ̯ ˈbʁuːdɐ/", "meaning": "n. 兄弟（阳性）", "example": "Ich habe einen älteren Bruder.", "example_cn": "我有一个哥哥。"},
                {"word": "die Schwester", "phonetic": "/diː ˈʃvɛstɐ/", "meaning": "n. 姐妹（阴性）", "example": "Meine Schwester ist jünger.", "example_cn": "我妹妹年龄更小。"},
                {"word": "der Hund", "phonetic": "/deːɐ̯ hʊnt/", "meaning": "n. 狗（阳性）", "example": "Der Hund ist sehr freundlich.", "example_cn": "这只狗很友好。"},
                {"word": "die Katze", "phonetic": "/diː ˈkatsə/", "meaning": "n. 猫（阴性）", "example": "Die Katze schläft auf dem Sofa.", "example_cn": "猫在沙发上睡觉。"},
                {"word": "der Baum", "phonetic": "/deːɐ̯ baʊ̯m/", "meaning": "n. 树（阳性）", "example": "Der Baum ist sehr alt.", "example_cn": "这棵树很老了。"},
                {"word": "die Blume", "phonetic": "/diː ˈbluːmə/", "meaning": "n. 花（阴性）", "example": "Die Blumen sind sehr schön.", "example_cn": "这些花很漂亮。"},
                {"word": "das Bett", "phonetic": "/das bɛt/", "meaning": "n. 床（中性）", "example": "Ich gehe jetzt ins Bett.", "example_cn": "我现在上床睡觉了。"},
                {"word": "der Stuhl", "phonetic": "/deːɐ̯ ʃtuːl/", "meaning": "n. 椅子（阳性）", "example": "Setzen Sie sich auf den Stuhl.", "example_cn": "请坐在椅子上。"},
                {"word": "der Apfel", "phonetic": "/deːɐ̯ ˈapfl̩/", "meaning": "n. 苹果（阳性）", "example": "Ich esse einen Apfel pro Tag.", "example_cn": "我每天吃一个苹果。"},
                {"word": "das Brot", "phonetic": "/das bʁoːt/", "meaning": "n. 面包（中性）", "example": "Ich esse Brot zum Frühstück.", "example_cn": "我早餐吃面包。"},
                {"word": "die Milch", "phonetic": "/diː mɪlç/", "meaning": "n. 牛奶（阴性）", "example": "Trinken Sie Milch?", "example_cn": "您喝牛奶吗？"},
                {"word": "das Fleisch", "phonetic": "/das flaɪ̯ʃ/", "meaning": "n. 肉（中性）", "example": "Ich esse nicht viel Fleisch.", "example_cn": "我不怎么吃肉。"},
                {"word": "der Fisch", "phonetic": "/deːɐ̯ fɪʃ/", "meaning": "n. 鱼（阳性）", "example": "Der Fisch schmeckt sehr gut.", "example_cn": "这鱼味道很好。"},
                {"word": "der Tee", "phonetic": "/deːɐ̯ teː/", "meaning": "n. 茶（阳性）", "example": "Ich trinke gern Tee.", "example_cn": "我喜欢喝茶。"},
                {"word": "der Saft", "phonetic": "/deːɐ̯ zaft/", "meaning": "n. 果汁（阳性）", "example": "Ein Glas Apfelsaft, bitte.", "example_cn": "请来一杯苹果汁。"},
                {"word": "das Bier", "phonetic": "/das biːɐ̯/", "meaning": "n. 啤酒（中性）", "example": "Das Bier ist sehr kalt.", "example_cn": "啤酒很冰。"},
                {"word": "der Wein", "phonetic": "/deːɐ̯ vaɪ̯n/", "meaning": "n. 葡萄酒（阳性）", "example": "Dieser Wein stammt aus Frankreich.", "example_cn": "这瓶葡萄酒来自法国。"},
                {"word": "das Obst", "phonetic": "/das oːpst/", "meaning": "n. 水果（中性）", "example": "Obst ist gesund.", "example_cn": "水果有益健康。"},
                {"word": "das Gemüse", "phonetic": "/das ɡəˈmyːzə/", "meaning": "n. 蔬菜（中性）", "example": "Ich esse viel Gemüse.", "example_cn": "我吃很多蔬菜。"},
                {"word": "der Montag", "phonetic": "/deːɐ̯ ˈmoːntaːk/", "meaning": "n. 星期一（阳性）", "example": "Am Montag habe ich viel zu tun.", "example_cn": "周一我有很多事要做。"},
                {"word": "der Samstag", "phonetic": "/deːɐ̯ ˈzamstaːk/", "meaning": "n. 星期六（阳性）", "example": "Am Samstag gehen wir ins Kino.", "example_cn": "周六我们去看电影。"},
                {"word": "das Wochenende", "phonetic": "/das ˈvɔxn̩ʔɛndə/", "meaning": "n. 周末（中性）", "example": "Schönes Wochenende!", "example_cn": "周末愉快！"},
            ]},
        }
    },
    "spanish": {
        "name": "西班牙语", "flag": "🇪🇸",
        "books": {
            "dele": {"name": "DELE核心词", "words": [
                {"word": "hola", "phonetic": "/ˈola/", "meaning": "interj. 你好", "example": "¡Hola! ¿Cómo estás?", "example_cn": "你好！你好吗？"},
                {"word": "el libro", "phonetic": "/el ˈliβɾo/", "meaning": "n.m. 书，书籍", "example": "Este libro es muy interesante.", "example_cn": "这本书非常有趣。"},
                {"word": "la casa", "phonetic": "/la ˈkasa/", "meaning": "n.f. 房屋，家", "example": "Mi casa es muy grande.", "example_cn": "我家很大。"},
                {"word": "el hombre", "phonetic": "/el ˈombɾe/", "meaning": "n.m. 男人；人", "example": "El hombre habla español.", "example_cn": "这个男人讲西班牙语。"},
                {"word": "la mujer", "phonetic": "/la muˈxeɾ/", "meaning": "n.f. 女人；妻子", "example": "La mujer es profesora.", "example_cn": "这位女士是老师。"},
                {"word": "el niño", "phonetic": "/el ˈniɲo/", "meaning": "n.m. 男孩；孩子", "example": "El niño juega en el parque.", "example_cn": "男孩在公园里玩耍。"},
                {"word": "la niña", "phonetic": "/la ˈniɲa/", "meaning": "n.f. 女孩", "example": "La niña lee un cuento.", "example_cn": "女孩在读一个故事。"},
                {"word": "el tiempo", "phonetic": "/el ˈtjempo/", "meaning": "n.m. 时间；天气", "example": "El tiempo pasa rápido.", "example_cn": "时间过得很快。"},
                {"word": "la vida", "phonetic": "/la ˈβiða/", "meaning": "n.f. 生活，生命", "example": "La vida es hermosa.", "example_cn": "生活是美好的。"},
                {"word": "el trabajo", "phonetic": "/el tɾaˈβaxo/", "meaning": "n.m. 工作，劳动", "example": "Voy al trabajo temprano.", "example_cn": "我很早就去上班。"},
                {"word": "la familia", "phonetic": "/la faˈmilja/", "meaning": "n.f. 家庭", "example": "Mi familia es muy unida.", "example_cn": "我的家庭非常团结。"},
                {"word": "el dinero", "phonetic": "/el diˈneɾo/", "meaning": "n.m. 钱，金钱", "example": "No tengo dinero.", "example_cn": "我没有钱。"},
                {"word": "la escuela", "phonetic": "/la esˈkwela/", "meaning": "n.f. 学校", "example": "Los niños van a la escuela.", "example_cn": "孩子们去上学。"},
                {"word": "el día", "phonetic": "/el ˈdia/", "meaning": "n.m. 天，日子", "example": "Buen día a todos.", "example_cn": "祝大家日安。"},
                {"word": "la noche", "phonetic": "/la ˈnotʃe/", "meaning": "n.f. 夜晚", "example": "Buenas noches.", "example_cn": "晚安。"},
                {"word": "el agua", "phonetic": "/el ˈaɣwa/", "meaning": "n.f. 水（冠词用 el 因开头为重读 a）", "example": "Bebo mucha agua.", "example_cn": "我喝很多水。"},
                {"word": "la comida", "phonetic": "/la koˈmiða/", "meaning": "n.f. 食物；午饭", "example": "La comida está deliciosa.", "example_cn": "饭菜很美味。"},
                {"word": "el perro", "phonetic": "/el ˈpero/", "meaning": "n.m. 狗", "example": "El perro es muy fiel.", "example_cn": "狗非常忠诚。"},
                {"word": "la ciudad", "phonetic": "/la θjuˈðað/", "meaning": "n.f. 城市", "example": "Madrid es una ciudad grande.", "example_cn": "马德里是一座大城市。"},
                {"word": "el país", "phonetic": "/el paˈis/", "meaning": "n.m. 国家", "example": "España es un país hermoso.", "example_cn": "西班牙是一个美丽的国家。"},
                {"word": "el idioma", "phonetic": "/el iˈðjoma/", "meaning": "n.m. 语言", "example": "Aprendo dos idiomas.", "example_cn": "我学两种语言。"},
                {"word": "el problema", "phonetic": "/el pɾoˈβlema/", "meaning": "n.m. 问题，难题", "example": "No hay problema.", "example_cn": "没问题。"},
                {"word": "la pregunta", "phonetic": "/la pɾeˈɣunta/", "meaning": "n.f. 问题，提问", "example": "Tengo una pregunta.", "example_cn": "我有一个问题。"},
                {"word": "el amigo", "phonetic": "/el aˈmiɣo/", "meaning": "n.m. 朋友", "example": "Él es mi mejor amigo.", "example_cn": "他是我最好的朋友。"},
                {"word": "la amiga", "phonetic": "/la aˈmiɣa/", "meaning": "n.f. 女朋友", "example": "Ella es mi amiga de la infancia.", "example_cn": "她是我童年的朋友。"},
                {"word": "la puerta", "phonetic": "/la ˈpweɾta/", "meaning": "n.f. 门", "example": "Cierra la puerta, por favor.", "example_cn": "请关门。"},
                {"word": "la ventana", "phonetic": "/la βenˈtana/", "meaning": "n.f. 窗户", "example": "Abre la ventana, hace calor.", "example_cn": "打开窗户吧，太热了。"},
                {"word": "la mesa", "phonetic": "/la ˈmesa/", "meaning": "n.f. 桌子", "example": "El libro está sobre la mesa.", "example_cn": "书在桌子上。"},
                {"word": "el café", "phonetic": "/el kaˈfe/", "meaning": "n.m. 咖啡；咖啡馆", "example": "Tomamos un café en la cafetería.", "example_cn": "我们在咖啡馆喝咖啡。"},
                {"word": "la música", "phonetic": "/la ˈmusika/", "meaning": "n.f. 音乐", "example": "Me gusta la música clásica.", "example_cn": "我喜欢古典音乐。"},
                {"word": "el deporte", "phonetic": "/el depoɾˈte/", "meaning": "n.m. 运动，体育", "example": "Hago deporte todos los días.", "example_cn": "我每天都做运动。"},
                {"word": "la salud", "phonetic": "/la saˈluð/", "meaning": "n.f. 健康", "example": "La salud es lo más importante.", "example_cn": "健康是最重要的。"},
                {"word": "la paz", "phonetic": "/la paθ/", "meaning": "n.f. 和平", "example": "Queremos la paz en el mundo.", "example_cn": "我们希望世界和平。"},
                {"word": "el coche", "phonetic": "/el ˈkotʃe/", "meaning": "n.m. 汽车", "example": "Mi coche es nuevo.", "example_cn": "我的车是新的。"},
                {"word": "el avión", "phonetic": "/el aˈβjon/", "meaning": "n.m. 飞机", "example": "El avión despega a las tres.", "example_cn": "飞机三点起飞。"},
                {"word": "la universidad", "phonetic": "/la uniβeɾsiˈðað/", "meaning": "n.f. 大学", "example": "Estudio en la universidad.", "example_cn": "我在大学学习。"},
                {"word": "el médico", "phonetic": "/el ˈmeðiko/", "meaning": "n.m. 医生", "example": "Tengo que ir al médico.", "example_cn": "我得去看医生。"},
                {"word": "el hospital", "phonetic": "/el ospiˈtal/", "meaning": "n.m. 医院", "example": "El hospital está cerca.", "example_cn": "医院就在附近。"},
                {"word": "la playa", "phonetic": "/la ˈplaʝa/", "meaning": "n.f. 海滩", "example": "Vamos a la playa este verano.", "example_cn": "今年夏天我们去海滩。"},
                {"word": "el mar", "phonetic": "/el maɾ/", "meaning": "n.m. 海，大海", "example": "El mar está muy tranquilo.", "example_cn": "大海风平浪静。"},
            ]},
            "basic_es": {"name": "西班牙语入门", "words": [
                {"word": "adiós", "phonetic": "/aˈðjos/", "meaning": "interj. 再见", "example": "Adiós, hasta mañana.", "example_cn": "再见，明天见。"},
                {"word": "gracias", "phonetic": "/ˈɡɾaθjas/", "meaning": "interj. 谢谢", "example": "Muchas gracias por tu ayuda.", "example_cn": "非常感谢你的帮助。"},
                {"word": "por favor", "phonetic": "/poɾ faˈβoɾ/", "meaning": "interj. 请；麻烦", "example": "Un café, por favor.", "example_cn": "请来一杯咖啡。"},
                {"word": "de nada", "phonetic": "/de ˈnaða/", "meaning": "interj. 不客气", "example": "A: ¡Gracias! B: De nada.", "example_cn": "甲：谢谢！乙：不客气。"},
                {"word": "perdón", "phonetic": "/peɾˈðon/", "meaning": "interj. 对不起；抱歉", "example": "Perdón, ¿qué ha dicho?", "example_cn": "对不起，您说什么？"},
                {"word": "el padre", "phonetic": "/el ˈpaðɾe/", "meaning": "n.m. 父亲", "example": "Mi padre es abogado.", "example_cn": "我父亲是律师。"},
                {"word": "la madre", "phonetic": "/la ˈmaðɾe/", "meaning": "n.f. 母亲", "example": "Mi madre cocina muy bien.", "example_cn": "我母亲做饭很好吃。"},
                {"word": "el hermano", "phonetic": "/el eɾˈmano/", "meaning": "n.m. 兄弟", "example": "Tengo dos hermanos.", "example_cn": "我有两个兄弟。"},
                {"word": "la hermana", "phonetic": "/la eɾˈmana/", "meaning": "n.f. 姐妹", "example": "Mi hermana mayor es doctora.", "example_cn": "我姐姐是医生。"},
                {"word": "el gato", "phonetic": "/el ˈɡato/", "meaning": "n.m. 猫", "example": "El gato duerme todo el día.", "example_cn": "猫整天睡觉。"},
                {"word": "la flor", "phonetic": "/la floɾ/", "meaning": "n.f. 花", "example": "Las flores son de color rojo.", "example_cn": "这些花是红色的。"},
                {"word": "el árbol", "phonetic": "/el ˈaɾβol/", "meaning": "n.m. 树", "example": "Hay muchos árboles en el parque.", "example_cn": "公园里有很多树。"},
                {"word": "el jardín", "phonetic": "/el xaɾˈðin/", "meaning": "n.m. 花园", "example": "El jardín está lleno de flores.", "example_cn": "花园里开满了花。"},
                {"word": "el cielo", "phonetic": "/el ˈθjelo/", "meaning": "n.m. 天空", "example": "El cielo está despejado hoy.", "example_cn": "今天天空晴朗。"},
                {"word": "la habitación", "phonetic": "/la aβitaˈθjon/", "meaning": "n.f. 房间", "example": "Mi habitación está ordenada.", "example_cn": "我的房间很整洁。"},
                {"word": "la cama", "phonetic": "/la ˈkama/", "meaning": "n.f. 床", "example": "Me acuesto a las once.", "example_cn": "我十一点上床。"},
                {"word": "la silla", "phonetic": "/la ˈsiʎa/", "meaning": "n.f. 椅子", "example": "Siéntate en esa silla.", "example_cn": "请坐在那张椅子上。"},
                {"word": "el pan", "phonetic": "/el pan/", "meaning": "n.m. 面包", "example": "Como pan en el desayuno.", "example_cn": "我早餐吃面包。"},
                {"word": "la leche", "phonetic": "/la ˈletʃe/", "meaning": "n.f. 牛奶", "example": "Me gusta la leche con café.", "example_cn": "我喜欢加咖啡的牛奶。"},
                {"word": "la manzana", "phonetic": "/la manˈθana/", "meaning": "n.f. 苹果", "example": "Como una manzana cada día.", "example_cn": "我每天吃一个苹果。"},
                {"word": "el jugo", "phonetic": "/el ˈxuɣo/", "meaning": "n.m. 果汁（西班牙多用 zumo）", "example": "Quiero un jugo de naranja.", "example_cn": "我要一杯橙汁。"},
                {"word": "el vino", "phonetic": "/el ˈbino/", "meaning": "n.m. 葡萄酒", "example": "Este vino es de muy buena calidad.", "example_cn": "这瓶葡萄酒品质很好。"},
                {"word": "la carne", "phonetic": "/la ˈkaɾne/", "meaning": "n.f. 肉", "example": "No como mucha carne.", "example_cn": "我不怎么吃肉。"},
                {"word": "el pescado", "phonetic": "/el pesˈkaðo/", "meaning": "n.m. 鱼（已烹调的）", "example": "El pescado está muy rico.", "example_cn": "这鱼很好吃。"},
                {"word": "la fruta", "phonetic": "/la ˈfɾuta/", "meaning": "n.f. 水果", "example": "La fruta es muy sana.", "example_cn": "水果非常有益健康。"},
                {"word": "el té", "phonetic": "/el ˈte/", "meaning": "n.m. 茶", "example": "Tomaré un té, gracias.", "example_cn": "我要一杯茶，谢谢。"},
                {"word": "la cerveza", "phonetic": "/la θeɾˈβeθa/", "meaning": "n.f. 啤酒", "example": "¿Quieres una cerveza fría?", "example_cn": "你想要一杯冰镇啤酒吗？"},
                {"word": "el lunes", "phonetic": "/el ˈlunes/", "meaning": "n.m. 星期一", "example": "El lunes empiezo las clases.", "example_cn": "周一我开始上课。"},
                {"word": "el sábado", "phonetic": "/el ˈsabaðo/", "meaning": "n.m. 星期六", "example": "El sábado voy a ver a mis abuelos.", "example_cn": "周六我去看望祖父母。"},
                {"word": "el fin de semana", "phonetic": "/el fin ðe seˈmana/", "meaning": "n.m. 周末", "example": "Buen fin de semana.", "example_cn": "周末愉快。"},
            ]},
        }
    },
    "italian": {
        "name": "意大利语", "flag": "🇮🇹",
        "books": {
            "basic_it": {"name": "意大利语入门", "words": [
                {"word": "ciao", "phonetic": "/ˈtʃaːo/", "meaning": "interj. 你好/再见（非正式）", "example": "Ciao, come stai?", "example_cn": "你好，你怎么样？"},
                {"word": "il libro", "phonetic": "/il ˈliːbro/", "meaning": "n.m. 书，书籍", "example": "Questo libro è molto bello.", "example_cn": "这本书非常好。"},
                {"word": "la casa", "phonetic": "/la ˈkaːza/", "meaning": "n.f. 房屋，家", "example": "La mia casa è in centro.", "example_cn": "我家在市中心。"},
                {"word": "l'uomo (m)", "phonetic": "/ˈlwɔːmo/", "meaning": "n.m. 男人；人", "example": "L'uomo parla italiano.", "example_cn": "这个男人说意大利语。"},
                {"word": "la donna", "phonetic": "/la ˈdɔnna/", "meaning": "n.f. 女人", "example": "La donna è italiana.", "example_cn": "这位女士是意大利人。"},
                {"word": "il bambino", "phonetic": "/il bamˈbiːno/", "meaning": "n.m. 男孩；孩子", "example": "Il bambino gioca nel giardino.", "example_cn": "男孩在花园里玩耍。"},
                {"word": "la bambina", "phonetic": "/la bamˈbiːna/", "meaning": "n.f. 女孩", "example": "La bambina mangia una mela.", "example_cn": "女孩在吃一个苹果。"},
                {"word": "il tempo", "phonetic": "/il ˈtɛmpo/", "meaning": "n.m. 时间；天气", "example": "Il tempo vola.", "example_cn": "光阴似箭。"},
                {"word": "la vita", "phonetic": "/la ˈviːta/", "meaning": "n.f. 生活，生命", "example": "La vita è bella.", "example_cn": "生活是美好的。"},
                {"word": "il lavoro", "phonetic": "/il laˈvoːro/", "meaning": "n.m. 工作，劳动", "example": "Vado al lavoro alle otto.", "example_cn": "我八点去上班。"},
                {"word": "la famiglia", "phonetic": "/la faˈmiʎʎa/", "meaning": "n.f. 家庭", "example": "La mia famiglia è numerosa.", "example_cn": "我的家庭成员很多。"},
                {"word": "il denaro", "phonetic": "/il deˈnaːro/", "meaning": "n.m. 钱，金钱", "example": "Non ho denaro con me.", "example_cn": "我身上没带钱。"},
                {"word": "la scuola", "phonetic": "/la ˈskwɔːla/", "meaning": "n.f. 学校", "example": "I bambini vanno a scuola.", "example_cn": "孩子们去上学。"},
                {"word": "il giorno", "phonetic": "/il ˈdʒorno/", "meaning": "n.m. 天，日子", "example": "Buongiorno a tutti!", "example_cn": "大家早上好！"},
                {"word": "la notte", "phonetic": "/la ˈnɔtte/", "meaning": "n.f. 夜晚", "example": "Buonanotte, sogni d'oro!", "example_cn": "晚安，好梦！"},
                {"word": "l'acqua (f)", "phonetic": "/ˈlakwa/", "meaning": "n.f. 水", "example": "Bevo molta acqua ogni giorno.", "example_cn": "我每天喝很多水。"},
                {"word": "il cibo", "phonetic": "/il ˈtʃiːbo/", "meaning": "n.m. 食物", "example": "Il cibo è delizioso.", "example_cn": "食物很美味。"},
                {"word": "il cane", "phonetic": "/il ˈkaːne/", "meaning": "n.m. 狗", "example": "Il cane è molto intelligente.", "example_cn": "这只狗非常聪明。"},
                {"word": "la città", "phonetic": "/la tʃitˈta/", "meaning": "n.f. 城市", "example": "Roma è una città meravigliosa.", "example_cn": "罗马是一座奇妙的城市。"},
                {"word": "il paese", "phonetic": "/il paˈeːze/", "meaning": "n.m. 国家；村庄", "example": "L'Italia è il mio paese.", "example_cn": "意大利是我的国家。"},
                {"word": "la lingua", "phonetic": "/la ˈliŋɡwa/", "meaning": "n.f. 语言；舌头", "example": "Studio due lingue straniere.", "example_cn": "我学习两门外语。"},
                {"word": "il problema", "phonetic": "/il proˈblɛːma/", "meaning": "n.m. 问题，难题", "example": "Non c'è nessun problema.", "example_cn": "完全没有问题。"},
                {"word": "la domanda", "phonetic": "/la doˈmanda/", "meaning": "n.f. 问题，提问", "example": "Ho una domanda da farti.", "example_cn": "我有个问题要问你。"},
                {"word": "l'amico (m)", "phonetic": "/laˈmiːko/", "meaning": "n.m. 朋友", "example": "Marco è il mio migliore amico.", "example_cn": "马尔科是我最好的朋友。"},
                {"word": "l'amica (f)", "phonetic": "/laˈmiːka/", "meaning": "n.f. 女朋友", "example": "Sara è la mia migliore amica.", "example_cn": "萨拉是我最好的朋友。"},
                {"word": "la porta", "phonetic": "/la ˈpɔrta/", "meaning": "n.f. 门", "example": "Chiudi la porta, per favore.", "example_cn": "请关门。"},
                {"word": "la finestra", "phonetic": "/la fiˈnɛstra/", "meaning": "n.f. 窗户", "example": "Apri la finestra, fa caldo.", "example_cn": "打开窗户吧，太热了。"},
                {"word": "la tavola", "phonetic": "/la ˈtaːvola/", "meaning": "n.f. 桌子，餐桌", "example": "Il libro è sulla tavola.", "example_cn": "书在桌子上。"},
                {"word": "il caffè", "phonetic": "/il kafˈfɛ/", "meaning": "n.m. 咖啡", "example": "Prendo un caffè al bar.", "example_cn": "我在酒吧喝一杯咖啡。"},
                {"word": "la musica", "phonetic": "/la ˈmuːzika/", "meaning": "n.f. 音乐", "example": "Ascolto la musica tutte le sere.", "example_cn": "我每天晚上都听音乐。"},
                {"word": "lo sport", "phonetic": "/lo spɔrt/", "meaning": "n.m. 运动，体育", "example": "Faccio sport tutti i giorni.", "example_cn": "我每天都做运动。"},
                {"word": "la salute", "phonetic": "/la saˈluːte/", "meaning": "n.f. 健康", "example": "La salute è più importante di tutto.", "example_cn": "健康比什么都重要。"},
                {"word": "la pace", "phonetic": "/la ˈpaːtʃe/", "meaning": "n.f. 和平", "example": "Vogliamo la pace nel mondo.", "example_cn": "我们希望世界和平。"},
                {"word": "la macchina", "phonetic": "/la ˈmakkina/", "meaning": "n.f. 汽车；机器", "example": "La mia macchina è rossa.", "example_cn": "我的汽车是红色的。"},
                {"word": "l'aereo (m)", "phonetic": "/laˈɛːreo/", "meaning": "n.m. 飞机", "example": "L'aereo parte alle tre.", "example_cn": "飞机三点起飞。"},
                {"word": "l'università (f)", "phonetic": "/luniversiˈta/", "meaning": "n.f. 大学", "example": "Studio all'università.", "example_cn": "我在上大学。"},
                {"word": "il dottore", "phonetic": "/il dotˈtoːre/", "meaning": "n.m. 医生；博士", "example": "Devo andare dal dottore.", "example_cn": "我得去看医生。"},
                {"word": "l'ospedale (m)", "phonetic": "/loSpeˈdaːle/", "meaning": "n.m. 医院", "example": "L'ospedale è vicino a casa.", "example_cn": "医院离家很近。"},
                {"word": "la spiaggia", "phonetic": "/la ˈspjaddʒa/", "meaning": "n.f. 海滩", "example": "Andiamo in spiaggia d'estate.", "example_cn": "夏天我们去海滩。"},
                {"word": "il mare", "phonetic": "/il ˈmaːre/", "meaning": "n.m. 海，大海", "example": "Il mare è calmo oggi.", "example_cn": "今天大海很平静。"},
            ]},
        }
    },
    "portuguese": {
        "name": "葡萄牙语", "flag": "🇵🇹",
        "books": {
            "basic_pt": {"name": "葡萄牙语入门", "words": [
                {"word": "olá", "phonetic": "/oˈla/", "meaning": "interj. 你好", "example": "Olá, como estás?", "example_cn": "你好，你好吗？"},
                {"word": "o livro", "phonetic": "/u ˈlivɾu/", "meaning": "n.m. 书，书籍", "example": "Este livro é muito interessante.", "example_cn": "这本书非常有趣。"},
                {"word": "a casa", "phonetic": "/ɐ ˈkazɐ/", "meaning": "n.f. 房屋，家", "example": "A minha casa é grande.", "example_cn": "我家很大。"},
                {"word": "o homem", "phonetic": "/u ˈɔmɐ̃j/", "meaning": "n.m. 男人；人", "example": "O homem fala português.", "example_cn": "这个男人讲葡萄牙语。"},
                {"word": "a mulher", "phonetic": "/ɐ muˈʎɛɾ/", "meaning": "n.f. 女人；妻子", "example": "A mulher é professora.", "example_cn": "这位女士是老师。"},
                {"word": "o menino", "phonetic": "/u mɨˈninu/", "meaning": "n.m. 男孩", "example": "O menino joga no parque.", "example_cn": "男孩在公园里玩。"},
                {"word": "a menina", "phonetic": "/ɐ mɨˈninɐ/", "meaning": "n.f. 女孩", "example": "A menina lê um livro.", "example_cn": "女孩在读一本书。"},
                {"word": "o tempo", "phonetic": "/u ˈtẽpu/", "meaning": "n.m. 时间；天气", "example": "O tempo passa rápido.", "example_cn": "时间过得很快。"},
                {"word": "a vida", "phonetic": "/ɐ ˈviðɐ/", "meaning": "n.f. 生活，生命", "example": "A vida é bela.", "example_cn": "生活是美好的。"},
                {"word": "o trabalho", "phonetic": "/u tɾɐˈbaʎu/", "meaning": "n.m. 工作，劳动", "example": "Eu vou para o trabalho às 8.", "example_cn": "我八点去上班。"},
                {"word": "a família", "phonetic": "/ɐ fɐˈmiʎjɐ/", "meaning": "n.f. 家庭", "example": "A minha família é unida.", "example_cn": "我的家庭很团结。"},
                {"word": "o dinheiro", "phonetic": "/u diˈnɐjɾu/", "meaning": "n.m. 钱，金钱", "example": "Eu não tenho dinheiro.", "example_cn": "我没有钱。"},
                {"word": "a escola", "phonetic": "/ɐ ɨʃˈkɔlɐ/", "meaning": "n.f. 学校", "example": "As crianças vão para a escola.", "example_cn": "孩子们去上学。"},
                {"word": "o dia", "phonetic": "/u ˈdiɐ/", "meaning": "n.m. 天，日子", "example": "Bom dia!", "example_cn": "早上好！"},
                {"word": "a noite", "phonetic": "/ɐ ˈnɔjtɨ/", "meaning": "n.f. 夜晚", "example": "Boa noite!", "example_cn": "晚安！"},
                {"word": "a água", "phonetic": "/ɐ ˈaɡwɐ/", "meaning": "n.f. 水", "example": "Eu bebo muita água.", "example_cn": "我喝很多水。"},
                {"word": "a comida", "phonetic": "/ɐ kuˈmiðɐ/", "meaning": "n.f. 食物", "example": "A comida está deliciosa.", "example_cn": "饭菜很美味。"},
                {"word": "o cão", "phonetic": "/u kɐ̃w/", "meaning": "n.m. 狗（巴葡常用 cachorro）", "example": "O cão é muito fiel.", "example_cn": "狗非常忠诚。"},
                {"word": "a cidade", "phonetic": "/ɐ siˈðaðɨ/", "meaning": "n.f. 城市", "example": "Lisboa é uma cidade bonita.", "example_cn": "里斯本是一座美丽的城市。"},
                {"word": "o país", "phonetic": "/u paˈiʃ/", "meaning": "n.m. 国家", "example": "Portugal é um país pequeno.", "example_cn": "葡萄牙是一个小国家。"},
                {"word": "a língua", "phonetic": "/ɐ ˈlĩɡwɐ/", "meaning": "n.f. 语言；舌头", "example": "Aprendo duas línguas.", "example_cn": "我学两种语言。"},
                {"word": "o problema", "phonetic": "/u pɾuˈblɛmɐ/", "meaning": "n.m. 问题，难题", "example": "Não há problema.", "example_cn": "没问题。"},
                {"word": "a pergunta", "phonetic": "/ɐ pɨɾˈɡũtɐ/", "meaning": "n.f. 问题，提问", "example": "Tenho uma pergunta.", "example_cn": "我有一个问题。"},
                {"word": "o amigo", "phonetic": "/u ɐˈmiɡu/", "meaning": "n.m. 朋友", "example": "Ele é o meu melhor amigo.", "example_cn": "他是我最好的朋友。"},
                {"word": "a amiga", "phonetic": "/ɐ ɐˈmiɡɐ/", "meaning": "n.f. 女朋友", "example": "Ela é a minha melhor amiga.", "example_cn": "她是我最好的朋友。"},
                {"word": "a porta", "phonetic": "/ɐ ˈpɔɾtɐ/", "meaning": "n.f. 门", "example": "Fecha a porta, por favor.", "example_cn": "请关门。"},
                {"word": "a janela", "phonetic": "/ɐ ʒɐˈnɛlɐ/", "meaning": "n.f. 窗户", "example": "Abre a janela, por favor.", "example_cn": "请打开窗户。"},
                {"word": "a mesa", "phonetic": "/ɐ ˈmɛzɐ/", "meaning": "n.f. 桌子", "example": "O livro está na mesa.", "example_cn": "书在桌子上。"},
                {"word": "o café", "phonetic": "/u kɐˈfɛ/", "meaning": "n.m. 咖啡；咖啡馆", "example": "Eu bebo um café de manhã.", "example_cn": "我早上喝一杯咖啡。"},
                {"word": "a música", "phonetic": "/ɐ ˈmuzikɐ/", "meaning": "n.f. 音乐", "example": "Gosto de música clássica.", "example_cn": "我喜欢古典音乐。"},
                {"word": "o desporto", "phonetic": "/u dɨʃˈpɔɾtu/", "meaning": "n.m. 运动，体育（巴葡常用 esporte）", "example": "Faço desporto todos os dias.", "example_cn": "我每天都做运动。"},
                {"word": "a saúde", "phonetic": "/ɐ sɐˈuðɨ/", "meaning": "n.f. 健康", "example": "A saúde é muito importante.", "example_cn": "健康非常重要。"},
                {"word": "a paz", "phonetic": "/ɐ paʃ/", "meaning": "n.f. 和平", "example": "Queremos a paz no mundo.", "example_cn": "我们希望世界和平。"},
                {"word": "o carro", "phonetic": "/u ˈkaʁu/", "meaning": "n.m. 汽车", "example": "O meu carro é novo.", "example_cn": "我的车是新的。"},
                {"word": "o avião", "phonetic": "/u ɐˈvjɐ̃w/", "meaning": "n.m. 飞机", "example": "O avião parte às três.", "example_cn": "飞机三点起飞。"},
                {"word": "a universidade", "phonetic": "/ɐ univɨɾsiˈðaðɨ/", "meaning": "n.f. 大学", "example": "Eu estudo na universidade.", "example_cn": "我在大学学习。"},
                {"word": "o médico", "phonetic": "/u ˈmɛðiku/", "meaning": "n.m. 医生", "example": "Preciso de ir ao médico.", "example_cn": "我得去看医生。"},
                {"word": "o hospital", "phonetic": "/u ɔʃpiˈtal/", "meaning": "n.m. 医院", "example": "O hospital está perto.", "example_cn": "医院就在附近。"},
                {"word": "a praia", "phonetic": "/ɐ ˈpɾajɐ/", "meaning": "n.f. 海滩", "example": "Vamos à praia no verão.", "example_cn": "夏天我们去海滩。"},
                {"word": "o mar", "phonetic": "/u maɾ/", "meaning": "n.m. 海，大海", "example": "O mar está calmo hoje.", "example_cn": "今天大海风平浪静。"},
            ]},
        }
    },
    "russian": {
        "name": "俄语", "flag": "🇷🇺",
        "books": {
            "basic_ru": {"name": "俄语入门", "words": [
                {"word": "привет", "phonetic": "/ˈprʲivʲet/", "meaning": "interj. 你好（非正式）", "example": "Привет, как дела?", "example_cn": "你好，最近怎么样？"},
                {"word": "здравствуйте", "phonetic": "/ˈzdrastvʊjtʲe/", "meaning": "interj. 您好（正式/复数）", "example": "Здравствуйте, меня зовут Анна.", "example_cn": "您好，我叫安娜。"},
                {"word": "спасибо", "phonetic": "/spɐˈsʲibə/", "meaning": "interj. 谢谢", "example": "Спасибо за помощь.", "example_cn": "谢谢你的帮助。"},
                {"word": "пожалуйста", "phonetic": "/poˈʐaːlʊjstə/", "meaning": "interj. 请；不客气", "example": "Пожалуйста, проходите.", "example_cn": "请进。"},
                {"word": "извините", "phonetic": "/ɪzvʲɪˈnʲitʲe/", "meaning": "interj. 对不起；抱歉", "example": "Извините, я опоздал.", "example_cn": "对不起，我迟到了。"},
                {"word": "книга (ж)", "phonetic": "/ˈknʲiɡə/", "meaning": "n.f. 书，书籍", "example": "Эта книга очень интересная.", "example_cn": "这本书非常有趣。"},
                {"word": "дом (м)", "phonetic": "/dom/", "meaning": "n.m. 房屋，家", "example": "Мой дом большой.", "example_cn": "我家很大。"},
                {"word": "мужчина (м)", "phonetic": "/muˈɕːinə/", "meaning": "n.m. 男人", "example": "Этот мужчина говорит по-русски.", "example_cn": "这个男人说俄语。"},
                {"word": "женщина (ж)", "phonetic": "/ʐenˈɕːinə/", "meaning": "n.f. 女人", "example": "Женщина - моя мама.", "example_cn": "这位女士是我的母亲。"},
                {"word": "мальчик (м)", "phonetic": "/ˈmalʲt͡ɕɪk/", "meaning": "n.m. 男孩", "example": "Мальчик играет в саду.", "example_cn": "男孩在花园里玩耍。"},
                {"word": "девочка (ж)", "phonetic": "/ˈdʲevət͡ɕkə/", "meaning": "n.f. 女孩", "example": "Девочка читает книгу.", "example_cn": "女孩在看书。"},
                {"word": "время (ср)", "phonetic": "/ˈvrʲemʲə/", "meaning": "n.n. 时间；天气（中性）", "example": "Время летит быстро.", "example_cn": "时间飞逝。"},
                {"word": "жизнь (ж)", "phonetic": "/ˈʐɨznʲ/", "meaning": "n.f. 生活，生命", "example": "Жизнь прекрасна.", "example_cn": "生活是美好的。"},
                {"word": "работа (ж)", "phonetic": "/rɐˈbotə/", "meaning": "n.f. 工作，劳动", "example": "Я иду на работу в 8 утра.", "example_cn": "我早上8点去上班。"},
                {"word": "семья (ж)", "phonetic": "/sʲɪˈmʲja/", "meaning": "n.f. 家庭", "example": "У меня большая семья.", "example_cn": "我有一个大家庭。"},
                {"word": "деньги (мн)", "phonetic": "/ˈdʲenʲɡʲɪ/", "meaning": "n.pl. 钱（复数）", "example": "У меня нет денег.", "example_cn": "我没有钱。"},
                {"word": "школа (ж)", "phonetic": "/ˈʂkolə/", "meaning": "n.f. 学校", "example": "Дети ходят в школу.", "example_cn": "孩子们去上学。"},
                {"word": "день (м)", "phonetic": "/dʲenʲ/", "meaning": "n.m. 天，日子", "example": "Какой сегодня день?", "example_cn": "今天星期几？"},
                {"word": "ночь (ж)", "phonetic": "/not͡ɕ/", "meaning": "n.f. 夜晚", "example": "Спокойной ночи!", "example_cn": "晚安！"},
                {"word": "вода (ж)", "phonetic": "/vɐˈda/", "meaning": "n.f. 水", "example": "Я пью много воды.", "example_cn": "我喝很多水。"},
                {"word": "еда (ж)", "phonetic": "/jɪˈda/", "meaning": "n.f. 食物", "example": "Еда очень вкусная.", "example_cn": "饭菜非常好吃。"},
                {"word": "собака (ж)", "phonetic": "/sɐˈbakə/", "meaning": "n.f. 狗", "example": "Собака очень умная.", "example_cn": "这只狗非常聪明。"},
                {"word": "город (м)", "phonetic": "/ˈɡorət/", "meaning": "n.m. 城市", "example": "Москва - большой город.", "example_cn": "莫斯科是一座大城市。"},
                {"word": "страна (ж)", "phonetic": "/strɐˈna/", "meaning": "n.f. 国家", "example": "Россия - большая страна.", "example_cn": "俄罗斯是一个大国。"},
                {"word": "язык (м)", "phonetic": "/jɪˈzɨk/", "meaning": "n.m. 语言；舌头", "example": "Я учу два языка.", "example_cn": "我学两种语言。"},
                {"word": "проблема (ж)", "phonetic": "/prɐˈblʲemə/", "meaning": "n.f. 问题，难题", "example": "Это не проблема.", "example_cn": "这不是问题。"},
                {"word": "вопрос (м)", "phonetic": "/vɐˈpros/", "meaning": "n.m. 问题，提问", "example": "У меня есть вопрос.", "example_cn": "我有一个问题。"},
                {"word": "друг (м)", "phonetic": "/druk/", "meaning": "n.m. 朋友", "example": "Он мой лучший друг.", "example_cn": "他是我最好的朋友。"},
                {"word": "подруга (ж)", "phonetic": "/pɐˈdruɡə/", "meaning": "n.f. 女朋友", "example": "Она моя подруга.", "example_cn": "她是我的朋友。"},
                {"word": "дверь (ж)", "phonetic": "/dvʲerʲ/", "meaning": "n.f. 门", "example": "Закройте дверь, пожалуйста.", "example_cn": "请关门。"},
                {"word": "окно (ср)", "phonetic": "/ɐˈkno/", "meaning": "n.n. 窗户（中性）", "example": "Откройте окно, пожалуйста.", "example_cn": "请打开窗户。"},
                {"word": "стол (м)", "phonetic": "/stoɫ/", "meaning": "n.m. 桌子", "example": "Книга лежит на столе.", "example_cn": "书在桌子上。"},
                {"word": "кофе (м/ср)", "phonetic": "/ˈkofʲe/", "meaning": "n. 咖啡（可阳可中）", "example": "Я пью кофе утром.", "example_cn": "我早上喝咖啡。"},
                {"word": "музыка (ж)", "phonetic": "/ˈmuzɨkə/", "meaning": "n.f. 音乐", "example": "Я слушаю музыку каждый день.", "example_cn": "我每天都听音乐。"},
                {"word": "спорт (м)", "phonetic": "/sport/", "meaning": "n.m. 运动，体育", "example": "Я занимаюсь спортом каждый день.", "example_cn": "我每天都做运动。"},
                {"word": "здоровье (ср)", "phonetic": "/zdɐˈrovʲjə/", "meaning": "n.n. 健康（中性）", "example": "Здоровье - самое главное.", "example_cn": "健康是最重要的。"},
                {"word": "мир (м)", "phonetic": "/mʲir/", "meaning": "n.m. 和平；世界", "example": "Мы хотим мира во всём мире.", "example_cn": "我们希望世界和平。"},
                {"word": "машина (ж)", "phonetic": "/mɐˈɕːinə/", "meaning": "n.f. 汽车；机器", "example": "Моя машина новая.", "example_cn": "我的车是新的。"},
                {"word": "самолёт (м)", "phonetic": "/səmɐˈlʲɵt/", "meaning": "n.m. 飞机", "example": "Самолёт вылетает в три.", "example_cn": "飞机三点起飞。"},
                {"word": "университет (м)", "phonetic": "/ʊnʲɪvʲɪrsʲɪˈtʲet/", "meaning": "n.m. 大学", "example": "Я учусь в университете.", "example_cn": "我在上大学。"},
                {"word": "врач (м)", "phonetic": "/vrat͡ɕ/", "meaning": "n.m. 医生", "example": "Мне нужно к врачу.", "example_cn": "我得去看医生。"},
                {"word": "больница (ж)", "phonetic": "/bɐlʲˈnʲitsə/", "meaning": "n.f. 医院", "example": "Больница рядом с домом.", "example_cn": "医院就在家附近。"},
            ]},
        }
    },
    "korean": {
        "name": "韩语", "flag": "🇰🇷",
        "books": {
            "topik1": {"name": "TOPIK I", "words": [
                {"word": "안녕하세요", "phonetic": "annyeonghaseyo", "meaning": "你好（敬语，常用）", "example": "안녕하세요, 만나서 반갑습니다.", "example_cn": "你好，很高兴见到你。"},
                {"word": "감사합니다", "phonetic": "gamsahamnida", "meaning": "谢谢（敬语，正式）", "example": "도와주셔서 감사합니다.", "example_cn": "非常感谢您的帮助。"},
                {"word": "미안합니다", "phonetic": "mianhamnida", "meaning": "对不起（正式）", "example": "늦어서 미안합니다.", "example_cn": "对不起，我迟到了。"},
                {"word": "네 / 아니요", "phonetic": "ne / aniyo", "meaning": "是 / 不是（敬语）", "example": "네, 맞습니다. / 아니요, 아닙니다.", "example_cn": "是，对的。/ 不，不是的。"},
                {"word": "책 (명)", "phonetic": "chaek (myeong)", "meaning": "n. 书，书籍", "example": "이 책은 매우 재미있어요.", "example_cn": "这本书非常有趣。"},
                {"word": "집 (명)", "phonetic": "jip (myeong)", "meaning": "n. 房屋，家", "example": "우리 집은 커요.", "example_cn": "我家很大。"},
                {"word": "남자 (명)", "phonetic": "namja (myeong)", "meaning": "n. 男人", "example": "그 남자는 한국어를 해요.", "example_cn": "那个男人说韩语。"},
                {"word": "여자 (명)", "phonetic": "yeoja (myeong)", "meaning": "n. 女人", "example": "저 여자는 제 어머니예요.", "example_cn": "那位女士是我母亲。"},
                {"word": "소년 (명)", "phonetic": "sonyeon (myeong)", "meaning": "n. 少年，男孩", "example": "소년이 공원에서 뛰어놀아요.", "example_cn": "男孩在公园里奔跑玩耍。"},
                {"word": "소녀 (명)", "phonetic": "sonyeo (myeong)", "meaning": "n. 少女，女孩", "example": "소녀가 책을 읽고 있어요.", "example_cn": "女孩在看书。"},
                {"word": "시간 (명)", "phonetic": "sigan (myeong)", "meaning": "n. 时间", "example": "시간이 빨리 가요.", "example_cn": "时间过得很快。"},
                {"word": "생활 (명)", "phonetic": "saenghwal (myeong)", "meaning": "n. 生活", "example": "생활이 즐거워요.", "example_cn": "生活很愉快。"},
                {"word": "일 (명)", "phonetic": "il (myeong)", "meaning": "n. 工作；事情", "example": "저는 아침 8시에 일해요.", "example_cn": "我早上8点工作。"},
                {"word": "가족 (명)", "phonetic": "gajok (myeong)", "meaning": "n. 家庭，家人", "example": "우리 가족은 4명이에요.", "example_cn": "我家有四口人。"},
                {"word": "돈 (명)", "phonetic": "don (myeong)", "meaning": "n. 钱，金钱", "example": "돈이 없어요.", "example_cn": "我没有钱。"},
                {"word": "학교 (명)", "phonetic": "hakgyo (myeong)", "meaning": "n. 学校", "example": "아이들이 학교에 가요.", "example_cn": "孩子们去上学。"},
                {"word": "날 (명) / 요일 (명)", "phonetic": "nal / yoil (myeong)", "meaning": "n. 天 / 星期，日子", "example": "오늘은 무슨 요일이에요?", "example_cn": "今天星期几？"},
                {"word": "밤 (명)", "phonetic": "bam (myeong)", "meaning": "n. 夜晚", "example": "안녕히 주무세요. (잘 자요)", "example_cn": "晚安。"},
                {"word": "물 (명)", "phonetic": "mul (myeong)", "meaning": "n. 水", "example": "저는 물을 많이 마셔요.", "example_cn": "我喝很多水。"},
                {"word": "음식 (명)", "phonetic": "eumsik (myeong)", "meaning": "n. 食物，饮食", "example": "한국 음식이 맛있어요.", "example_cn": "韩国食物很好吃。"},
                {"word": "개 (명)", "phonetic": "gae (myeong)", "meaning": "n. 狗", "example": "우리 개는 아주 똑똑해요.", "example_cn": "我家的狗非常聪明。"},
                {"word": "고양이 (명)", "phonetic": "goyangi (myeong)", "meaning": "n. 猫", "example": "고양이가 소파에서 자요.", "example_cn": "猫在沙发上睡觉。"},
                {"word": "도시 (명)", "phonetic": "dosi (myeong)", "meaning": "n. 城市", "example": "서울은 큰 도시예요.", "example_cn": "首尔是一座大城市。"},
                {"word": "나라 (명)", "phonetic": "nara (myeong)", "meaning": "n. 国家", "example": "한국은 아름다운 나라예요.", "example_cn": "韩国是一个美丽的国家。"},
                {"word": "언어 (명)", "phonetic": "eoneo (myeong)", "meaning": "n. 语言", "example": "저는 외국어를 2개 배워요.", "example_cn": "我学习两门外语。"},
                {"word": "문제 (명)", "phonetic": "munje (myeong)", "meaning": "n. 问题，难题", "example": "문제 없어요.", "example_cn": "没问题。"},
                {"word": "질문 (명)", "phonetic": "jilmun (myeong)", "meaning": "n. 提问，疑问", "example": "질문이 하나 있어요.", "example_cn": "我有一个问题。"},
                {"word": "친구 (명)", "phonetic": "chingu (myeong)", "meaning": "n. 朋友", "example": "그는 제 가장 친한 친구예요.", "example_cn": "他是我最要好的朋友。"},
                {"word": "문 (명)", "phonetic": "mun (myeong)", "meaning": "n. 门", "example": "문을 닫아 주세요.", "example_cn": "请关门。"},
                {"word": "창문 (명)", "phonetic": "changmun (myeong)", "meaning": "n. 窗户", "example": "창문을 열어 주세요.", "example_cn": "请打开窗户。"},
                {"word": "탁자 (명)", "phonetic": "takja (myeong)", "meaning": "n. 桌子", "example": "책이 탁자 위에 있어요.", "example_cn": "书在桌子上。"},
                {"word": "커피 (명)", "phonetic": "keopi (myeong)", "meaning": "n. 咖啡", "example": "저는 아침에 커피를 마셔요.", "example_cn": "我早上喝咖啡。"},
                {"word": "음악 (명)", "phonetic": "eumak (myeong)", "meaning": "n. 音乐", "example": "저는 매일 음악을 들어요.", "example_cn": "我每天都听音乐。"},
                {"word": "운동 (명)", "phonetic": "undong (myeong)", "meaning": "n. 运动，体育", "example": "저는 매일 운동해요.", "example_cn": "我每天都做运动。"},
                {"word": "건강 (명)", "phonetic": "geongang (myeong)", "meaning": "n. 健康", "example": "건강이 제일 중요해요.", "example_cn": "健康是最重要的。"},
                {"word": "평화 (명)", "phonetic": "pyeonghwa (myeong)", "meaning": "n. 和平", "example": "우리는 세계 평화를 원해요.", "example_cn": "我们希望世界和平。"},
                {"word": "자동차 (명)", "phonetic": "jadongcha (myeong)", "meaning": "n. 汽车", "example": "우리 차는 새 차예요.", "example_cn": "我们的车是新车。"},
                {"word": "비행기 (명)", "phonetic": "bihaenggi (myeong)", "meaning": "n. 飞机", "example": "비행기가 3시에 출발해요.", "example_cn": "飞机三点起飞。"},
                {"word": "대학교 (명)", "phonetic": "daehakgyo (myeong)", "meaning": "n. 大学", "example": "저는 대학교에 다녀요.", "example_cn": "我在上大学。"},
                {"word": "의사 (명)", "phonetic": "uisa (myeong)", "meaning": "n. 医生", "example": "저는 의사를 만나야 해요.", "example_cn": "我得去看医生。"},
                {"word": "병원 (명)", "phonetic": "byeongwon (myeong)", "meaning": "n. 医院", "example": "병원이 집 근처에 있어요.", "example_cn": "医院就在家附近。"},
                {"word": "바다 (명)", "phonetic": "bada (myeong)", "meaning": "n. 海，大海", "example": "여름에 바다에 가요.", "example_cn": "夏天去海边。"},
                {"word": "사과 (명)", "phonetic": "sagwa (myeong)", "meaning": "n. 苹果；道歉", "example": "저는 매일 사과를 먹어요.", "example_cn": "我每天吃一个苹果。"},
                {"word": "밥 (명)", "phonetic": "bap (myeong)", "meaning": "n. 米饭；饭", "example": "밥을 먹어요.", "example_cn": "我在吃饭。"},
                {"word": "우유 (명)", "phonetic": "uyu (myeong)", "meaning": "n. 牛奶", "example": "저는 우유를 좋아해요.", "example_cn": "我喜欢喝牛奶。"},
                {"word": "선생님 (명)", "phonetic": "seonsaengnim (myeong)", "meaning": "n. 老师（敬称）", "example": "선생님, 감사합니다.", "example_cn": "老师，谢谢您。"},
                {"word": "학생 (명)", "phonetic": "haksaeng (myeong)", "meaning": "n. 学生", "example": "저는 대학생이에요.", "example_cn": "我是大学生。"},
                {"word": "아버지 (명)", "phonetic": "abeoji (myeong)", "meaning": "n. 父亲（敬称）", "example": "우리 아버지는 회사원이에요.", "example_cn": "我父亲是公司职员。"},
                {"word": "어머니 (명)", "phonetic": "eomeoni (myeong)", "meaning": "n. 母亲（敬称）", "example": "어머니는 요리를 잘하셔요.", "example_cn": "妈妈做饭很好吃。"},
            ]},
        }
    },
    "cantonese": {
        "name": "粤语", "flag": "🇭🇰",
        "books": {
            "basic_yue": {"name": "粤语入门", "words": [
                {"word": "你好", "phonetic": "nei5 hou2", "meaning": "你好", "example": "你好，我係陳先生。", "example_cn": "你好，我是陈先生。"},
                {"word": "唔該", "phonetic": "m4 goi1", "meaning": "麻烦/谢谢/请", "example": "唔該借過。/ 唔該一杯奶茶。", "example_cn": "麻烦借过一下。/ 请来一杯奶茶。"},
                {"word": "多謝", "phonetic": "do1 ze6", "meaning": "谢谢（礼物/帮助）", "example": "多謝你嘅禮物。", "example_cn": "谢谢你的礼物。"},
                {"word": "對唔住", "phonetic": "deoi3 m4 zyu6", "meaning": "对不起，抱歉", "example": "對唔住，我遲到咗。", "example_cn": "对不起，我迟到了。"},
                {"word": "係 / 唔係", "phonetic": "hai6 / m4 hai6", "meaning": "是 / 不是", "example": "係呀，冇錯。/ 唔係，唔係咁樣。", "example_cn": "是，没错。/ 不，不是这样的。"},
                {"word": "書", "phonetic": "syu1", "meaning": "n. 书，书籍", "example": "呢本書好有趣。", "example_cn": "这本书很有趣。"},
                {"word": "屋企", "phonetic": "uk1 kei2", "meaning": "n. 家，住所", "example": "我屋企好大。", "example_cn": "我家很大。"},
                {"word": "男人", "phonetic": "naam4 jan4", "meaning": "n. 男人", "example": "個男人講廣東話。", "example_cn": "那个男人说粤语。"},
                {"word": "女人", "phonetic": "neoi5 jan4", "meaning": "n. 女人", "example": "個女人係我媽咪。", "example_cn": "那个女人是我妈妈。"},
                {"word": "細路仔", "phonetic": "sai3 lou6 zai2", "meaning": "n. 男孩，小男孩", "example": "細路仔喺公園度玩。", "example_cn": "小男孩在公园里玩。"},
                {"word": "細路女", "phonetic": "sai3 lou6 neoi2", "meaning": "n. 女孩，小女孩", "example": "細路女睇緊書。", "example_cn": "小女孩在看书。"},
                {"word": "時間", "phonetic": "si4 gaan1", "meaning": "n. 时间", "example": "時間過得好快。", "example_cn": "时间过得很快。"},
                {"word": "生活", "phonetic": "saang1 wut6", "meaning": "n. 生活", "example": "生活好開心。", "example_cn": "生活很开心。"},
                {"word": "返工", "phonetic": "faan1 gung1", "meaning": "v./n. 上班；工作", "example": "我朝早8點鐘返工。", "example_cn": "我早上8点上班。"},
                {"word": "屋企人 / 家人", "phonetic": "uk1 kei2 jan4 / gaa1 jan4", "meaning": "n. 家人", "example": "我屋企人有4個。", "example_cn": "我家有四口人。"},
                {"word": "錢", "phonetic": "cin2", "meaning": "n. 钱，金钱", "example": "我冇錢。", "example_cn": "我没有钱。"},
                {"word": "學校", "phonetic": "hok6 haau6", "meaning": "n. 学校", "example": "細路仔返學喇。", "example_cn": "孩子们上学了。"},
                {"word": "日 / 今日", "phonetic": "jat6 / gam1 jat6", "meaning": "n. 日子 / 今天", "example": "今日係咩日子？", "example_cn": "今天是什么日子？"},
                {"word": "夜晚", "phonetic": "je6 maan5", "meaning": "n. 夜晚", "example": "早啲瞓，晚安。", "example_cn": "早点睡，晚安。"},
                {"word": "水", "phonetic": "seoi2", "meaning": "n. 水", "example": "我飲好多水。", "example_cn": "我喝很多水。"},
                {"word": "嘢食 / 食物", "phonetic": "je5 sik6 / sik6 mat6", "meaning": "n. 食物，吃的东西", "example": "廣東嘢食好好味。", "example_cn": "广东食物很好吃。"},
                {"word": "狗", "phonetic": "gau2", "meaning": "n. 狗", "example": "隻狗好聰明。", "example_cn": "这只狗很聪明。"},
                {"word": "貓", "phonetic": "maau1", "meaning": "n. 猫", "example": "隻貓喺梳化度瞓覺。", "example_cn": "猫在沙发上睡觉。"},
                {"word": "城市", "phonetic": "sing4 si5", "meaning": "n. 城市", "example": "香港係一個大城市。", "example_cn": "香港是一个大城市。"},
                {"word": "國家", "phonetic": "gwok3 gaa1", "meaning": "n. 国家", "example": "中國係我嘅國家。", "example_cn": "中国是我的国家。"},
                {"word": "語言", "phonetic": "jyu5 jin4", "meaning": "n. 语言", "example": "我識兩種語言。", "example_cn": "我会两种语言。"},
                {"word": "問題", "phonetic": "man6 tai4", "meaning": "n. 问题", "example": "冇問題。", "example_cn": "没问题。"},
                {"word": "朋友", "phonetic": "pang4 jau5", "meaning": "n. 朋友", "example": "佢係我最好嘅朋友。", "example_cn": "他是我最好的朋友。"},
                {"word": "門", "phonetic": "mun4", "meaning": "n. 门", "example": "唔該閂埋門。", "example_cn": "麻烦关上门。"},
                {"word": "窗", "phonetic": "coeng1", "meaning": "n. 窗户", "example": "唔該開下窗，好熱。", "example_cn": "麻烦开下窗，好热。"},
                {"word": "枱", "phonetic": "toi2", "meaning": "n. 桌子", "example": "本書放咗喺枱面。", "example_cn": "书放在桌面上。"},
                {"word": "咖啡", "phonetic": "gaa3 fe1", "meaning": "n. 咖啡", "example": "我朝早飲咖啡。", "example_cn": "我早上喝咖啡。"},
                {"word": "音樂", "phonetic": "jam1 ngok6", "meaning": "n. 音乐", "example": "我每日都聽音樂。", "example_cn": "我每天都听音乐。"},
                {"word": "做運動", "phonetic": "zou6 wan6 dung6", "meaning": "v.phr. 做运动，锻炼", "example": "我每日都做運動。", "example_cn": "我每天都做运动。"},
                {"word": "健康", "phonetic": "gin6 hong1", "meaning": "n. 健康", "example": "健康最重要。", "example_cn": "健康最重要。"},
                {"word": "和平", "phonetic": "wo4 ping4", "meaning": "n. 和平", "example": "我哋想要世界和平。", "example_cn": "我们希望世界和平。"},
                {"word": "車", "phonetic": "ce1", "meaning": "n. 汽车，车", "example": "我架車係新嘅。", "example_cn": "我的车是新的。"},
                {"word": "飛機", "phonetic": "fei1 gei1", "meaning": "n. 飞机", "example": "飛機3點起飛。", "example_cn": "飞机三点起飞。"},
                {"word": "大學", "phonetic": "daai6 hok6", "meaning": "n. 大学", "example": "我讀大學。", "example_cn": "我在读大学。"},
                {"word": "醫生", "phonetic": "ji1 saang1", "meaning": "n. 医生", "example": "我要睇醫生。", "example_cn": "我得去看医生。"},
                {"word": "醫院", "phonetic": "ji1 jyun2", "meaning": "n. 医院", "example": "醫院喺屋企隔離。", "example_cn": "医院就在家旁边。"},
                {"word": "早餐 / 朝早", "phonetic": "zou2 caan1 / ziu1 zou2", "meaning": "n. 早餐 / 早上", "example": "我朝早食早餐。", "example_cn": "我早上吃早餐。"},
                {"word": "午餐 / 晏晝", "phonetic": "ng5 caan1 / aan3 zau3", "meaning": "n. 午餐 / 中午", "example": "晏晝食午餐。", "example_cn": "中午吃午餐。"},
                {"word": "晚餐 / 夜晚", "phonetic": "maan5 caan1 / je6 maan5", "meaning": "n. 晚餐 / 晚上", "example": "夜晚同朋友食晚餐。", "example_cn": "晚上和朋友一起吃晚餐。"},
                {"word": "老竇 / 爸爸", "phonetic": "lou5 dau6 / baa4 baa1", "meaning": "n. 父亲，爸爸", "example": "我老竇係工程師。", "example_cn": "我爸爸是工程师。"},
                {"word": "老母 / 媽咪", "phonetic": "lou5 mou2 / maa1 mai1", "meaning": "n. 母亲，妈妈", "example": "我老母煮嘢好食。", "example_cn": "我妈妈做饭好吃。"},
                {"word": "大佬 / 阿哥", "phonetic": "daai6 lou2 / aa3 go1", "meaning": "n. 哥哥（口语）", "example": "我大佬係醫生。", "example_cn": "我哥哥是医生。"},
                {"word": "細妹 / 阿妹", "phonetic": "sai3 mui6 / aa3 mui1", "meaning": "n. 妹妹（口语）", "example": "我細妹仲細個。", "example_cn": "我妹妹还很小。"},
                {"word": "蘋果", "phonetic": "ping4 gwo2", "meaning": "n. 苹果", "example": "我每日食一個蘋果。", "example_cn": "我每天吃一个苹果。"},
                {"word": "飯", "phonetic": "faan6", "meaning": "n. 米饭；饭", "example": "食飯喇。", "example_cn": "吃饭啦。"},
            ]},
        }
    },
    "japanese": {
        "name": "日语", "flag": "🇯🇵",
        "books": {
            "n1": {"name": "JLPT N1", "words": [
                {"word": "意向", "phonetic": "いこう", "meaning": "意向，打算；意图", "example": "彼の意向を確認した。", "example_cn": "确认了他的意向。"},
                {"word": "曖昧", "phonetic": "あいまい", "meaning": "暧昧，含糊，模棱两可", "example": "曖昧な返事をするな。", "example_cn": "别给含糊的答复。"},
                {"word": "憂鬱", "phonetic": "ゆううつ", "meaning": "忧郁，愁闷；阴沉", "example": "雨の日は憂鬱になる。", "example_cn": "下雨天会让人忧郁。"},
                {"word": "画期的", "phonetic": "がっきてき", "meaning": "划时代的，突破性的", "example": "画期的な発明だ。", "example_cn": "这是一项划时代的发明。"},
                {"word": "厳格", "phonetic": "げんかく", "meaning": "严格，严厉", "example": "彼は規則が厳格だ。", "example_cn": "他对规则要求很严格。"},
                {"word": "構築", "phonetic": "こうちく", "meaning": "构筑，建造；建立", "example": "新しい制度を構築する。", "example_cn": "构建新的制度。"},
                {"word": "頻繁", "phonetic": "ひんぱん", "meaning": "频繁，屡次", "example": "彼は頻繁に遅刻する。", "example_cn": "他频繁迟到。"},
                {"word": "自給自足", "phonetic": "じきゅうじそく", "meaning": "自给自足", "example": "田舎で自給自足の生活を送る。", "example_cn": "在乡下过着自给自足的生活。"},
                {"word": "一見", "phonetic": "いっけん / ひとみ", "meaning": "一看；乍一看；一见", "example": "一見、簡単そうに見える。", "example_cn": "乍一看好像很简单。"},
                {"word": "活躍", "phonetic": "かつやく", "meaning": "活跃，大显身手", "example": "国際舞台で活躍する。", "example_cn": "在国际舞台上大显身手。"},
                {"word": "調和", "phonetic": "ちょうわ", "meaning": "调和，和谐；协调", "example": "自然との調和を保つ。", "example_cn": "保持与自然的和谐。"},
                {"word": "矛盾", "phonetic": "むじゅん", "meaning": "矛盾", "example": "彼の言葉には矛盾がある。", "example_cn": "他的话里有矛盾。"},
                {"word": "露骨", "phonetic": "ろこつ", "meaning": "露骨，赤裸裸；明显", "example": "露骨な表現は控えろ。", "example_cn": "请避免露骨的表达。"},
                {"word": "婉曲", "phonetic": "えんきょく", "meaning": "委婉，婉转", "example": "婉曲に断った。", "example_cn": "委婉地拒绝了。"},
                {"word": "未曽有", "phonetic": "みぞう", "meaning": "前所未有，空前", "example": "未曽有の大災害だ。", "example_cn": "这是史无前例的大灾难。"},
                {"word": "懸命", "phonetic": "けんめい", "meaning": "拼命，竭尽全力", "example": "懸命に働く。", "example_cn": "拼命地工作。"},
                {"word": "慎重", "phonetic": "しんちょう", "meaning": "慎重，谨慎", "example": "慎重に判断する。", "example_cn": "慎重地判断。"},
                {"word": "強引", "phonetic": "ごういん", "meaning": "强制，强行；强硬", "example": "強引に進めるな。", "example_cn": "不要强行推进。"},
                {"word": "潔白", "phonetic": "けっぱく", "meaning": "洁白；清白，无罪", "example": "彼は潔白だと証明された。", "example_cn": "他被证明是清白的。"},
                {"word": "断固", "phonetic": "だんこ", "meaning": "断然，坚决，果断", "example": "断固として反対する。", "example_cn": "坚决反对。"},
                {"word": "無念", "phonetic": "むねん", "meaning": "悔恨，遗憾；窝囊", "example": "負けて無念だ。", "example_cn": "输了很遗憾。"},
                {"word": "壮絶", "phonetic": "そうぜつ", "meaning": "壮烈，悲壮", "example": "壮絶な戦いだった。", "example_cn": "这是一场壮烈的战斗。"},
                {"word": "難解", "phonetic": "なんかい", "meaning": "难懂，难解", "example": "この本は難解だ。", "example_cn": "这本书很难懂。"},
                {"word": "容易", "phonetic": "ようい", "meaning": "容易，轻易", "example": "そう容易なことではない。", "example_cn": "这不是件容易的事。"},
                {"word": "簡素", "phonetic": "かんそ", "meaning": "简朴，朴素，简陋", "example": "簡素な生活を好む。", "example_cn": "喜欢简朴的生活。"},
                {"word": "華奢", "phonetic": "きゃしゃ", "meaning": "纤细，苗条；奢华", "example": "華奢な体つきの女性。", "example_cn": "身材纤细的女性。"},
                {"word": "莫大", "phonetic": "ばくだい", "meaning": "莫大，极大，巨大", "example": "莫大な損害が出た。", "example_cn": "造成了巨大的损失。"},
                {"word": "些細", "phonetic": "ささい", "meaning": "细小，琐碎，微不足道", "example": "些細なことで喧嘩する。", "example_cn": "因为小事吵架。"},
                {"word": "重大", "phonetic": "じゅうだい", "meaning": "重大，重要", "example": "重大な決断を下す。", "example_cn": "做出重大决定。"},
                {"word": "切実", "phonetic": "せつじつ", "meaning": "切实，迫切，恳切", "example": "切実な願い。", "example_cn": "迫切的愿望。"},
            ]},
            "n2": {"name": "JLPT N2", "words": [
                {"word": "曖昧", "phonetic": "あいまい", "meaning": "暧昧，含糊，模棱两可", "example": "曖昧な返事をするな。", "example_cn": "别给含糊的答复。"},
                {"word": "余計", "phonetic": "よけい", "meaning": "多余，多余的；更加", "example": "余計な心配をした。", "example_cn": "白担心了一场。"},
                {"word": "感動", "phonetic": "かんどう", "meaning": "感动，打动", "example": "その映画に感動した。", "example_cn": "被那部电影感动了。"},
                {"word": "失敗", "phonetic": "しっぱい", "meaning": "失败，失误", "example": "初めての試みは失敗した。", "example_cn": "第一次尝试失败了。"},
                {"word": "成功", "phonetic": "せいこう", "meaning": "成功", "example": "実験は成功した。", "example_cn": "实验成功了。"},
                {"word": "努力", "phonetic": "どりょく", "meaning": "努力，奋斗", "example": "努力すれば報われる。", "example_cn": "努力就会有回报。"},
                {"word": "相談", "phonetic": "そうだん", "meaning": "商量，商议；咨询", "example": "先生に相談に行く。", "example_cn": "去和老师商量。"},
                {"word": "意見", "phonetic": "いけん", "meaning": "意见，见解；提议", "example": "ご意見をお聞かせください。", "example_cn": "请说说您的意见。"},
                {"word": "主張", "phonetic": "しゅちょう", "meaning": "主张，论点", "example": "自分の主張を曲げない。", "example_cn": "不放弃自己的主张。"},
                {"word": "開始", "phonetic": "かいし", "meaning": "开始", "example": "会議を開始します。", "example_cn": "现在开始会议。"},
                {"word": "終了", "phonetic": "しゅうりょう", "meaning": "结束，终了", "example": "試験は無事終了した。", "example_cn": "考试顺利结束了。"},
                {"word": "継続", "phonetic": "けいぞく", "meaning": "继续，持续", "example": "継続は力なり。", "example_cn": "坚持就是胜利。"},
                {"word": "達成", "phonetic": "たっせい", "meaning": "达成，完成", "example": "目標を達成した。", "example_cn": "达成了目标。"},
                {"word": "向上", "phonetic": "こうじょう", "meaning": "提高，向上，进步", "example": "学力が向上した。", "example_cn": "学习成绩提高了。"},
                {"word": "促進", "phonetic": "そくしん", "meaning": "促进，推进", "example": "経済の発展を促進する。", "example_cn": "促进经济发展。"},
                {"word": "影響", "phonetic": "えいきょう", "meaning": "影响", "example": "悪い影響を与える。", "example_cn": "造成不良影响。"},
                {"word": "原因", "phonetic": "げんいん", "meaning": "原因，起因", "example": "事故の原因を調べる。", "example_cn": "调查事故原因。"},
                {"word": "結果", "phonetic": "けっか", "meaning": "结果，结局", "example": "結果はまだ分からない。", "example_cn": "结果还不知道。"},
                {"word": "状況", "phonetic": "じょうきょう", "meaning": "状况，情况，形势", "example": "状況を説明してください。", "example_cn": "请说明情况。"},
                {"word": "環境", "phonetic": "かんきょう", "meaning": "环境", "example": "自然環境を守る。", "example_cn": "保护自然环境。"},
                {"word": "情報", "phonetic": "じょうほう", "meaning": "信息，情报", "example": "正確な情報を得る。", "example_cn": "获得准确的信息。"},
                {"word": "経験", "phonetic": "けいけん", "meaning": "经验；经历", "example": "貴重な経験をした。", "example_cn": "获得了宝贵的经验。"},
                {"word": "記憶", "phonetic": "きおく", "meaning": "记忆，回忆", "example": "子供の頃の記憶。", "example_cn": "童年的记忆。"},
                {"word": "能力", "phonetic": "のうりょく", "meaning": "能力，才能", "example": "彼は能力がある。", "example_cn": "他有能力。"},
                {"word": "機会", "phonetic": "きかい", "meaning": "机会，时机", "example": "良い機会を逃すな。", "example_cn": "不要错过好机会。"},
                {"word": "挑戦", "phonetic": "ちょうせん", "meaning": "挑战", "example": "新しいことに挑戦する。", "example_cn": "挑战新事物。"},
                {"word": "保証", "phonetic": "ほしょう", "meaning": "保证，担保", "example": "品質を保証する。", "example_cn": "保证质量。"},
                {"word": "承知", "phonetic": "しょうち", "meaning": "知道；同意，答应", "example": "その件は承知している。", "example_cn": "那件事我知道。"},
                {"word": "確認", "phonetic": "かくにん", "meaning": "确认，核实", "example": "スケジュールを確認する。", "example_cn": "确认日程。"},
                {"word": "準備", "phonetic": "じゅんび", "meaning": "准备，预备", "example": "出発の準備はできた？", "example_cn": "准备好出发了吗？"},
            ]},
            "n3": {"name": "JLPT N3", "words": [
                {"word": "余計", "phonetic": "よけい", "meaning": "多余，多余的；更加", "example": "余計な心配をした。", "example_cn": "白担心了一场。"},
                {"word": "約束", "phonetic": "やくそく", "meaning": "约定，诺言", "example": "約束を守ってください。", "example_cn": "请遵守约定。"},
                {"word": "学生", "phonetic": "がくせい", "meaning": "学生", "example": "私は大学生です。", "example_cn": "我是大学生。"},
                {"word": "先生", "phonetic": "せんせい", "meaning": "老师；医生；专家", "example": "田中先生は優しいです。", "example_cn": "田中老师很温柔。"},
                {"word": "友達", "phonetic": "ともだち", "meaning": "朋友", "example": "彼は私の一番の友達です。", "example_cn": "他是我最好的朋友。"},
                {"word": "家族", "phonetic": "かぞく", "meaning": "家人，家庭", "example": "家族は4人です。", "example_cn": "家里有四口人。"},
                {"word": "学校", "phonetic": "がっこう", "meaning": "学校", "example": "毎日学校に行きます。", "example_cn": "每天去上学。"},
                {"word": "会社", "phonetic": "かいしゃ", "meaning": "公司", "example": "父は会社員です。", "example_cn": "父亲是公司职员。"},
                {"word": "銀行", "phonetic": "ぎんこう", "meaning": "银行", "example": "銀行でお金を下ろす。", "example_cn": "在银行取钱。"},
                {"word": "病院", "phonetic": "びょういん", "meaning": "医院", "example": "病院に行かなければならない。", "example_cn": "必须得去医院。"},
                {"word": "電車", "phonetic": "でんしゃ", "meaning": "电车", "example": "電車で通勤しています。", "example_cn": "坐电车通勤。"},
                {"word": "車", "phonetic": "くるま", "meaning": "汽车，车", "example": "新しい車を買いました。", "example_cn": "买了新车。"},
                {"word": "飛行機", "phonetic": "ひこうき", "meaning": "飞机", "example": "飛行機で旅行する。", "example_cn": "坐飞机去旅行。"},
                {"word": "時間", "phonetic": "じかん", "meaning": "时间", "example": "時間がありません。", "example_cn": "没有时间了。"},
                {"word": "今日", "phonetic": "きょう", "meaning": "今天", "example": "今日はいい天気ですね。", "example_cn": "今天天气真好啊。"},
                {"word": "明日", "phonetic": "あした", "meaning": "明天", "example": "明日また会いましょう。", "example_cn": "明天见。"},
                {"word": "昨日", "phonetic": "きのう", "meaning": "昨天", "example": "昨日は何をしましたか？", "example_cn": "昨天做了什么？"},
                {"word": "毎日", "phonetic": "まいにち", "meaning": "每天，每日", "example": "毎日日本語を勉強する。", "example_cn": "每天学习日语。"},
                {"word": "朝", "phonetic": "あさ", "meaning": "早晨，早上", "example": "朝6時に起きます。", "example_cn": "早上6点起床。"},
                {"word": "夜", "phonetic": "よる", "meaning": "晚上，夜里", "example": "夜は早く寝ます。", "example_cn": "晚上睡得早。"},
                {"word": "本", "phonetic": "ほん", "meaning": "书，书籍", "example": "この本はとても面白いです。", "example_cn": "这本书非常有趣。"},
                {"word": "手紙", "phonetic": "てがみ", "meaning": "信，书信", "example": "母に手紙を書きます。", "example_cn": "给妈妈写信。"},
                {"word": "新聞", "phonetic": "しんぶん", "meaning": "报纸", "example": "毎朝新聞を読みます。", "example_cn": "每天早上看报纸。"},
                {"word": "雑誌", "phonetic": "ざっし", "meaning": "杂志", "example": "雑誌を購読している。", "example_cn": "订阅着杂志。"},
                {"word": "音楽", "phonetic": "おんがく", "meaning": "音乐", "example": "音楽を聴きながら勉強する。", "example_cn": "边听音乐边学习。"},
                {"word": "映画", "phonetic": "えいが", "meaning": "电影", "example": "週末に映画を見に行く。", "example_cn": "周末去看电影。"},
                {"word": "食べ物", "phonetic": "たべもの", "meaning": "食物，吃的东西", "example": "日本の食べ物が好きです。", "example_cn": "我喜欢日本食物。"},
                {"word": "飲み物", "phonetic": "のみもの", "meaning": "饮料，喝的东西", "example": "何か飲み物はいりますか？", "example_cn": "需要喝点什么吗？"},
                {"word": "水", "phonetic": "みず", "meaning": "水", "example": "水をたくさん飲みます。", "example_cn": "喝很多水。"},
                {"word": "お茶", "phonetic": "おちゃ", "meaning": "茶", "example": "毎日お茶を飲みます。", "example_cn": "每天喝茶。"},
                {"word": "牛乳", "phonetic": "ぎゅうにゅう", "meaning": "牛奶", "example": "牛乳が好きです。", "example_cn": "我喜欢牛奶。"},
                {"word": "果物", "phonetic": "くだもの", "meaning": "水果", "example": "果物を毎日食べます。", "example_cn": "每天都吃水果。"},
                {"word": "りんご", "phonetic": "りんご", "meaning": "苹果", "example": "りんごを一つ食べます。", "example_cn": "吃一个苹果。"},
                {"word": "家", "phonetic": "いえ / うち", "meaning": "房屋，家", "example": "私の家は小さいです。", "example_cn": "我家很小。"},
                {"word": "部屋", "phonetic": "へや", "meaning": "房间", "example": "部屋を片付けなさい。", "example_cn": "把房间收拾一下。"},
                {"word": "机", "phonetic": "つくえ", "meaning": "桌子，书桌", "example": "机の上に本があります。", "example_cn": "桌子上有书。"},
                {"word": "椅子", "phonetic": "いす", "meaning": "椅子", "example": "その椅子に座ってください。", "example_cn": "请坐在那张椅子上。"},
                {"word": "戸", "phonetic": "と", "meaning": "门（多指日本式门）", "example": "戸を閉めてください。", "example_cn": "请把门关上。"},
                {"word": "窓", "phonetic": "まど", "meaning": "窗户", "example": "暑いから窓を開けてください。", "example_cn": "太热了，请打开窗户。"},
            ]},
            "n4": {"name": "JLPT N4", "words": [
                {"word": "約束", "phonetic": "やくそく", "meaning": "约定，诺言", "example": "約束を守ってください。", "example_cn": "请遵守约定。"},
                {"word": "学生", "phonetic": "がくせい", "meaning": "学生", "example": "私は大学生です。", "example_cn": "我是大学生。"},
                {"word": "行く", "phonetic": "いく", "meaning": "v. 去，走", "example": "学校へ行きます。", "example_cn": "我去学校。"},
                {"word": "来る", "phonetic": "くる", "meaning": "v. 来，到来", "example": "友達が家に来ます。", "example_cn": "朋友来家里。"},
                {"word": "帰る", "phonetic": "かえる", "meaning": "v. 回去，回来，回家", "example": "5時に家へ帰ります。", "example_cn": "5点回家。"},
                {"word": "食べる", "phonetic": "たべる", "meaning": "v. 吃", "example": "朝ごはんを食べます。", "example_cn": "吃早饭。"},
                {"word": "飲む", "phonetic": "のむ", "meaning": "v. 喝，饮", "example": "水を飲みます。", "example_cn": "喝水。"},
                {"word": "見る", "phonetic": "みる", "meaning": "v. 看，观看；查看", "example": "テレビを見ます。", "example_cn": "看电视。"},
                {"word": "聞く", "phonetic": "きく", "meaning": "v. 听；问，打听", "example": "音楽を聞きます。", "example_cn": "听音乐。"},
                {"word": "読む", "phonetic": "よむ", "meaning": "v. 读，阅读", "example": "本を読みます。", "example_cn": "看书。"},
                {"word": "書く", "phonetic": "かく", "meaning": "v. 写，书写", "example": "手紙を書きます。", "example_cn": "写信。"},
                {"word": "話す", "phonetic": "はなす", "meaning": "v. 说，讲；说话", "example": "日本語を話します。", "example_cn": "我讲日语。"},
                {"word": "買う", "phonetic": "かう", "meaning": "v. 买，购买", "example": "本屋で本を買います。", "example_cn": "在书店买书。"},
                {"word": "作る", "phonetic": "つくる", "meaning": "v. 做，制作；创造", "example": "料理を作ります。", "example_cn": "做饭做菜。"},
                {"word": "使う", "phonetic": "つかう", "meaning": "v. 使用，用", "example": "パソコンを使います。", "example_cn": "使用电脑。"},
                {"word": "分かる", "phonetic": "わかる", "meaning": "v. 明白，懂；知道", "example": "日本語が分かります。", "example_cn": "我懂日语。"},
                {"word": "知る", "phonetic": "しる", "meaning": "v. 知道，了解", "example": "そのニュースを知っています。", "example_cn": "我知道那个消息。"},
                {"word": "思う", "phonetic": "おもう", "meaning": "v. 想，思考；认为", "example": "そう思います。", "example_cn": "我也这么想。"},
                {"word": "言う", "phonetic": "いう", "meaning": "v. 说，讲；叫做", "example": "何と言いましたか？", "example_cn": "你说了什么？"},
                {"word": "出る", "phonetic": "でる", "meaning": "v. 出去，出来；出现", "example": "家を出ます。", "example_cn": "出门。"},
                {"word": "入る", "phonetic": "はいる", "meaning": "v. 进入，进去", "example": "部屋に入ります。", "example_cn": "进入房间。"},
                {"word": "開ける", "phonetic": "あける", "meaning": "v. 开，打开", "example": "ドアを開けます。", "example_cn": "把门打开。"},
                {"word": "閉める", "phonetic": "しめる", "meaning": "v. 关，关闭", "example": "窓を閉めます。", "example_cn": "把窗户关上。"},
                {"word": "つける", "phonetic": "つける", "meaning": "v. 打开（电器）；安装", "example": "電気をつけます。", "example_cn": "开灯。"},
                {"word": "消す", "phonetic": "けす", "meaning": "v. 关掉；擦掉；删除", "example": "ライトを消してください。", "example_cn": "请把灯关掉。"},
                {"word": "立つ", "phonetic": "たつ", "meaning": "v. 站，站立", "example": "ここに立ってください。", "example_cn": "请站在这里。"},
                {"word": "座る", "phonetic": "すわる", "meaning": "v. 坐，坐下", "example": "椅子に座ります。", "example_cn": "坐在椅子上。"},
                {"word": "寝る", "phonetic": "ねる", "meaning": "v. 睡觉，就寝", "example": "夜11時に寝ます。", "example_cn": "晚上11点睡觉。"},
                {"word": "起きる", "phonetic": "おきる", "meaning": "v. 起床；醒", "example": "朝6時に起きます。", "example_cn": "早上6点起床。"},
                {"word": "働く", "phonetic": "はたらく", "meaning": "v. 工作，劳动", "example": "会社で働いています。", "example_cn": "在公司工作。"},
                {"word": "休む", "phonetic": "やすむ", "meaning": "v. 休息；请假", "example": "日曜日は休みます。", "example_cn": "周日休息。"},
                {"word": "勉強する", "phonetic": "べんきょうする", "meaning": "v.suru 学习，用功", "example": "毎日日本語を勉強します。", "example_cn": "每天学习日语。"},
                {"word": "便利", "phonetic": "べんり", "meaning": "adj.na 方便，便利", "example": "この辺りはとても便利です。", "example_cn": "这一带非常方便。"},
                {"word": "静か", "phonetic": "しずか", "meaning": "adj.na 安静，宁静", "example": "静かな図書館。", "example_cn": "安静的图书馆。"},
                {"word": "にぎやか", "phonetic": "にぎやか", "meaning": "adj.na 热闹，繁华", "example": "にぎやかな通り。", "example_cn": "热闹的街道。"},
                {"word": "大丈夫", "phonetic": "だいじょうぶ", "meaning": "adj.na 不要紧；没关系", "example": "大丈夫ですか？", "example_cn": "你不要紧吧？"},
                {"word": "病気", "phonetic": "びょうき", "meaning": "n. 生病，疾病", "example": "病気で学校を休みました。", "example_cn": "因为生病没去上学。"},
            ]},
            "n5": {"name": "JLPT N5", "words": [
                {"word": "学生", "phonetic": "がくせい", "meaning": "n. 学生", "example": "私は学生です。", "example_cn": "我是学生。"},
                {"word": "先生", "phonetic": "せんせい", "meaning": "n. 老师；先生", "example": "田中先生は日本人です。", "example_cn": "田中老师是日本人。"},
                {"word": "友達", "phonetic": "ともだち", "meaning": "n. 朋友", "example": "彼は私の友達です。", "example_cn": "他是我的朋友。"},
                {"word": "家族", "phonetic": "かぞく", "meaning": "n. 家人，家庭", "example": "家族は何人ですか？", "example_cn": "你家有几口人？"},
                {"word": "学校", "phonetic": "がっこう", "meaning": "n. 学校", "example": "学校は8時からです。", "example_cn": "学校8点开始上课。"},
                {"word": "会社", "phonetic": "かいしゃ", "meaning": "n. 公司", "example": "父は会社員です。", "example_cn": "父亲是公司职员。"},
                {"word": "本", "phonetic": "ほん", "meaning": "n. 书，书籍", "example": "これは私の本です。", "example_cn": "这是我的书。"},
                {"word": "手紙", "phonetic": "てがみ", "meaning": "n. 信，书信", "example": "母に手紙を書きます。", "example_cn": "给妈妈写信。"},
                {"word": "鉛筆", "phonetic": "えんぴつ", "meaning": "n. 铅笔", "example": "鉛筆を持っていますか？", "example_cn": "你带铅笔了吗？"},
                {"word": "時計", "phonetic": "とけい", "meaning": "n. 钟表；手表", "example": "この時計は新しいです。", "example_cn": "这块表是新的。"},
                {"word": "車", "phonetic": "くるま", "meaning": "n. 汽车，车", "example": "車を持っています。", "example_cn": "我有车。"},
                {"word": "自転車", "phonetic": "じてんしゃ", "meaning": "n. 自行车", "example": "自転車で行きます。", "example_cn": "骑自行车去。"},
                {"word": "電車", "phonetic": "でんしゃ", "meaning": "n. 电车", "example": "電車で学校へ行きます。", "example_cn": "坐电车去学校。"},
                {"word": "駅", "phonetic": "えき", "meaning": "n. 车站", "example": "駅はどこですか？", "example_cn": "车站在哪里？"},
                {"word": "家", "phonetic": "いえ / うち", "meaning": "n. 房屋，家", "example": "家は駅の近くです。", "example_cn": "我家在车站附近。"},
                {"word": "部屋", "phonetic": "へや", "meaning": "n. 房间", "example": "部屋はきれいです。", "example_cn": "房间很干净。"},
                {"word": "机", "phonetic": "つくえ", "meaning": "n. 桌子，书桌", "example": "机の上に本があります。", "example_cn": "桌子上有书。"},
                {"word": "椅子", "phonetic": "いす", "meaning": "n. 椅子", "example": "椅子がありますか？", "example_cn": "有椅子吗？"},
                {"word": "窓", "phonetic": "まど", "meaning": "n. 窗户", "example": "窓を開けてください。", "example_cn": "请打开窗户。"},
                {"word": "ドア", "phonetic": "どあ", "meaning": "n. 门（door）", "example": "ドアを閉めます。", "example_cn": "关门。"},
                {"word": "今日", "phonetic": "きょう", "meaning": "n. 今天", "example": "今日は月曜日です。", "example_cn": "今天是星期一。"},
                {"word": "明日", "phonetic": "あした", "meaning": "n. 明天", "example": "明日また来ます。", "example_cn": "明天再来。"},
                {"word": "昨日", "phonetic": "きのう", "meaning": "n. 昨天", "example": "昨日は何をしましたか？", "example_cn": "昨天做了什么？"},
                {"word": "時間", "phonetic": "じかん", "meaning": "n. 时间", "example": "時間がありません。", "example_cn": "没有时间。"},
                {"word": "今", "phonetic": "いま", "meaning": "n./adv. 现在，此刻", "example": "今何時ですか？", "example_cn": "现在几点？"},
                {"word": "朝", "phonetic": "あさ", "meaning": "n. 早晨，早上", "example": "朝6時に起きます。", "example_cn": "早上6点起床。"},
                {"word": "晩", "phonetic": "ばん", "meaning": "n. 晚上，傍晚", "example": "晩ご飯を食べます。", "example_cn": "吃晚饭。"},
                {"word": "毎日", "phonetic": "まいにち", "meaning": "n. 每天，每日", "example": "毎日勉強します。", "example_cn": "每天学习。"},
                {"word": "先週", "phonetic": "せんしゅう", "meaning": "n. 上周，上星期", "example": "先週日本へ行きました。", "example_cn": "上周去了日本。"},
                {"word": "来週", "phonetic": "らいしゅう", "meaning": "n. 下周，下星期", "example": "来週テストがあります。", "example_cn": "下周有考试。"},
                {"word": "月曜日", "phonetic": "げつようび", "meaning": "n. 星期一", "example": "月曜日から金曜日まで仕事です。", "example_cn": "从周一到周五上班。"},
                {"word": "日曜日", "phonetic": "にちようび", "meaning": "n. 星期日", "example": "日曜日は休みです。", "example_cn": "周日休息。"},
            ]},
        }
    },
    "chinese": {
        "name": "中文", "flag": "🇨🇳",
        "books": {
            "chengyu": {"name": "成语词典", "words": [
                {"word": "画龙点睛", "phonetic": "huà lóng diǎn jīng", "meaning": "比喻在关键处点明实质，使内容生动有力", "example": "这篇文章结尾真是画龙点睛。", "example_cn": ""},
                {"word": "一心一意", "phonetic": "yī xīn yī yì", "meaning": "只有一个心眼，没有别的考虑", "example": "做事要一心一意才能成功。", "example_cn": ""},
                {"word": "三心二意", "phonetic": "sān xīn èr yì", "meaning": "又想这样又想那样，犹豫不决，不专心", "example": "学习不能三心二意。", "example_cn": ""},
                {"word": "守株待兔", "phonetic": "shǒu zhū dài tù", "meaning": "比喻不主动努力，存侥幸心理，希望得到意外成功", "example": "成功靠努力，不能守株待兔。", "example_cn": ""},
                {"word": "刻舟求剑", "phonetic": "kè zhōu qiú jiàn", "meaning": "比喻办事刻板拘泥，不知根据实际情况变通", "example": "时代在变，不能刻舟求剑。", "example_cn": ""},
                {"word": "掩耳盗铃", "phonetic": "yǎn ěr dào líng", "meaning": "比喻自己欺骗自己，明明掩盖不住的事情偏要想法掩盖", "example": "这样做简直是掩耳盗铃。", "example_cn": ""},
                {"word": "亡羊补牢", "phonetic": "wáng yáng bǔ láo", "meaning": "出了问题以后想办法补救，可以防止继续受损失", "example": "现在改正还来得及，亡羊补牢嘛。", "example_cn": ""},
                {"word": "愚公移山", "phonetic": "yú gōng yí shān", "meaning": "比喻坚持不懈地改造自然和坚定不移地进行斗争", "example": "只要有愚公移山的精神，就一定能成功。", "example_cn": ""},
                {"word": "叶公好龙", "phonetic": "yè gōng hào lóng", "meaning": "比喻口头上说爱好某事物，实际上并不真爱好", "example": "他不过是叶公好龙罢了。", "example_cn": ""},
                {"word": "杯弓蛇影", "phonetic": "bēi gōng shé yǐng", "meaning": "比喻疑神疑鬼，自相惊扰，虚惊一场", "example": "你别杯弓蛇影，自己吓自己。", "example_cn": ""},
                {"word": "狐假虎威", "phonetic": "hú jiǎ hǔ wēi", "meaning": "比喻依仗别人的势力欺压人", "example": "他不过是狐假虎威罢了。", "example_cn": ""},
                {"word": "井底之蛙", "phonetic": "jǐng dǐ zhī wā", "meaning": "比喻见识短浅的人", "example": "不能做井底之蛙，要开阔眼界。", "example_cn": ""},
                {"word": "对牛弹琴", "phonetic": "duì niú tán qín", "meaning": "比喻对不懂道理的人讲道理，对外行人说内行话", "example": "跟他说这些，简直是对牛弹琴。", "example_cn": ""},
                {"word": "画蛇添足", "phonetic": "huà shé tiān zú", "meaning": "比喻做了多余的事，反而不恰当，弄巧成拙", "example": "这段话加上去反而画蛇添足了。", "example_cn": ""},
                {"word": "胸有成竹", "phonetic": "xiōng yǒu chéng zhú", "meaning": "在做事之前已有通盘的考虑和打算", "example": "他胸有成竹地走上讲台。", "example_cn": ""},
                {"word": "一举两得", "phonetic": "yī jǔ liǎng dé", "meaning": "做一件事得到两方面的好处", "example": "这样做可以一举两得。", "example_cn": ""},
                {"word": "马到成功", "phonetic": "mǎ dào chéng gōng", "meaning": "形容事情顺利，一开始就取得成功", "example": "祝你马到成功！", "example_cn": ""},
                {"word": "风和日丽", "phonetic": "fēng hé rì lì", "meaning": "形容天气晴朗暖和（多用于春天）", "example": "今天风和日丽，适合出游。", "example_cn": ""},
                {"word": "风调雨顺", "phonetic": "fēng tiáo yǔ shùn", "meaning": "风雨适合农时，形容年成好", "example": "今年风调雨顺，五谷丰登。", "example_cn": ""},
                {"word": "和颜悦色", "phonetic": "hé yán yuè sè", "meaning": "形容态度和蔼可亲，脸色和霭喜悦", "example": "老师总是和颜悦色地对待我们。", "example_cn": ""},
                {"word": "自强不息", "phonetic": "zì qiáng bù xī", "meaning": "自觉地努力向上，永不松懈", "example": "中华民族自强不息的精神值得学习。", "example_cn": ""},
                {"word": "废寝忘食", "phonetic": "fèi qǐn wàng shí", "meaning": "顾不得睡觉，忘记了吃饭，形容专心努力", "example": "为了考试，他废寝忘食地学习。", "example_cn": ""},
                {"word": "百折不挠", "phonetic": "bǎi zhé bù náo", "meaning": "比喻意志坚强，无论受到多少次挫折，毫不动摇退缩", "example": "他百折不挠地攻克了一道道难关。", "example_cn": ""},
                {"word": "实事求是", "phonetic": "shí shì qiú shì", "meaning": "按照实际情况办事，不夸大也不缩小", "example": "我们要实事求是地看待问题。", "example_cn": ""},
                {"word": "一丝不苟", "phonetic": "yī sī bù gǒu", "meaning": "形容做事认真细致，一点儿也不马虎", "example": "他做事总是一丝不苟。", "example_cn": ""},
                {"word": "雪中送炭", "phonetic": "xuě zhōng sòng tàn", "meaning": "比喻在别人急需时给以物质上或精神上的帮助", "example": "你的帮助真是雪中送炭。", "example_cn": ""},
                {"word": "锦上添花", "phonetic": "jǐn shàng tiān huā", "meaning": "比喻好上加好，美上添美", "example": "这次获奖，让他的事业锦上添花。", "example_cn": ""},
                {"word": "人山人海", "phonetic": "rén shān rén hǎi", "meaning": "形容聚集的人极多", "example": "国庆节的广场上人山人海。", "example_cn": ""},
                {"word": "车水马龙", "phonetic": "chē shuǐ mǎ lóng", "meaning": "形容来往车马很多，连续不断的热闹情景", "example": "大街上车水马龙，非常热闹。", "example_cn": ""},
                {"word": "眼花缭乱", "phonetic": "yǎn huā liáo luàn", "meaning": "看着复杂纷繁的东西而感到迷乱", "example": "商店里的商品让人眼花缭乱。", "example_cn": ""},
            ]},
            "gushi": {"name": "古诗词名句", "words": [
                {"word": "海内存知己", "phonetic": "hǎi nèi cún zhī jǐ", "meaning": "四海之内有知心朋友", "example": "海内存知己，天涯若比邻。——王勃《送杜少府之任蜀州》", "example_cn": ""},
                {"word": "床前明月光", "phonetic": "chuáng qián míng yuè guāng", "meaning": "明亮的月光洒在床前", "example": "床前明月光，疑是地上霜。——李白《静夜思》", "example_cn": ""},
                {"word": "举头望明月", "phonetic": "jǔ tóu wàng míng yuè", "meaning": "抬起头来看天上的明月", "example": "举头望明月，低头思故乡。——李白《静夜思》", "example_cn": ""},
                {"word": "白日依山尽", "phonetic": "bái rì yī shān jìn", "meaning": "夕阳依傍着西山慢慢地沉没", "example": "白日依山尽，黄河入海流。——王之涣《登鹳雀楼》", "example_cn": ""},
                {"word": "欲穷千里目", "phonetic": "yù qióng qiān lǐ mù", "meaning": "想要把千里的风光景物看够", "example": "欲穷千里目，更上一层楼。——王之涣《登鹳雀楼》", "example_cn": ""},
                {"word": "春眠不觉晓", "phonetic": "chūn mián bù jué xiǎo", "meaning": "春天睡眠很好不知不觉就亮了", "example": "春眠不觉晓，处处闻啼鸟。——孟浩然《春晓》", "example_cn": ""},
                {"word": "锄禾日当午", "phonetic": "chú hé rì dāng wǔ", "meaning": "盛夏中午烈日炎炎农民还在锄草", "example": "锄禾日当午，汗滴禾下土。——李绅《悯农》", "example_cn": ""},
                {"word": "谁知盘中餐", "phonetic": "shuí zhī pán zhōng cān", "meaning": "谁知道盘中的饭食", "example": "谁知盘中餐，粒粒皆辛苦。——李绅《悯农》", "example_cn": ""},
                {"word": "两个黄鹂鸣翠柳", "phonetic": "liǎng gè huáng lí míng cuì liǔ", "meaning": "两只黄鹂在翠绿的柳枝间鸣叫", "example": "两个黄鹂鸣翠柳，一行白鹭上青天。——杜甫《绝句》", "example_cn": ""},
                {"word": "窗含西岭千秋雪", "phonetic": "chuāng hán xī lǐng qiān qiū xuě", "meaning": "窗户中可以望见西岭上千年不化的积雪", "example": "窗含西岭千秋雪，门泊东吴万里船。——杜甫《绝句》", "example_cn": ""},
                {"word": "千山鸟飞绝", "phonetic": "qiān shān niǎo fēi jué", "meaning": "所有的山上都看不到飞鸟的影子", "example": "千山鸟飞绝，万径人踪灭。——柳宗元《江雪》", "example_cn": ""},
                {"word": "独钓寒江雪", "phonetic": "dú diào hán jiāng xuě", "meaning": "独自在寒冷的江面上垂钓", "example": "孤舟蓑笠翁，独钓寒江雪。——柳宗元《江雪》", "example_cn": ""},
                {"word": "日照香炉生紫烟", "phonetic": "rì zhào xiāng lú shēng zǐ yān", "meaning": "阳光照在香炉峰上生起紫色烟霞", "example": "日照香炉生紫烟，遥看瀑布挂前川。——李白《望庐山瀑布》", "example_cn": ""},
                {"word": "飞流直下三千尺", "phonetic": "fēi liú zhí xià sān qiān chǐ", "meaning": "瀑布飞流直下仿佛有三千尺长", "example": "飞流直下三千尺，疑是银河落九天。——李白《望庐山瀑布》", "example_cn": ""},
                {"word": "朝辞白帝彩云间", "phonetic": "zhāo cí bái dì cǎi yún jiān", "meaning": "清晨告别白云之间的白帝城", "example": "朝辞白帝彩云间，千里江陵一日还。——李白《早发白帝城》", "example_cn": ""},
                {"word": "两岸猿声啼不住", "phonetic": "liǎng àn yuán shēng tí bù zhù", "meaning": "两岸猿猴的啼声还在耳边不停地回响", "example": "两岸猿声啼不住，轻舟已过万重山。——李白《早发白帝城》", "example_cn": ""},
                {"word": "好雨知时节", "phonetic": "hǎo yǔ zhī shí jié", "meaning": "好雨知道下雨的节气", "example": "好雨知时节，当春乃发生。——杜甫《春夜喜雨》", "example_cn": ""},
                {"word": "随风潜入夜", "phonetic": "suí fēng qián rù yè", "meaning": "春雨随着春风在夜里悄悄地落下", "example": "随风潜入夜，润物细无声。——杜甫《春夜喜雨》", "example_cn": ""},
                {"word": "会当凌绝顶", "phonetic": "huì dāng líng jué dǐng", "meaning": "一定要登上泰山的最高峰", "example": "会当凌绝顶，一览众山小。——杜甫《望岳》", "example_cn": ""},
                {"word": "国破山河在", "phonetic": "guó pò shān hé zài", "meaning": "国都沦陷但山河依旧存在", "example": "国破山河在，城春草木深。——杜甫《春望》", "example_cn": ""},
                {"word": "但愿人长久", "phonetic": "dàn yuàn rén cháng jiǔ", "meaning": "只希望人们都能长久平安", "example": "但愿人长久，千里共婵娟。——苏轼《水调歌头》", "example_cn": ""},
                {"word": "明月几时有", "phonetic": "míng yuè jǐ shí yǒu", "meaning": "明月是什么时候才有的呢", "example": "明月几时有？把酒问青天。——苏轼《水调歌头》", "example_cn": ""},
                {"word": "大江东去", "phonetic": "dà jiāng dōng qù", "meaning": "长江向东流去", "example": "大江东去，浪淘尽，千古风流人物。——苏轼《念奴娇·赤壁怀古》", "example_cn": ""},
                {"word": "人生自古谁无死", "phonetic": "rén shēng zì gǔ shuí wú sǐ", "meaning": "人生自古以来有谁能够长生不死", "example": "人生自古谁无死，留取丹心照汗青。——文天祥《过零丁洋》", "example_cn": ""},
                {"word": "落红不是无情物", "phonetic": "luò hóng bù shì wú qíng wù", "meaning": "从枝头上掉下来的落花不是无情之物", "example": "落红不是无情物，化作春泥更护花。——龚自珍《己亥杂诗》", "example_cn": ""},
                {"word": "天生我材必有用", "phonetic": "tiān shēng wǒ cái bì yǒu yòng", "meaning": "天生我这样的人才必然是有用处的", "example": "天生我材必有用，千金散尽还复来。——李白《将进酒》", "example_cn": ""},
                {"word": "读书破万卷", "phonetic": "dú shū pò wàn juàn", "meaning": "读书读透了上万卷书", "example": "读书破万卷，下笔如有神。——杜甫《奉赠韦左丞丈二十二韵》", "example_cn": ""},
                {"word": "路漫漫其修远兮", "phonetic": "lù màn màn qí xiū yuǎn xī", "meaning": "前面的道路啊又远又长", "example": "路漫漫其修远兮，吾将上下而求索。——屈原《离骚》", "example_cn": ""},
                {"word": "采菊东篱下", "phonetic": "cǎi jú dōng lí xià", "meaning": "在东篱边采摘菊花", "example": "采菊东篱下，悠然见南山。——陶渊明《饮酒》", "example_cn": ""},
                {"word": "夕阳无限好", "phonetic": "xī yáng wú xiàn hǎo", "meaning": "夕阳的景色无限美好", "example": "夕阳无限好，只是近黄昏。——李商隐《登乐游原》", "example_cn": ""},
            ]},
        }
    },
}

# ==================== 远程扩充词库（启动时拉取，失败用内置词库兜底） ====================
# 词库来源清单维护在仓库 wordbank_sources.txt（以后更新词库只改该文件，无需动代码）：
#   json <url>  —— 明文 JSON 词库（兼容旧的 zlib+base64 封装）
#   b64  <url>  —— gzip+base64 分片，按行序拼接解码为一个 JSON 词库
# 英语词条/音标/释义来自 ECDICT（MIT 开源词典）；例句来自 tatoeba.org（CC-BY 2.0 FR），
# 例句中文翻译 = Tatoeba 中文句对 + 人工补译。单个来源失败不影响其它。
SOURCES_URL = "https://raw.githubusercontent.com/serenashenn3-art/kindle-display-render/main/wordbank_sources.txt"
EMBEDDED_SOURCES = """
b64 https://paste.rs/t0bf6
b64 https://paste.rs/0eDn4
b64 https://paste.rs/SPLv7
b64 https://paste.rs/snbCE
b64 https://paste.rs/AOLoA
b64 https://paste.rs/2yk36
b64 https://paste.rs/6jkIk
b64 https://paste.rs/YrbkB
b64 https://paste.rs/DJbOT
b64 https://paste.rs/n89yG
b64 https://paste.rs/xcQ77
b64 https://paste.rs/7RE56
b64 https://paste.rs/PZk77
b64 https://paste.rs/92aZU
b64 https://paste.rs/Y9q5s
b64 https://paste.rs/yEJTN
b64 https://paste.rs/r4asO
b64 https://paste.rs/uOxAG
b64 https://paste.rs/hooxd
b64 https://paste.rs/xRziw
b64 https://paste.rs/Rkcnt
b64 https://paste.rs/Vjcue
b64 https://paste.rs/AXUFq
b64 https://paste.rs/Au8XV
b64 https://paste.rs/kmXqM
b64 https://paste.rs/K9Yzd
b64 https://paste.rs/OnOxD
b64 https://paste.rs/9Z7nf
b64 https://paste.rs/2gjIJ
b64 https://paste.rs/Gdoco
b64 https://paste.rs/c0XCS
b64 https://paste.rs/Nt8pg
b64 https://paste.rs/mMQka
b64 https://paste.rs/T4S70
b64 https://paste.rs/kWxCa
b64 https://paste.rs/vbwRh
b64 https://paste.rs/atMce
b64 https://paste.rs/564A5
b64 https://paste.rs/e3jCz
b64 https://paste.rs/nZesA
b64 https://paste.rs/U9Dmu
b64 https://paste.rs/miA0B
b64 https://paste.rs/vno7A
b64 https://paste.rs/aYzkX
b64 https://paste.rs/CNDUq
b64 https://paste.rs/LunXJ
b64 https://paste.rs/hnWrh
b64 https://paste.rs/dg6LF
b64 https://paste.rs/vjExF
b64 https://paste.rs/UKzxr
b64 https://paste.rs/6XILc
b64 https://paste.rs/gmEkC
b64 https://paste.rs/JFpOS
b64 https://paste.rs/y4m40
"""

def _merge_bank(data):
    n = 0
    for lang, lpack in (data or {}).items():
        if lang == "meta" or lang not in WORD_BANK or not isinstance(lpack, dict):
            continue
        for bk, pack in lpack.items():
            words = pack.get("words") if isinstance(pack, dict) else pack
            if bk in WORD_BANK[lang]["books"] and words:
                WORD_BANK[lang]["books"][bk]["words"] = [
                    {"word": w["w"], "phonetic": w.get("p", ""), "meaning": w.get("m", ""),
                     "example": w.get("e", ""), "example_cn": w.get("c", "")}
                    for w in words]
                if isinstance(pack, dict) and pack.get("name"):
                    WORD_BANK[lang]["books"][bk]["name"] = pack["name"]
                n += len(words)
    return n

def _parse_bank_payload(raw):
    for algo in ("gzip", "zlib", "plain"):
        try:
            if algo == "gzip":
                return json.loads(gzip.decompress(base64.b64decode(raw)).decode("utf-8"))
            if algo == "zlib":
                return json.loads(zlib.decompress(base64.b64decode(raw)).decode("utf-8"))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            continue
    return None

def load_remote_bank():
    try:
        src = requests.get(SOURCES_URL, timeout=8).text
        if "json" not in src and "b64" not in src:
            src = EMBEDDED_SOURCES
    except Exception:
        src = EMBEDDED_SOURCES
    json_urls, b64_urls = [], []
    for line in src.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        kind, url = parts
        if kind == "json":
            json_urls.append(url)
        elif kind == "b64":
            b64_urls.append(url)
    total = 0
    for url in json_urls:
        try:
            data = _parse_bank_payload(requests.get(url, timeout=15).content)
            if data:
                total += _merge_bank(data)
                print(f"[wordbank] merged {url}")
        except Exception as exc:
            print(f"[wordbank] fetch failed {url}: {exc}")
    if b64_urls:
        try:
            blob = "".join(requests.get(u, timeout=15).text for u in b64_urls)
            data = json.loads(gzip.decompress(base64.b64decode(blob)).decode("utf-8"))
            total += _merge_bank(data)
            print(f"[wordbank] merged {len(b64_urls)} b64 shards")
        except Exception as exc:
            print(f"[wordbank] b64 shards failed: {exc}")
    print(f"[wordbank] total remote words: {total}")
    return total > 100

try:
    load_remote_bank()
except Exception:
    pass

# ==================== 天气 API ====================
CITY_COORDS = {
    "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
    "guangzhou": (23.1291, 113.2644), "shenzhen": (22.5431, 114.0579),
    "chengdu": (30.5728, 104.0668), "hangzhou": (30.2741, 120.1551),
    "wuhan": (30.5928, 114.3055), "xian": (34.3416, 108.9398),
    "nanjing": (32.0603, 118.7969), "chongqing": (29.5630, 106.5516),
    "tianjin": (39.0842, 117.2009), "suzhou": (31.2989, 120.5853),
    "tokyo": (35.6762, 139.6503), "newyork": (40.7128, -74.0060),
    "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
}

CITY_TZ = {
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "guangzhou": "Asia/Shanghai", "shenzhen": "Asia/Shanghai",
    "chengdu": "Asia/Shanghai", "hangzhou": "Asia/Shanghai",
    "wuhan": "Asia/Shanghai", "xian": "Asia/Shanghai",
    "nanjing": "Asia/Shanghai", "chongqing": "Asia/Shanghai",
    "tianjin": "Asia/Shanghai", "suzhou": "Asia/Shanghai",
    "tokyo": "Asia/Tokyo", "newyork": "America/New_York",
    "london": "Europe/London", "paris": "Europe/Paris",
}
DEFAULT_TZ = "Asia/Shanghai"

WEATHER_CODES = {
    0: "晴", 1: "多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "小雨", 55: "中雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "阵雨", 82: "暴雨",
    95: "雷雨", 96: "雷雨伴冰雹", 99: "雷雨伴冰雹",
}

def get_weather(city_key):
    if city_key not in CITY_COORDS:
        return {"temp": "--", "weather": "未知", "city": city_key}
    lat, lon = CITY_COORDS[city_key]
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,weather_code")
        r = requests.get(url, timeout=5)
        data = r.json()
        cur = data.get("current") or {}
        if "temperature_2m" in cur:
            temp = cur["temperature_2m"]
            code = cur.get("weather_code", 0)
            return {"temp": f"{int(temp)}°C", "weather": WEATHER_CODES.get(code, "多云"), "city": city_key.capitalize()}
        raise ValueError("unexpected response shape")
    except Exception:
        try:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   f"&current_weather=true")
            r = requests.get(url, timeout=5)
            data = r.json()
            cw = data.get("current_weather") or {}
            if "temperature" in cw:
                temp = cw["temperature"]
                code = cw.get("weathercode", 0)
                return {"temp": f"{int(temp)}°C", "weather": WEATHER_CODES.get(code, "多云"), "city": city_key.capitalize()}
        except Exception:
            pass
        return {"temp": "--°C", "weather": "获取失败", "city": city_key.capitalize()}


# ==================== 刷新策略选择器（各模式默认不同） ====================
REFRESH_OPTIONS = [
    ("5", "5 秒（极速轮播）"),
    ("10", "10 秒（番茄钟推荐）"),
    ("15", "15 秒"),
    ("30", "30 秒（相框推荐）"),
    ("60", "1 分钟（时钟推荐）"),
    ("180", "3 分钟"),
    ("300", "5 分钟（看板/单词推荐）"),
    ("600", "10 分钟"),
    ("1800", "30 分钟"),
    ("3600", "1 小时"),
    ("0", "不自动刷新（纯静态）"),
]

def build_refresh_select(default_value="300"):
    options = ""
    for val, label in REFRESH_OPTIONS:
        selected = "selected" if val == default_value else ""
        options += f'<option value="{val}" {selected}>{label}</option>\n'
    return f"""
    <label>刷新策略</label>
    <select name="interval">
        {options}
    </select>
    <p class="hint">「不自动刷新」适合固定展示，Kindle 按刷新键手动更新</p>
    """

# ==================== 看板/阅读 数据计算（生成与永久链接渲染共用） ====================
def compute_events(events_raw):
    events = []
    for er in events_raw:
        if "|" in er:
            name, date_str = er.split("|", 1)
            try:
                target = datetime.strptime(date_str.strip(), "%Y-%m-%d")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                delta = (target - today).days
                if delta < 0:
                    events.append({"name": name.strip(), "days": "已过去"})
                elif delta == 0:
                    events.append({"name": name.strip(), "days": "就是今天！"})
                else:
                    events.append({"name": name.strip(), "days": f"还有 {delta} 天"})
            except Exception:
                events.append({"name": name.strip(), "days": "日期格式错误"})
    return events

def compute_habits(habits):
    habits_out = []
    for i, h in enumerate(habits):
        pct = ((i * 37 + datetime.now().day * 13) % 100)
        habits_out.append({"name": h, "pct": pct})
    return habits_out

def compute_books(books_raw):
    books = []
    for br in books_raw:
        if "|" in br:
            parts = br.split("|")
            if len(parts) >= 3:
                try:
                    cur, tot = int(parts[1].strip()), int(parts[2].strip())
                    pct = min(100, max(0, int(cur / tot * 100)))
                    books.append({"name": parts[0].strip(), "current": cur, "total": tot, "pct": pct})
                except Exception:
                    pass
    return books

# ==================== 永久链接（配置压缩编码进 URL，重启不过期） ====================
def encode_cfg(tc):
    raw = json.dumps(tc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")

def decode_cfg(token):
    pad = "=" * (-len(token) % 4)
    raw = zlib.decompress(base64.urlsafe_b64decode(token + pad))
    return json.loads(raw.decode("utf-8"))

def expand_token_cfg(tc):
    """把 URL 里的紧凑配置还原成渲染用的完整配置"""
    m = tc.get("m")
    if m not in ("info", "board", "reading", "pomodoro", "words"):
        raise ValueError("unknown mode")
    cfg = {"mode": m, "model": tc.get("md", "pw4"), "interval": int(tc.get("i", 300))}
    if m == "info":
        cfg["city"] = tc.get("c", "beijing")
    elif m == "board":
        cfg["todos"] = tc.get("t", [])
        cfg["events"] = compute_events(tc.get("e", []))
        cfg["habits"] = compute_habits(tc.get("hb", []))
    elif m == "reading":
        cfg["books"] = compute_books(tc.get("bk", []))
    elif m == "pomodoro":
        cfg["duration"] = int(tc.get("d", 25))
        cfg["task_name"] = tc.get("t", "专注中") or "专注中"
        cfg["start_time"] = tc.get("s") or datetime.now().isoformat()
    elif m == "words":
        lang = tc.get("l", "english")
        book = tc.get("b", "cet4")
        book_info = WORD_BANK.get(lang, {}).get("books", {}).get(book, {})
        words = book_info.get("words", [])
        cfg.update({
            "language": lang,
            "book": book,
            "words": words,
            "total": len(words),
            "book_name": book_info.get("name", ""),
            "lang_flag": WORD_BANK.get(lang, {}).get("flag", "🇺🇸"),
            "show_phonetic": bool(tc.get("sp", 1)),
            "show_meaning": bool(tc.get("sm", 1)),
            "show_progress": bool(tc.get("sg", 1)),
        })
    return cfg

# ==================== 配置页面（纯链接切换，零 JavaScript，兼容 Kindle 老浏览器） ====================
MODE_DEFS = [
    ("info", "📊", "信息面板"),
    ("board", "📋", "个人看板"),
    ("frame", "🖼", "电子相框"),
    ("reading", "📚", "阅读进度"),
    ("pomodoro", "🍅", "番茄钟"),
    ("words", "🔤", "单词卡片"),
]

CONFIG_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kindle 展示中心</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f6fa; padding:16px; max-width:560px; margin:0 auto; color:#1a1a1a; }
.header { text-align:center; padding:24px 0 12px; }
.header h1 { font-size:24px; margin-bottom:6px; }
.header p { color:#666; font-size:14px; }
.mode-grid { margin:16px 0; }
.mode-card { display:inline-block; width:31%; margin:0 1% 10px 0; vertical-align:top; background:#fff; border:2px solid #e5e5e5; border-radius:14px; padding:16px 8px; text-align:center; text-decoration:none; color:#1a1a1a; }
.mode-card:hover { border-color:#999; }
.mode-card.active { border-color:#1a1a1a; background:#1a1a1a; color:#fff; }
.mode-card .icon { font-size:28px; margin-bottom:6px; display:block; }
.mode-card .title { font-size:13px; font-weight:600; }
.card { background:#fff; border-radius:14px; padding:20px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
.card h2 { font-size:15px; font-weight:600; margin-bottom:14px; color:#333; }
label { display:block; margin-bottom:6px; font-size:14px; color:#444; font-weight:500; }
input[type="text"], input[type="number"], input[type="date"], textarea, select {
    width:100%; padding:12px; border:1.5px solid #e5e5e5; border-radius:10px; font-size:15px; margin-bottom:12px; background:#fafafa;
}
textarea { min-height:80px; resize:vertical; font-family:inherit; }
.hint { font-size:12px; color:#999; margin-top:-8px; margin-bottom:12px; }
.btn { width:100%; padding:16px; background:#1a1a1a; color:#fff; border:none; border-radius:14px; font-size:16px; font-weight:600; cursor:pointer; margin-top:8px; }
.tip { font-size:13px; color:#666; margin-top:16px; line-height:1.7; background:#fff; padding:16px; border-radius:14px; }
.tip code { background:#f0f0f0; padding:2px 6px; border-radius:4px; font-family:monospace; }
.checkbox-row { margin-bottom:10px; }
.checkbox-row input { width:20px; height:20px; accent-color:#1a1a1a; vertical-align:middle; }
.checkbox-row span { vertical-align:middle; }
.file-input { padding:10px; border:2px dashed #ddd; border-radius:10px; text-align:center; margin-bottom:12px; }
.chip { display:inline-block; padding:8px 12px; border:1.5px solid #e5e5e5; border-radius:20px; margin:0 6px 8px 0; font-size:14px; color:#1a1a1a; text-decoration:none; background:#fafafa; }
.chip.active { background:#1a1a1a; color:#fff; border-color:#1a1a1a; }
</style>
</head>
<body>

<div class="header">
    <h1>📖 Kindle 展示中心</h1>
    <p>6 种展示模式 · 刷新策略自由选 · 零越狱</p>
</div>

<div class="mode-grid">
    {% for key, icon, title in modes %}
    <a class="mode-card{% if key == mode %} active{% endif %}" href="/?mode={{ key }}">
        <span class="icon">{{ icon }}</span>
        <span class="title">{{ title }}</span>
    </a>
    {% endfor %}
</div>

<form action="/generate" method="POST" enctype="multipart/form-data">
    <input type="hidden" name="mode" value="{{ mode }}">

    <div class="card">
        <h2>通用设置</h2>
        <label>Kindle 型号</label>
        <select name="model">
            <option value="pw4" selected>Paperwhite 第10代 (758×1024)</option>
            <option value="pw5">Paperwhite 第11代 (1236×1648)</option>
            <option value="pw3">Paperwhite 第7代及以前 (758×1024)</option>
            <option value="basic11">Kindle 基础版 第11代 (758×1024)</option>
            <option value="basic">Kindle 基础版 第10代及以前 (600×800)</option>
            <option value="oasis">Oasis 第9/10代 (1264×1680)</option>
            <option value="scribe">Scribe (1860×2480)</option>
        </select>
    </div>

    {% if mode == "info" %}
    <div class="card">
        <h2>📊 信息面板设置</h2>
        <label>城市</label>
        <select name="city">
            <option value="beijing">北京</option>
            <option value="shanghai">上海</option>
            <option value="guangzhou">广州</option>
            <option value="shenzhen">深圳</option>
            <option value="chengdu">成都</option>
            <option value="hangzhou">杭州</option>
            <option value="wuhan">武汉</option>
            <option value="xian">西安</option>
            <option value="nanjing">南京</option>
            <option value="chongqing">重庆</option>
            <option value="tianjin">天津</option>
            <option value="suzhou">苏州</option>
            <option value="tokyo">东京</option>
            <option value="newyork">纽约</option>
            <option value="london">伦敦</option>
            <option value="paris">巴黎</option>
        </select>
        """ + build_refresh_select("60") + """
    </div>
    {% endif %}

    {% if mode == "board" %}
    <div class="card">
        <h2>📋 个人看板设置</h2>
        <label>待办事项（每行一个）</label>
        <textarea name="todos" placeholder="完成报告&#10;预约牙医&#10;买牛奶"></textarea>
        <label>纪念日（格式：名称|日期，每行一个）</label>
        <textarea name="events" placeholder="结婚纪念日|2025-05-20&#10;生日|1995-08-15"></textarea>
        <p class="hint">日期格式：YYYY-MM-DD，自动计算剩余天数</p>
        <label>习惯打卡（每行一个）</label>
        <textarea name="habits" placeholder="早起&#10;阅读30分钟&#10;运动"></textarea>
        """ + build_refresh_select("300") + """
    </div>
    {% endif %}

    {% if mode == "frame" %}
    <div class="card">
        <h2>🖼 电子相框设置</h2>
        <label>上传照片（可多张，建议 3-10 张）</label>
        <input type="file" name="photos" multiple accept="image/*" class="file-input">
        <p class="hint">后端自动转为 E-ink 灰度高对比度图片（建议在手机上配置上传）</p>
        """ + build_refresh_select("30") + """
    </div>
    {% endif %}

    {% if mode == "reading" %}
    <div class="card">
        <h2>📚 阅读进度设置</h2>
        <label>书籍信息（格式：书名|当前页|总页数，每行一本）</label>
        <textarea name="books" placeholder="三体|280|400&#10;百年孤独|120|360&#10;人类简史|45|300"></textarea>
        <p class="hint">自动计算阅读百分比并渲染进度条</p>
        """ + build_refresh_select("300") + """
    </div>
    {% endif %}

    {% if mode == "pomodoro" %}
    <div class="card">
        <h2>🍅 番茄钟设置</h2>
        <label>专注时长（分钟）</label>
        <input type="number" name="duration" value="25" min="1" max="120">
        <label>任务名称</label>
        <input type="text" name="task_name" placeholder="例如：写论文、背单词">
        <label>倒计时刷新精度</label>
        <select name="interval">
            <option value="1">1 秒（高精度，Kindle 刷新频繁）</option>
            <option value="5">5 秒</option>
            <option value="10" selected>10 秒（推荐平衡）</option>
            <option value="30">30 秒</option>
            <option value="60">1 分钟</option>
            <option value="0">不自动刷新（需手动按刷新键）</option>
        </select>
        <p class="hint">E-ink 屏幕刷新有闪烁，10 秒是精度与体验的平衡</p>
    </div>
    {% endif %}

    {% if mode == "words" %}
    <div class="card">
        <h2>🔤 单词卡片设置</h2>
        <label>语种（点击切换，页面会刷新）</label>
        <div class="chip-row">
            {% for k, v in wordbank.items() %}
            <a class="chip{% if k == lang %} active{% endif %}" href="/?mode=words&lang={{ k }}">{{ v.flag }} {{ v.name }}</a>
            {% endfor %}
        </div>
        <input type="hidden" name="language" value="{{ lang }}">
        <label>词书</label>
        <select name="book">
            {% for bk, bv in books.items() %}
            <option value="{{ bk }}">{{ bv.name }}</option>
            {% endfor %}
        </select>
        <label>显示内容</label>
        <div class="checkbox-row"><input type="checkbox" name="show_phonetic" checked> <span>音标/发音</span></div>
        <div class="checkbox-row"><input type="checkbox" name="show_meaning" checked> <span>释义</span></div>
        <div class="checkbox-row"><input type="checkbox" name="show_progress" checked> <span>进度</span></div>
        <p class="hint">例句和中文翻译始终显示</p>
        """ + build_refresh_select("300") + """
    </div>
    {% endif %}

    <button type="submit" class="btn">生成 Kindle 展示链接</button>
</form>

<div class="tip">
    <strong>📌 Kindle 使用步骤：</strong><br>
    1. 连接 WiFi → 打开「体验版浏览器」<br>
    2. 输入生成的链接地址<br>
    3. 在搜索框输入 <code>~ds</code> 并按回车（禁止锁屏）<br>
    4. 插上电源，即可长期展示
</div>

</body>
</html>
"""

# ==================== Kindle 展示模板 ====================
# vh = 可视区域高度（屏幕高 - 浏览器工具栏），用于垂直居中

TMPL_INFO = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Info</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; }
.time { font-size:{{ t_time }}px; font-weight:bold; margin-bottom:10px; letter-spacing:2px; }
.date { font-size:{{ t_date }}px; color:#333; margin-bottom:30px; }
.divider { width:60px; height:2px; background:#000; margin:20px auto; }
.weather-row { font-size:{{ t_body }}px; }
.weather-item { display:inline-block; text-align:center; margin:0 18px; }
.weather-label { font-size:{{ t_small }}px; color:#666; margin-bottom:4px; }
.city { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#777; border:1px solid #999; padding:4px 10px; border-radius:12px; }
.footer { position:absolute; bottom:{{ pad }}px; left:0; right:0; text-align:center; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; left:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="city">{{ city }}</div>
<div class="vc"><div class="vc-cell">
<div class="time">{{ time }}</div>
<div class="date">{{ date }}</div>
<div class="divider"></div>
<div class="weather-row">
    <div class="weather-item"><div class="weather-label">天气</div><div>{{ weather }}</div></div>
    <div class="weather-item"><div class="weather-label">温度</div><div>{{ temp }}</div></div>
</div>
</div></div>
<div class="footer">Kindle Info Panel</div>
</body></html>
"""

TMPL_BOARD = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Board</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; padding:{{ pad }}px; overflow:hidden; position:relative; }
h1 { font-size:{{ t_title }}px; margin-bottom:16px; border-bottom:2px solid #000; padding-bottom:8px; }
.section { margin-bottom:20px; }
.section-title { font-size:{{ t_sub }}px; font-weight:bold; margin-bottom:8px; color:#333; }
.todo-item, .event-item, .habit-item { font-size:{{ t_body }}px; margin-bottom:6px; line-height:1.4; }
.event-days { color:#d32f2f; font-weight:bold; }
.habit-bar { width:100%; height:8px; background:#eee; border-radius:4px; margin-top:4px; overflow:hidden; }
.habit-fill { height:100%; background:#000; border-radius:4px; }
.footer { position:absolute; bottom:{{ pad }}px; left:{{ pad }}px; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<h1>📋 今日看板</h1>
{% if todos %}
<div class="section">
    <div class="section-title">待办事项</div>
    {% for t in todos %}<div class="todo-item">• {{ t }}</div>{% endfor %}
</div>
{% endif %}
{% if events %}
<div class="section">
    <div class="section-title">纪念日</div>
    {% for e in events %}<div class="event-item">{{ e.name }} — <span class="event-days">{{ e.days }}</span></div>{% endfor %}
</div>
{% endif %}
{% if habits %}
<div class="section">
    <div class="section-title">习惯打卡</div>
    {% for h in habits %}
    <div class="habit-item">{{ h.name }}<div class="habit-bar"><div class="habit-fill" style="width:{{ h.pct }}%"></div></div></div>
    {% endfor %}
</div>
{% endif %}
<div class="footer">Kindle Board</div>
</body></html>
"""

TMPL_FRAME = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }};url={{ next_url }}">{% endif %}
<title>Kindle Frame</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#000; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; }
img { max-width:100%; max-height:{{ vh }}px; filter:contrast(1.2); }
.counter { position:absolute; bottom:20px; right:20px; font-size:14px; color:#fff;
    background:rgba(0,0,0,0.5); padding:4px 10px; border-radius:10px; font-family:Arial; }
{% if interval == 0 %}.static-badge { position:absolute; top:20px; left:20px; font-size:12px; color:#fff; background:rgba(0,0,0,0.5); padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="vc"><div class="vc-cell"><img src="{{ img_url }}" alt="frame"></div></div>
<div class="counter">{{ cur }} / {{ total }}</div>
</body></html>
"""

TMPL_READING = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Reading</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; padding:{{ pad }}px; overflow:hidden; position:relative; }
h1 { font-size:{{ t_title }}px; margin-bottom:20px; border-bottom:2px solid #000; padding-bottom:8px; }
.book { margin-bottom:18px; }
.book-name { font-size:{{ t_sub }}px; font-weight:bold; margin-bottom:6px; }
.book-meta { font-size:{{ t_body }}px; color:#333; margin-bottom:4px; }
.progress-bg { width:100%; height:10px; background:#eee; border-radius:5px; overflow:hidden; }
.progress-fill { height:100%; background:#000; border-radius:5px; }
.footer { position:absolute; bottom:{{ pad }}px; left:{{ pad }}px; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<h1>📚 阅读进度</h1>
{% for b in books %}
<div class="book">
    <div class="book-name">{{ b.name }}</div>
    <div class="book-meta">{{ b.current }} / {{ b.total }} 页 · {{ b.pct }}%</div>
    <div class="progress-bg"><div class="progress-fill" style="width:{{ b.pct }}%"></div></div>
</div>
{% endfor %}
<div class="footer">Kindle Reading</div>
</body></html>
"""

TMPL_POMO = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Pomodoro</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; }
.task { font-size:{{ t_sub }}px; color:#555; margin:0 auto 20px; text-align:center; max-width:80%; }
.time-left { font-size:{{ t_time }}px; font-weight:bold; margin-bottom:16px; letter-spacing:2px; }
.progress-bg { width:70%; height:14px; background:#eee; border-radius:7px; overflow:hidden; margin:0 auto 10px; }
.progress-fill { height:100%; background:#000; border-radius:7px; }
.pct { font-size:{{ t_body }}px; color:#666; }
.status { font-size:{{ t_sub }}px; margin-top:20px; font-weight:bold; }
.footer { position:absolute; bottom:{{ pad }}px; left:0; right:0; text-align:center; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad }}px; right:{{ pad }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="vc"><div class="vc-cell">
<div class="task">{{ task }}</div>
<div class="time-left">{{ time_left }}</div>
<div class="progress-bg"><div class="progress-fill" style="width:{{ pct }}%"></div></div>
<div class="pct">{{ pct }}%</div>
<div class="status">{{ status }}</div>
</div></div>
<div class="footer">Kindle Pomodoro</div>
</body></html>
"""

TMPL_WORDS = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
{% if interval > 0 %}<meta http-equiv="refresh" content="{{ interval }}">{% endif %}
<title>Kindle Word</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { width:{{ w }}px; height:{{ vh }}px; background:#fff; color:#000;
    font-family:"Georgia","Times New Roman",serif; overflow:hidden; position:relative; }
.vc { display:table; width:100%; height:100%; }
.vc-cell { display:table-cell; vertical-align:middle; text-align:center; padding:0 {{ pad }}px; }
.lang-tag { position:absolute; top:{{ pad_s }}px; right:{{ pad_s }}px; font-size:{{ t_small }}px; color:#555; border:1px solid #999; padding:3px 10px; border-radius:12px; font-family:Arial; }
.book-tag { position:absolute; top:{{ pad_s }}px; left:{{ pad_s }}px; font-size:{{ t_small }}px; color:#777; font-family:Arial; }
.word { font-size:{{ t_word }}px; font-weight:bold; margin-bottom:10px; text-align:center; line-height:1.2; }
.phonetic { font-size:{{ t_sub }}px; color:#333; margin-bottom:18px; font-family:Arial; }
.divider { width:50px; height:2px; background:#000; margin:14px auto; }
.meaning { font-size:{{ t_body }}px; margin:0 auto 14px; text-align:center; line-height:1.5; }
.example { font-size:{{ t_small2 }}px; color:#333; font-style:italic; text-align:center; line-height:1.5; margin:0 auto 6px; max-width:85%; }
.example-cn { font-size:{{ t_small }}px; color:#555; text-align:center; line-height:1.5; margin:0 auto; max-width:85%; }
.progress { position:absolute; bottom:{{ pad_s }}px; left:0; right:0; text-align:center; font-size:{{ t_small }}px; color:#555; font-family:Arial; }
.footer-line { position:absolute; bottom:{{ pad_s }}px; left:{{ pad_s }}px; font-size:{{ t_small }}px; color:#999; }
{% if interval == 0 %}.static-badge { position:absolute; top:{{ pad_s }}px; right:{{ pad_s }}px; font-size:{{ t_small }}px; color:#999; border:1px solid #ccc; padding:3px 8px; border-radius:8px; }{% endif %}
</style></head>
<body>
{% if interval == 0 %}<div class="static-badge">静态模式</div>{% endif %}
<div class="book-tag">{{ book_name }}</div>
<div class="lang-tag">{{ lang_flag }}</div>
<div class="vc"><div class="vc-cell">
<div class="word">{{ word }}</div>
{% if show_phonetic %}<div class="phonetic">{{ phonetic }}</div>{% endif %}
<div class="divider"></div>
{% if show_meaning %}<div class="meaning">{{ meaning }}</div>{% endif %}
{% if example %}<div class="example">{{ example }}</div>{% endif %}
{% if example_cn %}<div class="example-cn">{{ example_cn }}</div>{% endif %}
</div></div>
{% if show_progress %}<div class="progress">{{ current }} / {{ total }}</div>{% endif %}
<div class="footer-line">Kindle Word</div>
</body></html>
"""


# ==================== 路由 ====================

@app.route("/")
def index():
    mode = request.args.get("mode", "info")
    valid_modes = {k for k, _, _ in MODE_DEFS}
    if mode not in valid_modes:
        mode = "info"
    lang = request.args.get("lang", "english")
    if lang not in WORD_BANK:
        lang = "english"
    return render_template_string(CONFIG_HTML,
        modes=MODE_DEFS,
        mode=mode,
        lang=lang,
        wordbank=WORD_BANK,
        books=WORD_BANK[lang]["books"])


@app.route("/generate", methods=["POST"])
def generate():
    mode = request.form.get("mode", "info")
    model_key = request.form.get("model", "pw4")
    model = MODELS.get(model_key, MODELS["pw4"])
    cfg_id = str(uuid.uuid4())[:6]

    interval = int(request.form.get("interval", 300))

    base_cfg = {
        "mode": mode,
        "model": model_key,
        "interval": interval,
        "w": model["w"],
        "h": model["h"],
    }
    # 永久链接用的紧凑配置（编码进 URL，不依赖服务器内存）
    token_cfg = {"m": mode, "md": model_key, "i": interval}

    if mode == "info":
        city = request.form.get("city", "beijing")
        base_cfg.update({"city": city})
        token_cfg.update({"c": city})

    elif mode == "board":
        todos = [t.strip() for t in request.form.get("todos", "").split("\n") if t.strip()]
        events_raw = [e.strip() for e in request.form.get("events", "").split("\n") if e.strip()]
        habits = [h.strip() for h in request.form.get("habits", "").split("\n") if h.strip()]
        base_cfg.update({
            "todos": todos,
            "events": compute_events(events_raw),
            "habits": compute_habits(habits),
        })
        token_cfg.update({"t": todos, "e": events_raw, "hb": habits})

    elif mode == "frame":
        files = request.files.getlist("photos")
        processed = []
        for f in files:
            if f and f.filename:
                uid = str(uuid.uuid4())[:8]
                ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
                save_name = f"{cfg_id}_{uid}{ext}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], save_name)
                img = Image.open(f.stream)
                img = img.convert("L")
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.4)
                img.thumbnail((model["w"], model["h"]), Image.LANCZOS)
                img.save(save_path, "JPEG", quality=90)
                processed.append(save_name)
        base_cfg.update({"photos": processed, "photo_count": len(processed)})

    elif mode == "reading":
        books_raw = [b.strip() for b in request.form.get("books", "").split("\n") if b.strip()]
        base_cfg.update({"books": compute_books(books_raw)})
        token_cfg.update({"bk": books_raw})

    elif mode == "pomodoro":
        duration = int(request.form.get("duration", 25))
        task_name = request.form.get("task_name", "专注中") or "专注中"
        start_time = datetime.now().isoformat()
        base_cfg.update({
            "duration": duration,
            "task_name": task_name,
            "start_time": start_time,
        })
        token_cfg.update({"d": duration, "t": task_name, "s": start_time})

    elif mode == "words":
        lang = request.form.get("language", "english")
        book = request.form.get("book", "cet4")
        words = WORD_BANK.get(lang, {}).get("books", {}).get(book, {}).get("words", [])
        base_cfg.update({
            "language": lang,
            "book": book,
            "words": words,
            "total": len(words),
            "book_name": WORD_BANK.get(lang, {}).get("books", {}).get(book, {}).get("name", ""),
            "lang_flag": WORD_BANK.get(lang, {}).get("flag", "🇺🇸"),
            "show_phonetic": "show_phonetic" in request.form,
            "show_meaning": "show_meaning" in request.form,
            "show_progress": "show_progress" in request.form,
        })
        token_cfg.update({
            "l": lang, "b": book,
            "sp": 1 if "show_phonetic" in request.form else 0,
            "sm": 1 if "show_meaning" in request.form else 0,
            "sg": 1 if "show_progress" in request.form else 0,
        })

    USER_CONFIGS[cfg_id] = base_cfg

    show_url = f"{request.host_url}s/{cfg_id}"

    # 永久链接：配置编码进 URL，服务器重启/重新部署也不过期
    # 相框模式除外（照片文件存在服务器磁盘，重启必然丢失）
    perm_block = ""
    if mode != "frame":
        perm_url = f"{request.host_url}p/{encode_cfg(token_cfg)}"
        perm_block = f"""
            <p class="short-label">♾ 永久链接（重启也不过期，推荐 Kindle 输入这个并加书签）：</p>
            <div class="url-box short">{perm_url}</div>"""
    else:
        perm_block = """
            <p class="short-label" style="color:#b71c1c;">⚠ 相框照片存在服务器内存，服务重启后需重新上传生成</p>"""

    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>配置完成</title>
        <style>
            body {{ font-family:-apple-system,sans-serif; padding:20px; max-width:520px; margin:0 auto; background:#f5f6fa; }}
            .card {{ background:#fff; border-radius:16px; padding:24px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
            h1 {{ font-size:20px; margin-bottom:8px; }}
            .subtitle {{ color:#666; font-size:14px; margin-bottom:20px; }}
            .url-box {{ background:#f5f5f5; padding:14px; border-radius:10px; font-family:monospace; font-size:13px; word-break:break-all; border:1px dashed #999; margin:12px 0; }}
            .btn {{ display:block; width:100%; padding:14px; background:#1a1a1a; color:#fff; text-align:center; border-radius:12px; text-decoration:none; margin-top:10px; font-size:15px; }}
            .tip {{ font-size:13px; color:#555; margin-top:16px; line-height:1.7; }}
            .tip code {{ background:#f0f0f0; padding:2px 6px; border-radius:4px; font-family:monospace; }}
            .success {{ color:#4caf50; font-weight:600; margin-bottom:8px; }}
            .badge {{ display:inline-block; background:#1a1a1a; color:#fff; padding:4px 10px; border-radius:8px; font-size:12px; margin-right:6px; }}
            .short-label {{ color:#2e7d32; font-size:14px; font-weight:600; margin-top:6px; }}
            .url-box.short {{ font-size:16px; text-align:center; border:2px solid #4caf50; background:#e8f5e9; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="success">✅ 配置生成成功</div>
            <h1>你的专属 Kindle 展示链接</h1>
            <p class="subtitle">
                <span class="badge">{mode}</span>
                <span class="badge">{model['name']}</span>
                <span class="badge">刷新: {interval if interval > 0 else '静态'}</span>
            </p>
            {perm_block}
            <p class="short-label" style="color:#666; font-weight:400;">临时短链接（服务重启后失效）：</p>
            <div class="url-box">{show_url}</div>
            <a href="{show_url}" class="btn" target="_blank">点击预览效果</a>
            <div class="tip">
                <strong>Kindle 使用步骤：</strong><br>
                1. 连接 WiFi → 打开「体验版浏览器」<br>
                2. 输入上方链接（建议添加到书签）<br>
                3. 在搜索框输入 <code>~ds</code> 并按回车（禁止锁屏）<br>
                4. 插上电源，长期展示即可
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/show")
def show():
    return render_display(request.args.get("id"))


@app.route("/s/<cfg_id>")
def show_short(cfg_id):
    return render_display(cfg_id)


@app.route("/p/<token>")
def show_perm(token):
    try:
        cfg = expand_token_cfg(decode_cfg(token))
    except Exception:
        return "链接无效或已损坏", 400
    return render_cfg(cfg)


def render_display(cfg_id):
    if not cfg_id or cfg_id not in USER_CONFIGS:
        return "配置不存在", 404
    cfg = dict(USER_CONFIGS[cfg_id])
    cfg["_cfg_id"] = cfg_id
    return render_cfg(cfg)


def render_cfg(cfg):
    mode = cfg["mode"]
    m = MODELS.get(cfg.get("model", "pw4"), MODELS["pw4"])
    w, h = m["w"], m["h"]
    vh = h - m.get("chrome", 90)  # 可视区域高度 = 屏幕高 - 浏览器工具栏
    if m["w"] <= 600:
        pad = 36
    elif m["w"] <= 758:
        pad = 48
    elif m["w"] <= 1264:
        pad = 64
    else:
        pad = 96
    interval = cfg.get("interval", 300)

    if mode == "info":
        city_key = cfg.get("city", "beijing")
        try:
            tz = ZoneInfo(CITY_TZ.get(city_key, DEFAULT_TZ))
        except Exception:
            tz = None
        now = datetime.now(tz) if tz else datetime.now()
        weather = get_weather(city_key)
        return render_template_string(TMPL_INFO,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_time=int(h*0.12), t_date=int(h*0.045), t_body=int(h*0.035), t_small=int(h*0.022),
            time=now.strftime("%H:%M"),
            date=now.strftime("%Y年%m月%d日 %a"),
            city=weather["city"],
            weather=weather["weather"],
            temp=weather["temp"])

    elif mode == "board":
        return render_template_string(TMPL_BOARD,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_title=int(h*0.05), t_sub=int(h*0.032), t_body=int(h*0.026), t_small=int(h*0.02),
            todos=cfg.get("todos", []),
            events=cfg.get("events", []),
            habits=cfg.get("habits", []))

    elif mode == "frame":
        photos = cfg.get("photos", [])
        if not photos:
            return "没有上传图片", 400
        idx = int(request.args.get("idx", 0)) % len(photos)
        next_idx = (idx + 1) % len(photos)
        img_url = f"{request.host_url}uploads/{photos[idx]}"
        next_url = f"{request.host_url}s/{cfg.get('_cfg_id', '')}?idx={next_idx}"
        return render_template_string(TMPL_FRAME,
            interval=interval,
            w=w, h=h, vh=vh,
            img_url=img_url,
            next_url=next_url,
            cur=idx+1, total=len(photos))

    elif mode == "reading":
        return render_template_string(TMPL_READING,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_title=int(h*0.05), t_sub=int(h*0.032), t_body=int(h*0.026), t_small=int(h*0.02),
            books=cfg.get("books", []))

    elif mode == "pomodoro":
        start = datetime.fromisoformat(cfg["start_time"])
        duration_min = cfg["duration"]
        total_sec = duration_min * 60
        elapsed = (datetime.now() - start).total_seconds()
        remaining = total_sec - elapsed

        if remaining <= 0:
            time_left = "00:00"
            pct = 100
            status = "✅ 专注完成！"
        else:
            mins, secs = divmod(int(remaining), 60)
            time_left = f"{mins:02d}:{secs:02d}"
            pct = min(100, int((elapsed / total_sec) * 100))
            status = "🔔 专注中..."

        return render_template_string(TMPL_POMO,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad,
            t_time=int(h*0.14), t_sub=int(h*0.04), t_body=int(h*0.03), t_small=int(h*0.022),
            task=cfg.get("task_name", "专注中"),
            time_left=time_left,
            pct=pct,
            status=status)

    elif mode == "words":
        words = cfg.get("words", [])
        if not words:
            return "词书为空", 400
        idx = random.randint(0, len(words) - 1)
        wdata = words[idx]
        return render_template_string(TMPL_WORDS,
            interval=interval,
            w=w, h=h, vh=vh, pad=pad, pad_s=int(pad*0.5),
            t_word=int(h*0.09), t_sub=int(h*0.035), t_body=int(h*0.03), t_small=int(h*0.022), t_small2=int(h*0.025),
            word=wdata["word"],
            phonetic=wdata.get("phonetic", ""),
            meaning=wdata.get("meaning", ""),
            example=wdata.get("example", ""),
            example_cn=wdata.get("example_cn", ""),
            book_name=cfg.get("book_name", ""),
            lang_flag=cfg.get("lang_flag", "🇺🇸"),
            show_phonetic=cfg.get("show_phonetic", True),
            show_meaning=cfg.get("show_meaning", True),
            show_progress=cfg.get("show_progress", True),
            current=idx+1,
            total=cfg.get("total", 1))

    return "未知模式", 400


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
