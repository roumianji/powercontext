import getpass
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_BASE = "https://api.minimax.cn/anthropic"
DEFAULT_MODEL = "MiniMax-M3.1-Flash"
ALLOWED_HOSTS = {"api.minimax.cn", "api.minimax.io", "api.minimaxi.com"}


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE
    model: str = DEFAULT_MODEL
    max_tokens: int = 8192
    effort: str = "low"
    timeout: float = 240

    def public(self):
        return {"base_url": self.base_url, "model": self.model, "max_tokens": self.max_tokens,
                "effort": self.effort, "timeout_seconds": self.timeout,
                "protocol": "Anthropic-compatible Messages HTTP API"}


def validate(config):
    if not config.api_key or config.api_key.casefold() in {"your_subscription_key", "replace_me"} or any(char.isspace() for char in config.api_key):
        raise ValueError("请先运行 python -m coding_assistant configure，在本机填写 MiniMax 订阅 Key。")
    url = urlsplit(config.base_url)
    if (url.scheme != "https" or url.hostname not in ALLOWED_HOSTS or url.username or url.password
            or url.query or url.fragment or url.port not in (None, 443) or url.path.rstrip("/") != "/anthropic"):
        raise ValueError("Base URL 应为 MiniMax 官方 Anthropic 兼容地址，如 https://api.minimax.cn/anthropic。")
    if not config.model.startswith("MiniMax-"):
        raise ValueError("请填写账号可用的 MiniMax 模型 ID。")
    if config.effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise ValueError("MINIMAX_EFFORT 应为 low、medium、high、xhigh 或 max。")
    if not 1024 <= config.max_tokens <= 32768 or not 10 <= config.timeout <= 600:
        raise ValueError("输出上限应为 1024～32768，超时应为 10～600 秒。")
    return config


def load(root):
    from dotenv import dotenv_values

    values = {**dotenv_values(Path(root) / ".env", interpolate=False), **os.environ}
    return validate(Config(api_key=values.get("MINIMAX_API_KEY", ""),
                           base_url=values.get("MINIMAX_BASE_URL", DEFAULT_BASE).rstrip("/"),
                           model=values.get("MINIMAX_MODEL", DEFAULT_MODEL),
                           max_tokens=int(values.get("MINIMAX_MAX_OUTPUT_TOKENS", "8192")),
                           effort=values.get("MINIMAX_EFFORT", "low"),
                           timeout=float(values.get("MINIMAX_TIMEOUT_SECONDS", "240"))))


def configure(root):
    from dotenv import dotenv_values

    root = Path(root).resolve()
    path = root / ".env"
    values = dict(dotenv_values(path, interpolate=False)) if path.is_file() else {}
    old_key = values.get("MINIMAX_API_KEY", "")
    print("请填写套餐详情中的订阅 Key；输入不会显示。", flush=True)
    entered = getpass.getpass("MiniMax 订阅 Key" + ("（留空保留原值）" if old_key else "") + "：").strip()
    base = input(f"Base URL（回车使用 {values.get('MINIMAX_BASE_URL', DEFAULT_BASE)}）：").strip()
    model = input(f"模型 ID（回车使用 {values.get('MINIMAX_MODEL', DEFAULT_MODEL)}）：").strip()
    config = validate(Config(api_key=entered or old_key,
                             base_url=(base or values.get("MINIMAX_BASE_URL", DEFAULT_BASE)).rstrip("/"),
                             model=model or values.get("MINIMAX_MODEL", DEFAULT_MODEL)))
    values.update({"MINIMAX_API_KEY": config.api_key, "MINIMAX_BASE_URL": config.base_url,
                   "MINIMAX_MODEL": config.model, "MINIMAX_EFFORT": "low",
                   "MINIMAX_MAX_OUTPUT_TOKENS": "8192", "MINIMAX_TIMEOUT_SECONDS": "240"})
    ignore = root / ".gitignore"
    old_ignore = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    missing = [line for line in (".env", ".runtime/") if line not in old_ignore.splitlines()]
    if missing:
        ignore.write_text(old_ignore.rstrip() + "\n" + "\n".join(missing) + "\n", encoding="utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        for key, value in values.items():
            if value is not None:
                stream.write(f"{key}={json.dumps(str(value), ensure_ascii=False)}\n")
    path.chmod(0o600)
    print("本机配置已保存到 .env；尚未调用模型。", flush=True)
    print(f"模型：{config.model}；地址：{config.base_url}", flush=True)
