import pytest
import asyncio
from rotk_agent.qwen3_agent import StandaloneChatAgent, LLMConfig, Message


class TestShrinkHistory:
    """_shrink_history方法的完整测试套件"""
    
    def create_test_agent(self):
        """创建测试用的Agent实例"""
        return StandaloneChatAgent(LLMConfig(
            provider="vllm",
            model_id="test-model", 
            api_key="EMPTY",
            base_url="http://localhost"
        ))

    @pytest.mark.asyncio
    async def test_shrink_history_basic_functionality(self):
        """测试基本功能：历史长度 > window，保留system + 最后window条"""
        agent = self.create_test_agent()
        
        # 构造：1条system + 100条消息
        original = [Message(role="system", content="system prompt")] + \
                   [Message(role="user", content=f"user message {i}") for i in range(50)] + \
                   [Message(role="assistant", content=f"assistant response {i}") for i in range(50)]
        
        agent.conversation_history = list(original)
        original_length = len(agent.conversation_history)
        print(f"原始历史长度: {original_length}")
        
        # 执行缩减，window=40
        await agent._shrink_history(window=40)
        
        # 验证结果
        new_length = len(agent.conversation_history) 
        print(f"缩减后历史长度: {new_length}")
        
        # 应该是: 1(system) + 40(tail) = 41
        assert new_length == 41, f"期望41条消息，实际{new_length}条"
        assert agent.conversation_history[0].role == "system"
        assert agent.conversation_history[0].content == "system prompt"
        
        # 验证只有1条system消息
        system_count = sum(1 for m in agent.conversation_history if m.role == "system")
        assert system_count == 1, f"期望1条system消息，实际{system_count}条"
        
        # 验证tail部分是原始历史的最后40条
        expected_tail = original[-40:]
        actual_tail = agent.conversation_history[1:]  # 除去第一条system
        assert len(actual_tail) == 40
        assert actual_tail == expected_tail

    @pytest.mark.asyncio
    async def test_shrink_history_exactly_window_size(self):
        """测试历史长度恰好等于window"""
        agent = self.create_test_agent()
        
        # 构造：恰好40条消息（包含1条system）
        original = [Message(role="system", content="sys")] + \
                   [Message(role="user", content=f"msg{i}") for i in range(39)]
        
        agent.conversation_history = list(original)
        print(f"原始长度: {len(original)} (等于window=40)")
        
        await agent._shrink_history(window=40)
        
        # 当历史长度等于window时，会出现重复system的问题
        print(f"缩减后长度: {len(agent.conversation_history)}")
        print("消息角色分布:", [m.role for m in agent.conversation_history])
        
        # 显示当前实现的问题
        system_count = sum(1 for m in agent.conversation_history if m.role == "system")
        print(f"System消息数量: {system_count}")

    @pytest.mark.asyncio  
    async def test_shrink_history_smaller_than_window(self):
        """测试历史长度小于window的情况"""
        agent = self.create_test_agent()
        
        # 构造：仅3条消息，window=40
        original = [
            Message(role="system", content="sys"),
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi")
        ]
        
        agent.conversation_history = list(original)
        print(f"原始长度: {len(original)} (小于window=40)")
        
        await agent._shrink_history(window=40)
        
        print(f"缩减后长度: {len(agent.conversation_history)}")
        print("消息内容:", [(m.role, m.content) for m in agent.conversation_history])
        
        system_count = sum(1 for m in agent.conversation_history if m.role == "system")
        print(f"System消息数量: {system_count}")

    @pytest.mark.asyncio
    async def test_shrink_history_no_system_message(self):
        """测试没有system消息的情况"""
        agent = self.create_test_agent()
        
        # 构造：没有system消息的历史
        original = [Message(role="user", content=f"msg{i}") for i in range(50)]
        
        agent.conversation_history = list(original)
        print(f"原始长度: {len(original)} (无system消息)")
        
        await agent._shrink_history(window=30)
        
        print(f"缩减后长度: {len(agent.conversation_history)}")
        
        # 应该只保留最后30条
        assert len(agent.conversation_history) == 30
        system_count = sum(1 for m in agent.conversation_history if m.role == "system")
        assert system_count == 0, "不应该有system消息"
        
        # 验证是最后30条
        expected_tail = original[-30:]
        assert agent.conversation_history == expected_tail

    @pytest.mark.asyncio
    async def test_shrink_history_multiple_system_messages(self):
        """测试多条system消息的情况"""
        agent = self.create_test_agent()
        
        # 构造：多条system消息
        original = [
            Message(role="system", content="sys1"),
            Message(role="user", content="msg1"),
            Message(role="system", content="sys2"),
            Message(role="user", content="msg2"),
            Message(role="system", content="sys3"),
        ] + [Message(role="user", content=f"msg{i}") for i in range(3, 50)]
        
        agent.conversation_history = list(original)
        original_system_count = sum(1 for m in original if m.role == "system")
        print(f"原始system消息数量: {original_system_count}")
        
        await agent._shrink_history(window=20)
        
        # 应该只保留第一条system消息
        final_system_count = sum(1 for m in agent.conversation_history if m.role == "system")
        print(f"最终system消息数量: {final_system_count}")
        
        # 检查第一条是否是sys1
        if agent.conversation_history and agent.conversation_history[0].role == "system":
            print(f"保留的system消息: '{agent.conversation_history[0].content}'")

    @pytest.mark.asyncio
    async def test_shrink_history_window_zero(self):
        """测试window=0的边界情况"""
        agent = self.create_test_agent()
        
        original = [Message(role="system", content="sys")] + \
                   [Message(role="user", content=f"msg{i}") for i in range(10)]
        
        agent.conversation_history = list(original)
        
        await agent._shrink_history(window=0)
        
        print(f"Window=0时的结果长度: {len(agent.conversation_history)}")
        print("内容:", [(m.role, m.content) for m in agent.conversation_history])

    def test_slice_behavior_demonstration(self):
        """演示切片操作的行为"""
        print("\n=== 切片操作演示 ===")
        
        # 模拟消息列表
        messages = [f"msg{i}" for i in range(10)]  # ['msg0', 'msg1', ..., 'msg9']
        print(f"原始列表: {messages}")
        print(f"列表长度: {len(messages)}")
        
        # 各种切片操作
        print(f"messages[-3:] = {messages[-3:]}")  # 最后3个
        print(f"messages[-5:] = {messages[-5:]}")  # 最后5个
        print(f"messages[-15:] = {messages[-15:]}")  # 超出长度时的结果
        print(f"messages[-0:] = {messages[-0:]}")   # -0相当于0，即全部
        
        # 空列表的切片
        empty = []
        print(f"空列表[-5:] = {empty[-5:]}")


# 运行演示
if __name__ == "__main__":
    # 先运行切片演示
    test = TestShrinkHistory()
    test.test_slice_behavior_demonstration()
    
    # 然后运行异步测试
    async def run_tests():
        test = TestShrinkHistory()
        
        print("\n=== 测试1: 基本功能 ===")
        await test.test_shrink_history_basic_functionality()
        
        print("\n=== 测试2: 历史长度等于window ===")
        await test.test_shrink_history_exactly_window_size()
        
        print("\n=== 测试3: 历史长度小于window ===")
        await test.test_shrink_history_smaller_than_window()
        
        print("\n=== 测试4: 无system消息 ===")
        await test.test_shrink_history_no_system_message()
        
        print("\n=== 测试5: 多条system消息 ===")
        await test.test_shrink_history_multiple_system_messages()
        
        print("\n=== 测试6: window=0边界情况 ===")
        await test.test_shrink_history_window_zero()
    
    asyncio.run(run_tests())