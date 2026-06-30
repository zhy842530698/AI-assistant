# AI-assistant

终端对话助手 · 模型 `minimax-portal/MiniMax-M3`

## 快速开始

```bash
cd ~/Projects/AI-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export MINIMAX_API_KEY="你的 key"
python chat.py
```

输入 `/quit` 退出，`/clear` 清空上下文。

## 文件

- `chat.py` — 主入口，多轮 REPL
- `client.py` — MiniMax-M3 API 客户端（OpenAI 兼容协议）
- `requirements.txt` — 依赖
- `.env.example` — 环境变量模板