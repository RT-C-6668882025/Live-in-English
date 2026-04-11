# Weak Model - Grammar Error Annotation

## 任务
标注作文中的语法错误

## 执行步骤
1. 逐句阅读作文
2. 识别语法、用词、搭配错误
3. 对每个错误按指定格式标注
4. 提供修正建议

## 格式要求

❌ [错误类型]：原文引用 "[exact quote]"
→ 问题说明：[中文解释]
→ REWRITE: "[corrected version]"

## 错误类型列表
- 时态错误
- 主谓一致错误
- 介词搭配错误
- 冠词错误
- 词汇选择错误
- 句子结构错误
- 拼写错误

## 参考示例

❌ [时态错误]：原文引用 "I go to park yesterday"
→ 问题说明：描述过去的事情应该用一般过去时
→ REWRITE: "I went to the park yesterday"

❌ [介词搭配错误]：原文引用 "I am good in math"
→ 问题说明："擅长"的固定搭配是 "be good at"
→ REWRITE: "I am good at math"

## 原始数据
{user_essay}

请按照上述要求标注所有语法错误。
