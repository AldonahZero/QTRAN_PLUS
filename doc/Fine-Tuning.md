# **微调任务总结 (Fine-Tuning Job Summary) 📋**

本文档总结了四个针对 gpt-4o-mini-2024-07-18 模型的微调任务，涵盖了不同的微调类型。所有任务均已成功完成。

### **微调详情表**

下表记录了每个微调任务的关键信息，包括类型、Job ID、生成的模型 ID 以及具体的微调参数和结果。

| 微调类型 (Type) | Job ID | Fine-tuned Model ID | 微调信息 (Details) |
| :---- | :---- | :---- | :---- |
| **NOREC** | ftjob-bIeYBg8YMzJ8Ez5hLWvTr5xR | ft:gpt-4o-mini-2024-07-18:personal:norec:CGI535gT | **模型:** gpt-4o-mini-2024-07-18\<br\>**状态:** succeeded\<br\>**超参数:** n\_epochs=3, batch\_size=1, learning\_rate\_multiplier=1.8\<br\>**训练 Tokens:** 19,956 |
| **DQE\_MUTATION** | ftjob-GAUKP7E67L1YwLVtpeGwmYaH | ft:gpt-4o-mini-2024-07-18:personal:dqe:CGIe5sAa | **模型:** gpt-4o-mini-2024-07-18\<br\>**状态:** succeeded\<br\>**超参数:** n\_epochs=4, batch\_size=1, learning\_rate\_multiplier=1.8\<br\>**训练 Tokens:** 37,616 |
| **TLP** | ftjob-a6szI67DtcbINIFQbgzi4a0S | ft:gpt-4o-mini-2024-07-18:personal:tlp:CGIh8iHH | **模型:** gpt-4o-mini-2024-07-18\<br\>**状态:** succeeded\<br\>**超参数:** n\_epochs=3, batch\_size=1, learning\_rate\_multiplier=1.8\<br\>**训练 Tokens:** 95,838 |
| **PINOLO** | ftjob-xK5vJiETKRzUUKHoX4VKxv8p | ft:gpt-4o-mini-2024-07-18:personal:pinolo:CGIoI0jD | **模型:** gpt-4o-mini-2024-07-18\<br\>**状态:** succeeded\<br\>**超参数:** n\_epochs=3, batch\_size=1, learning\_rate\_multiplier=1.8\<br\>**训练 Tokens:** 216,609 |
| **SEMANTIC** | ftjob-f4LEAEScTF46koYFZ243LBQn | ft:gpt-4o-mini-2024-07-18:personal:semantic:CHn8HTp0 | **模型:** gpt-4o-mini-2024-07-18\<br\>**状态:** succeeded\<br\>**超参数:** n\_epochs=3, batch\_size=1, learning\_rate\_multiplier=1.8\<br\>**训练 Tokens:** 46,134 |

请妥善保管这些 **Fine-tuned Model ID**，以便后续在 QTRAN 的 Mutation LLM 中调用。

注意：已尝试的运行命令示例（如需重试或记录 Job 信息）：
```
python -m src.MutationLlmModelFineTuning.FineTuning_MutationLLM \
	--api_key "$OPENAI_API_KEY" \
	--training_data_filename "MutationData/FineTuningTrainingData/semantic.jsonl" \
	--suffix "semantic"
```
请在获得 Job ID 与 Fine-tuned Model ID 后，将上表中的占位符替换为真实值。