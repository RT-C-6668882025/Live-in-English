# 一分钱学英语 / Learn English for one cent

> "Everything is possible in the AI era."

**Why pay $50/hr for a human tutor when you can debate with the distilled minds of Nobel Laureates for pennies?**

---

## 💡 Core Philosophy

- **API is all you need.** No bloated backends, just raw, unfiltered intelligence.
- **Atomic Cost.** ~¥0.5 per session. A cup of coffee buys you a month of fluency.
- **Dissolution over Solutions.** We don't provide answers; we dissolve problems. English is not a subject to study—it is the medium you inhabit.

---

## 🛠️ The "Fundamental Logic"

Human time is limited; AI never sleeps. In this space, language barriers don't just break—they vanish into your logic.

**Don't learn English. Live in it.**

---

## ✨ Features

### 🎭 Multi-Expert Chatroom
Debate with historical figures, philosophers, scientists, and thinkers:
- **Feynman** - Break down complex concepts into simple terms
- **Einstein** - Thought experiments and imagination
- **Kahneman** - Cognitive bias detection and System 1/2 thinking
- **And more...**

### 🎯 IELTS Evaluation
- Writing assessment with band scoring
- Speaking evaluation with pronunciation analysis
- Short input expansion with structural layering
- Detailed feedback and improvement suggestions

### 🗣️ AI-Powered Conversation Practice
- Real-time dialogue with AI examiners
- Speech-to-text integration
- Text-to-speech with natural voices
- Pronunciation analysis via Azure Speech Services

### 🤖 Multi-Model Support
Bring your own API key:
- **DeepSeek** (Chat / Reasoner)
- **OpenAI** (GPT-4 / GPT-4o / GPT-3.5)
- **Anthropic** (Claude 3 Opus / Sonnet / Haiku)
- **Google** (Gemini 2.5 Pro / Flash)

### ⚡ Layered Model Config
- Configure different models for different sections
- Per-section API key support
- Priority: Layered config > Global config

---

## 🚀 Quick Start

### One-Click Launch (Windows)
```bash
双击 IELTS-Evaluator.bat
```

### Manual Setup
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
# Open frontend/index.html in browser
# Or serve with: python -m http.server 3000
```

---

## ⚙️ Configuration

1. Click **Settings** (top-right)
2. Select your AI model
3. Enter your API key
4. Test connection
5. Start learning English for one cent

---

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /evaluate` | IELTS writing/speaking assessment |
| `POST /practice/chat` | AI examiner conversation |
| `POST /chatroom/discuss` | Multi-expert discussion |
| `POST /chatroom/followup` | Follow-up discussion |
| `POST /tts` | Text-to-speech |
| `POST /analyze-pronunciation` | Azure Speech pronunciation analysis |

---

## 💰 Cost Breakdown

| Component | Cost per Session |
|-----------|-----------------|
| AI API (DeepSeek/OpenAI/etc) | ~¥0.3-0.8 |
| Azure Speech (optional) | Free tier: 5 hours/month |
| **Total** | **~¥0.5** |

Compare: Human tutor = $50/hour = ~¥360/hour

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│  AI APIs    │
│  (Vanilla)  │     │  (FastAPI)  │     │(DeepSeek/   │
└─────────────┘     └─────────────┘     │ OpenAI/etc) │
                                         └─────────────┘
```

**No database. No user accounts. No tracking.**
Just you, your API key, and infinite intelligence.

---

## 📝 License

Apache License 2.0

Copyright 2025 RT-C-6668882025

---

> *"The limits of my language mean the limits of my world."* — Ludwig Wittgenstein

**一分钱学英语。Learn English for one cent.**
