import json
import urllib.request
import urllib.error
from typing import List, Dict

def call_openai(api_key: str, model: str, messages: List[Dict[str, str]], system_context: str = "") -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    final_messages = []
    if system_context:
        final_messages.append({"role": "system", "content": system_context})
    final_messages.extend(messages)
    
    data = {"model": model, "messages": final_messages, "temperature": 0.7}
    
    req = urllib.request.Request(url, json.dumps(data).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        try:
            error_data = json.loads(e.read().decode("utf-8"))
            return f"❌ Lỗi OpenAI: {error_data.get('error', {}).get('message', 'Unknown Error')}"
        except:
            return f"❌ Lỗi OpenAI (HTTP {e.code})"
    except Exception as e:
        return f"❌ Không thể kết nối OpenAI: {str(e)}"

def call_gemini(api_key: str, model: str, messages: List[Dict[str, str]], system_context: str = "") -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    gemini_messages = []
    last_role = None
    for m in messages:
        role = "user" if m["role"] in ["user", "system"] else "model"
        
        if role == last_role and len(gemini_messages) > 0:
            gemini_messages[-1]["parts"][0]["text"] += "\n" + m["content"]
        else:
            gemini_messages.append({"role": role, "parts": [{"text": m["content"]}]})
        last_role = role
        
    data = {"contents": gemini_messages}
    if system_context:
        data["system_instruction"] = {"parts": [{"text": system_context}]}
    
    req = urllib.request.Request(url, json.dumps(data).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            if "candidates" in result and result["candidates"]:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            return "Khởi tạo content trống từ Google Gemini."
    except urllib.error.HTTPError as e:
        try:
            error_data = json.loads(e.read().decode("utf-8"))
            return f"❌ Lỗi Gemini: {error_data.get('error', {}).get('message', 'Unknown Error')}"
        except:
            return f"❌ Lỗi Gemini (HTTP {e.code})"
    except Exception as e:
        return f"❌ Không thể kết nối Google Gemini: {str(e)}"

def call_anthropic(api_key: str, model: str, messages: List[Dict[str, str]], system_context: str = "") -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    anthropic_msgs = []
    last_role = None
    for m in messages:
        # Anthropic uses 'user' and 'assistant' only for the messages array
        role = "user" if m["role"] in ["user", "system"] else "assistant"
        if role == last_role and len(anthropic_msgs) > 0:
             anthropic_msgs[-1]["content"] += "\n" + m["content"]
        else:
             anthropic_msgs.append({"role": role, "content": m["content"]})
        last_role = role
        
    data = {
        "model": model, 
        "max_tokens": 4000, 
        "messages": anthropic_msgs
    }
    if system_context:
        data["system"] = system_context
        
    req = urllib.request.Request(url, json.dumps(data).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        try:
            error_data = json.loads(e.read().decode("utf-8"))
            return f"❌ Lỗi Claude: {error_data.get('error', {}).get('message', 'Unknown Error')}"
        except:
            return f"❌ Lỗi Claude (HTTP {e.code})"
    except Exception as e:
        return f"❌ Không thể kết nối Anthropic: {str(e)}"
