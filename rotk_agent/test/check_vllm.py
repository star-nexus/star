#!/usr/bin/env python3
"""
简单的 vLLM 服务检查脚本
用于快速验证 vLLM 服务是否正常运行
"""

import asyncio
import httpx
import json
import sys


async def check_vllm_service(base_url: str = "http://localhost:8000"):
    """检查 vLLM 服务状态"""
    print(f"🔍 检查 vLLM 服务: {base_url}")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # 1. 健康检查
            print("1️⃣ 健康检查...")
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("   ✅ 服务健康状态正常")
            else:
                print(f"   ❌ 健康检查失败: {response.status_code}")
                return False
            
            # 2. 模型列表
            print("\n2️⃣ 获取模型列表...")
            response = await client.get(
                f"{base_url}/v1/models",
                headers={"Authorization": "Bearer sk-no-key-required"}
            )
            if response.status_code == 200:
                models = response.json()
                print("   ✅ 模型列表获取成功")
                for model in models.get("data", []):
                    print(f"      📋 模型: {model.get('id', 'unknown')}")
            else:
                print(f"   ❌ 模型列表获取失败: {response.status_code}")
                return False
            
            # 3. 简单聊天测试
            print("\n3️⃣ 简单聊天测试...")
            chat_payload = {
                "model": models["data"][0]["id"] if models.get("data") else "default",
                "messages": [
                    {"role": "user", "content": "请简单回答：1+1等于几？"}
                ],
                "max_tokens": 50,
                "temperature": 0.7
            }
            
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={
                    "Authorization": "Bearer sk-no-key-required",
                    "Content-Type": "application/json"
                },
                json=chat_payload
            )
            
            if response.status_code == 200:
                result = response.json()
                message = result["choices"][0]["message"]["content"]
                print("   ✅ 聊天测试成功")
                print(f"      💬 回复: {message.strip()}")
            else:
                print(f"   ❌ 聊天测试失败: {response.status_code}")
                print(f"      📝 错误信息: {response.text}")
                return False
            
            print("\n🎉 vLLM 服务检查完成 - 一切正常！")
            return True
            
        except httpx.ConnectError:
            print("❌ 无法连接到 vLLM 服务")
            print("💡 请确保 vLLM 服务正在运行:")
            print("   python -m vllm.entrypoints.openai.api_server --model <model_name>")
            return False
        except Exception as e:
            print(f"❌ 检查过程中发生错误: {e}")
            return False


async def main():
    """主函数"""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    print("🚀 vLLM 服务检查工具")
    print(f"📍 目标地址: {base_url}")
    print()
    
    success = await check_vllm_service(base_url)
    
    if success:
        print("\n✅ 检查完成 - vLLM 服务运行正常")
        print("🎯 现在可以使用 vLLM 配置运行代理了:")
        print("   uv run python rotk_agent/test_vllm_agent.py")
        print("   uv run python rotk_agent/standalone_agent.py")
    else:
        print("\n❌ 检查失败 - vLLM 服务未正常运行")
        print("📋 故障排除步骤:")
        print("   1. 启动 vLLM 服务: ./start_vllm_server.sh")
        print("   2. 检查端口是否被占用: netstat -tlnp | grep 8000")
        print("   3. 查看 vLLM 服务日志")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
