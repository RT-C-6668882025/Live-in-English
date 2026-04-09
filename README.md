# Live in English - 英语即日常

一个基于多AI模型（DeepSeek/OpenAI/Anthropic/Google）的英语口语练习与评估工具，提供专业的发音分析、AI对话练习，以及日常英语场景模拟功能。

## 功能特性

### 📝 核心评估功能

- ✍️ **写作评估 (Writing)**
  - Task Achievement/Response (TR)
  - Coherence & Cohesion (CC)
  - Lexical Resource (LR)
  - Grammatical Range & Accuracy (GRA)
  - 字数检测与短文本扩写模式

- 🎤 **口语评估 (Speaking)**
  - Fluency & Coherence (FC)
  - Lexical Resource (LR)
  - Grammatical Range & Accuracy (GRA)
  - Pronunciation (P)

- 📊 **详细反馈**
  - 四项评分标准单独打分
  - 致命错误分析
  - 改进建议
  - Band 8.0 版本示范
  - 总体评价

### 🗣️ Practice 练习模式

- **AI 考官对话**
  - 模拟雅思口语考试场景
  - 支持语音输入（Web Speech API）
  - AI 实时回应与追问

- **发音分析** (Azure Speech Integration)
  - 音素级评分 (Phoneme-level scoring)
  - 单词准确度颜色标注
  - 常见发音错误诊断（L/R不分、TH音等）
  - 音调曲线可视化 (Pitch contour)
  - 5小时/月免费额度

- **TTS 语音播放**
  - 支持 AI 回复语音朗读
  - 播放状态可视化（⏳ loading → ⏸ playing → ▶）
  - 可调节语速

### ⚙️ 多模型支持

支持以下 AI 提供商：
- **DeepSeek** (deepseek-chat, deepseek-reasoner)
- **OpenAI** (GPT-4, GPT-4o, GPT-3.5-turbo)
- **Anthropic** (Claude 3 Opus/Sonnet/Haiku)
- **Google** (Gemini 2.5 Pro/Flash, Gemini 1.5 Pro/Flash)

每个模型可独立配置 API Key，自动识别提供商。

## 项目结构

```
ielts-evaluator/
├── backend/
│   ├── main.py              # FastAPI 后端服务
│   ├── requirements.txt     # Python 依赖
│   └── simple_server.py     # 简化版后端（备用）
├── frontend/
│   └── index.html           # 前端界面（单页应用）
├── IELTS-Evaluator.bat      # Windows 一键启动脚本
├── start-backend.bat        # 启动后端
├── install-deps.bat         # 安装依赖
├── create-shortcut.ps1      # 创建桌面快捷方式
└── README.md                # 项目说明
```

## 快速开始

### 方式一：使用一键启动脚本（推荐）

Windows 用户双击 `IELTS-Evaluator.bat` 即可自动启动后端和前端。

### 方式二：手动启动

#### 1. 安装依赖

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 2. 启动后端服务

```bash
cd backend
python main.py
```

后端服务将在 `http://localhost:8000` 启动。

#### 3. 使用前端界面

直接在浏览器中打开 `frontend/index.html` 文件，或使用简单的 HTTP 服务器：

```bash
cd frontend
python -m http.server 3000
```

然后访问 `http://localhost:3000`。

## 配置说明

### API 配置

1. 点击右上角 "Settings" 按钮
2. 选择 AI 模型
3. 输入对应提供商的 API Key
4. 点击 "Test Connection" 测试连接
5. 保存配置

### Azure Speech 配置（可选，用于发音分析）

1. 进入 Practice 模式
2. 点击 "Azure: OFF" 按钮
3. 输入 Azure Speech Key 和 Region
4. 点击 Save，按钮变为 "Azure: ON"

获取 Azure Key: https://azure.microsoft.com/en-us/services/cognitive-services/speech-services/

## API 接口

### POST /evaluate

评估雅思写作或口语。

**请求体：**

```json
{
  "mode": "writing" | "speaking",
  "task_prompt": "题目（可选）",
  "response": "考生的回答内容",
  "word_count": 250,
  "api_config": {
    "api_key": "your-api-key",
    "model": "deepseek-chat"
  }
}
```

### POST /chat

AI 考官对话（Practice 模式）。

**请求体：**

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "api_config": {...}
}
```

### POST /analyze-pronunciation

发音分析（需要 Azure 配置）。

**请求体：**

```multipart/form-data
- audio: [音频文件]
- azure_key: [Azure Speech Key]
- azure_region: [Azure Region]
```

### POST /tts

文本转语音。

**请求体：**

```json
{
  "text": "要朗读的文本",
  "voice": "en-US-AriaNeural",
  "rate": "+0%"
}
```

## 使用说明

### Writing/Speaking 评估模式

1. 选择评估模式（Writing 或 Speaking）
2. 输入题目（可选，但建议提供以获得更准确的评估）
3. 粘贴你的作文或口语转录文本
4. 点击 "Evaluate My Response" 按钮
5. 查看详细的评估结果和改进建议

**字数检测功能：**
- 输入少于150词时，自动触发"扩写模式"
- AI 会帮你将短文本扩展为 Band 8.0 质量的完整文章

### Practice 练习模式

1. 选择 "Practice" 标签
2. 选择话题类型（Part 1/2/3）
3. 点击麦克风按钮开始录音，或输入文字
4. AI 考官会根据你的回答进行追问
5. 使用 Azure 发音分析获取详细的发音反馈

## 技术栈

- **后端**: FastAPI, Python 3.8+
- **前端**: HTML5, CSS3, Vanilla JavaScript
- **AI 模型**: DeepSeek, OpenAI, Anthropic, Google Gemini
- **语音**: Azure Speech SDK, Edge-TTS, Web Speech API
- **音频分析**: Parselmouth (Praat), OpenAI Whisper

## 系统要求

- Python 3.8+
- 现代浏览器（Chrome/Edge/Firefox/Safari）
- 麦克风（用于语音输入功能）

## 注意事项

- 需要有效的 AI API Key（DeepSeek/OpenAI/Anthropic/Google 之一）
- Azure Speech 功能需要额外的 Azure 订阅（有免费额度）
- 评估结果基于 AI 模型，仅供参考
- 建议结合官方评分标准使用

## License

Apache License 2.0

Copyright 2025 RT-C-6668882025
