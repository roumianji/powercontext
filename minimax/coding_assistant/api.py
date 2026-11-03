import json
import re
import time
import urllib.error
import urllib.request


SYSTEM = """你是本地项目的代码修改助手。请根据用户提供的当前规格、代码、测试与任务状态完成局部修改。
只能修改 demo_app/service.py 中 TaskBoard.list_tasks 的函数体；保持签名及其他代码的行为不变。
不修改任何测试、规格、日志或其他文件，不跳过测试，不引入新依赖。
仅返回一个 JSON 对象，不要 Markdown 围栏，不输出推理过程。格式为：
{"summary":"简短说明修改行为", "files":[{"path":"demo_app/service.py", "content":"该文件修改后的完整 Python 源码"}]}。
文件内容必须完整、语法正确，保留原有其他函数。以提供的真实有效规格为准。"""


def request_body(context, config):
    body = {"model": config.model, "max_tokens": config.max_tokens, "stream": False,
            "system": SYSTEM, "messages": [{"role": "user", "content": [{"type": "text", "text":
                "请完成以下开发任务。上下文来自 seekdb，进度来自 PowerContext。\n" +
                json.dumps(context, ensure_ascii=False, indent=2)}]}]}
    if config.model.startswith("MiniMax-M3.1"):
        body["output_config"] = {"effort": config.effort}
    return body


def redact(text, api_key):
    text = str(text).replace(api_key, "[REDACTED]") if api_key else str(text)
    return re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)


def public_text(payload):
    text = "\n".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Do not retain an incomplete thinking segment in a truncated response.
    return text.split("<think>", 1)[0].strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def call(config, body, *, opener=None):
    opener = opener or urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(config.base_url + "/v1/messages",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + config.api_key, "Content-Type": "application/json",
                 "anthropic-version": "2023-06-01", "User-Agent": "minimax-sdd-coursework/0.1.0"})
    start = time.monotonic()
    try:
        with opener.open(request, timeout=config.timeout) as response:
            payload = json.loads(response.read(16 * 1024 * 1024))
            request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
    except urllib.error.HTTPError as error:
        detail = redact(error.read(8192).decode("utf-8", errors="replace"), config.api_key)
        raise RuntimeError(f"MiniMax HTTP {error.code}: {detail}") from None
    except urllib.error.URLError as error:
        raise RuntimeError("MiniMax 网络请求失败：" + redact(error.reason, config.api_key)) from None
    text = public_text(payload)
    metadata = {"response_id": payload.get("id"), "request_id": request_id,
                "model_returned": payload.get("model"), "stop_reason": payload.get("stop_reason"),
                "usage": payload.get("usage"), "elapsed_seconds": round(time.monotonic() - start, 3),
                "retained_content_types": ["text"], "omitted_content_types": sorted({
                    block.get("type", "unknown") for block in payload.get("content", []) if block.get("type") != "text"})}
    if payload.get("error"):
        raise RuntimeError("MiniMax 返回错误：" + redact(json.dumps(payload["error"], ensure_ascii=False), config.api_key))
    return text, metadata
