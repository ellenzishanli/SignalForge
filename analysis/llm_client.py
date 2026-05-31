"""
统一 LLM 客户端，支持多个免费/付费模型提供商
Unified LLM client supporting multiple free/paid providers.

优先级 / Priority: Groq (免费/free) → Ollama (本地/local) → Anthropic (付费/paid)
通过 .env 中的 LLM_PROVIDER 来切换 / Set LLM_PROVIDER in .env to override.
"""
import os


def get_provider() -> str:
    # 优先读取用户手动指定的 provider / Check manually set provider first
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider:
        return provider
    # 按优先级自动检测 / Auto-detect by priority
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "ollama"


def call_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """统一调用接口，自动路由到对应 provider / Unified call, auto-routes to the right provider."""
    provider = get_provider()

    if provider == "groq":
        return _call_groq(prompt, system, max_tokens)
    elif provider == "anthropic":
        return _call_anthropic(prompt, system, max_tokens)
    elif provider == "gemini":
        return _call_gemini(prompt, system, max_tokens)
    elif provider == "ollama":
        return _call_ollama(prompt, system, max_tokens)
    else:
        raise ValueError(f"未知的 LLM provider / Unknown LLM provider: {provider}")


def _call_groq(prompt: str, system: str, max_tokens: int) -> str:
    """Groq 免费 API，使用 Llama 3.1 70B / Free Groq API using Llama 3.1 70B."""
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
        messages=messages,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def _call_anthropic(prompt: str, system: str, max_tokens: int) -> str:
    """Anthropic Claude API（付费）/ Anthropic Claude API (paid)."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    kwargs = {
        "model": os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"),
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return resp.content[0].text


def _call_gemini(prompt: str, system: str, max_tokens: int) -> str:
    """Google Gemini 免费 tier / Google Gemini free tier."""
    import requests
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_ollama(prompt: str, system: str, max_tokens: int) -> str:
    """Ollama 本地运行，完全免费无需 API Key / Ollama local inference, fully free."""
    import requests
    model = os.getenv("OLLAMA_MODEL", "llama3")
    url = os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(url, json={
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]
