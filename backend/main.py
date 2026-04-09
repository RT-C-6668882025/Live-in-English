"""
英语即日常 - FastAPI 后端服务
Live in English Backend Service
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
from typing import Literal, Optional, Dict, Any, List
from datetime import datetime

app = FastAPI(title="Live in English API", version="1.1.0")

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
        "service": "Live in English API",
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

# TTS 可用语音列表
TTS_VOICES = {
    "en-US-AriaNeural": {"name": "Aria (Female, US)", "gender": "Female", "lang": "en-US"},
    "en-US-DavisNeural": {"name": "Davis (Male, US)", "gender": "Male", "lang": "en-US"},
    "en-US-JennyNeural": {"name": "Jenny (Female, US)", "gender": "Female", "lang": "en-US"},
    "en-US-GuyNeural": {"name": "Guy (Male, US)", "gender": "Male", "lang": "en-US"},
    "en-GB-SoniaNeural": {"name": "Sonia (Female, UK)", "gender": "Female", "lang": "en-GB"},
    "en-GB-RyanNeural": {"name": "Ryan (Male, UK)", "gender": "Male", "lang": "en-GB"},
    "en-AU-NatashaNeural": {"name": "Natasha (Female, AU)", "gender": "Female", "lang": "en-AU"},
}


class TTSRequest(BaseModel):
    """TTS 请求模型"""
    text: str = Field(description="要转换为语音的文本")
    voice: str = Field(default="en-US-AriaNeural", description="语音名称")
    rate: str = Field(default="+0%", description="语速调整，如 +20%, -10%")


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


@app.get("/tts/voices")
async def get_tts_voices():
    """获取可用的 TTS 语音列表"""
    return {"voices": TTS_VOICES}


@app.post("/tts/speak")
async def text_to_speech(request: TTSRequest):
    """将文本转换为语音并返回音频流"""
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="edge-tts not installed. Run: pip install edge-tts"
        )

    voice = request.voice
    if voice not in TTS_VOICES:
        voice = "en-US-AriaNeural"

    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
