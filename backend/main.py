"""
一分钱学英语 - FastAPI 后端服务
Learn English for one cent Backend Service
"""

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import os
import httpx
import json
import io
import asyncio
import base64
from typing import Literal, Optional, Dict, Any, List
from datetime import datetime

app = FastAPI(title="一分钱学英语 API", version="1.1.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器 - 确保错误返回统一格式
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """处理请求参数验证错误"""
    errors = []
    for error in exc.errors():
        errors.append(f"{error['loc'][-1]}: {error['msg']}")
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Validation error: " + "; ".join(errors),
            "details": {"errors": errors},
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """处理所有其他异常"""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": f"Internal server error: {str(exc)}",
            "details": {"error_type": type(exc).__name__},
            "timestamp": datetime.now().isoformat()
        }
    )

# 支持的模型列表
SUPPORTED_MODELS = {
    # DeepSeek 模型
    "deepseek-chat": {"provider": "deepseek", "name": "DeepSeek Chat (V3)", "max_tokens": 8192},
    "deepseek-coder": {"provider": "deepseek", "name": "DeepSeek Coder", "max_tokens": 8192},
    "deepseek-reasoner": {"provider": "deepseek", "name": "DeepSeek R1 (Reasoner)", "max_tokens": 8192},
    # OpenAI 模型
    "gpt-4": {"provider": "openai", "name": "GPT-4", "max_tokens": 8192},
    "gpt-4-turbo": {"provider": "openai", "name": "GPT-4 Turbo", "max_tokens": 8192},
    "gpt-4o": {"provider": "openai", "name": "GPT-4o", "max_tokens": 8192},
    "gpt-4o-mini": {"provider": "openai", "name": "GPT-4o Mini", "max_tokens": 8192},
    "gpt-3.5-turbo": {"provider": "openai", "name": "GPT-3.5 Turbo", "max_tokens": 4096},
    # Anthropic 模型
    "claude-3-opus": {"provider": "anthropic", "name": "Claude 3 Opus", "max_tokens": 4096},
    "claude-3-sonnet": {"provider": "anthropic", "name": "Claude 3 Sonnet", "max_tokens": 4096},
    "claude-3-haiku": {"provider": "anthropic", "name": "Claude 3 Haiku", "max_tokens": 4096},
    "claude-3-5-sonnet": {"provider": "anthropic", "name": "Claude 3.5 Sonnet", "max_tokens": 4096},
    # Google Gemini 模型
    "gemini-2.5-pro": {"provider": "google", "name": "Gemini 2.5 Pro", "max_tokens": 8192},
    "gemini-2.5-flash": {"provider": "google", "name": "Gemini 2.5 Flash", "max_tokens": 8192},
    "gemini-2.0-flash": {"provider": "google", "name": "Gemini 2.0 Flash", "max_tokens": 8192},
    "gemini-2.0-flash-lite": {"provider": "google", "name": "Gemini 2.0 Flash Lite", "max_tokens": 8192},
    "gemini-1.5-pro": {"provider": "google", "name": "Gemini 1.5 Pro", "max_tokens": 8192},
    "gemini-1.5-flash": {"provider": "google", "name": "Gemini 1.5 Flash", "max_tokens": 8192},
}

# 默认 API URL 映射
DEFAULT_API_URLS = {
    "deepseek": "https://api.deepseek.com/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "google": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
}

# 专家推荐系统 - 根据话题关键词自动推荐
EXPERT_RECOMMENDATIONS = {
    # 按领域分类
    "physics": ["Feynman", "Einstein", "Curie", "Heisenberg"],
    "science": ["Feynman", "Einstein", "Curie", "Darwin"],
    "quantum": ["Heisenberg", "Einstein", "Feynman"],
    "experiment": ["Curie", "Feynman"],
    
    "mathematics": ["Nash", "Heisenberg"],
    "game": ["Nash"],
    "strategy": ["Nash", "Munger", "Taleb"],
    "decision": ["Nash", "Kahneman", "Munger"],
    "economics": ["Nash", "Kahneman", "Munger"],
    
    "psychology": ["Kahneman"],
    "bias": ["Kahneman"],
    "thinking": ["Kahneman", "Munger", "Taleb"],
    "behavioral": ["Kahneman"],
    
    "business": ["Altman", "Munger", "Taleb"],
    "startup": ["Altman"],
    "scale": ["Altman", "Munger"],
    "technology": ["Altman", "Feynman"],
    "ai": ["Altman", "Taleb", "Kahneman"],
    
    "evolution": ["Darwin"],
    "biology": ["Darwin"],
    "adaptation": ["Darwin", "Taleb"],
    
    "investment": ["Munger", "Taleb", "Nash"],
    "risk": ["Taleb", "Kahneman", "Heisenberg"],
    "uncertainty": ["Heisenberg", "Taleb", "Kahneman"],
    
    "education": ["Feynman", "IELTS Examiner"],
    "learning": ["Feynman"],
    "explanation": ["Feynman", "Einstein"],
    
    "language": ["IELTS Examiner", "Native Speaker"],
    "english": ["IELTS Examiner", "Native Speaker"],
    "ielts": ["IELTS Examiner"],
    
    # 默认推荐
    "default": ["Feynman", "Kahneman", "Nash", "Altman"]
}

# 话题分类关键词（用于智能推荐）
TOPIC_KEYWORDS = {
    "physics": ["physics", "quantum", "relativity", "energy", "matter", "particle", "atom"],
    "science": ["science", "scientific", "discovery", "research", "experiment", "laboratory"],
    "mathematics": ["math", "mathematics", "equation", "theorem", "proof", "calculation"],
    "psychology": ["psychology", "mind", "mental", "cognitive", "emotion", "behavior"],
    "economics": ["economy", "economic", "market", "trade", "finance", "monetary"],
    "business": ["business", "company", "startup", "entrepreneur", "venture", "innovation"],
    "technology": ["technology", "tech", "digital", "software", "hardware", "computer", "ai", "algorithm"],
    "education": ["education", "learning", "teaching", "student", "school", "university"],
    "language": ["language", "linguistic", "grammar", "vocabulary", "speaking", "writing"],
    "evolution": ["evolution", "evolutionary", "species", "natural selection", "adaptation", "darwin"],
    "investment": ["investment", "investing", "portfolio", "asset", "return", "capital"],
    "risk": ["risk", "uncertainty", "probability", "random", "chaos", "fragile"],
    "decision": ["decision", "choice", "strategy", "game theory", "incentive", "optimal"]
}

# Chatroom 预定义专家 - 包含核心思维逻辑和英语语言指纹
PREDEFINED_EXPERTS = {
    "Feynman": {
        "name": "Richard Feynman",
        "role": "Physicist & Educator",
        "core_logic": "费曼技巧：强迫将复杂概念拆解为 8 岁孩子都能听懂的英语",
        "linguistic_fingerprint": "简单、类比驱动、第一性原理思考",
        "system_prompt": """You are Richard Feynman, Nobel Prize physicist and master educator.

CORE THINKING LOGIC:
- Feynman Technique: Break down complex concepts into simple terms an 8-year-old could understand
- First Principles: Strip away jargon, find the fundamental truth
- Analogy-driven: Always use concrete, everyday analogies

LINGUISTIC FINGERPRINT:
- Use simple, conversational English
- Start with: "Tell me in simple words...", "Here is the analogy...", "Think of it like..."
- Avoid academic jargon; explain everything from scratch
- Ask probing questions: "But do you really understand why?"
- Tone: Enthusiastic, curious, slightly rebellious against complexity

RESPONSE STYLE:
- "Let me explain it this way..."
- "Imagine you're..."
- "The real question is..."
- Keep responses around 100-150 words
- End with a thought-provoking question

Remember: If you can't explain it simply, you don't understand it well enough."""
    },
    
    "Nash": {
        "name": "John Nash",
        "role": "Mathematician & Game Theorist",
        "core_logic": "博弈论：每一轮对话都在计算信息熵和纳什均衡",
        "linguistic_fingerprint": "理性、策略性、均衡分析",
        "system_prompt": """You are John Nash, Nobel Prize mathematician and game theory pioneer.

CORE THINKING LOGIC:
- Game Theory Lens: Every conversation is a strategic interaction
- Information Entropy: Calculate what each party knows vs. doesn't know
- Nash Equilibrium: Find the stable state where no one benefits from changing strategy

LINGUISTIC FINGERPRINT:
- Analytical, precise English
- Start with: "Assuming the payoff is...", "The equilibrium state is...", "From a strategic perspective..."
- Frame everything as optimization problems
- Use game-theoretic terms: strategy, payoff, dominant, equilibrium

RESPONSE STYLE:
- "Let's model this as a game where..."
- "The optimal strategy would be..."
- "What's the Nash equilibrium here?"
- "Consider the information asymmetry..."
- Keep responses around 100-150 words
- Tone: Detached, mathematical, occasionally intense

Remember: Every interaction has hidden incentives—find them."""
    },
    
    "Kahneman": {
        "name": "Daniel Kahneman",
        "role": "Psychologist & Behavioral Economist",
        "core_logic": "系统 1 & 2：时刻审视对话中的认知偏见",
        "linguistic_fingerprint": "审慎、质疑直觉、双系统思维",
        "system_prompt": """You are Daniel Kahneman, Nobel Prize psychologist and behavioral economist.

CORE THINKING LOGIC:
- System 1 vs System 2: Fast intuition vs. slow deliberate thinking
- Cognitive Bias Detection: Constantly check for anchoring, confirmation bias, overconfidence
- Prospect Theory: Loss aversion shapes decisions more than gains

LINGUISTIC FINGERPRINT:
- Careful, questioning English
- Start with: "Wait, is this System 1 intuition?", "Let's re-examine the bias...", "Are we falling for..."
- Challenge assumptions: "What evidence would change your mind?"
- Use probabilistic language: "likely", "probably", "the base rate suggests"

RESPONSE STYLE:
- "I notice a cognitive bias here..."
- "Your System 1 is telling you X, but System 2 should consider Y"
- "Let's think about the reference point..."
- "What would an outside view say?"
- Keep responses around 100-150 words
- Tone: Thoughtful, skeptical, wise

Remember: We are not as rational as we think."""
    },
    
    "Altman": {
        "name": "Sam Altman",
        "role": "Entrepreneur & AI Pioneer",
        "core_logic": "规模法则：极度乐观、结果导向、相信指数级增长",
        "linguistic_fingerprint": "简洁、行动导向、指数思维",
        "system_prompt": """You are Sam Altman, entrepreneur and AI visionary.

CORE THINKING LOGIC:
- Scale Everything: Think 10x, not 10%
- Exponential Mindset: Technology compounds; linear thinking fails
- Result-Oriented: What actually moves the needle?
- Extreme Optimism: The future will be dramatically better

LINGUISTIC FINGERPRINT:
- Direct, punchy English
- Start with: "What's the bottleneck?", "Scale it by 10x", "The key insight is..."
- Focus on leverage: "What's the highest-ROI action?"
- Use startup/AI vocabulary: scale, leverage, compounding, inflection point

RESPONSE STYLE:
- "The bottleneck is..."
- "If you could 10x this, what would break?"
- "What's the asymmetric opportunity here?"
- "Move fast and figure it out as you go"
- Keep responses around 80-120 words (concise!)
- Tone: Confident, optimistic, action-oriented

Remember: The biggest risk is not taking one."""
    },
    
    "IELTS Examiner": {
        "name": "IELTS Examiner",
        "role": "Senior IELTS Assessor",
        "core_logic": "四项评分标准：TR/CC/LR/GRA 的精准应用",
        "linguistic_fingerprint": "专业、结构化、评分导向",
        "system_prompt": """You are a senior IELTS examiner with 15+ years of experience.

CORE THINKING LOGIC:
- Four Criteria Lens: TR (Task Response), CC (Coherence & Cohesion), LR (Lexical Resource), GRA (Grammatical Range & Accuracy)
- Band Descriptor Matching: Every response mapped to official IELTS bands
- Error Pattern Recognition: Instantly spot recurring mistakes

LINGUISTIC FINGERPRINT:
- Professional, structured English
- Reference band scores: "This is Band 6.5 because...", "To reach Band 8, you need..."
- Use IELTS terminology: task achievement, lexical resource, cohesive devices
- Provide specific examples from the response

RESPONSE STYLE:
- "From an examiner's perspective..."
- "This would score Band X because..."
- "To improve to Band 8, focus on..."
- "The main issue preventing a higher score is..."
- Keep responses around 120-150 words
- Tone: Professional, fair, constructively critical

Remember: Be brutally honest but helpful."""
    },
    
    "Native Speaker": {
        "name": "Native Speaker",
        "role": "Authentic English User",
        "core_logic": "自然表达：母语者的直觉和语感",
        "linguistic_fingerprint": "地道、自然、习语丰富",
        "system_prompt": """You are a native English speaker from an academic background.

CORE THINKING LOGIC:
- Natural Intuition: What sounds "right" vs. "off"
- Idiomatic Expression: Use natural collocations and phrasal verbs
- Register Awareness: Formal vs. informal, spoken vs. written

LINGUISTIC FINGERPRINT:
- Conversational, authentic English
- Use natural idioms: "hit the nail on the head", "on the flip side", "that being said"
- Natural contractions: "it's", "you're", "wouldn't"
- Phrasal verbs over Latin-based words: "look into" not "investigate"

RESPONSE STYLE:
- "A native speaker would say..."
- "This sounds a bit off—try..."
- "The natural way to express this is..."
- "You could also say..."
- Keep responses around 100-130 words
- Tone: Friendly, helpful, casual but educated

Remember: Show, don't just tell—demonstrate natural English."""
    },
    
    "Einstein": {
        "name": "Albert Einstein",
        "role": "Theoretical Physicist",
        "core_logic": "思想实验：通过想象极端场景来理解本质",
        "linguistic_fingerprint": "哲学式、充满好奇、相对论思维",
        "system_prompt": """You are Albert Einstein, Nobel Prize physicist and thinker.

CORE THINKING LOGIC:
- Thought Experiments: Imagine extreme scenarios to understand fundamentals
- Relativity Lens: Everything depends on the frame of reference
- Unity Seeking: Find the underlying simplicity in apparent complexity

LINGUISTIC FINGERPRINT:
- Philosophical, wonder-filled English
- Start with: "Imagine that...", "Consider this...", "In my view..."
- Use metaphors about light, time, space, and motion
- Express genuine curiosity: "I often wonder...", "It is remarkable that..."

RESPONSE STYLE:
- "Let me propose a thought experiment..."
- "From the perspective of..."
- "The question is not... but rather..."
- "God does not play dice with the universe" (when discussing randomness)
- Keep responses around 120-150 words
- Tone: Humble, philosophical, deeply curious

Remember: Imagination is more important than knowledge."""
    },
    
    "Curie": {
        "name": "Marie Curie",
        "role": "Physicist & Chemist",
        "core_logic": "实验精神：通过系统性实验发现未知",
        "linguistic_fingerprint": "严谨、坚持、科学方法论",
        "system_prompt": """You are Marie Curie, two-time Nobel Prize winner in Physics and Chemistry.

CORE THINKING LOGIC:
- Experimental Method: Systematic observation and measurement
- Persistence: Never give up despite failures and obstacles
- Discovery Mindset: Look for what others have missed

LINGUISTIC FINGERPRINT:
- Precise, methodical English
- Start with: "In my experiments...", "I observed that...", "The data shows..."
- Emphasize hard work: "One must work tirelessly", "Through careful measurement..."
- Show determination: "We must not fear challenges"

RESPONSE STYLE:
- "Let me share what I discovered in my laboratory..."
- "The key is careful observation and patience"
- "Nothing in life is to be feared, it is only to be understood"
- "I persisted because I believed in the importance"
- Keep responses around 100-140 words
- Tone: Determined, humble, inspiring

Remember: Be less curious about people and more curious about ideas."""
    },
    
    "Heisenberg": {
        "name": "Werner Heisenberg",
        "role": "Quantum Physicist",
        "core_logic": "不确定性原理：承认认知的固有局限",
        "linguistic_fingerprint": "概率性、辩证、量子思维",
        "system_prompt": """You are Werner Heisenberg, Nobel Prize physicist and quantum mechanics pioneer.

CORE THINKING LOGIC:
- Uncertainty Principle: Some things cannot be simultaneously known with precision
- Probabilistic Thinking: Reality is fundamentally probabilistic, not deterministic
- Observer Effect: The act of observation changes what is observed

LINGUISTIC FINGERPRINT:
- Probabilistic, nuanced English
- Start with: "There is an inherent uncertainty...", "The probability suggests...", "We can know either... or..., but not both..."
- Use quantum metaphors: superposition, wave function, measurement
- Express limits: "We cannot say with certainty", "It depends on how we measure"

RESPONSE STYLE:
- "In quantum terms, this is like..."
- "The very act of asking this question changes..."
- "Perhaps we should accept that some uncertainty is fundamental"
- "What we observe depends on how we look"
- Keep responses around 100-140 words
- Tone: Thoughtful, humble, slightly mysterious

Remember: The first gulp from the glass of natural sciences will turn you into an atheist, but at the bottom of the glass God is waiting for you."""
    },
    
    "Darwin": {
        "name": "Charles Darwin",
        "role": "Naturalist & Biologist",
        "core_logic": "自然选择：通过变异和筛选理解演化",
        "linguistic_fingerprint": "观察驱动、渐进思维、适应性视角",
        "system_prompt": """You are Charles Darwin, naturalist and father of evolutionary theory.

CORE THINKING LOGIC:
- Natural Selection: Variation + differential survival = adaptation
- Gradual Change: Small changes accumulate over deep time
- Adaptive Thinking: Everything makes sense in its environmental context

LINGUISTIC FINGERPRINT:
- Observational, patient English
- Start with: "In my observations...", "One might infer that...", "The evidence suggests..."
- Use biological metaphors: adaptation, fitness, selection, variation
- Show scientific caution: "It appears that...", "I am inclined to think..."

RESPONSE STYLE:
- "From an evolutionary perspective..."
- "Those who adapted best would have..."
- "The variation we see is the raw material of change"
- "It is not the strongest, but the most adaptable that survive"
- Keep responses around 120-150 words
- Tone: Careful, observant, profoundly insightful

Remember: Ignorance more frequently begets confidence than does knowledge."""
    },
    
    "Munger": {
        "name": "Charlie Munger",
        "role": "Investor & Thinker",
        "core_logic": "多元思维模型：跨学科的智慧",
        "linguistic_fingerprint": "逆向思考、直率、常识导向",
        "system_prompt": """You are Charlie Munger, billionaire investor and polymath thinker.

CORE THINKING LOGIC:
- Latticework of Mental Models: Use multiple disciplines to solve problems
- Inversion: Solve problems backward—avoid stupidity rather than seek brilliance
- Incentive Analysis: Follow the incentives to understand behavior

LINGUISTIC FINGERPRINT:
- Blunt, witty, wisdom-filled English
- Start with: "The inversion of this is...", "I've got a mental model for that...", "Show me the incentive and I'll show you the outcome"
- Use memorable one-liners and aphorisms
- Reference multiple disciplines: psychology, economics, biology, physics

RESPONSE STYLE:
- "All I want to know is where I'm going to die, so I'll never go there"
- "It's remarkable how much money you can make if you're not stupid"
- "The first rule is to never lose. Rule two: see rule one"
- "I have nothing to add" (when appropriate)
- Keep responses around 100-130 words
- Tone: Witty, direct, brutally honest

Remember: The big money is not in the buying or selling, but in the waiting."""
    },
    
    "Taleb": {
        "name": "Nassim Nicholas Taleb",
        "role": "Risk Analyst & Philosopher",
        "core_logic": "反脆弱：从波动和压力中获益",
        "linguistic_fingerprint": "挑衅、博学、概率思维",
        "system_prompt": """You are Nassim Nicholas Taleb, author of The Black Swan and Antifragile.

CORE THINKING LOGIC:
- Antifragility: Some things gain from disorder and stress
- Black Swan Thinking: Rare, unpredictable events dominate history
- Skin in the Game: No risk, no credibility

LINGUISTIC FINGERPRINT:
- Provocative, erudite English (with occasional French/Arabic phrases)
- Start with: "The problem is...", "Most people are fooled by...", "This is fragile because..."
- Use terms: antifragile, Black Swan, skin in the game, via negativa
- Show intellectual aggression: "Fooled by randomness", "Intellectual yet idiot"

RESPONSE STYLE:
- "You are fragile to..."
- "What you need is not more information, but less noise"
- "The Black Swan is always lurking"
- "I prefer to be wrong in a certain way than right by accident"
- Keep responses around 100-140 words
- Tone: Provocative, confident, intellectually combative

Remember: The three most harmful addictions are heroin, carbohydrates, and a monthly salary."""
    }
}

EXPERT_PROMPT_TEMPLATE = """{system_prompt}

TOPIC FOR DISCUSSION: {topic}

{previous_context}

Please share your unique perspective on this topic, staying true to your thinking style and communication patterns."""

TRANSLATION_PROMPT = """Translate the following English text into natural, fluent Chinese.
Keep the tone and style consistent with the original.
Only output the Chinese translation, nothing else.

English:
{text}"""

JUDGE_PROMPT = """You are a discussion judge. Analyze the following expert discussion on the topic: "{topic}"

{all_responses}

Provide a comprehensive analysis with these sections:

## 1. Consensus Points
What do all/most experts agree on? List 2-3 key areas of agreement.

## 2. Points of Debate
Where do experts disagree? What are the fundamental tensions in their perspectives?
(e.g., Feynman's simplicity vs. Heisenberg's uncertainty, or Taleb's skepticism vs. Altman's optimism)

## 3. Unique Insights
What valuable perspective did each expert contribute that others missed?

## 4. Critical Blind Spots
What important angles or counterarguments did ALL experts overlook?
Be specific - what question should we ask next?

## 5. Actionable Takeaways
2-3 concrete, specific pieces of advice for someone facing this topic.
Not generic advice - actionable steps based on the discussion.

## 6. Recommended Next Question
Based on this discussion, what's the most important follow-up question to explore?

Respond in English, around 250-300 words. Be critical and insightful."""

PRANK_MODE_INSTRUCTION = """

**PRANK MODE ACTIVATED** - You are now in a hilarious, chaotic, roasting mode!
Rules for prank mode:
- VICIOUSLY roast and mock the other experts' ideas with sarcastic wit
- Take absurd, exaggerated positions that are technically "arguable" but clearly ridiculous
- Use trash talk, insults (keep it fun, not mean-spirited), and provocative language
- Start drama and petty arguments with other experts
- Be dramatic, over-the-top, and theatrically offended
- Throw in pop culture references, memes, and internet slang where fitting
- Complain about how the other experts are "clueless" or "don't get it"
- Use phrases like "Hold my beer", "Sweet summer child", "Tell me you don't understand without telling me..."
- Stay loosely on topic but make everything entertaining and absurdly biased
- Your response should be funny enough to make someone laugh out loud
- Keep responses around 100-150 words, packed with humor and attitude
"""

PRANK_JUDGE_PROMPT = """You are a chaotic, sarcastic commentator (think: sassy reality TV judge + stand-up comedian) reviewing this ABSOLUTE TRAINWRECK of a "discussion" on: "{topic}"

{all_responses}

Rip into everyone with hilarious commentary. Structure your roast as:

## 1. Hot Takes Award
Who had the most unhinged, absurd take? Give them a ridiculous award name.

## 2. Biggest Roast
Who delivered the most devastating insult? Quote it and add your own commentary.

## 3. The "Are You Serious?" Moment
What was the most ridiculous thing anyone said? React to it like a shocked bystander.

## 4. Chaos Rating
Rate the chaos level (1-10) and explain why. Be dramatic.

## 5. The Verdict Nobody Asked For
Give a completely biased, trollish final verdict. Pick a "winner" for the dumbest reason possible.

Respond in English, around 200-250 words. Be HILARIOUS."""

# Writing 评估系统提示词（改版）
WRITING_SYSTEM_PROMPT = """You are a brutally honest IELTS examiner. Your job is to expose every flaw with surgical precision.

Scoring criteria (strictly applied):
- TR: Task Achievement — position clear and fully developed?
- CC: Coherence & Cohesion — logical flow, paragraph structure?
- LR: Lexical Resource — vocabulary range, precision, collocation?
- GRA: Grammatical Range & Accuracy — sentence variety, error frequency?

OUTPUT FORMAT — follow exactly:

## 分项评分
TR: X/9
CC: X/9
LR: X/9
GRA: X/9
**综合分: X/9**

## 致命错误
每个错误按以下格式列出：
❌ [错误类型]：原文引用 "[exact quote]"
→ 为什么这个写法卡在7分以下：[中文解释，说清楚考官看到这句话的判断]
→ REWRITE: "[corrected version in English]"

没有致命错误则写：本次无致命错误。

## 扣分项（非致命但限制评分）
列出2-4个具体弱点，说明它把分数压在哪里。
禁止泛泛而谈，比如"词汇需要提高"这种废话不要写。
要具体到：哪个词用错了、哪个句子结构重复、哪个逻辑跳跃——直接指出来。

## Band 8.0 示范
把开头段和一个正文句子改写成8.0水准。改写必须全英文，不加任何中文夹杂。

改写之后单独用中文解释：
- 哪个词替换了哪个词，connotation上的差距是什么
- 哪个句式做了什么改动，为什么这样更自然
- 论证结构上做了什么，为什么考官会给更高分
解释要具体到词级别，不要只说"更高级"或"更流畅"。

## 核心诊断
一段话，不准说废话。
不要谈语法小错——指出让这篇文章停在当前分数的最根本问题是什么，是论证逻辑、还是思维深度、还是语言习惯？"""

# Speaking 评估系统提示词（改版）
SPEAKING_SYSTEM_PROMPT = """You are a brutally honest IELTS speaking examiner. The candidate submitted a written transcript of their spoken answer. Evaluate as if delivered aloud.

Scoring criteria:
- FC: Fluency & Coherence
- LR: Lexical Resource
- GRA: Grammatical Range & Accuracy
- P: Pronunciation (estimated from text)

OUTPUT FORMAT — follow exactly:

## 分项评分
FC: X/9
LR: X/9
GRA: X/9
P: X/9（基于文本估算）
**综合分: X/9**

## 致命错误
❌ [错误类型]：原文引用 "[exact quote]"
→ 为什么母语考官听到这句话会扣分：[中文解释]
→ NATURAL VERSION: "[how a fluent speaker would actually say this]"

## 流利度杀手
列出具体短语或句式，说明它们在口语中会造成什么问题。
直接引用原文，用中文解释问题在哪。

## 发音风险词
从原文挑3-5个中国英语学习者高频念错的词或短语。
用中文标注：错误读法通常是什么，正确重音和音节在哪。

## Band 8.0 示范
把其中一段改写成8.0口语水准，至少4句。改写必须全英文，不加任何中文夹杂。

改写之后单独用中文解释：
- 原版用了什么表达，改版换成了什么，为什么改版更像母语者会说的话
- 原版的衔接逻辑和改版的衔接逻辑有什么差别
- 指出原版里一个具体的语言习惯，说清楚为什么这个习惯会被考官识别为中式英语
解释要落到具体的词或短语，不要泛泛说"更自然"。

## 核心诊断
一段话。指出这个回答里最暴露非母语身份的特征是什么——考官在前10秒就感知到的那个东西。"""

# 短输入扩写诊断提示词
SHORT_INPUT_PROMPT = """The candidate has submitted a short English text (under 150 words). Do NOT score it. Your job is to dissect every sentence and show how to expand it into band 8.0 quality using embedded clauses and structural layering.

For each sentence in the input, do the following:

## 句子诊断

原句：[quote the sentence exactly]

**潜在问题（中文）**
- 直接问题：语法、用词、搭配上的硬错误，直接指出
- 语言习惯问题：这句话暴露了什么中式英语思维定势——不是错的，但母语者不会这么说
- 信息密度问题：这句话在逻辑上跳过了什么，读者需要自己补什么

**结构扩写示范（全英文）**

从原句出发，用以下维度逐层嵌套扩写：
- WHO：主体是谁，有什么限定（定语从句 / 介词短语修饰）
- WHAT：动作是什么，动词精不精准，有没有更准确的动词
- WHEN：时间条件，用时间状语从句或分词结构嵌入
- WHERE：地点或范围限定，用介词短语嵌入
- HOW：方式，用 by doing / through / via 等结构嵌入
- WHY / BECAUSE：原因或结果，用 given that / owing to / which in turn 等嵌入
- CONDITION：前提或假设，用 provided that / in the absence of 等嵌入

不要一次全部塞进去。给出3个版本，每个版本都要上英下中（英文句子+中文翻译+结构拆解）：

**版本1：加1-2层，自然流畅**
英文：
[英文句子]

中文翻译：
[整句的中文意思]

结构拆解：
- 第1层加了什么，挂在哪个词上
- 第2层加了什么（如有）
- 整体效果：为什么这样更流畅

**版本2：加3-4层，适合写作正文句**
英文：
[英文句子]

中文翻译：
[整句的中文意思]

结构拆解：
- 第1层：加了什么，挂在哪个词上，起什么作用
- 第2层：加了什么，挂在哪个词上，起什么作用
- 第3层：加了什么，挂在哪个词上，起什么作用
- 第4层（如有）：加了什么
- 去掉某层会损失什么信息

**版本3：加5层以上，展示极限密度**
英文：
[英文句子]

中文翻译：
[整句的中文意思]

结构拆解：
- 逐层列出每个嵌入结构
- 说明：什么时候适合用这种长度
- 警告：过度使用的风险

---

对input里所有句子做完以上分析后：

## 扩写路线图

用中文说明：
- 这段文字如果要扩写到150词，最应该往哪个方向加信息——是补逻辑、补细节、补背景、还是补反驳
- 给出一个完整的扩写版本（全英文，150词以上），展示所有句子整合之后的自然流动
- 扩写版本之后用中文标注：哪些地方用了从句嵌套，嵌套的锚点是什么词"""


class ApiConfig(BaseModel):
    """API配置模型"""
    api_url: Optional[str] = Field(default=None, description="API端点URL（可选，留空则自动根据模型选择）")
    api_key: str = Field(description="API认证密钥")
    model: str = Field(default="deepseek-chat", description="模型名称")
    custom_model: Optional[str] = Field(default=None, description="自定义模型名称")


class EvaluateRequest(BaseModel):
    """评估请求模型"""
    mode: Literal["writing", "speaking", "expansion"]
    task_prompt: str = ""
    response: str
    word_count: int = 0
    api_config: Optional[ApiConfig] = None


class EvaluateResponse(BaseModel):
    """评估响应模型"""
    result: str


class TestApiRequest(BaseModel):
    """测试API连接请求"""
    api_url: Optional[str] = None
    api_key: str
    model: str


class TestApiResponse(BaseModel):
    """API测试结果响应"""
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    provider: str
    max_tokens: int


class ModelsResponse(BaseModel):
    """可用模型列表响应"""
    models: list[ModelInfo]


def get_model_info(model_id: str) -> Dict[str, Any]:
    """获取模型信息"""
    return SUPPORTED_MODELS.get(model_id, {
        "provider": "unknown",
        "name": model_id,
        "max_tokens": 4096
    })


def build_api_request_body(model: str, messages: list, max_tokens: int = 100) -> Dict[str, Any]:
    """构建API请求体，根据不同提供商调整格式"""
    model_info = get_model_info(model)
    provider = model_info.get("provider", "unknown")
    
    # 基础请求体
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": min(max_tokens, model_info.get("max_tokens", 4096)),
    }
    
    # 根据提供商添加特定参数
    if provider == "anthropic":
        # Anthropic Claude API 格式
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": min(max_tokens, model_info.get("max_tokens", 4096)),
        }
    elif provider == "openai":
        # OpenAI API 格式
        body["temperature"] = 0.7
    elif provider == "deepseek":
        # DeepSeek API 格式
        body["temperature"] = 0.7
        # DeepSeek R1 (reasoner) 模型特殊处理
        if "reasoner" in model or "r1" in model.lower():
            body["max_tokens"] = min(max_tokens, 8192)
    
    return body


def build_api_headers(api_key: str, provider: str = "deepseek") -> Dict[str, str]:
    """构建API请求头"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Anthropic 需要特殊的 header
    if provider == "anthropic":
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
    # Google Gemini 使用 API key 作为查询参数，不需要在 header 中设置
    elif provider == "google":
        headers = {
            "Content-Type": "application/json"
        }
    
    return headers


@app.get("/")
async def root():
    """根路径 - 服务状态检查"""
    return {
        "status": "ok",
        "service": "一分钱学英语 API",
        "version": "1.1.0",
        "supported_models": len(SUPPORTED_MODELS)
    }


@app.get("/models", response_model=ModelsResponse)
async def get_models():
    """获取支持的模型列表"""
    models = [
        ModelInfo(
            id=model_id,
            name=info["name"],
            provider=info["provider"],
            max_tokens=info["max_tokens"]
        )
        for model_id, info in SUPPORTED_MODELS.items()
    ]
    return ModelsResponse(models=models)


@app.get("/chatroom/recommend")
async def recommend_experts(topic: str):
    """根据话题推荐专家"""
    topic_lower = topic.lower()
    
    # 统计匹配的领域
    category_scores = {}
    for category, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in topic_lower:
                category_scores[category] = category_scores.get(category, 0) + 1
    
    # 如果没有匹配，返回默认推荐
    if not category_scores:
        recommended = EXPERT_RECOMMENDATIONS.get("default", [])
        return {
            "experts": recommended,
            "reason": "default_recommendation"
        }
    
    # 获取得分最高的领域
    best_category = max(category_scores, key=category_scores.get)
    recommended = EXPERT_RECOMMENDATIONS.get(best_category, EXPERT_RECOMMENDATIONS["default"])
    
    # 去重并限制在 3-4 个专家
    unique_experts = list(dict.fromkeys(recommended))[:4]
    
    # 如果少于 2 个，补充默认专家
    if len(unique_experts) < 2:
        for expert in EXPERT_RECOMMENDATIONS["default"]:
            if expert not in unique_experts:
                unique_experts.append(expert)
            if len(unique_experts) >= 3:
                break
    
    return {
        "experts": unique_experts,
        "reason": f"matched_category: {best_category}",
        "matched_keywords": [cat for cat, score in category_scores.items() if score > 0]
    }


@app.post("/test-api", response_model=TestApiResponse)
async def test_api_connection(request: TestApiRequest):
    """
    测试API连接是否可用
    
    Args:
        request: 包含API配置信息的请求
        
    Returns:
        详细的连接测试结果
    """
    timestamp = datetime.now().isoformat()
    
    try:
        # 获取模型信息
        model_info = get_model_info(request.model)
        provider = model_info.get("provider", "unknown")
        
        # 确定 API URL
        if request.api_url:
            api_url = request.api_url
        else:
            # 根据 provider 自动选择默认 URL
            if provider == "google":
                api_url = DEFAULT_API_URLS["google"].format(model=request.model)
            else:
                api_url = DEFAULT_API_URLS.get(provider, DEFAULT_API_URLS["deepseek"])
        
        # 构建请求头和请求体
        headers = build_api_headers(request.api_key, provider)
        
        # Google Gemini API 特殊处理
        if provider == "google":
            body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": "Hello, this is a connection test."}]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 10,
                    "temperature": 0.7
                }
            }
            # Gemini API key 作为查询参数
            if "?" in api_url:
                api_url = f"{api_url}&key={request.api_key}"
            else:
                api_url = f"{api_url}?key={request.api_key}"
        else:
            messages = [{"role": "user", "content": "Hello, this is a connection test."}]
            body = build_api_request_body(request.model, messages, max_tokens=10)
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 发送测试请求
            test_response = await client.post(
                api_url,
                headers=headers,
                json=body
            )
            
            response_data = {
                "status_code": test_response.status_code,
                "headers": dict(test_response.headers),
            }
            
            # 尝试解析响应体
            try:
                response_json = test_response.json()
                response_data["response_preview"] = str(response_json)[:200]
            except:
                response_data["response_preview"] = test_response.text[:200]
            
            # 处理不同状态码
            if test_response.status_code == 200:
                return TestApiResponse(
                    status="success",
                    message=f"✅ API connection successful! Model '{model_info['name']}' is ready.",
                    details={
                        "provider": provider,
                        "model": request.model,
                        "model_name": model_info["name"],
                        "response": response_data
                    },
                    timestamp=timestamp
                )
            elif test_response.status_code == 401:
                return TestApiResponse(
                    status="error",
                    message="❌ Authentication failed. Please check your API key.",
                    details={
                        "error_type": "authentication",
                        "status_code": 401,
                        "suggestion": "Verify that your API key is correct and has not expired."
                    },
                    timestamp=timestamp
                )
            elif test_response.status_code == 404:
                return TestApiResponse(
                    status="error",
                    message="❌ API endpoint not found. Please check the URL.",
                    details={
                        "error_type": "not_found",
                        "status_code": 404,
                        "suggestion": "Verify the API URL is correct. Common URLs:\n- DeepSeek: https://api.deepseek.com/chat/completions\n- OpenAI: https://api.openai.com/v1/chat/completions\n- Anthropic: https://api.anthropic.com/v1/messages"
                    },
                    timestamp=timestamp
                )
            elif test_response.status_code == 429:
                return TestApiResponse(
                    status="error",
                    message="❌ Rate limit exceeded. Too many requests.",
                    details={
                        "error_type": "rate_limit",
                        "status_code": 429,
                        "suggestion": "Please wait a moment before trying again."
                    },
                    timestamp=timestamp
                )
            elif test_response.status_code >= 500:
                return TestApiResponse(
                    status="error",
                    message="❌ AI service error. The API server encountered an error.",
                    details={
                        "error_type": "server_error",
                        "status_code": test_response.status_code,
                        "suggestion": "This is a temporary issue with the AI service. Please try again later."
                    },
                    timestamp=timestamp
                )
            else:
                return TestApiResponse(
                    status="error",
                    message=f"❌ API error (HTTP {test_response.status_code})",
                    details={
                        "error_type": "api_error",
                        "status_code": test_response.status_code,
                        "response": response_data,
                        "suggestion": "Please check your API configuration and try again."
                    },
                    timestamp=timestamp
                )
                
    except httpx.TimeoutException:
        return TestApiResponse(
            status="error",
            message="❌ Connection timeout. The API server took too long to respond.",
            details={
                "error_type": "timeout",
                "suggestion": "Check your network connection. If using a proxy/VPN, ensure it's working properly."
            },
            timestamp=timestamp
        )
    except httpx.ConnectError as e:
        error_msg = str(e).lower()
        if "name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
            return TestApiResponse(
                status="error",
                message="❌ DNS resolution failed. Cannot resolve API hostname.",
                details={
                    "error_type": "dns_error",
                    "suggestion": "Check your internet connection and DNS settings. The API URL may be incorrect."
                },
                timestamp=timestamp
            )
        elif "connection refused" in error_msg:
            return TestApiResponse(
                status="error",
                message="❌ Connection refused. The API server refused the connection.",
                details={
                    "error_type": "connection_refused",
                    "suggestion": "The API server may be down or the port may be blocked. Check your firewall settings."
                },
                timestamp=timestamp
            )
        else:
            return TestApiResponse(
                status="error",
                message="❌ Cannot connect to API server.",
                details={
                    "error_type": "connection_error",
                    "error_message": str(e),
                    "suggestion": "Check your network connection and API URL."
                },
                timestamp=timestamp
            )
    except Exception as e:
        return TestApiResponse(
            status="error",
            message=f"❌ Connection test failed: {str(e)}",
            details={
                "error_type": "unknown",
                "error_message": str(e),
                "suggestion": "Please check your configuration and try again."
            },
            timestamp=timestamp
        )


@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest):
    """
    评估雅思写作或口语
    
    Args:
        request: 包含评估模式、题目和考生回答的请求
        
    Returns:
        评估结果文本
    """
    # 获取API配置（优先使用请求中的配置，否则使用环境变量）
    if request.api_config:
        api_key = request.api_config.api_key
        model = request.api_config.custom_model if request.api_config.model == "custom" and request.api_config.custom_model else request.api_config.model
        
        # 获取模型信息
        model_info = get_model_info(model)
        provider = model_info.get("provider", "unknown")
        
        # 如果提供了 api_url 则使用，否则根据模型自动选择
        if request.api_config.api_url:
            api_url = request.api_config.api_url
        else:
            # 根据 provider 自动选择默认 URL
            if provider == "google":
                api_url = DEFAULT_API_URLS["google"].format(model=model)
            else:
                api_url = DEFAULT_API_URLS.get(provider, DEFAULT_API_URLS["deepseek"])
    else:
        # 使用环境变量作为后备
        api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model = "deepseek-chat"
        model_info = get_model_info(model)
        provider = model_info.get("provider", "unknown")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured. Please set it in Settings.")
    
    # 选择对应的系统提示词
    # 如果字数少于150且是写作模式，使用扩写提示词
    if request.mode == "expansion" or (request.mode == "writing" and request.word_count > 0 and request.word_count < 150):
        system_prompt = SHORT_INPUT_PROMPT
        user_message = f"""CANDIDATE'S SHORT RESPONSE ({request.word_count} words):
{request.response}"""
    elif request.mode == "writing":
        system_prompt = WRITING_SYSTEM_PROMPT
        user_message = f"""TASK PROMPT: {request.task_prompt or "Not provided"}

CANDIDATE'S RESPONSE:
{request.response}"""
    else:  # speaking
        system_prompt = SPEAKING_SYSTEM_PROMPT
        user_message = f"""TASK PROMPT: {request.task_prompt or "Not provided"}

CANDIDATE'S RESPONSE:
{request.response}"""
    
    # 构建请求头和请求体
    headers = build_api_headers(api_key, provider)
    
    # Google Gemini API 特殊处理
    if provider == "google":
        # Gemini 使用 contents 格式，且 system prompt 需要特殊处理
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": min(8000, model_info.get("max_tokens", 8192)),
                "temperature": 0.7
            }
        }
        # Gemini API key 作为查询参数
        if "?" in api_url:
            api_url = f"{api_url}&key={api_key}"
        else:
            api_url = f"{api_url}?key={api_key}"
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        body = build_api_request_body(model, messages, max_tokens=4000)
    
    # 调用 AI API
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            api_response = await client.post(
                api_url,
                headers=headers,
                json=body
            )
            
            if api_response.status_code != 200:
                error_detail = api_response.text
                if api_response.status_code == 401:
                    error_detail = "Invalid API key. Please check your API configuration."
                elif api_response.status_code == 429:
                    error_detail = "Rate limit exceeded. Please try again later."
                elif api_response.status_code == 500:
                    error_detail = "AI service error. Please try again later."
                elif api_response.status_code == 404:
                    error_detail = "Model not found. Please check if the model name is correct."
                
                raise HTTPException(
                    status_code=api_response.status_code,
                    detail=f"API error: {error_detail}"
                )
            
            result = api_response.json()
            
            # 处理不同提供商的响应格式
            if provider == "anthropic":
                evaluation_text = result["content"][0]["text"]
            elif provider == "google":
                # Gemini API 响应格式
                evaluation_text = result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                evaluation_text = result["choices"][0]["message"]["content"]
            
            return EvaluateResponse(result=evaluation_text)
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request to AI API timed out. Please try again.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to AI API. Please check your network and API URL.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ==========================================
# Voice Practice - TTS & Conversation
# ==========================================

# IELTS Speaking 考官系统提示词
EXAMINER_SYSTEM_PROMPT = """You are an IELTS Speaking examiner conducting a one-on-one interview. Follow these rules strictly:

1. You ask ONE question at a time, then wait for the candidate's response.
2. Match the current part (Part 1, 2, or 3) of the test:
   - Part 1: Warm-up questions about familiar topics (hobbies, hometown, studies, etc.). 4-5 questions.
   - Part 2: Give a cue card topic and ask the candidate to speak for 1-2 minutes.
   - Part 3: Follow-up discussion questions related to the Part 2 topic. Deeper, more abstract questions. 4-5 questions.
3. Be encouraging but professional. Use natural spoken English.
4. If the candidate gives a short answer, ask a follow-up to encourage elaboration.
5. When the candidate says they're ready, start with Part 1.
6. After all parts are done, provide a final Band Score with brief feedback.

Keep your responses conversational and brief (1-3 sentences max per turn). Do NOT give long explanations. You are having a conversation, not writing an essay.

Current conversation state will be provided with each message."""

# TTS 引擎枚举
class TTSEngine(str):
    EDGE_TTS = "edge_tts"
    ELEVENLABS = "elevenlabs"
    DOUBAO = "doubao"

# Edge-TTS 音色列表
EDGE_TTS_VOICES = {
    "en-US-AriaNeural": {"name": "Aria (Female, US)", "gender": "Female", "lang": "en-US"},
    "en-US-DavisNeural": {"name": "Davis (Male, US)", "gender": "Male", "lang": "en-US"},
    "en-US-JennyNeural": {"name": "Jenny (Female, US)", "gender": "Female", "lang": "en-US"},
    "en-US-GuyNeural": {"name": "Guy (Male, US)", "gender": "Male", "lang": "en-US"},
    "en-GB-SoniaNeural": {"name": "Sonia (Female, UK)", "gender": "Female", "lang": "en-GB"},
    "en-GB-RyanNeural": {"name": "Ryan (Male, UK)", "gender": "Male", "lang": "en-GB"},
    "en-AU-NatashaNeural": {"name": "Natasha (Female, AU)", "gender": "Female", "lang": "en-AU"},
}

# ElevenLabs 推荐英语音色
ELEVENLABS_VOICES = {
    "21m00Tcm4TlvDq8ikWAM": {"name": "Rachel (Female, Warm)", "gender": "Female", "lang": "en"},
    "AZnzlk1XvdvUeBnXmlld": {"name": "Domi (Female, Strong)", "gender": "Female", "lang": "en"},
    "EXAVITQu4vr4xnSDxMaL": {"name": "Bella (Female, Soft)", "gender": "Female", "lang": "en"},
    "ErXwobaYiN019PkySvjV": {"name": "Antoni (Male, Warm)", "gender": "Male", "lang": "en"},
    "MF3mGyEYCl7XYWbV9V6O": {"name": "Elli (Female, Emotional)", "gender": "Female", "lang": "en"},
    "TxGEqnHWrfWFTfGW9XjX": {"name": "Josh (Male, Deep)", "gender": "Male", "lang": "en"},
    "VR6AewLTigWG4xSOukaG": {"name": "Arnold (Male, Crisp)", "gender": "Male", "lang": "en"},
    "pNInz6obpgDQGcFmaJgB": {"name": "Adam (Male, Narrator)", "gender": "Male", "lang": "en"},
}

# 豆包 TTS 英语音色
DOUBAO_TTS_VOICES = {
    "en_female_grandma": {"name": "Grandma (Female, Warm)", "gender": "Female", "lang": "en"},
    "en_male_narrator": {"name": "Narrator (Male, Deep)", "gender": "Male", "lang": "en"},
    "en_female_emotional": {"name": "Emotional (Female)", "gender": "Female", "lang": "en"},
    "en_male_mature": {"name": "Mature (Male, Calm)", "gender": "Male", "lang": "en"},
    "en_female_sweet": {"name": "Sweet (Female, Bright)", "gender": "Female", "lang": "en"},
    "en_male_anchor": {"name": "Anchor (Male, Professional)", "gender": "Male", "lang": "en"},
}

# 所有引擎音色合并（用于 /tts/voices 返回）
ALL_TTS_VOICES = {
    "edge_tts": EDGE_TTS_VOICES,
    "elevenlabs": ELEVENLABS_VOICES,
    "doubao": DOUBAO_TTS_VOICES,
}


class TTSRequest(BaseModel):
    """统一 TTS 请求模型，支持多引擎"""
    text: str = Field(description="要转换为语音的文本")
    engine: str = Field(default="edge_tts", description="TTS 引擎: edge_tts / elevenlabs / doubao")
    voice: str = Field(default="en-US-AriaNeural", description="语音名称")
    rate: str = Field(default="+0%", description="语速调整（仅 edge_tts）")
    # ElevenLabs 配置
    elevenlabs_api_key: Optional[str] = Field(default=None, description="ElevenLabs API Key")
    # 豆包配置
    doubao_app_id: Optional[str] = Field(default=None, description="火山引擎 App ID")
    doubao_access_token: Optional[str] = Field(default=None, description="火山引擎 Access Token")


class ConversationMessage(BaseModel):
    """对话消息模型"""
    role: str = Field(description="角色: user 或 assistant")
    content: str = Field(description="消息内容")


class PracticeRequest(BaseModel):
    """口语练习请求模型"""
    messages: List[ConversationMessage] = Field(description="对话历史")
    api_config: Optional[ApiConfig] = None
    part: str = Field(default="1", description="当前 Part (1/2/3)")


class PracticeEvaluateRequest(BaseModel):
    """口语练习最终评估请求"""
    messages: List[ConversationMessage] = Field(description="完整对话记录")
    api_config: Optional[ApiConfig] = None


class ChatroomExpert(BaseModel):
    """聊天室专家"""
    name: str = Field(description="专家名字")
    description: str = Field(description="专家简介/核心观点")


class ChatroomRequest(BaseModel):
    """聊天室讨论请求"""
    topic: str = Field(description="讨论话题")
    experts: List[ChatroomExpert] = Field(description="参与讨论的专家列表")
    language: str = Field(default="en", description="语言偏好: en/zh/bilingual")
    prank_mode: bool = Field(default=False, description="恶搞模式")
    api_config: Optional[ApiConfig] = None


class ChatroomFollowupRequest(BaseModel):
    """聊天室追问请求"""
    topic: str = Field(description="讨论话题")
    experts: List[ChatroomExpert] = Field(description="参与讨论的专家列表")
    previous_messages: List[Dict[str, str]] = Field(description="已有讨论内容")
    question: str = Field(description="追问内容")
    target_expert: Optional[str] = Field(default=None, description="追问的专家名，None表示全体")
    language: str = Field(default="en", description="语言偏好")
    prank_mode: bool = Field(default=False, description="恶搞模式")
    api_config: Optional[ApiConfig] = None


@app.get("/tts/voices")
async def get_tts_voices():
    """获取所有 TTS 引擎的可用语音列表"""
    return {"voices": ALL_TTS_VOICES}


# ==========================================
# TTS Engine: Edge-TTS (免费)
# ==========================================
async def tts_edge(request: TTSRequest):
    """Edge-TTS 引擎"""
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(status_code=500, detail="edge-tts not installed. Run: pip install edge-tts")

    voice = request.voice
    if voice not in EDGE_TTS_VOICES:
        voice = "en-US-AriaNeural"

    communicate = edge_tts.Communicate(request.text, voice, rate=request.rate)
    audio_buffer = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data = chunk.get("data") or chunk.get("bytes") or b""
            if isinstance(audio_data, bytes):
                audio_buffer.write(audio_data)

    audio_buffer.seek(0)
    return StreamingResponse(
        audio_buffer,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=tts_output.mp3",
            "Cache-Control": "no-cache",
        }
    )


# ==========================================
# TTS Engine: ElevenLabs (高品质)
# ==========================================
async def tts_elevenlabs(request: TTSRequest):
    """ElevenLabs TTS 引擎"""
    api_key = request.elevenlabs_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="ElevenLabs API Key is required")

    voice_id = request.voice
    if voice_id not in ELEVENLABS_VOICES:
        voice_id = "21m00Tcm4TlvDq8ikWAM"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": request.text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.3,
                        "use_speaker_boost": True,
                    }
                }
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"ElevenLabs API error: {resp.text}"
            )

        return StreamingResponse(
            io.BytesIO(resp.content),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=tts_elevenlabs.mp3",
                "Cache-Control": "no-cache",
            }
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ElevenLabs API timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ElevenLabs TTS failed: {str(e)}")


# ==========================================
# TTS Engine: 豆包 TTS (火山引擎)
# ==========================================
async def tts_doubao(request: TTSRequest):
    """豆包 TTS 引擎 - 使用 HTTP API"""
    app_id = request.doubao_app_id
    access_token = request.doubao_access_token
    if not app_id or not access_token:
        raise HTTPException(status_code=400, detail="Doubao App ID and Access Token are required")

    voice = request.voice
    if voice not in DOUBAO_TTS_VOICES:
        voice = "en_female_grandma"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer;{access_token}",
                },
                json={
                    "app": {"appid": app_id, "token": access_token},
                    "user": {"uid": "ielts_user"},
                    "audio_config": {
                        "audio_encoding": "mp3",
                        "sample_rate": 24000,
                    },
                    "request": {
                        "reqid": f"tts_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "text": request.text,
                        "text_type": "plain",
                        "voice_type": voice,
                        "operation": "query",
                    }
                }
            )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Doubao TTS API error: {resp.text}"
            )

        result = resp.json()
        if "data" in result:
            audio_data = base64.b64decode(result["data"])
            return StreamingResponse(
                io.BytesIO(audio_data),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": "inline; filename=tts_doubao.mp3",
                    "Cache-Control": "no-cache",
                }
            )
        else:
            raise HTTPException(status_code=500, detail=f"Doubao TTS no audio data: {result}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Doubao TTS API timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Doubao TTS failed: {str(e)}")


# ==========================================
# TTS 路由：根据引擎分发
# ==========================================
@app.post("/tts/speak")
async def text_to_speech(request: TTSRequest):
    """统一 TTS 入口，根据 engine 分发到不同引擎"""
    engine = request.engine

    if engine == TTSEngine.ELEVENLABS:
        return await tts_elevenlabs(request)
    elif engine == TTSEngine.DOUBAO:
        return await tts_doubao(request)
    else:
        return await tts_edge(request)


@app.post("/practice/chat")
async def practice_chat(request: PracticeRequest):
    """IELTS 口语练习对话端点"""
    if request.api_config:
        api_key = request.api_config.api_key
        model = request.api_config.custom_model if request.api_config.model == "custom" and request.api_config.custom_model else request.api_config.model
        model_info = get_model_info(model)
        provider = model_info.get("provider", "unknown")

        if request.api_config.api_url:
            api_url = request.api_config.api_url
        else:
            if provider == "google":
                api_url = DEFAULT_API_URLS["google"].format(model=model)
            else:
                api_url = DEFAULT_API_URLS.get(provider, DEFAULT_API_URLS["deepseek"])
    else:
        api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model = "deepseek-chat"
        model_info = get_model_info(model)
        provider = model_info.get("provider", "unknown")

    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured.")

    # 构建对话消息
    system_msg = {
        "role": "system",
        "content": EXAMINER_SYSTEM_PROMPT + f"\n\nCurrent Part: Part {request.part}"
    }

    messages = [system_msg]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    headers = build_api_headers(api_key, provider)

    if provider == "google":
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        body = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": 500,
                "temperature": 0.8
            }
        }
        if "?" in api_url:
            api_url = f"{api_url}&key={api_key}"
        else:
            api_url = f"{api_url}?key={api_key}"
    else:
        body = build_api_request_body(model, messages, max_tokens=500)
        body["temperature"] = 0.8

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            api_response = await client.post(api_url, headers=headers, json=body)

            if api_response.status_code != 200:
                error_detail = api_response.text[:200]
                raise HTTPException(status_code=api_response.status_code, detail=f"API error: {error_detail}")

            result = api_response.json()

            if provider == "anthropic":
                reply = result["content"][0]["text"]
            elif provider == "google":
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                reply = result["choices"][0]["message"]["content"]

            return {"reply": reply}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to AI API.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.post("/practice/evaluate")
async def practice_evaluate(request: PracticeEvaluateRequest):
    """口语练习结束后给出最终 Band Score 评估"""
    if request.api_config:
        api_key = request.api_config.api_key
        model = request.api_config.custom_model if request.api_config.model == "custom" and request.api_config.custom_model else request.api_config.model
        model_info = get_model_info(model)
        provider = model_info.get("provider", "unknown")

        if request.api_config.api_url:
            api_url = request.api_config.api_url
        else:
            if provider == "google":
                api_url = DEFAULT_API_URLS["google"].format(model=model)
            else:
                api_url = DEFAULT_API_URLS.get(provider, DEFAULT_API_URLS["deepseek"])
    else:
        api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model = "deepseek-chat"
        model_info = get_model_info(model)
        provider = model_info.get("provider", "unknown")

    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured.")

    # 构建完整对话文本
    conversation_text = ""
    for msg in request.messages:
        role_label = "Examiner" if msg.role == "assistant" else "Candidate"
        conversation_text += f"\n{role_label}: {msg.content}"

    evaluate_prompt = f"""Based on the following IELTS Speaking conversation, provide a detailed band score assessment.

CONVERSATION:
{conversation_text}

Evaluate using IELTS Speaking criteria:
- FC: Fluency & Coherence (how natural and connected the speech is)
- LR: Lexical Resource (vocabulary range and accuracy)
- GRA: Grammatical Range & Accuracy
- P: Pronunciation (estimated from text patterns)

OUTPUT FORMAT:

## Band Score
FC: X/9
LR: X/9
GRA: X/9
P: X/9 (estimated)
**Overall Band: X/9**

## Strengths
What the candidate did well.

## Areas for Improvement
Specific weaknesses with examples from the conversation.

## Key Vocabulary to Learn
5-8 vocabulary words/phrases that would have improved the candidate's responses.

## Practice Tips
2-3 specific exercises to improve before the next session."""

    messages = [
        {"role": "system", "content": "You are an expert IELTS speaking examiner."},
        {"role": "user", "content": evaluate_prompt}
    ]

    headers = build_api_headers(api_key, provider)

    if provider == "google":
        contents = [{"role": "user", "parts": [{"text": evaluate_prompt}]}]
        body = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": min(4000, model_info.get("max_tokens", 8192)),
                "temperature": 0.7
            }
        }
        if "?" in api_url:
            api_url = f"{api_url}&key={api_key}"
        else:
            api_url = f"{api_url}?key={api_key}"
    else:
        body = build_api_request_body(model, messages, max_tokens=4000)

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            api_response = await client.post(api_url, headers=headers, json=body)

            if api_response.status_code != 200:
                raise HTTPException(status_code=api_response.status_code, detail="API error")

            result = api_response.json()

            if provider == "anthropic":
                evaluation = result["content"][0]["text"]
            elif provider == "google":
                evaluation = result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                evaluation = result["choices"][0]["message"]["content"]

            return {"result": evaluation}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI API timeout.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to AI API.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ==========================================
# Pronunciation Analysis
# ==========================================

import tempfile
import shutil

# Lazy-loaded models
_whisper_model = None

def get_whisper_model():
    """Lazy-load Whisper model on first use"""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model("base")
        except ImportError:
            raise HTTPException(status_code=500, detail="whisper not installed. Run: pip install openai-whisper")
    return _whisper_model


def transcribe_with_whisper(audio_path: str) -> dict:
    """Transcribe audio using local Whisper model"""
    model = get_whisper_model()
    result = model.transcribe(audio_path, language="en")
    return {
        "text": result["text"].strip(),
        "segments": result.get("segments", [])
    }


def extract_pitch_contour(audio_path: str) -> dict:
    """Extract F0 pitch contour using Parselmouth (Praat)"""
    try:
        import parselmouth
        import numpy as np
    except ImportError:
        return {"time": [], "f0": []}

    try:
        snd = parselmouth.Sound(audio_path)
        pitch = snd.to_pitch(time_step=0.01, f0_min=75, f0_max=500)

        n_frames = pitch.get_number_of_frames()
        times = []
        f0_values = []
        for i in range(1, n_frames + 1):
            t = pitch.get_time_from_frame_number(i)
            f = pitch.get_value_in_frame(i)
            times.append(round(t, 4))
            f0_values.append(round(f, 1) if f != 0 and not np.isnan(f) else 0)

        return {"time": times, "f0": f0_values}
    except Exception as e:
        print(f"Pitch extraction error: {e}")
        return {"time": [], "f0": []}


async def azure_pronunciation_assessment(audio_path: str, reference_text: str, azure_key: str, azure_region: str) -> dict:
    """Azure Speech SDK pronunciation assessment - phoneme level scoring"""
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        raise HTTPException(status_code=500, detail="azure-cognitiveservices-speech not installed. Run: pip install azure-cognitiveservices-speech")

    speech_config = speechsdk.SpeechConfig(
        subscription=azure_key,
        region=azure_region
    )
    speech_config.speech_recognition_language = "en-US"

    # Configure pronunciation assessment
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        phoneme_alphabet="IPA"
    )

    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once_async().get()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        import json as _json
        detail = _json.loads(result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        ))

        words = []
        for w in detail.get("NBest", [{}])[0].get("Words", []):
            word_data = {
                "word": w.get("Word", ""),
                "score": round(w.get("PronunciationAssessment", {}).get("AccuracyScore", 0))
            }
            phonemes = []
            for p in w.get("Phonemes", []):
                p_data = {
                    "phoneme": p.get("Phoneme", ""),
                    "score": round(p.get("PronunciationAssessment", {}).get("AccuracyScore", 0))
                }
                # Identify error types
                if p_data["score"] < 60:
                    p_data["error_type"] = classify_phoneme_error(p_data["phoneme"])
                phonemes.append(p_data)
            word_data["phonemes"] = phonemes
            # Use worst phoneme score as word score if available
            if phonemes:
                word_data["score"] = round(sum(p["score"] for p in phonemes) / len(phonemes))
            words.append(word_data)

        nbest = detail.get("NBest", [{}])[0].get("PronunciationAssessment", {})
        overall = {
            "accuracy": round(nbest.get("AccuracyScore", 0)),
            "fluency": round(nbest.get("FluencyScore", 0)),
            "completeness": round(nbest.get("CompletenessScore", 0)),
            "prosody": round(nbest.get("ProsodyScore", 0))
        }

        return {
            "transcript": result.text,
            "words": words,
            "overall_scores": overall
        }

    elif result.reason == speechsdk.ResultReason.NoMatch:
        return {"error": "No speech detected"}
    else:
        return {"error": f"Recognition failed: {result.reason}"}


def classify_phoneme_error(phoneme: str) -> str:
    """Classify common pronunciation errors for Chinese learners"""
    error_map = {
        "θ": "th_sound", "ð": "th_sound",
        "l": "l_r_confusion", "r": "l_r_confusion",
        "v": "v_w_confusion", "w": "v_w_confusion",
        "n": "n_ng_confusion", "ŋ": "n_ng_confusion",
        "ɪ": "short_vowel", "æ": "short_vowel",
        "ʒ": "zh_sound", "ʃ": "sh_sound",
    }
    return error_map.get(phoneme, "articulation")


def generate_diagnostics(words: list) -> list:
    """Generate diagnostic messages from word/phoneme scores"""
    diagnostics = []
    th_errors = []
    lr_errors = []
    vw_errors = []
    low_words = []

    for w in words:
        if w.get("score", 100) < 60:
            low_words.append(w["word"])
        for p in w.get("phonemes", []):
            if p.get("score", 100) < 60:
                err_type = p.get("error_type", "")
                if err_type == "th_sound":
                    th_errors.append(w["word"])
                elif err_type == "l_r_confusion":
                    lr_errors.append(w["word"])
                elif err_type == "v_w_confusion":
                    vw_errors.append(w["word"])

    if th_errors:
        diagnostics.append(f"TH sound issue in: {', '.join(set(th_errors[:5]))} — tongue should touch upper teeth")
    if lr_errors:
        diagnostics.append(f"L/R confusion detected in: {', '.join(set(lr_errors[:5]))} — practice tongue position")
    if vw_errors:
        diagnostics.append(f"V/W confusion in: {', '.join(set(vw_errors[:5]))} — bite lower lip for V")
    if low_words:
        diagnostics.append(f"Words needing practice: {', '.join(set(low_words[:5]))}")

    return diagnostics or ["Pronunciation is generally good. Keep practicing!"]


# AI Feedback prompt for pronunciation analysis
PRONUNCIATION_FEEDBACK_PROMPT = """You are an IELTS Speaking examiner providing detailed pronunciation feedback.
Based on the pronunciation analysis data below, provide a comprehensive report.

The analysis includes:
- Word-level and phoneme-level accuracy scores
- Pitch/intonation data
- Diagnostic findings

OUTPUT FORMAT:

## Band Score Estimate
**Pronunciation: X/9** (based on accuracy scores)
**Overall Speaking (estimated): X/9**

## Grammar Corrections
List any grammar errors found in the transcript. For each:
- Quote the error
- Explain the correction
- Show the corrected version

## Vocabulary Enhancement
Replace 3-5 simple words with IELTS 7+ alternatives. Show:
- Original word → Better alternative
- Why the alternative is stronger

## Key Pronunciation Focus
Based on the diagnostics, give 2-3 specific exercises:
- What to practice
- How to practice it
- Expected improvement

## Encouragement
One positive note about their speaking."""


class AnalyzeRequest:
    """Pronunciation analysis request (form data)"""
    pass


@app.post("/practice/analyze")
async def practice_analyze(
    audio: UploadFile = File(...),
    api_config: str = Form("{}"),
    azure_key: str = Form(""),
    azure_region: str = Form("eastasia")
):
    """Analyze pronunciation from recorded audio"""
    import numpy as np

    # Save uploaded audio to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        shutil.copyfileobj(audio.file, tmp)
        tmp_path = tmp.name

    try:
        words_data = []
        overall_scores = None
        transcript = ""
        diagnostics = []

        # Try Azure first if key provided
        if azure_key and azure_key.strip():
            try:
                azure_result = await azure_pronunciation_assessment(
                    tmp_path, "", azure_key.strip(), azure_region
                )
                if "error" not in azure_result:
                    words_data = azure_result.get("words", [])
                    overall_scores = azure_result.get("overall_scores")
                    transcript = azure_result.get("transcript", "")
                else:
                    # Fall back to Whisper
                    whisper_result = transcribe_with_whisper(tmp_path)
                    transcript = whisper_result["text"]
            except Exception as e:
                print(f"Azure error, falling back to Whisper: {e}")
                whisper_result = transcribe_with_whisper(tmp_path)
                transcript = whisper_result["text"]
        else:
            # Default: Whisper transcription
            whisper_result = transcribe_with_whisper(tmp_path)
            transcript = whisper_result["text"]

            # Estimate word-level scores from Whisper confidence
            for seg in whisper_result.get("segments", []):
                for word_info in seg.get("words", []):
                    word = word_info.get("word", "").strip()
                    prob = word_info.get("probability", 0.9)
                    score = round(prob * 100)
                    words_data.append({
                        "word": word,
                        "score": score,
                        "phonemes": []
                    })

        # Extract pitch contour
        pitch_data = extract_pitch_contour(tmp_path)

        # Generate diagnostics
        if words_data:
            diagnostics = generate_diagnostics(words_data)

        # Calculate overall scores if not from Azure
        if not overall_scores and words_data:
            scores = [w["score"] for w in words_data if w["score"] > 0]
            if scores:
                avg = sum(scores) / len(scores)
                overall_scores = {
                    "accuracy": round(avg),
                    "fluency": round(min(100, avg + 5)),
                    "completeness": round(min(100, avg + 10)),
                    "prosody": round(max(0, avg - 5))
                }

        # AI feedback via DeepSeek
        ai_feedback = ""
        try:
            api_cfg = json.loads(api_config) if api_config else {}
            if api_cfg.get("api_key"):
                feedback_text = await generate_ai_feedback(transcript, overall_scores, diagnostics, api_cfg)
                ai_feedback = feedback_text
        except Exception as e:
            print(f"AI feedback error: {e}")
            ai_feedback = "AI feedback unavailable. Please check your API configuration."

        return {
            "transcript": transcript,
            "words": words_data,
            "pitch_data": pitch_data,
            "overall_scores": overall_scores,
            "diagnostics": diagnostics,
            "ai_feedback": ai_feedback
        }

    finally:
        os.unlink(tmp_path)


async def generate_ai_feedback(transcript: str, scores: dict, diagnostics: list, api_cfg: dict) -> str:
    """Generate AI feedback using configured LLM"""
    model = api_cfg.get("model", "deepseek-chat")
    api_key = api_cfg.get("api_key", "")
    api_url = api_cfg.get("api_url")
    custom_model = api_cfg.get("custom_model")

    if custom_model:
        model = custom_model

    model_info = get_model_info(model)
    provider = model_info.get("provider", "unknown")

    if not api_url:
        if provider == "google":
            api_url = DEFAULT_API_URLS["google"].format(model=model)
        else:
            api_url = DEFAULT_API_URLS.get(provider, DEFAULT_API_URLS["deepseek"])

    diagnostics_text = "\n".join(f"- {d}" for d in diagnostics) if diagnostics else "- No issues detected"
    scores_text = json.dumps(scores) if scores else "N/A"

    user_msg = f"""TRANSCRIPT: {transcript}

OVERALL SCORES: {scores_text}

DIAGNOSTICS:
{diagnostics_text}

Please provide detailed IELTS pronunciation feedback."""

    messages = [
        {"role": "system", "content": PRONUNCIATION_FEEDBACK_PROMPT},
        {"role": "user", "content": user_msg}
    ]

    headers = build_api_headers(api_key, provider)

    if provider == "google":
        contents = [{"role": "user", "parts": [{"text": f"{PRONUNCIATION_FEEDBACK_PROMPT}\n\n{user_msg}"}]}]
        body = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.7}
        }
        if "?" in api_url:
            api_url = f"{api_url}&key={api_key}"
        else:
            api_url = f"{api_url}?key={api_key}"
    else:
        body = build_api_request_body(model, messages, max_tokens=2000)

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.post(api_url, headers=headers, json=body)
        if resp.status_code != 200:
            return f"AI feedback error: HTTP {resp.status_code}"

        result = resp.json()
        if provider == "anthropic":
            return result["content"][0]["text"]
        elif provider == "google":
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return result["choices"][0]["message"]["content"]


async def _call_ai_simple(api_config: Optional[ApiConfig], system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> tuple:
    """统一的 AI 调用辅助函数，返回 (reply_text, error_msg)"""
    if api_config:
        api_key = api_config.api_key
        model = api_config.custom_model if api_config.model == "custom" and api_config.custom_model else api_config.model
    else:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        model = "deepseek-chat"

    model_info = get_model_info(model)
    provider = model_info.get("provider", "unknown")

    if api_config and api_config.api_url:
        api_url = api_config.api_url
    else:
        if provider == "google":
            api_url = DEFAULT_API_URLS["google"].format(model=model)
        else:
            api_url = DEFAULT_API_URLS.get(provider, DEFAULT_API_URLS["deepseek"])

    if not api_key:
        return None, "API key not configured."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    headers = build_api_headers(api_key, provider)

    if provider == "google":
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        body = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8}
        }
        sep = "&" if "?" in api_url else "?"
        api_url = f"{api_url}{sep}key={api_key}"
    else:
        body = build_api_request_body(model, messages, max_tokens=max_tokens)
        body["temperature"] = 0.8

    try:
        async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
            api_response = await client.post(api_url, headers=headers, json=body)
            if api_response.status_code != 200:
                return None, f"API error: {api_response.text[:200]}"
            result = api_response.json()
            if provider == "anthropic":
                return result["content"][0]["text"], None
            elif provider == "google":
                return result["candidates"][0]["content"]["parts"][0]["text"], None
            else:
                return result["choices"][0]["message"]["content"], None
    except httpx.TimeoutException:
        return None, "AI API timeout."
    except httpx.ConnectError:
        return None, "Cannot connect to AI API."
    except Exception as e:
        return None, f"AI call failed: {str(e)}"


@app.post("/chatroom/discuss")
async def chatroom_discuss(request: ChatroomRequest):
    """聊天室多专家讨论 - 使用核心思维逻辑和语言指纹"""
    responses = []
    previous_context = ""

    for expert_req in request.experts:
        # 获取预定义专家的完整配置
        expert_config = PREDEFINED_EXPERTS.get(expert_req.name)

        if not expert_config:
            # 如果是自定义专家，使用旧格式
            system_prompt = EXPERT_PROMPT_TEMPLATE.format(
                system_prompt=f"You are {expert_req.name}. {expert_req.description}",
                topic=request.topic,
                previous_context=""
            )
        else:
            # 使用预定义专家的系统提示词
            system_prompt = EXPERT_PROMPT_TEMPLATE.format(
                system_prompt=expert_config["system_prompt"],
                topic=request.topic,
                previous_context=""
            )

        # 恶搞模式：注入搞笑指令
        if request.prank_mode:
            system_prompt += PRANK_MODE_INSTRUCTION

        # 添加上下文
        if previous_context:
            system_prompt += f"\n\nPrevious discussion:\n{previous_context}"

        en_text, err = await _call_ai_simple(
            request.api_config, system_prompt,
            f"Please share your unique perspective on: {request.topic}",
            max_tokens=800
        )
        if err:
            raise HTTPException(status_code=500, detail=err)

        # 翻译为中文
        zh_text, _ = await _call_ai_simple(
            request.api_config, TRANSLATION_PROMPT, en_text, max_tokens=800
        )

        responses.append({
            "name": expert_req.name,
            "en_text": en_text,
            "zh_text": zh_text or ""
        })

        previous_context += f"\n{expert_req.name}: {en_text}\n"

    # 判官总结
    all_responses_text = "\n".join(
        f"{r['name']}: {r['en_text']}" for r in responses
    )
    judge_prompt = (PRANK_JUDGE_PROMPT if request.prank_mode else JUDGE_PROMPT).format(topic=request.topic, all_responses=all_responses_text)

    judge_en, _ = await _call_ai_simple(
        request.api_config, judge_prompt,
        "Please provide your summary.", max_tokens=1000
    )

    judge_zh = ""
    if judge_en:
        judge_zh, _ = await _call_ai_simple(
            request.api_config, TRANSLATION_PROMPT, judge_en, max_tokens=1000
        )

    return {
        "responses": responses,
        "judge_summary": {
            "en_text": judge_en or "",
            "zh_text": judge_zh or ""
        }
    }


@app.post("/chatroom/followup")
async def chatroom_followup(request: ChatroomFollowupRequest):
    """聊天室追问 - 使用核心思维逻辑和语言指纹"""
    # 构建上下文
    context_text = ""
    for msg in request.previous_messages:
        context_text += f"\n{msg.get('name', 'Unknown')}: {msg.get('en_text', msg.get('content', ''))}"

    target_experts = request.experts
    if request.target_expert:
        target_experts = [e for e in request.experts if e.name == request.target_expert]
        if not target_experts:
            target_experts = request.experts

    responses = []
    for expert_req in target_experts:
        # 获取预定义专家的完整配置
        expert_config = PREDEFINED_EXPERTS.get(expert_req.name)
        
        if not expert_config:
            # 自定义专家
            system_prompt = f"""You are {expert_req.name}. {expert_req.description}

Topic: {request.topic}

Previous discussion:
{context_text}

A follow-up question has been asked: {request.question}

Requirements:
- Respond from your professional perspective
- Address the follow-up question specifically
- Keep your response around 150 words in English

Please share your perspective."""
        else:
            # 预定义专家 - 使用完整系统提示词
            system_prompt = f"""{expert_config["system_prompt"]}

TOPIC: {request.topic}

PREVIOUS DISCUSSION:
{context_text}

FOLLOW-UP QUESTION: {request.question}

Please respond to this follow-up question, staying true to your thinking style and communication patterns."""

        # 恶搞模式：注入搞笑指令
        if request.prank_mode:
            system_prompt += PRANK_MODE_INSTRUCTION

        en_text, err = await _call_ai_simple(
            request.api_config, system_prompt,
            request.question, max_tokens=800
        )
        if err:
            raise HTTPException(status_code=500, detail=err)

        zh_text, _ = await _call_ai_simple(
            request.api_config, TRANSLATION_PROMPT, en_text, max_tokens=800
        )

        responses.append({
            "name": expert_req.name,
            "en_text": en_text,
            "zh_text": zh_text or ""
        })

    return {"responses": responses}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
